# chat_project/app/services/vector_service.py

import os
import pickle
import numpy as np
from flask import current_app
from typing import Optional, List, Dict, Any

# Try Pinecone import, but don't fail if it's not available
try:
    from pinecone import Pinecone
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False

# Local vector DB imports
try:
    import faiss
    from sentence_transformers import SentenceTransformer
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

class VectorService:
    """
    A hybrid service layer for vector databases with Pinecone primary and FAISS fallback.
    Maintains the exact same interface regardless of backend.
    """
    def __init__(self):
        self.use_local = False
        self.local_index = None
        self.local_metadata = {}
        self.local_index_path = "local_faiss_index"
        
        # FAISS file paths (needed for fallback)
        config = current_app.config
        self.vector_store_path = config.get('VECTOR_STORE_PATH', 'uploads')
        self.index_file = os.path.join(self.vector_store_path, 'faiss.index')
        self.metadata_file = os.path.join(self.vector_store_path, 'metadata.pkl')
        
        # Ensure vector store directory exists
        os.makedirs(self.vector_store_path, exist_ok=True)
        
        # Get configuration
        api_key = current_app.config.get('PINECONE_API_KEY')
        self.index_name = current_app.config.get('PINECONE_INDEX_NAME')
        
        # 🎯 PRIORITY 1: Try Pinecone first (if credentials are available and not placeholders)
        if (PINECONE_AVAILABLE and 
            api_key and 
            not api_key.startswith('your-') and 
            self.index_name and 
            not self.index_name.startswith('your-')):
            
            try:
                current_app.logger.info(f"🔗 Attempting Pinecone connection to index '{self.index_name}'...")
                
                pc = Pinecone(api_key=api_key)
                
                # List all available indexes for debugging
                available_indexes = pc.list_indexes().names()
                current_app.logger.info(f"📋 Available Pinecone indexes: {available_indexes}")
                
                # Check if index exists (case-sensitive)
                if self.index_name not in available_indexes:
                    current_app.logger.warning(f"⚠️ Pinecone index '{self.index_name}' not found")
                    current_app.logger.info(f"💡 Available indexes: {available_indexes}")
                    
                    # Try to find a similar index name (in case of typos)
                    similar = [idx for idx in available_indexes if 'chat' in idx.lower() or 'project' in idx.lower()]
                    if similar:
                        current_app.logger.info(f"🔍 Similar indexes found: {similar}")
                    
                    raise ValueError(f"Index '{self.index_name}' does not exist")
                
                # Connect to the index
                self.index = pc.Index(self.index_name)
                
                # Test the connection with a simple describe operation
                index_stats = self.index.describe_index_stats()
                current_app.logger.info(f"✅ Pinecone connected! Index stats: {index_stats.get('total_vector_count', 0)} vectors")
                
                # Success! Use Pinecone
                self.use_local = False
                return
                
            except Exception as e:
                current_app.logger.warning(f"⚠️ Pinecone connection failed: {e}")
                current_app.logger.info("🔄 Falling back to local FAISS...")
        else:
            current_app.logger.info("📝 Pinecone credentials not configured or are placeholders")

        # 🎯 FALLBACK: Use local FAISS only if Pinecone failed or not configured
        if not FAISS_AVAILABLE:
            raise ValueError("Neither Pinecone nor FAISS is available. Install faiss-cpu and sentence-transformers for local fallback.")

        self.use_local = True
        self._init_local_vector_db()
        current_app.logger.info("✅ VectorService: Using local FAISS vector database")

    def _init_local_vector_db(self):
        """Initialize local FAISS vector database"""
        try:
            # Load existing index and metadata if available
            if os.path.exists(self.index_file) and os.path.exists(self.metadata_file):
                self.local_index = faiss.read_index(self.index_file)
                with open(self.metadata_file, 'rb') as f:
                    self.local_metadata = pickle.load(f)
                current_app.logger.info(f"📂 Loaded existing FAISS index with {self.local_index.ntotal} vectors")
            else:
                # Create new empty index (dimension will be set on first upsert)
                self.local_index = None
                self.local_metadata = []
                current_app.logger.info("🆕 Created new FAISS index")
                
            # Initialize sentence transformer for embeddings fallback if needed
            # Add timeout and better error handling for model loading
            import socket
            original_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(10)  # 10 second timeout
            
            try:
                self.local_model = SentenceTransformer('all-MiniLM-L6-v2')  # Fast, lightweight model
                current_app.logger.info("✅ Local sentence transformer model loaded successfully")
            except Exception as e:
                current_app.logger.warning(f"⚠️ Failed to load sentence transformer model: {e}")
                self.local_model = None  # Set to None if loading fails
            finally:
                socket.setdefaulttimeout(original_timeout)  # Restore original timeout
            
        except Exception as e:
            current_app.logger.error(f"❌ Failed to initialize local vector DB: {e}")
            raise

    def _save_local_index(self):
        """Save local FAISS index and metadata to disk"""
        if self.local_index is not None:
            faiss.write_index(self.local_index, self.index_file)
            with open(self.metadata_file, 'wb') as f:
                pickle.dump(self.local_metadata, f)

    def upsert(self, chunks_with_embeddings: list[dict], provider: str = 'openai'):
        """
        Upserts document chunks into the vector database.
        Works with both Pinecone and local FAISS.
        """
        if not self.use_local:
            return self._upsert_pinecone(chunks_with_embeddings, provider)
        else:
            return self._upsert_local(chunks_with_embeddings, provider)

    def _upsert_pinecone(self, chunks_with_embeddings: list[dict], provider: str):
        """Original Pinecone upsert logic"""
        vectors_to_upsert = []
        for i, chunk in enumerate(chunks_with_embeddings):
            embedding = chunk.get("embeddings", {}).get(provider)
            if not embedding:
                current_app.logger.warning(f"Chunk missing '{provider}' embedding. Skipping.")
                continue

            metadata = chunk.get("metadata", {})
            metadata['page_content'] = chunk.get("page_content")
            
            doc_id = metadata.get("doc_id", "unknown-doc")
            chunk_id = f"{doc_id}-chunk-{i}"

            vectors_to_upsert.append({
                "id": chunk_id,
                "values": embedding,
                "metadata": metadata
            })

        if not vectors_to_upsert:
            return {"message": "No valid vectors to upsert."}

        batch_size = 100
        for i in range(0, len(vectors_to_upsert), batch_size):
            batch = vectors_to_upsert[i:i + batch_size]
            self.index.upsert(vectors=batch)
        
        upserted_count = len(vectors_to_upsert)
        current_app.logger.info(f"📤 Upserted {upserted_count} vectors to Pinecone")
        return {"upserted_count": upserted_count}

    def _upsert_local(self, chunks_with_embeddings: list[dict], provider: str):
        """Local FAISS upsert logic"""
        vectors_to_add = []
        metadata_to_add = []
        
        for i, chunk in enumerate(chunks_with_embeddings):
            embedding = chunk.get("embeddings", {}).get(provider)
            if not embedding:
                # Fallback: generate embedding using local model
                text_content = chunk.get("page_content", "")
                if text_content:
                    embedding = self.local_model.encode([text_content])[0].tolist()
                else:
                    current_app.logger.warning(f"Chunk missing '{provider}' embedding and content. Skipping.")
                    continue

            metadata = chunk.get("metadata", {})
            metadata['page_content'] = chunk.get("page_content")
            doc_id = metadata.get("doc_id", "unknown-doc")
            chunk_id = f"{doc_id}-chunk-{i}"
            metadata['id'] = chunk_id

            vectors_to_add.append(embedding)
            metadata_to_add.append(metadata)

        if not vectors_to_add:
            return {"message": "No valid vectors to upsert."}

        # Convert to numpy array
        vectors_array = np.array(vectors_to_add, dtype=np.float32)
        
        # Initialize index if first time
        if self.local_index is None:
            dimension = vectors_array.shape[1]
            self.local_index = faiss.IndexFlatIP(dimension)  # Inner product (cosine similarity)
            current_app.logger.info(f"🔧 Initialized FAISS index with dimension {dimension}")

        # Add vectors to index
        try:
            self.local_index.add(vectors_array)
            self.local_metadata.extend(metadata_to_add)
        except AssertionError as e:
            # Handle dimension mismatch by recreating the index
            current_app.logger.warning(f"⚠️ Dimension mismatch detected. Recreating FAISS index with new dimensions.")
            dimension = vectors_array.shape[1]
            self.local_index = faiss.IndexFlatIP(dimension)
            self.local_metadata = []
            
            # Now add the vectors to the new index
            self.local_index.add(vectors_array)
            self.local_metadata.extend(metadata_to_add)
            current_app.logger.info(f"✅ Recreated FAISS index with dimension {dimension}")
        
        # Save to disk
        self._save_local_index()
        
        upserted_count = len(vectors_to_add)
        current_app.logger.info(f"📤 Upserted {upserted_count} vectors to local FAISS")
        return {"upserted_count": upserted_count}

    def query(self, query_embedding: list[float], top_k: int = 5, filter_dict: dict = None):
        """
        Queries the vector database to find the most relevant document chunks.
        Works with both Pinecone and local FAISS.
        """
        if not self.use_local:
            return self._query_pinecone(query_embedding, top_k, filter_dict)
        else:
            return self._query_local(query_embedding, top_k, filter_dict)

    def _query_pinecone(self, query_embedding: list[float], top_k: int, filter_dict: dict):
        """Original Pinecone query logic"""
        if not query_embedding:
            raise ValueError("Query embedding cannot be empty.")

        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            filter=filter_dict,
            include_metadata=True
        )
        
        matches = []
        for match in results.get('matches', []):
            metadata = match.get('metadata', {})
            page_content = metadata.pop('page_content', '') 
            matches.append({
                "score": match.get('score'),
                "page_content": page_content,
                "metadata": metadata
            })
            
        return matches

    def _query_local(self, query_embedding: list[float], top_k: int, filter_dict: dict):
        """Local FAISS query logic"""
        if not query_embedding:
            raise ValueError("Query embedding cannot be empty.")
        
        if self.local_index is None or self.local_index.ntotal == 0:
            current_app.logger.warning("🔍 Local index is empty")
            return []

        # Convert query to numpy array
        query_vector = np.array([query_embedding], dtype=np.float32)
        
        # Search in FAISS
        scores, indices = self.local_index.search(query_vector, min(top_k, self.local_index.ntotal))
        
        matches = []
        for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx == -1:  # FAISS returns -1 for empty slots
                continue
                
            metadata = self.local_metadata[idx].copy()
            page_content = metadata.pop('page_content', '')
            
            # Apply filter if provided
            if filter_dict:
                skip = False
                for key, value in filter_dict.items():
                    if key in metadata and metadata[key] != value:
                        skip = True
                        break
                if skip:
                    continue
            
            matches.append({
                "score": float(score),
                "page_content": page_content,
                "metadata": metadata
            })
        
        # Sort by score (descending)
        matches.sort(key=lambda x: x['score'], reverse=True)
        return matches[:top_k]

    def search_similar(self, query: str, chatbot_id: int = None, limit: int = 5):
        """
        Search for similar documents using text query.
        This method generates embeddings for the query and searches the vector database.
        """
        try:
            # current_app.logger.info(f"🔍 search_similar called: query='{query[:50]}...', chatbot_id={chatbot_id}, use_local={self.use_local}")
            
            # Check if we have any data at all
            if self.use_local:
                if self.local_index is None or self.local_index.ntotal == 0:
                    current_app.logger.warning("🔍 Local FAISS index is empty or not initialized")
                    return []
                # current_app.logger.info(f"🔍 Local FAISS index has {self.local_index.ntotal} vectors")
            else:
                current_app.logger.info(f"🔍 Using Pinecone index: {self.index_name}")
            # Generate embedding for the query using the same service that was used for indexing
            query_embedding = None
            
            # Try to use the same embedding service that was used for indexing
            if hasattr(current_app, 'embedding_service'):
                # current_app.logger.info("🔍 Using embedding service for query")
                try:
                    embedding_result = current_app.embedding_service.generate_embeddings_for_texts([query])
                    query_embedding = embedding_result.get('openai_embeddings', [None])[0]
                    if query_embedding:
                        # current_app.logger.info(f"🔍 Generated OpenAI embedding with dimension: {len(query_embedding)}")
                        pass
                    else:
                        current_app.logger.warning("🔍 OpenAI embedding returned None")
                except Exception as e:
                    current_app.logger.error(f"Failed to generate OpenAI embedding: {e}")
                    import traceback
                    current_app.logger.error(f"Embedding error traceback: {traceback.format_exc()}")
            
            # Fallback to local model if OpenAI embedding failed AND index uses local dimensions
            if not query_embedding and self.use_local:
                expected_dim = self.local_index.d if self.local_index else 384
                if expected_dim == 384 and self.local_model is not None:  # Check if local model is available
                    current_app.logger.info("🔍 Fallback to local model for embedding")
                    try:
                        query_embedding = self.local_model.encode([query])[0].tolist()
                        current_app.logger.info(f"🔍 Generated local embedding with dimension: {len(query_embedding)}")
                    except Exception as e:
                        current_app.logger.error(f"🔍 Local model encoding failed: {e}")
                        return []
                elif self.local_model is None:
                    current_app.logger.error(f"🔍 Cannot generate embedding: local model failed to load and OpenAI embedding failed")
                    return []
                else:
                    current_app.logger.error(f"🔍 Cannot generate embedding: index expects {expected_dim} dimensions but OpenAI embedding failed")
                    return []
            
            # Check dimension compatibility
            if self.use_local and self.local_index and query_embedding:
                expected_dim = self.local_index.d
                actual_dim = len(query_embedding)
                # current_app.logger.info(f"🔍 Dimension check: expected={expected_dim}, actual={actual_dim}")
                
                if expected_dim != actual_dim:
                    current_app.logger.error(f"❌ Dimension mismatch: index expects {expected_dim}, query has {actual_dim}")
                    return []
            
            if not query_embedding:
                current_app.logger.warning("Failed to generate query embedding")
                return []
            
            # Build filter for chatbot_id if provided
            filter_dict = None
            if chatbot_id is not None:
                filter_dict = {"chatbot_id": chatbot_id}
            
            # Query the vector database
            results = self.query(query_embedding, top_k=limit, filter_dict=filter_dict)
            
            # Convert results to Document-like objects for compatibility
            documents = []
            for result in results:
                # Create a simple object with page_content attribute
                class SimpleDoc:
                    def __init__(self, content, metadata):
                        self.page_content = content
                        self.metadata = metadata
                
                doc = SimpleDoc(result['page_content'], result.get('metadata', {}))
                documents.append(doc)
            
            # current_app.logger.info(f"🔍 Vector search found {len(documents)} documents for query: '{query[:50]}...'")
            return documents
            
        except Exception as e:
            current_app.logger.error(f"❌ Error in search_similar: {e}", exc_info=True)
            current_app.logger.error(f"❌ Query: '{query}', chatbot_id: {chatbot_id}, use_local: {self.use_local}")
            return []

    def add_vectors(self, vectors: List[Dict[str, Any]]):
        """
        Adds pre-formatted vectors directly to the vector database.
        This method is a simpler alternative to `upsert` and expects a list of dicts,
        each with "id", "values", and "metadata".
        """
        if not vectors:
            print("✅ [BG-PRINT-VS] add_vectors: No vectors to add.")
            return {"message": "No vectors to add."}

        if not self.use_local:
            try:
                print("🔍 [BG-PRINT-VS] add_vectors: Attempting to store in Pinecone.")
                # Pinecone takes vectors in the format: [{"id": "A", "values": [..], "metadata": {..}}, ...]
                batch_size = 100
                for i in range(0, len(vectors), batch_size):
                    batch = vectors[i:i + batch_size]
                    print(f"🔍 [BG-PRINT-VS] add_vectors: Upserting batch {i//batch_size + 1} to Pinecone.")
                    self.index.upsert(vectors=batch)
                print(f"✅ [BG-PRINT-VS] add_vectors: Pinecone upsert successful.")
                current_app.logger.info(f"📤 Upserted {len(vectors)} vectors to Pinecone")
                return {"upserted_count": len(vectors)}
            except Exception as e:
                print(f"❌ [BG-PRINT-VS] add_vectors: Pinecone upsert failed: {e}")
                raise e
        else:
            try:
                print("🔍 [BG-PRINT-VS] add_vectors: Attempting to store in local FAISS.")
                # FAISS logic
                embeddings = [v['values'] for v in vectors]
                metadata_list = [v['metadata'] for v in vectors]
                vectors_array = np.array(embeddings, dtype=np.float32)

                if self.local_index is None:
                    dimension = vectors_array.shape[1]
                    self.local_index = faiss.IndexFlatIP(dimension)
                    print(f"🔧 [BG-PRINT-VS] add_vectors: Initialized new FAISS index with dimension {dimension}.")
                    current_app.logger.info(f"🔧 Initialized FAISS index with dimension {dimension}")

                try:
                    print("🔍 [BG-PRINT-VS] add_vectors: Adding vectors to FAISS index.")
                    self.local_index.add(vectors_array)
                    self.local_metadata.extend(metadata_list)
                    print("✅ [BG-PRINT-VS] add_vectors: Added vectors to FAISS successfully.")
                except Exception:
                    # Handle dimension mismatch by recreating the index (loses old data, matches existing service behavior)
                    print(f"⚠️ [BG-PRINT-VS] add_vectors: FAISS dimension mismatch. Recreating index.")
                    current_app.logger.warning(f"⚠️ FAISS dimension mismatch detected. Recreating index.")
                    dimension = vectors_array.shape[1]
                    self.local_index = faiss.IndexFlatIP(dimension)
                    self.local_metadata = [] 
                    self.local_index.add(vectors_array)
                    self.local_metadata.extend(metadata_list)
                
                print("💾 [BG-PRINT-VS] add_vectors: Saving FAISS index to disk.")
                self._save_local_index()
                print("✅ [BG-PRINT-VS] add_vectors: FAISS save complete.")
                current_app.logger.info(f"📤 Upserted {len(vectors)} vectors to local FAISS")
                return {"upserted_count": len(vectors)}
            except Exception as e:
                print(f"❌ [BG-PRINT-VS] add_vectors: FAISS operation failed: {e}")
                raise e

    def delete_by_source(self, source_filename: str) -> dict:
        """
        Deletes all vectors associated with a specific source filename.
        """
        if not self.use_local:
            return self._delete_by_source_pinecone(source_filename)
        else:
            return self._delete_by_source_local(source_filename)

    def _delete_by_source_pinecone(self, source_filename: str):
        """Delete all vectors associated with a specific source filename from Pinecone"""
        if not source_filename:
            raise ValueError("Source filename cannot be empty.")
        
        current_app.logger.info(f"🗑️ Attempting to delete vectors for source: {source_filename}")
        
        try:
            # Query all vectors with this source to get their IDs first
            query_response = self.index.query(
                vector=[0.0] * 3072,  # Dummy vector for metadata-only query
                filter={"source": {"$eq": source_filename}},
                top_k=10000,  # Large number to get all matches
                include_metadata=True,
                include_values=False
            )
            
            if not query_response.matches:
                current_app.logger.info(f"📭 No vectors found for source: {source_filename}")
                return {
                    "deleted_count": 0, 
                    "message": f"No vectors found with source: {source_filename}"
                }
            
            # Extract IDs to delete
            ids_to_delete = [match.id for match in query_response.matches]
            current_app.logger.info(f"🔍 Found {len(ids_to_delete)} vectors to delete for source: {source_filename}")
            
            # Delete the vectors
            delete_response = self.index.delete(ids=ids_to_delete)
            current_app.logger.info(f"✅ Successfully deleted {len(ids_to_delete)} vectors for source: {source_filename}")
            
            return {
                "deleted_count": len(ids_to_delete),
                "message": f"Successfully deleted {len(ids_to_delete)} vectors from source: {source_filename}",
                "source": source_filename
            }
            
        except Exception as e:
            current_app.logger.error(f"❌ Error deleting vectors for source {source_filename}: {e}")
            raise Exception(f"Failed to delete vectors for source {source_filename}: {str(e)}")

    def get_chunks_by_doc_id(self, doc_id: str, provider: str = 'openai', top_k: int = None) -> List[Dict[str, Any]]:
        """
        Retrieves chunks associated with a specific document ID.
        Works with both Pinecone and local FAISS.
        
        Args:
            doc_id: Document ID to retrieve chunks for
            provider: Provider for embeddings (default: 'openai')
            top_k: Maximum number of chunks to return (None = all chunks)
        """
        if not self.use_local:
            chunks = self._get_chunks_by_doc_id_pinecone(doc_id, top_k)
        else:
            chunks = self._get_chunks_by_doc_id_local(doc_id, top_k)
        
        # Apply top_k limit if specified
        if top_k is not None and len(chunks) > top_k:
            chunks = chunks[:top_k]
            
        return chunks

    def _get_chunks_by_doc_id_pinecone(self, doc_id: str, top_k: int = None) -> List[Dict[str, Any]]:
        """Get chunks by doc_id from Pinecone"""
        try:
            # Query vectors with this doc_id
            query_top_k = top_k if top_k is not None else 1000  # Use provided top_k or default to large number
            response = self.index.query(
                vector=[0.0] * 3072,  # Dummy vector for metadata-only query
                filter={"doc_id": {"$eq": doc_id}},
                top_k=query_top_k,
                include_metadata=True,
                include_values=True
            )
            
            chunks = []
            for match in response.matches:
                chunk = {
                    'page_content': match.metadata.get('page_content', ''),
                    'metadata': {k: v for k, v in match.metadata.items() if k != 'page_content'},
                    'embeddings': {
                        'openai': match.values  # Pinecone stores embeddings directly
                    }
                }
                chunks.append(chunk)
            
            return chunks
            
        except Exception as e:
            current_app.logger.error(f"❌ Error retrieving chunks for doc_id {doc_id} from Pinecone: {e}")
            raise

    def _get_chunks_by_doc_id_local(self, doc_id: str, top_k: int = None) -> List[Dict[str, Any]]:
        """Get chunks by doc_id from local FAISS"""
        chunks = []
        
        # Search through metadata for matching doc_id
        for i, metadata in enumerate(self.local_metadata):
            if metadata.get('doc_id') == doc_id:
                # Get the vector from FAISS
                vector = self.local_index.reconstruct(i) if self.local_index else None
                
                chunk = {
                    'page_content': metadata.get('page_content', ''),
                    'metadata': {k: v for k, v in metadata.items() if k not in ['page_content', 'id']},
                    'embeddings': {
                        'openai': vector.tolist() if vector is not None else []
                    }
                }
                chunks.append(chunk)
        
        return chunks

    def _delete_by_source_local(self, source_filename: str):
        """Local FAISS deletion logic"""
        if not source_filename:
            raise ValueError("Source filename cannot be empty.")

        # Find indices to delete
        indices_to_delete = []
        for i, metadata in enumerate(self.local_metadata):
            if metadata.get('source') == source_filename:
                indices_to_delete.append(i)

        if not indices_to_delete:
            return {"deleted_count": 0, "message": f"No vectors found with source: {source_filename}"}

        # FAISS doesn't support deletion, so we need to rebuild the index
        # This is expensive but necessary for local fallback
        current_app.logger.info(f"🔄 Rebuilding FAISS index to remove {len(indices_to_delete)} vectors")
        
        # Collect remaining vectors and metadata
        remaining_metadata = []
        remaining_vectors = []
        
        for i, metadata in enumerate(self.local_metadata):
            if i not in indices_to_delete and self.local_index is not None:
                remaining_metadata.append(metadata)
                # Extract vector from index (this is expensive)
                vector = self.local_index.reconstruct(i)
                remaining_vectors.append(vector)

        # Rebuild index
        if remaining_vectors:
            vectors_array = np.array(remaining_vectors, dtype=np.float32)
            dimension = vectors_array.shape[1]
            self.local_index = faiss.IndexFlatIP(dimension)
            self.local_index.add(vectors_array)
            self.local_metadata = remaining_metadata
        else:
            self.local_index = None
            self.local_metadata = []

        # Save rebuilt index
        self._save_local_index()
        
        deleted_count = len(indices_to_delete)
        current_app.logger.info(f"🗑️ Deleted {deleted_count} vectors from local FAISS")
        return {"deleted_count": deleted_count, "message": f"Successfully deleted vectors from source: {source_filename}"}