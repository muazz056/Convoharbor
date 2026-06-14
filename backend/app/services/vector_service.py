from flask import current_app
from typing import List, Dict, Any
from sqlalchemy import text
from .. import db
from ..models.document_embedding import DocumentEmbedding, PGVECTOR_AVAILABLE


class VectorService:
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

    def query(self, query_embedding: list[float], top_k: int = 5, filter_dict: dict = None):
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
            from sqlalchemy import func as _sa_func
            count_q = db.session.query(_sa_func.count(DocumentEmbedding.id))
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

        # Over-fetch so we can dedup BEFORE slicing to top_k.
        # If duplicates exist (same doc_id+chunk_index), the dedup pass
        # may shrink the result set, so we want headroom.
        raw_limit = max(top_k * 3, top_k + 5)
        raw_results = base_query.order_by(text('distance')).limit(raw_limit).all()

        current_app.logger.info(
            f"[VECTOR_QUERY] raw_results_count={len(raw_results)} provider={provider} top_k={top_k}"
        )

        # Deduplicate by (doc_id, chunk_index) keeping the best (smallest
        # distance) match. This is what prevents the same chunk from being
        # returned 4 times because the same chunk was ingested 4 times.
        dedup: dict[tuple, tuple] = {}
        for row, distance in raw_results:
            key = (row.doc_id, row.chunk_index)
            if key not in dedup or distance < dedup[key][1]:
                dedup[key] = (row, distance)

        # Sort by distance and slice to top_k.
        ranked = sorted(dedup.values(), key=lambda pair: pair[1])[:top_k]

        current_app.logger.info(
            f"[VECTOR_QUERY] after_dedup={len(ranked)} top_scores={[round(max(0, 1-float(d)),3) for _,d in ranked[:3]]}"
        )

        matches = []
        for row, distance in ranked:
            score = max(0.0, 1.0 - float(distance))
            embedding_openai = row.embedding_openai
            embedding_gemini = row.embedding_gemini
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
                    "openai": embedding_openai,
                    "gemini": embedding_gemini,
                }
            })

        return matches

    def search_similar(self, query: str, chatbot_id: int = None, limit: int = 5):
        try:
            if not hasattr(current_app, 'embedding_service'):
                current_app.logger.error("Embedding service not available")
                return []

            cache_key = f"vector_search:{query}:{chatbot_id}:{limit}"
            redis_service = getattr(current_app, 'redis_service', None)
            if redis_service:
                cached = redis_service.get_cache(cache_key)
                if cached is not None:
                    current_app.logger.info(f"Cache hit for vector search: '{query[:50]}...'")
                    return self._dicts_to_docs(cached)

            query_embedding = None
            embed_provider = 'openai'
            try:
                embedding_result = current_app.embedding_service.generate_embeddings_for_texts([query])
                embeddings_list = embedding_result.get("embeddings")
                embed_provider = embedding_result.get("provider", "openai")
                query_embedding = embeddings_list[0] if embeddings_list else None
                embed_error = embedding_result.get("error")
                current_app.logger.info(
                    f"[VECTOR_SEARCH] query='{query[:60]}' chatbot_id={chatbot_id} "
                    f"embed_provider={embed_provider} embed_dim={len(query_embedding) if query_embedding else 0} "
                    f"error={embed_error}"
                )
            except Exception as e:
                current_app.logger.error(f"Failed to generate embedding: {e}", exc_info=True)
                embed_error = str(e)

            if not query_embedding:
                current_app.logger.warning(
                    f"[VECTOR_SEARCH] NO QUERY EMBEDDING - retrieval will return 0 results. "
                    f"check EMBEDDINGS_SERVICE_USE, OPENAI_API_KEY, GEMINI_API_KEY"
                )
                return []

            # Always filter by chatbot_id when one is provided. We do NOT
            # fall back to a global search because that would let unrelated
            # documents (from a different chatbot's KB, or older legacy
            # embeddings) pollute the current chatbot's context.
            filter_dict = {"provider": embed_provider}
            if chatbot_id is not None:
                filter_dict["chatbot_id"] = chatbot_id

            results = self.query(query_embedding, top_k=limit, filter_dict=filter_dict)

            # If 0 results with the active provider, try the OTHER providers
            # as a courtesy fallback. This keeps older KBs (stored under
            # 'openai') retrievable even if the active provider switched.
            if not results and chatbot_id is not None:
                all_providers = ['openai', 'gemini', 'local']
                fallback_providers = [p for p in all_providers if p != embed_provider]
                for fallback_provider in fallback_providers:
                    current_app.logger.warning(
                        f"[VECTOR_SEARCH] 0 results with provider={embed_provider} - "
                        f"trying fallback provider={fallback_provider}"
                    )
                    fallback_filter = {"provider": fallback_provider, "chatbot_id": chatbot_id}
                    fallback_results = self.query(query_embedding, top_k=limit, filter_dict=fallback_filter)
                    if fallback_results:
                        results = fallback_results
                        current_app.logger.info(
                            f"[VECTOR_SEARCH] fallback provider={fallback_provider} returned {len(results)} results"
                        )
                        break
                else:
                    current_app.logger.warning(
                        f"[VECTOR_SEARCH] ALL FALLBACKS FAILED - 0 results with "
                        f"{[p for p in all_providers if p != embed_provider]} too. "
                        f"DB has chunks for chatbot_id={chatbot_id} but no provider's "
                        f"embedding column has a matching vector. Re-upload the document or run repair."
                    )

            if redis_service:
                redis_service.set_cache(cache_key, results, ttl=60)

            documents = self._results_to_docs(results)
            return documents

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
