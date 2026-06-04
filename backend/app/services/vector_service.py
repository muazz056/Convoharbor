from flask import current_app
from typing import Optional, List, Dict, Any
from sqlalchemy import text, or_
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
                else:
                    existing.embedding_gemini = embedding
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
                    'embedding_gemini': embedding if provider != 'openai' else None,
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
        else:
            embed_col = DocumentEmbedding.embedding_gemini

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

        results = base_query.order_by(text('distance')).limit(top_k).all()

        matches = []
        for row, distance in results:
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
            except Exception as e:
                current_app.logger.error(f"Failed to generate embedding: {e}")

            if not query_embedding:
                current_app.logger.warning("Failed to generate query embedding")
                return []

            # First try with chatbot_id filter
            filter_dict = {"provider": embed_provider}
            if chatbot_id is not None:
                filter_dict["chatbot_id"] = chatbot_id

            results = self.query(query_embedding, top_k=limit, filter_dict=filter_dict)

            # Fallback: if no results with chatbot_id, try without it (for legacy embeddings)
            if not results and chatbot_id is not None:
                current_app.logger.warning(
                    f"Vector search found 0 results for chatbot_id={chatbot_id}, "
                    f"trying fallback without chatbot_id filter"
                )
                filter_dict_fallback = {"provider": embed_provider}
                results = self.query(query_embedding, top_k=limit, filter_dict=filter_dict_fallback)
                if results:
                    current_app.logger.info(
                        f"Fallback search found {len(results)} results (chatbot_id={chatbot_id} "
                        f"embeddings may be missing chatbot_id)"
                    )

            if redis_service:
                redis_service.set_cache(cache_key, results, ttl=60)

            documents = self._results_to_docs(results)
            return documents

        except Exception as e:
            current_app.logger.error(f"Error in search_similar: {e}", exc_info=True)
            return []

    def add_vectors(self, vectors: List[Dict[str, Any]]):
        if not vectors:
            return {"message": "No vectors to add."}

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

                existing = existing_by_vid.get(vector_id)
                if existing:
                    existing.page_content = page_content
                    existing.meta_data = metadata
                    existing.embedding_openai = embedding
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
                        'provider': 'openai',
                        'embedding_openai': embedding,
                        'embedding_gemini': None,
                    })

            if new_records:
                db.session.bulk_insert_mappings(DocumentEmbedding, new_records)

            db.session.commit()
            vectors_created = len(new_records) + len(existing_by_vid)
            current_app.logger.info(f"Upserted {vectors_created} vectors to pgvector (add_vectors)")
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
