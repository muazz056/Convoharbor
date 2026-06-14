import re
import threading
import time

from flask import current_app
from langchain_openai import OpenAIEmbeddings

from .rate_limiter import get_gemini_rate_limiter

_local_embedding_model = None
_local_model_lock = threading.Lock()


def _get_local_model():
    global _local_embedding_model
    if _local_embedding_model is None:
        with _local_model_lock:
            if _local_embedding_model is None:
                from sentence_transformers import SentenceTransformer
                model_name = current_app.config.get(
                    'LOCAL_EMBEDDING_MODEL', 'thenlper/gte-small'
                )
                current_app.logger.info(f"Loading local embedding model: {model_name}")
                _local_embedding_model = SentenceTransformer(model_name)
                current_app.logger.info(
                    f"Local embedding model loaded on {_local_embedding_model.device}"
                )
    return _local_embedding_model


def _local_embed(texts: list[str]) -> list[list[float]]:
    model = _get_local_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()


def preload_local_embedding_model(app):
    """Pre-load the local embedding model in a background thread at app startup."""
    def _load():
        with app.app_context():
            try:
                _get_local_model()
                app.logger.info("Local embedding model pre-loaded at startup")
            except Exception as e:
                app.logger.warning(f"Local embedding model pre-load skipped: {e}")

    thread = threading.Thread(target=_load, daemon=True)
    thread.start()


def _parse_retry_delay_seconds(error) -> float:
    """Extract the ``retry_delay.seconds`` hint from a Gemini
    ``ResourceExhausted`` exception, falling back to scraping the
    string representation when the structured field is missing.

    The Google API always tells us exactly how long to wait before
    retrying — the previous implementation ignored this and used a
    fixed 2/4/8s backoff, which is why every retry failed (the
    quota window can be 26-60s) and the code gave up and fell back
    to OpenAI even when the user wanted Gemini.
    """
    try:
        # Structured proto field (most reliable).
        if hasattr(error, 'metadata') and getattr(error, 'metadata', None):
            md = error.metadata
            # metadata can be a Mapping[str, str] or a list of tuples
            for key in ('retry_delay', 'Retry-After'):
                val = md.get(key) if hasattr(md, 'get') else None
                if val:
                    m = re.search(r'(\d+(?:\.\d+)?)', str(val))
                    if m:
                        return float(m.group(1))
        # Inside the error message body, look for "retry in {N}s" or
        # "Please retry in {N}s".
        msg = str(error) or ''
        for pattern in (r'retry in (\d+(?:\.\d+)?)\s*s',
                        r'Please retry in (\d+(?:\.\d+)?)\s*s',
                        r'retryDelay[^0-9]*(\d+(?:\.\d+)?)\s*s'):
            m = re.search(pattern, msg, re.IGNORECASE)
            if m:
                return float(m.group(1))
    except Exception:
        pass
    # Conservative default: 60s (the full rate-limit window).
    return 60.0


