import re
import json
from flask import current_app
from typing import List, Dict, Any
from sqlalchemy import text, func as sa_func
from .. import db
from ..models.document_embedding import DocumentEmbedding, PGVECTOR_AVAILABLE


class VectorService:
    RRF_K = 60

    def __init__(self):
        if not PGVECTOR_AVAILABLE:
            raise RuntimeError("pgvector package is not installed. Install with: pip install pgvector")

        engine = db.get_engine()
        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
            current_app.logger.info("pgvector extension verified/enabled")
        except Exception as e:
            current_app.logger.warning(f"pgvector extension setup skipped (test mode?): {e}")

        try:
            with engine.connect() as conn:
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_doc_embeddings_fts
                    ON document_embeddings
                    USING GIN (to_tsvector('english', COALESCE(page_content, '')))
                """))
                conn.commit()
            current_app.logger.info("FTS GIN index verified/created on document_embeddings.page_content")
        except Exception as e:
            current_app.logger.warning(f"FTS index creation skipped: {e}")

    def upsert(self, chunks_with_embeddings: list[dict], provider: str = 'openai'):
        if not chunks_with_embeddings:
            return {"upserted_count": 0}

        # Extract doc_id from first chunk (all chunks in a batch share the same doc)
        first_meta = chunks_with_embeddings[0].get("metadata", {})
        doc_id = first_meta.get("doc_id", "unknown-doc")

        # Batch 1: Fetch ALL existing vector_ids for this doc in ONE query
        expected_ids = {f"{doc_id}-chunk-{i}" for i in range(len(chunks_with_embeddings))}
        existing_rows = DocumentEmbedding.query.filter(
            DocumentEmbedding.vector_id.in_(expected_ids)
        ).all()
        existing_by_vid = {row.vector_id: row for row in existing_rows}

        # Batch 2: Partition into inserts and updates
        new_records = []
        update_records = []
        for i, chunk in enumerate(chunks_with_embeddings):
            embedding = chunk.get("embeddings", {}).get(provider)

            metadata = chunk.get("metadata", {})
            page_content = chunk.get("page_content") or metadata.get("page_content", "")
            vector_id = f"{doc_id}-chunk-{i}"

            existing = existing_by_vid.get(vector_id)
            if existing:
                existing.page_content = page_content
                existing.meta_data = metadata
                existing.provider = provider
                if provider == 'openai':
                    existing.embedding_openai = embedding
                elif provider == 'gemini':
                    existing.embedding_gemini = embedding
                else:
                    existing.embedding_local = embedding
                update_records.append(existing)
            else:
                new_records.append({
                    'vector_id': vector_id,
                    'doc_id': doc_id,
                    'chunk_index': i,
                    'page_content': page_content,
                    'meta_data': metadata,
                    'source': metadata.get("source", "unknown"),
                    'chatbot_id': metadata.get("chatbot_id"),
                    'tenant_id': metadata.get("tenant_id"),
                    'provider': provider,
                    'embedding_openai': embedding if provider == 'openai' else None,
                    'embedding_gemini': embedding if provider == 'gemini' else None,
                    'embedding_local': embedding if provider == 'local' else None,
                })

        # Bulk insert all new records in ONE query
        skipped = len(chunks_with_embeddings) - len(new_records) - len(update_records)
        if new_records:
            db.session.bulk_insert_mappings(DocumentEmbedding, new_records)

        db.session.commit()

        vectors_created = len(new_records) + len(update_records)
        if skipped:
            current_app.logger.warning(
                f"Upserted {vectors_created} vectors ({skipped} chunks had no '{provider}' embedding)"
            )
        else:
            current_app.logger.info(
                f"Upserted {vectors_created} vectors to pgvector "
                f"(inserted={len(new_records)}, updated={len(update_records)})"
            )

        self._invalidate_vector_cache()

        return {"upserted_count": vectors_created}

    def _score_to_similarity(self, distance: float) -> float:
        return max(0.0, 1.0 - float(distance))

    def _build_matches(self, results: list) -> list:
        matches = []
        for row, distance in results:
            score = self._score_to_similarity(distance)
            matches.append({
                "score": score,
                "page_content": row.page_content,
                "metadata": {
                    **row.meta_data,
                    "id": row.id,
                    "vector_id": row.vector_id,
                    "doc_id": row.doc_id,
                    "chunk_index": row.chunk_index,
                    "source": row.source,
                    "chatbot_id": row.chatbot_id,
                    "tenant_id": row.tenant_id,
                    "provider": row.provider,
                    "page_content": row.page_content,
                },
                "embeddings": {
                    "openai": row.embedding_openai,
                    "gemini": row.embedding_gemini,
                    "local": row.embedding_local,
                }
            })
        return matches

    def query(self, query_embedding: list[float], top_k: int = 5, filter_dict: dict = None,
              query_text: str = None, use_hybrid: bool = True):
        if not query_embedding:
            raise ValueError("Query embedding cannot be empty.")

        filter_dict = filter_dict or {}
        provider = filter_dict.get('provider', 'openai')

        if provider == 'openai':
            embed_col = DocumentEmbedding.embedding_openai
        elif provider == 'gemini':
            embed_col = DocumentEmbedding.embedding_gemini
        else:
            embed_col = DocumentEmbedding.embedding_local

        base_query = db.session.query(
            DocumentEmbedding,
            embed_col.cosine_distance(query_embedding).label('distance')
        )

        base_query = base_query.filter(embed_col.isnot(None))

        for key, value in filter_dict.items():
            if key == 'provider':
                continue
            if hasattr(DocumentEmbedding, key):
                base_query = base_query.filter(getattr(DocumentEmbedding, key) == value)
            else:
                base_query = base_query.filter(
                    DocumentEmbedding.meta_data[key].astext == str(value)
                )

        # === DIAGNOSTIC: log how many rows match the filter (before embedding
        # null check, before ordering) so we can see if the filter itself is
        # dropping everything.  We temporarily build a separate count query
        # that mirrors every filter except the embed_col.isnot(None) clause.
        try:
            count_q = db.session.query(sa_func.count(DocumentEmbedding.id))
            for key, value in filter_dict.items():
                if key == 'provider':
                    continue
                if hasattr(DocumentEmbedding, key):
                    count_q = count_q.filter(getattr(DocumentEmbedding, key) == value)
                else:
                    count_q = count_q.filter(
                        DocumentEmbedding.meta_data[key].astext == str(value)
                    )
            total_matching_filter = count_q.scalar() or 0
            with_embedding = count_q.filter(embed_col.isnot(None)).scalar() or 0
            current_app.logger.info(
                f"[VECTOR_QUERY] provider={provider} filter={dict((k,v) for k,v in filter_dict.items() if k != 'provider')} "
                f"rows_matching_filter={total_matching_filter} rows_with_embedding={with_embedding}"
            )
        except Exception as diag_err:
            current_app.logger.warning(f"[VECTOR_QUERY] diagnostic count failed: {diag_err}")

        if use_hybrid and query_text and query_text.strip():
            return self._hybrid_query(base_query, embed_col, query_text, query_embedding,
                                      top_k, filter_dict, provider)

        # Pure vector (no hybrid)
        raw_limit = max(top_k * 3, top_k + 5)
        raw_results = base_query.order_by(text('distance')).limit(raw_limit).all()
        current_app.logger.info(
            f"[VECTOR_QUERY] raw_results_count={len(raw_results)} provider={provider} top_k={top_k} (pure vector)"
        )

        dedup = self._dedup(raw_results)
        ranked = sorted(dedup.values(), key=lambda pair: pair[1])[:top_k]
        ranked = self._mmr_diversify(ranked, query_embedding, top_k,
                                     lambda_param=0.5)
        current_app.logger.info(
            f"[VECTOR_QUERY] after_dedup+mmr={len(ranked)} top_scores={[round(self._score_to_similarity(float(d)),3) for _,d in ranked[:3]]}"
        )
        return self._build_matches(ranked)

    def _dedup(self, raw_results: list) -> dict:
        dedup: dict[tuple, tuple] = {}
        for row, distance in raw_results:
            key = (row.doc_id, row.chunk_index)
            if key not in dedup or distance < dedup[key][1]:
                dedup[key] = (row, distance)
        return dedup

    def _fts_rank(self, query_text: str, filter_dict: dict, top_k: int) -> list:
        sanitized = re.sub(r'[^\w\s]', ' ', query_text).strip()
        if not sanitized or len(sanitized.split()) < 1:
            return []

        col = DocumentEmbedding
        tsq = sa_func.websearch_to_tsquery('english', sanitized)
        tsvec = sa_func.to_tsvector('english', sa_func.coalesce(col.page_content, ''))

        hl_options = 'MaxWords=50, MinWords=20, StartSel=, StopSel=, FragmentDelimiter=...'
        q = db.session.query(
            col,
            sa_func.ts_rank(tsvec, tsq).label('fts_score'),
            sa_func.ts_headline('english', col.page_content, tsq, hl_options).label('headline')
        ).filter(tsvec.op('@@')(tsq))

        for key, value in filter_dict.items():
            if key == 'provider':
                continue
            if hasattr(col, key):
                q = q.filter(getattr(col, key) == value)
            else:
                q = q.filter(col.meta_data[key].astext == str(value))

        results = q.order_by(text('fts_score DESC')).limit(top_k * 3).all()
        return results  # list of (DocumentEmbedding, fts_score, headline)

    def _hybrid_query(self, base_query, embed_col, query_text: str,
                      query_embedding: list, top_k: int, filter_dict: dict,
                      provider: str) -> list:
        raw_limit = max(top_k * 6, top_k + 15)

        vector_results = base_query.order_by(text('distance')).limit(raw_limit).all()
        current_app.logger.info(
            f"[HYBRID] vector_results={len(vector_results)} limit={raw_limit}"
        )

        fts_results = self._fts_rank(query_text, filter_dict, top_k)
        current_app.logger.info(
            f"[HYBRID] fts_results={len(fts_results)}"
        )

        if not fts_results:
            dedup = self._dedup(vector_results)
            ranked = sorted(dedup.values(), key=lambda pair: pair[1])[:top_k]
            ranked = self._mmr_diversify(ranked, query_embedding, top_k,
                                         lambda_param=0.5)
            return self._build_matches(ranked)

        fts_map = {}
        for row, fts_score, headline in fts_results:
            fts_map[(row.doc_id, row.chunk_index)] = float(fts_score)

        vec_ranked = sorted(
            self._dedup(vector_results).items(),
            key=lambda kv: kv[1][1]
        )

        combined_scores = {}
        for rank_pos, ((doc_id, chunk_idx), (row, distance)) in enumerate(vec_ranked):
            vector_rrf = 1.0 / (self.RRF_K + rank_pos)
            fts_score = fts_map.get((row.doc_id, row.chunk_index), 0.0)
            if fts_score > 0:
                fts_rank = sum(1 for k, v in fts_map.items() if v > fts_score)
                fts_rrf = 1.0 / (self.RRF_K + fts_rank)
            else:
                fts_rrf = 0.0
            combined_scores[(row.doc_id, row.chunk_index)] = (row, - (vector_rrf + fts_rrf), distance)

        for row, fts_score, headline in fts_results:
            key = (row.doc_id, row.chunk_index)
            if key not in combined_scores:
                fts_rank = sum(1 for k, v in fts_map.items() if v > fts_score)
                fts_rrf = 1.0 / (self.RRF_K + fts_rank)
                combined_scores[key] = (row, -fts_rrf, 1.0)

        ranked = sorted(combined_scores.values(), key=lambda x: x[1])[:top_k]
        ranked_as_pairs = [(row, dist) for row, _score, dist in ranked]
        ranked_as_pairs = self._mmr_diversify(ranked_as_pairs, query_embedding, top_k,
                                              lambda_param=0.4)

        current_app.logger.info(
            f"[HYBRID] final_count={len(ranked_as_pairs)} "
            f"top_scores={[round(self._score_to_similarity(float(d)),3) for _,d in ranked_as_pairs[:3]]}"
        )
        return self._build_matches(ranked_as_pairs)

    def _mmr_diversify(self, candidates: list, query_embedding: list,
                       top_k: int, lambda_param: float = 0.5) -> list:
        if len(candidates) <= top_k:
            return candidates

        selected = []
        remaining = list(candidates)

        query_vec = query_embedding
        _norm_q = sum(x * x for x in query_vec) ** 0.5
        if _norm_q > 0:
            query_vec = [x / _norm_q for x in query_vec]

        def _sim(vec_a, vec_b):
            dot = sum(a * b for a, b in zip(vec_a, vec_b))
            na = sum(x * x for x in vec_a) ** 0.5
            nb = sum(x * x for x in vec_b) ** 0.5
            if na == 0 or nb == 0:
                return 0.0
            return dot / (na * nb)

        def _get_embedding(row):
            provider = getattr(row, 'provider', None)
            if provider == 'openai':
                return getattr(row, 'embedding_openai', None) or getattr(row, 'embedding_gemini', None) or getattr(row, 'embedding_local', None)
            elif provider == 'gemini':
                return getattr(row, 'embedding_gemini', None) or getattr(row, 'embedding_openai', None) or getattr(row, 'embedding_local', None)
            return getattr(row, 'embedding_local', None) or getattr(row, 'embedding_openai', None) or getattr(row, 'embedding_gemini', None)

        for _ in range(min(top_k, len(candidates))):
            best_score = -float('inf')
            best_idx = -1
            for i, (row, distance) in enumerate(remaining):
                sim_to_query = self._score_to_similarity(float(distance))
                emb = _get_embedding(row)
                if emb is None:
                    mmr_score = sim_to_query
                else:
                    max_sim_to_selected = 0.0
                    if selected:
                        for sel_row, _ in selected:
                            sel_emb = _get_embedding(sel_row)
                            if sel_emb is not None:
                                max_sim_to_selected = max(max_sim_to_selected, _sim(emb, sel_emb))
                    mmr_score = lambda_param * sim_to_query - (1 - lambda_param) * max_sim_to_selected

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i

            if best_idx >= 0:
                selected.append(remaining.pop(best_idx))
            else:
                break

        return selected

    def _rerank(self, query: str, candidates: list) -> list:
        if len(candidates) <= 1:
            return candidates

        try:
            from .prompt_service import PromptService
            from .model_resolver import resolve_model

            config = {'ai_model': None, 'ai_provider': None}
            model_name, provider = resolve_model(config)

            if not model_name:
                return candidates

            chunks_text = []
            for i, (score, content, meta) in enumerate(candidates):
                preview = content[:300] if content else "(empty)"
                chunks_text.append(f"[{i+1}] {preview}")

            rerank_prompt = PromptService().render(
                'rerank',
                query=query,
                chunks="\n\n---\n\n".join(chunks_text)
            )

            response = current_app.llm_service.generate_answer(
                messages=[{"role": "user", "content": rerank_prompt}],
                model_name=model_name,
                temperature=0.1
            )
            if response is None:
                return candidates
            response = response.get('content', '')

            raw = response.strip()
            raw = re.sub(r'^```(?:json)?\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw)
            scores = json.loads(raw)

            if isinstance(scores, list) and len(scores) == len(candidates):
                scored = [(float(scores[i]), *candidates[i]) for i in range(len(candidates))]
                scored.sort(key=lambda x: -x[0])
                current_app.logger.info(
                    f"[RERANK] scores: {[round(s,2) for s,_,_,_ in scored]}"
                )
                # Return (rerank_score, content, metadata) — rerank_score replaces original
                return [(s, c, m) for s, _, c, m in scored]

            current_app.logger.warning(f"[RERANK] unexpected response format, using original order")
            return candidates

        except Exception as e:
            current_app.logger.warning(f"[RERANK] failed: {e}, using original order")
            return candidates

    def expand_query(self, query: str, provider: str = None, model_name: str = None) -> list:
        original = query.strip()
        queries = [original]

        if not original or len(original.split()) < 2:
            return queries

        try:
            from .prompt_service import PromptService
            from .model_resolver import get_default_llm_model

            if not model_name:
                model_name, resolved_provider = get_default_llm_model(provider=provider or 'openai')
                provider = resolved_provider or provider or 'openai'

            if not model_name:
                return queries

            expand_prompt = PromptService().render('query_expansion', query=original)

            response = current_app.llm_service.generate_answer(
                messages=[{"role": "user", "content": expand_prompt}],
                model_name=model_name,
                temperature=0.3
            )
            if response is None:
                return queries

            raw = response.get('content', '').strip()
            raw = re.sub(r'^```(?:json)?\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw)
            expanded = json.loads(raw)
            if isinstance(expanded, list):
                for q in expanded:
                    if isinstance(q, str) and q.strip() and q.strip() != original:
                        queries.append(q.strip())
            current_app.logger.info(
                f"[QUERY_EXPANSION] '{original}' -> {len(queries)-1} extra queries"
            )
        except Exception as e:
            current_app.logger.warning(f"[QUERY_EXPANSION] failed: {e}")

        return list(dict.fromkeys(queries))[:5]

    def rewrite_query(self, query: str, chat_history: str = '', provider: str = None,
                      model_name: str = None) -> str:
        try:
            from .query_processor_service import rewrite_query_with_history
            return rewrite_query_with_history(
                chat_history=chat_history,
                latest_query=query,
                provider=provider or 'openai',
                model_name=model_name
            )
        except Exception as e:
            current_app.logger.warning(f"[QUERY_REWRITE] failed: {e}")
            return query

    def search_similar(self, query: str, chatbot_id: int = None, limit: int = 5,
                       chat_history: str = None):
        try:
            if not hasattr(current_app, 'embedding_service'):
                current_app.logger.error("Embedding service not available")
                return []

            if chatbot_id is None:
                return []

            cache_key = f"vector_search:{query}:{chatbot_id}:{limit}"
            redis_service = getattr(current_app, 'redis_service', None)
            if redis_service:
                cached = redis_service.get_cache(cache_key)
                if cached is not None:
                    current_app.logger.info(f"Cache hit for vector search: '{query[:50]}...'")
                    return self._dicts_to_docs(cached)

            # Step 1: Find which providers actually have data for this chatbot
            active_providers_rows = db.session.query(
                DocumentEmbedding.provider
            ).filter(
                DocumentEmbedding.chatbot_id == chatbot_id,
                DocumentEmbedding.provider.isnot(None)
            ).distinct().all()
            active_providers = [r[0] for r in active_providers_rows if r[0]]
            if not active_providers:
                active_providers = [current_app.config.get('EMBEDDINGS_SERVICE_USE', 'openai')]
            current_app.logger.info(
                f"[ENHANCED_SEARCH] active_providers_in_db={active_providers} for chatbot {chatbot_id}"
            )

            # Step 2: Search with original query in each active provider's column
            all_results = {}
            for provider in active_providers:
                try:
                    emb_result = current_app.embedding_service.generate_embeddings_for_texts(
                        [query], provider=provider
                    )
                    emb_list = emb_result.get("embeddings")
                    if not emb_list:
                        continue
                    q_emb = emb_list[0]
                    filter_dict = {"provider": provider, "chatbot_id": chatbot_id}
                    results = self.query(q_emb, top_k=max(limit * 3, 15), filter_dict=filter_dict,
                                         query_text=query)
                    for r in results:
                        key = (r['metadata']['doc_id'], r['metadata']['chunk_index'])
                        if key not in all_results or r['score'] > all_results[key][0]:
                            all_results[key] = (r['score'], r['page_content'], r['metadata'])
                except Exception as q_err:
                    current_app.logger.warning(
                        f"[ENHANCED_SEARCH] provider={provider} query failed: {q_err}"
                    )

            if not all_results:
                current_app.logger.warning(
                    f"[ENHANCED_SEARCH] 0 results for '{query[:60]}'"
                )
                return []

            merged = sorted(all_results.values(), key=lambda x: -x[0])[:limit]
            top_score = f"{merged[0][0]:.3f}" if merged else "0"
            current_app.logger.info(
                f"[ENHANCED_SEARCH] final {len(merged)} results for limit={limit} "
                f"top_score={top_score}"
            )

            docs = self._results_to_docs([
                {"score": s, "page_content": c, "metadata": m}
                for s, c, m in merged
            ])

            if redis_service and docs:
                redis_service.set_cache(cache_key, merged, ttl=60)

            return docs

        except Exception as e:
            current_app.logger.error(f"Error in search_similar: {e}", exc_info=True)
            return []

    def add_vectors(self, vectors: List[Dict[str, Any]], provider: str = None):
        if not vectors:
            return {"message": "No vectors to add."}

        # Auto-detect provider from the first vector's metadata if not given
        if provider is None:
            provider = (vectors[0].get("metadata") or {}).get("provider", "openai")

        try:
            # Collect all vector IDs to check in one query
            vector_ids = [v.get("id", str(v.get("metadata", {}).get("doc_id", "unknown"))) for v in vectors]
            existing_rows = DocumentEmbedding.query.filter(
                DocumentEmbedding.vector_id.in_(vector_ids)
            ).all()
            existing_by_vid = {row.vector_id: row for row in existing_rows}

            new_records = []
            for v in vectors:
                vector_id = v.get("id", str(v.get("metadata", {}).get("doc_id", "unknown")))
                metadata = v.get("metadata", {})
                page_content = metadata.pop("page_content", "")
                embedding = v.get("values", [])
                doc_id = metadata.get("doc_id", "unknown-doc")
                chunk_index = metadata.get("chunk_index", 0)
                source = metadata.get("source", "unknown")
                chatbot_id = metadata.get("chatbot_id")
                tenant_id = metadata.get("tenant_id")

                # Defensive: if chatbot_id still missing, try to derive it
                # from the DataSource row matching this doc_id.
                if chatbot_id is None and doc_id and doc_id != "unknown-doc":
                    try:
                        from ..models.datasource import DataSource
                        ds = DataSource.query.filter(
                            DataSource.meta_data['doc_id'].astext == doc_id
                        ).first() if False else None
                        if ds is None:
                            for cand in DataSource.query.all():
                                if cand.meta_data and cand.meta_data.get('doc_id') == doc_id:
                                    ds = cand
                                    break
                        if ds is not None:
                            chatbot_id = ds.chatbot_id
                            tenant_id = ds.tenant_id
                            if not source or source == "unknown":
                                source = ds.source_name
                            metadata['chatbot_id'] = chatbot_id
                            metadata['tenant_id'] = tenant_id
                    except Exception:
                        pass

                existing = existing_by_vid.get(vector_id)
                if existing:
                    existing.page_content = page_content
                    existing.meta_data = metadata
                    existing.provider = provider
                    existing.chatbot_id = chatbot_id
                    existing.tenant_id = tenant_id
                    existing.source = source
                    if provider == 'openai':
                        existing.embedding_openai = embedding
                    elif provider == 'gemini':
                        existing.embedding_gemini = embedding
                    else:
                        existing.embedding_local = embedding
                else:
                    new_records.append({
                        'vector_id': vector_id,
                        'doc_id': doc_id,
                        'chunk_index': chunk_index,
                        'page_content': page_content,
                        'meta_data': metadata,
                        'source': source,
                        'chatbot_id': chatbot_id,
                        'tenant_id': tenant_id,
                        'provider': provider,
                        'embedding_openai': embedding if provider == 'openai' else None,
                        'embedding_gemini': embedding if provider == 'gemini' else None,
                        'embedding_local': embedding if provider == 'local' else None,
                    })

            if new_records:
                db.session.bulk_insert_mappings(DocumentEmbedding, new_records)

            db.session.commit()
            vectors_created = len(new_records) + len(existing_by_vid)
            current_app.logger.info(
                f"Upserted {vectors_created} vectors to pgvector (add_vectors, provider={provider})"
            )
            self._invalidate_vector_cache()
            return {"upserted_count": vectors_created}
        except Exception as e:
            current_app.logger.error(f"pgvector upsert failed: {e}")
            db.session.rollback()
            raise

    def delete_by_source(self, source_filename: str) -> dict:
        if not source_filename:
            raise ValueError("Source filename cannot be empty.")

        current_app.logger.info(f"Deleting vectors for source: {source_filename}")

        try:
            records = DocumentEmbedding.query.filter_by(source=source_filename).all()

            if not records:
                current_app.logger.info(f"No vectors found for source: {source_filename}")
                return {
                    "deleted_count": 0,
                    "message": f"No vectors found with source: {source_filename}"
                }

            ids_to_delete = [r.id for r in records]
            DocumentEmbedding.query.filter(DocumentEmbedding.id.in_(ids_to_delete)).delete(
                synchronize_session=False
            )
            db.session.commit()

            current_app.logger.info(f"Deleted {len(ids_to_delete)} vectors for source: {source_filename}")
            self._invalidate_vector_cache()

            return {
                "deleted_count": len(ids_to_delete),
                "message": f"Successfully deleted {len(ids_to_delete)} vectors from source: {source_filename}",
                "source": source_filename
            }

        except Exception as e:
            current_app.logger.error(f"Error deleting vectors for source {source_filename}: {e}")
            db.session.rollback()
            raise

    def get_chunks_by_doc_id(self, doc_id: str, provider: str = 'openai', top_k: int = None) -> List[Dict[str, Any]]:
        try:
            query_limit = top_k if top_k is not None else 1000

            records = DocumentEmbedding.query.filter_by(
                doc_id=doc_id
            ).order_by(DocumentEmbedding.chunk_index).limit(query_limit).all()

            chunks = []
            for row in records:
                embedding_openai = row.embedding_openai
                embedding_gemini = row.embedding_gemini
                embedding_local = row.embedding_local

                chunk = {
                    'page_content': row.page_content,
                    'metadata': {
                        **row.meta_data,
                        "id": row.id,
                        "vector_id": row.vector_id,
                        "doc_id": row.doc_id,
                        "source": row.source,
                        "chatbot_id": row.chatbot_id,
                        "tenant_id": row.tenant_id,
                    },
                    'embeddings': {}
                }
                if embedding_openai is not None:
                    chunk['embeddings']['openai'] = embedding_openai
                if embedding_gemini is not None:
                    chunk['embeddings']['gemini'] = embedding_gemini
                if embedding_local is not None:
                    chunk['embeddings']['local'] = embedding_local
                chunks.append(chunk)

            return chunks

        except Exception as e:
            current_app.logger.error(f"Error retrieving chunks for doc_id {doc_id}: {e}")
            raise

    def vector_count(self) -> int:
        try:
            return DocumentEmbedding.query.count()
        except Exception:
            return 0

    def _invalidate_vector_cache(self):
        redis_service = getattr(current_app, 'redis_service', None)
        if redis_service:
            redis_service.invalidate_cache("vector_search:*")

    def _dicts_to_docs(self, results: list):
        documents = []
        for result in results:
            class SimpleDoc:
                def __init__(self, content, metadata):
                    self.page_content = content
                    self.metadata = metadata
            doc = SimpleDoc(result['page_content'], result.get('metadata', {}))
            documents.append(doc)
        return documents

    def _results_to_docs(self, results: list):
        documents = []
        for result in results:
            class SimpleDoc:
                def __init__(self, content, metadata):
                    self.page_content = content
                    self.metadata = metadata
            doc = SimpleDoc(result['page_content'], result.get('metadata', {}))
            documents.append(doc)
        return documents
