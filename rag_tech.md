# RAG Technology Stack — ConvoHarbor

## Overview

ConvoHarbor implements a multi-stage Retrieval-Augmented Generation (RAG) pipeline. Every user message passes through **query processing → hybrid search → re-ranking → LLM generation** before a response is returned.

```
User Query
  │
  ├─ 1. Query Rewriting      (resolve pronouns, standalone query)
  ├─ 2. Query Expansion      (3 semantic variants via LLM)
  ├─ 3. Hybrid Search
  │      ├─ Vector (pgvector cosine distance)
  │      └─ Full-Text Search (PostgreSQL tsvector + ts_rank)
  │         └─ Reciprocal Rank Fusion (RRF)
  ├─ 4. MMR Diversification  (Maximum Marginal Relevance)
  ├─ 5. LLM Re-ranking       (relevance scoring 0–5)
  └─ 6. LLM Generation       (answer from top-K chunks + system prompt)
```

---

## 1. Chunk Overlap (Indexing)

**File:** `backend/app/services/processing_service.py`
**Config:** `CHUNK_SIZE` (default 1000 chars), `CHUNK_OVERLAP` (default 150 chars) — both env-configurable via `.env`.

Uses `langchain.text_splitter.RecursiveCharacterTextSplitter`. Splits documents on natural boundaries (`\n\n`, `\n`, space) while keeping each chunk ≤ `CHUNK_SIZE`. Overlap of `CHUNK_OVERLAP` characters prevents information loss at chunk boundaries — the same sentence or paragraph may span two chunks.

**Environment variables:**
```
CHUNK_SIZE=1000
CHUNK_OVERLAP=150
```

All ingestion paths (file upload, web crawl, scraped content) converge through this single chunking function.

---

## 2. Query Rewriting

**File:** `backend/app/services/vector_service.py` → `rewrite_query()` (line ~430)
**Prompt:** `prompts.yml` → `query_rewrite`
**Model:** Uses chatbot's configured AI model (from `AiModel` table).

Before searching, the user's query is rewritten to be **self-contained** by resolving pronouns ("it", "they", "this") using conversation history. For example:

- User says: "Tell me more about it"
- History: "What are your projects?"  → "I offer web development and mobile apps"
- Rewritten: "Tell me more about your projects"

Skips rewrite for conversation-ending phrases (bye, goodbye, thanks).

**Why:** Vector embeddings of "it" alone produce poor similarity. A self-contained query matches the correct chunks.

---

## 3. Query Expansion

**File:** `backend/app/services/vector_service.py` → `expand_query()` (line ~387)
**Prompt:** `prompts.yml` → `query_expansion`
**Model:** Uses chatbot's configured AI model.

Generates **3 search variants** from the original query. Each captures a different angle, phrasing, or synonym set:

| Original | Expanded |
|----------|----------|
| "what projects do you have" | "what projects do you have", "list your projects and services", "what work has your company done" |
| "pricing plans" | "pricing plans", "cost and subscription tiers", "how much does it cost" |

Each variant is embedded and searched independently. Results are merged with original query weighted 1.0, variants weighted 0.7.

**Why:** A single query may not capture all possible phrasings of relevant chunks. Multiple queries cast a wider net.

---

## 4. Hybrid Search (Vector + FTS via RRF)

**File:** `backend/app/services/vector_service.py` → `_hybrid_query()` (line ~268), `_fts_rank()` (line ~240)
**Provider:** Single active provider from `EMBEDDINGS_SERVICE_USE` (openai / gemini / local).

Combines two independent retrieval methods:

### 4a. Vector Search (Semantic)
- **Storage:** pgvector column (`embedding_openai`, `embedding_gemini`, or `embedding_local` — only the active one is populated).
- **Index:** IVFFlat or HNSW index on the active embedding column.
- **Query:** Cosine distance between query embedding and stored embeddings: `1 - cos(q, d)`.
- **Strength:** Captures semantic meaning. "automobiles" matches "cars".

### 4b. Full-Text Search (Keyword)
- **PostgreSQL tsvector:** GIN index on `to_tsvector('english', page_content)` — auto-created at startup.
- **Query Parsing:** `websearch_to_tsquery('english', query)` converts natural language to tsquery operators (`&`, `|`, `!`).
- **Ranking:** `ts_rank(tsvector, tsquery)` — TF/IDF-based relevance score.
- **Strength:** Exact keyword matching. "project" matches chunks containing "project" precisely.

### RRF (Reciprocal Rank Fusion)

```
RRF_score(doc) = 1/(k + rank_vector(doc)) + 1/(k + rank_fts(doc))
```

Where `k = 60` and ranks are 0-indexed. Documents found by both methods get a boost. Documents found by only one method still appear but with lower score.

**Why:** Pure vector search can miss exact matches (especially for named entities, codes, prices). Pure FTS misses synonyms. RRF combines both without tuning weights.

---

## 5. MMR Diversification

**File:** `backend/app/services/vector_service.py` → `_mmr_diversify()` (line ~328)

After hybrid scoring, MMR selects a **diverse subset** to avoid near-duplicate chunks:

```
MMR = λ * sim(query, chunk) - (1 - λ) * max(sim(chunk, selected))
```