def _gemini_embed(texts: list[str], api_key: str, model_name: str, api_endpoint: str,
                  on_batch_start=None, on_batch_done=None) -> list[list[float]]:
    """Embed texts using Google Gemini v1 API (not v1beta).

    The Gemini Embedding API rejects batches larger than 100 requests with
    HTTP 400, and the free tier additionally caps total throughput at
    ``GEMINI_RATE_LIMIT_PER_MINUTE`` requests per 60 seconds per model.

    Rate-limit handling: when a batch returns 429 (quota exceeded),
    we parse the ``retry_delay`` from the error response, sleep for
    that long (plus a small buffer), and retry the SAME model — we
    do NOT skip to the fallback model just because we got rate
    limited. The fallback model is reserved for genuine hard
    failures (auth errors, model-not-found, etc.).
    """
    from google.ai.generativelanguage_v1 import GenerativeServiceClient
    from google.ai.generativelanguage_v1.types import (
        BatchEmbedContentsRequest,
        EmbedContentRequest,
    )
    from google.api_core import client_options as client_options_lib
    from google.api_core.exceptions import ResourceExhausted, GoogleAPIError

    client = GenerativeServiceClient(
        client_options=client_options_lib.ClientOptions(
            api_key=api_key,
            api_endpoint=api_endpoint,
        ),
    )

    GEMINI_BATCH_LIMIT = 100
    all_embeddings: list[list[float]] = []
    rate_limiter = get_gemini_rate_limiter()

    total_batches = (len(texts) + GEMINI_BATCH_LIMIT - 1) // GEMINI_BATCH_LIMIT
    batch_index = 0

    for chunk_start in range(0, len(texts), GEMINI_BATCH_LIMIT):
        chunk_texts = texts[chunk_start:chunk_start + GEMINI_BATCH_LIMIT]

        def _notify_start(wait_seconds, used, capacity, _bs=batch_index):
            if on_batch_start is None:
                return
            try:
                on_batch_start(
                    batch_index=_bs,
                    total_batches=total_batches,
                    wait_seconds=max(0.0, float(wait_seconds)),
                    used=int(used),
                    capacity=int(capacity),
                )
            except Exception:
                pass

        # Acquire a rate-limit token before issuing the request. The
        # limiter blocks (and calls our callback) until a slot is free.
        rate_limiter.wait_for_token(progress_callback=_notify_start)

        requests = [
            EmbedContentRequest(
                model=model_name,
                content={"parts": [{"text": t}]},
                task_type="RETRIEVAL_DOCUMENT",
            )
            for t in chunk_texts
        ]
        batch_request = BatchEmbedContentsRequest(requests=requests, model=model_name)

        # Retry loop for THIS model. We only give up on a non-429
        # error; for rate limits we keep waiting and retrying.
        attempt = 0
        success = False
        last_error = None
        while True:
            try:
                response = client.batch_embed_contents(batch_request)
                batch_embeddings = [list(e.values) for e in response.embeddings]
                if len(batch_embeddings) != len(chunk_texts):
                    raise RuntimeError(
                        f"Gemini returned {len(batch_embeddings)} embeddings for "
                        f"{len(chunk_texts)} texts (model={model_name})"
                    )
                all_embeddings.extend(batch_embeddings)
                success = True
                break
            except ResourceExhausted as e:
                last_error = e
                retry_seconds = _parse_retry_delay_seconds(e)
                # Add a 2s buffer to make sure the window has actually
                # rolled over (the response is often an estimate).
                sleep_for = max(retry_seconds, 10.0) + 2.0
                current_app.logger.warning(
                    f"Gemini rate limited (429) on {model_name} (batch "
                    f"{chunk_start}-{chunk_start + len(chunk_texts)}), "
                    f"retrying in {sleep_for:.0f}s (attempt {attempt + 1})"
                )
                # Tell the frontend exactly how long we're waiting so
                # it can show a live countdown.
                _notify_start(sleep_for, rate_limiter.get_used(), rate_limiter.get_capacity())
                time.sleep(sleep_for)
                attempt += 1
                # Keep retrying the SAME model — the user's spec is
                # "wait for the limit to reset, then retry".
                continue
            except GoogleAPIError:
                # Non-429 API error (auth, model-not-found, bad
                # request, etc.) — caller will move to the fallback
                # model.
                raise
            except Exception as e:
                # Network or other transient — retry once after a
                # short delay, then give up so the caller can fall
                # back.
                last_error = e
                if attempt < 2:
                    current_app.logger.warning(
                        f"Gemini unexpected error on {model_name} (batch "
                        f"{chunk_start}-{chunk_start + len(chunk_texts)}): {e}, "
                        f"retrying in 2s"
                    )
                    time.sleep(2.0)
                    attempt += 1
                    continue
                raise

        if not success:
            raise last_error or RuntimeError(
                f"Gemini embedding failed for batch {chunk_start}-{chunk_start+len(chunk_texts)} (model={model_name})"
            )

        # Notify caller that this batch is done. We invoke the callback
        # AFTER the embeddings are stored in `all_embeddings` so the
        # caller can safely persist them.
        if on_batch_done is not None:
            try:
                on_batch_done(
                    batch_index=batch_index,
                    total_batches=total_batches,
                    batch_size=len(chunk_texts),
                    embeddings_so_far=len(all_embeddings),
                )
            except Exception:
                # Never let a progress callback break the embedding flow.
                pass

        batch_index += 1

    return all_embeddings


