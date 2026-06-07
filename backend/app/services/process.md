PHASE 1: INGESTION (happens when you upload a PDF)
Step 1 — HTTP upload, row creation
File: backend/app/api/datasources.py:82 — POST /api/v1/datasources/upload
- Frontend posts multipart/form-data with files[] + chatbot_id.
- For each file, a row is created in the datasources table with:
- chatbot_id (from request)
- tenant_id (from g.tenant_id)
- source_name = the filename
- status = 'uploading'
- meta_data = {file_id, upload_batch_id, description}
- Returns 202 immediately, then spawns a background thread (process_files at line 152) so the HTTP request doesn't block.
Step 2 — Save file to temp, upload to Cloudinary
File: backend/app/services/document_service.py:16 — process_uploaded_files()
- File is first written to a tempfile (so the background thread can still access it — request.files is request-lifecycle scoped).
- cloudinary_service.upload_temp_file() uploads the raw PDF to Cloudinary (your log shows Uploaded Metamorphosis.pdf to Cloudinary: Convoharbor/okg9tyxe98syedbkaixd.pdf).
- The Cloudinary public_id is kept temporarily in case we need it for retries, but it's deleted right after processing (Deleted Metamorphosis.pdf from Cloudinary after processing).
Step 3 — Document loading
File: document_service.py:47
- Picks a LangChain loader based on extension: .pdf → PyPDFLoader, .txt → TextLoader, .docx → Docx2txtLoader.
- PyPDFLoader.load() reads the PDF page-by-page and returns a list of Document objects — one per page, each with page_content (the raw text) and metadata (page number, source path).
Step 4 — Text cleaning
File: document_service.py:51-52 → text_cleaner_service.py:6 — clean_extracted_text()
For every page, this strips:
- Null bytes, control characters, zero-width chars
- Smart quotes → ASCII ('…' → ', "…" → ")
- Single-letter fragmentation ("t h i s" → "this")
- Hyphenated line-breaks ("exam-\nple" → "example")
- Word section markers, page breaks, multiple underscores/dashes
- Collapses runs of spaces/tabs/newlines
Your log shows this for every page: 🧹 Text cleaner: Final text length: 1807 chars (reduced by 505).
Step 5 — Chunking
File: backend/app/services/processing_service.py:5 — process_documents_into_chunks()
- Uses LangChain's RecursiveCharacterTextSplitter with:
- chunk_size = 1000 chars (from app/config.py:107)
- chunk_overlap = 150 chars (from app/config.py:108)
- This splitter tries separators in order: ["\n\n", "\n", " ", ""], splitting on the most natural boundary first while keeping each chunk ≤ 1000 chars. The 150-char overlap prevents losing context at chunk boundaries.
- For each chunk it stamps metadata: {doc_id: <uuid>, source: <filename>, language: 'und'}.
- Returns a list of LangChain Document objects — 151 of them for your PDF (the 85 pages × ~1.7 chunks/page).
Step 6 — Embedding generation ⚠️ THE CULPRIT WAS HERE
File: backend/app/services/embedding_service.py:51 — generate_embeddings_for_texts()
- Reads EMBEDDINGS_SERVICE_USE from .env — you have it set to gemini.
- Calls _gemini_embed(texts, ...) which builds a BatchEmbedContentsRequest and calls Google's Generative Language API.
- The original bug: it sent all 151 chunks in a single batch. Gemini's hard limit is 100 requests/batch → HTTP 400 → both Gemini models fail → function returns {"embeddings": None, "provider": "gemini", "error": "All Gemini embedding models failed"}.
- The fix I just applied:
1. _gemini_embed now splits texts into chunks of 100 and calls batch_embed_contents once per slice, concatenating the per-slice results in original order.
2. If both Gemini models still fail, the function now falls back to OpenAIEmbeddings (using OPENAI_EMBEDDING_MODEL from .env) and returns {"provider": "openai"} so the embeddings are never silently lost.
- Result: a list of 151 float vectors, each ~768/3072 dimensions (depending on the model).
Step 7 — Build processed chunks with chatbot_id
File: backend/app/api/datasources.py:220-235 (in process_files() background thread)
- For each of the 151 chunks:
- Copies chunk.metadata into a new dict chunk_meta.
- Injects chatbot_id and tenant_id (this is the fix I added yesterday — the old code didn't, which is why your previous upload's rows had NULL chatbot_id).
- Builds {"metadata": chunk_meta, "page_content": ..., "embeddings": {<provider>: <vector>}}.
Step 8 — Vector upsert to pgvector
File: backend/app/services/vector_service.py:22 — VectorService.upsert()
- For each of the 151 chunks:
- Generates vector_id = f"{doc_id}-chunk-{i}".
- One bulk query fetches all 151 existing rows matching those vector_ids (fast dedup).
- For each chunk: if exists, update; if new, append to a bulk-insert list.
- db.session.bulk_insert_mappings(DocumentEmbedding, new_records) — single SQL INSERT for all 151 rows.
- db.session.commit() — flushed to the document_embeddings table in Postgres with the pgvector extension.
- _invalidate_vector_cache() — clears the Redis vector_search:* cache (Redis is disabled in your env, so this is a no-op).
Step 9 — Mark DataSource row as completed
File: datasources.py:262-264
- data_source.status = 'completed'
- data_source.meta_data['doc_id'] = doc_id ← critical, used by the repair endpoint and add_vectors defensive lookup.
- data_source.meta_data['processed_chunks'] = 151
- WebSocket emits crawl_completed (or in this case, no socketio for the upload path, so just DB write).
- Your log: ✅ Stored 151 chunks in vector DB for Metamorphosis.pdf (chatbot_id=9).
End of Phase 1. The 151 vectors now live in the document_embeddings Postgres+pgvector table, each with {vector_id, doc_id, chunk_index, page_content, meta_data{chatbot_id:9, tenant_id:3, source:'Metamorphosis.pdf', ...}, provider:'gemini', embedding_gemini: <float[]>}.
PHASE 2: ONLINE QUERY (happens when the user types a message)

Step 10 — User sends "What instrument did Grete play?"
File: backend/app/api/chatbots.py — POST /api/v1/chatbots/<id>/test-message (or conversations.py:send_message for embed chat)
- Validates message, fetches the Chatbot row, calls model_resolver.resolve_model(config) to get the LLM (Gemini-2.5-pro / llama-4-scout / etc.) from the Super Admin's ai_models DB table.
Step 11 — Semantic search for context
File: backend/app/services/vector_service.py:169 — VectorService.search_similar(query, chatbot_id, limit)
- Calls embedding_service.generate_embeddings_for_texts([query]) — for ONE query text this works fine (well under the 100 limit). Returns {"embeddings": [vector], "provider": "gemini"}.
- Builds the filter: {"provider": "gemini", "chatbot_id": 9} — chatbot_id filter is strictly enforced (the silent fallback was removed).
- Calls self.query(query_embedding, top_k=10, filter_dict=...) which:
1. Picks the embedding_gemini column.
2. Filters embed_col.isnot(None) ← THIS is what was killing your retrieval yesterday because Gemini batch failed, all embedding columns were NULL, this filter excluded everything.
3. Filters chatbot_id == 9 and provider == 'gemini'.
4. Over-fetches (max(top_k*3, top_k+5) = 30 rows) and dedupes by (doc_id, chunk_index).
5. Sorts by cosine distance, slices to top_k=10.
6. Graceful fallback: if the active provider returns 0, tries the OTHER provider (e.g. openai column) as a courtesy.
- Returns a list of 10 chunk documents with page_content + metadata + similarity score.
Step 12 — Build context block
File: chatbots.py:1611-1653 (or conversations.py:765-)
- Loops through the 10 results, dedupes by (source, doc_id, chunk_index, content[:80]) so the same physical chunk ingested twice doesn't flood the LLM context.
- Joins the chunks with \n\n separators into one big context_text string.
- Logs: 🔍 Test chat retrieved from 1 source(s): ['Metamorphosis.pdf'] and 🔍 Test chat found N matching chunks, total context length: XXXX.
Step 13 — Build the LLM prompt
File: conversations.py:920-965 (or chatbots.py mirror)
- Base system message comes from the chatbot's configured prompts.system_message (or personality default).
- Then appended (from prompts.yml):
- Strict mode + context found → rag_system.strict template: "You are ${chatbot_role} known as ${chatbot_name}. ... Use ONLY the following knowledge base to answer: ${context}. If the answer is not in the knowledge base, say so. Respond in ${target_lang}."
- Strict mode + no context → rag_system.out_of_scope template: refuses politely.
- Permissive mode → rag_system.permissive template: can use KB + general knowledge.
- prompt_svc.render(key, **kwargs) uses string.Template.safe_substitute to inject the variables.
Step 14 — Call the LLM
File: backend/app/services/llm_service.py (or ai_connector)
- Sends {system: full_system_message, user: "What instrument did Grete play?"} to the configured model (e.g. meta-llama/llama-4-scout-17b-16e-instruct).
- Gets back the assistant's text response.
- Your log preview: 🧪 Test mode: System message preview: You are AI Assistant known as this chatbot in STRICT (Knowledge-Base Locked) mode....
Step 15 — Stream/store response
- For embed chat (streaming): SSE chunks sent to the browser; full response saved to messages table.
- For test chat: response returned as JSON and stored in the user's localStorage only (no DB write).
Summary table
#	Phase	Where	What
1	Ingest	datasources.py:82	HTTP upload, create DataSource row
2	Ingest	datasources.py:152-208	Background thread, temp file, Cloudinary upload
3	Ingest	document_service.py:47	LangChain PyPDFLoader.load()
4	Ingest	text_cleaner_service.py:6	Strip control chars, smart quotes, hyphenation, whitespace
5	Ingest	processing_service.py:5	Split into 1000-char chunks with 150-char overlap
6	Ingest	embedding_service.py:51	Batch of 100 Gemini (or OpenAI fallback) embedding
7	Ingest	datasources.py:220-235	Inject chatbot_id/tenant_id into chunk metadata
8	Ingest	vector_service.py:22	Bulk INSERT to pgvector document_embeddings table
9	Ingest	datasources.py:262	Mark DataSource row completed
10	Query	chatbots.py	Receive message, resolve LLM model
11	Query	vector_service.py:169	Embed query (1 text) + cosine search filtered by chatbot_id
12	Query	chatbots.py:1611	Dedupe and concatenate chunks into context_text
13	Query	conversations.py:920	Build system prompt with rag_system.strict template
14	Query	llm_service.py	Call LLM with system + user messages
15	Query	api endpoint	Stream/return to user, persist if embed chat