- `λ = 0.5` for pure vector path, `λ = 0.4` for hybrid path.
- First chunk is selected by relevance to query.
- Each subsequent chunk is penalized if it's too similar to already-selected chunks.

**Why:** If 4 out of 5 top chunks are from the same page section, the LLM sees redundant information. MMR trades some relevance for diversity, giving the LLM a broader view.

---

## 6. LLM Re-ranking

**File:** `backend/app/services/vector_service.py` → `_rerank()` (line ~308)
**Prompt:** `prompts.yml` → `rerank`
**Model:** Uses chatbot's configured AI model (same as response generation).

After hybrid search + MMR, the top 10–15 candidates are sent to the LLM for fine-grained relevance scoring:

```
USER QUERY: "what projects do you have"

CHUNK 1: Our company specializes in web development...
CHUNK 2: We are located at 123 Main Street...
...

→ LLM returns: [4, 1, 5, 2, 3, ...]  (0–5 per chunk)
```

Scoring rules:
- **5** = perfect match (exactly what user wants)
- **4** = highly relevant (directly answers the query)
- **3** = relevant (addresses the topic)
- **2** = somewhat related
- **1** = barely related
- **0** = irrelevant

Results are re-sorted by LLM score. Only top-K (per `limit` parameter) are returned as context.

**Why:** Cosine similarity and FTS rank are proxies for relevance. An LLM can understand the actual question-answer relationship. A chunk about "location" ranks well for "where are you" but poorly for "what projects" — something pure embedding similarity may miss.

---

## 7. Provider Architecture

### Storage

Each chunk stores its embedding in one of **3 columns**, depending on which `EMBEDDINGS_SERVICE_USE` was active at ingestion time:
- `embedding_openai` (3072d)
- `embedding_gemini` (3072d)
- `embedding_local` (384d, model: `thenlper/gte-small`)

The `provider` column records which provider generated the embedding. **Multiple providers can co-exist** in the same table — chunks ingested while config was `openai` sit alongside chunks ingested after a switch to `gemini`.

### Query-Time Provider Detection

`search_similar` does **not** use `EMBEDDINGS_SERVICE_USE` at query time. Instead it queries the DB for all distinct providers that have non-NULL embeddings for the given chatbot:

```python
active_providers_rows = db.session.query(
    DocumentEmbedding.provider
).filter(
    DocumentEmbedding.chatbot_id == chatbot_id,
    DocumentEmbedding.provider.isnot(None)
).distinct().all()
```

Each active provider gets its own embedding generated (OpenAI query → OpenAI column, Gemini query → Gemini column). Results from all providers are merged via weighted scoring.

**Benefit:** Switching `EMBEDDINGS_SERVICE_USE` does not orphan old chunks. All chunks — regardless of which provider created them — are found at query time.

---

## 8. Complete Pipeline Walkthrough

### Indexing (offline)
```
Source Document
  → RecursiveCharacterTextSplitter (CHUNK_SIZE=1000, CHUNK_OVERLAP=150)
    → Chunk metadata stamped (doc_id, source, language)
      → Embedding generated (provider from EMBEDDINGS_SERVICE_USE)
        → Stored in document_embeddings table:
            page_content, embedding_{provider}, provider, meta_data, doc_id, chunk_index
```

### Retrieval (per user message)
```
User Query
  → Query Rewriting (resolve pronouns via chat_history)
    → Query Expansion (3 variants via LLM)
      → For each active provider in DB (openai/gemini/local — may be multiple):
          → For each expanded query variant:
              → Generate embedding using THAT provider
                → Hybrid Search in THAT provider's column (vector + FTS → RRF)
                  → MMR Diversification (λ=0.4 hybrid / 0.5 pure)
                    → Merge all variant results (weighted 1.0 / 0.7)
                      → Merge all provider results
                        → LLM Re-ranking (score 0–5 per chunk)
                          → Top-K chunks → context_text
                            → LLM Generation (with system prompt)
```

---

## 9. Key Files

| File | Purpose |
|------|---------|
| `backend/app/services/processing_service.py` | Document chunking with overlap |
| `backend/app/services/vector_service.py` | All retrieval logic: hybrid search, MMR, re-ranking, query expansion |
| `backend/app/services/query_processor_service.py` | Query rewriting with history |
| `backend/app/services/embedding_service.py` | Embedding generation (per provider) |
| `backend/app/models/document_embedding.py` | pgvector table model |
| `backend/app/config.py` | CHUNK_SIZE, CHUNK_OVERLAP, RETRIEVAL_SCORE_THRESHOLD |
| `backend/prompts.yml` | All prompts: query_rewrite, query_expansion, rerank, etc. |
| `backend/app/api/conversations.py` | JSON + streaming message endpoints (builds chat_history) |

---

## 10. Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDINGS_SERVICE_USE` | `openai` | Embedding provider for **new** chunks (`openai`, `gemini`, `local`). Query time ignores this and searches all providers that have data in DB. |
| `CHUNK_SIZE` | `1000` | Max characters per chunk |
| `CHUNK_OVERLAP` | `150` | Overlap characters between consecutive chunks |
| `RETRIEVAL_SCORE_THRESHOLD` | `0.4` | Min similarity score (reserved, currently not enforced in filter) |
| `DEFAULT_TOP_K` | `10` | Default chunks to retrieve |