def generate_embeddings_for_texts(texts: list[str], on_batch_start=None,
                                  on_batch_done=None) -> dict:
    """Generate embeddings for a list of texts using the configured provider.

    Optional progress callbacks let the ingestion pipeline push real-time
    status to the frontend without coupling the embedding service to the
    HTTP/WS layers.

    Fallback policy:
      * For Gemini, a 429 (quota exhausted) is NOT a model failure.
        We wait for the rate limit to reset inside ``_gemini_embed``
        and keep retrying the SAME model.
      * Only hard errors (auth, model-not-found, etc.) move us to
        the next Gemini model.
      * OpenAI is the absolute last resort and is only reached when
        every Gemini model in the list returns a hard error (not a
        rate limit).

    Args:
        texts: list of strings to embed.
        on_batch_start: ``fn(wait_seconds, used, capacity)`` called when
            the rate limiter has to wait for a token (or the API
            returned 429 and we're sleeping for the retry window).
        on_batch_done: ``fn(batch_index, total_batches, batch_size,
            embeddings_so_far)`` called after each successful batch.

    Returns:
        dict with keys ``embeddings`` (list[list[float]] or None),
        ``provider`` (str) and ``error`` (str, only if failed).
    """
    provider = current_app.config.get('EMBEDDINGS_SERVICE_USE', 'openai')

    if provider == 'local':
        try:
            embeddings = _local_embed(texts)
            current_app.logger.info(
                f"Local embeddings generated: {len(embeddings)} vectors "
                f"(model={current_app.config.get('LOCAL_EMBEDDING_MODEL', 'thenlper/gte-small')})"
            )
            if on_batch_done is not None:
                try:
                    on_batch_done(
                        batch_index=0,
                        total_batches=1,
                        batch_size=len(texts),
                        embeddings_so_far=len(embeddings),
                    )
                except Exception:
                    pass
            return {"embeddings": embeddings, "provider": "local"}
        except Exception as e:
            current_app.logger.error(f"Local embeddings failed: {str(e)}")
            return {"embeddings": None, "provider": "local", "error": str(e)}

    if provider == 'gemini':
        api_key = current_app.config.get('GEMINI_API_KEY', '')
        if not api_key or api_key.startswith('your-'):
            current_app.logger.error("GEMINI_API_KEY not configured for embeddings")
            return {"embeddings": None, "provider": "gemini", "error": "GEMINI_API_KEY not configured"}
        api_endpoint = current_app.config.get('GEMINI_API_BASE_URL', 'generativelanguage.googleapis.com')
        model_names = list(dict.fromkeys([
            current_app.config.get('GEMINI_EMBEDDING_MODEL', 'models/gemini-embedding-2'),
            current_app.config.get('GEMINI_EMBEDDING_FALLBACK_MODEL', 'models/gemini-embedding-001'),
        ]))
        last_error = None
        for model_name in model_names:
            try:
                embeddings = _gemini_embed(
                    texts, api_key, model_name, api_endpoint,
                    on_batch_start=on_batch_start, on_batch_done=on_batch_done,
                )
                current_app.logger.info(f"Gemini embeddings generated: {len(embeddings)} vectors (model={model_name})")
                return {"embeddings": embeddings, "provider": "gemini"}
            except Exception as e:
                last_error = e
                current_app.logger.warning(f"Gemini embedding model {model_name} failed: {e}")
                continue
        current_app.logger.error(
            f"All Gemini embedding models failed (last error: {last_error})"
        )
        # Final fallback to OpenAI so we never silently drop KB embeddings.
        # This is only reached on hard errors (auth, model-not-found, etc.)
        # — rate-limit errors are handled inside _gemini_embed by waiting
        # and retrying the same model.
        try:
            openai_api_key = current_app.config.get('OPENAI_API_KEY', '')
            if openai_api_key and not openai_api_key.startswith('your-'):
                openai_model = current_app.config.get('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-large')
                openai_embedder = OpenAIEmbeddings(model=openai_model, api_key=openai_api_key)
                embeddings = openai_embedder.embed_documents(texts)
                current_app.logger.info(
                    f"OpenAI fallback embeddings generated: {len(embeddings)} vectors (model={openai_model})"
                )
                return {"embeddings": embeddings, "provider": "openai"}
            current_app.logger.error("OPENAI_API_KEY not configured - cannot fall back")
        except Exception as oai_err:
            current_app.logger.error(f"OpenAI fallback embedding failed: {oai_err}")
        return {"embeddings": None, "provider": "gemini", "error": "All embedding providers failed (gemini + openai)"}

    # Default: openai
    api_key = current_app.config.get('OPENAI_API_KEY', '')
    if not api_key or api_key.startswith('your-'):
        current_app.logger.error("OPENAI_API_KEY not configured for embeddings")
        return {"embeddings": None, "provider": "openai", "error": "OPENAI_API_KEY not configured"}
    try:
        model_name = current_app.config.get('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-large')
        embedder = OpenAIEmbeddings(
            model=model_name,
            api_key=api_key
        )
        embeddings = embedder.embed_documents(texts)
        current_app.logger.info(f"OpenAI embeddings generated: {len(embeddings)} vectors")
        # Mirror the same callback contract: one final "done" event
        # covering the whole batch.
        if on_batch_done is not None:
            try:
                on_batch_done(
                    batch_index=0,
                    total_batches=1,
                    batch_size=len(texts),
                    embeddings_so_far=len(embeddings),
                )
            except Exception:
                pass
        return {"embeddings": embeddings, "provider": "openai"}
    except Exception as e:
        current_app.logger.error(f"OpenAI embeddings failed: {str(e)}")
        return {"embeddings": None, "provider": "openai", "error": str(e)}
