# AI Document Chat API

This project provides a robust, scalable backend service for a cross-lingual, retrieval-augmented generation (RAG) chat application. It allows users to upload documents, which are then processed, chunked, and vectorized. The API can answer questions about the documents in multiple languages, even if the source document is written in a different language.

This API is built with Flask and leverages a sophisticated, multi-stage pipeline:
1.  **Ingestion:** Cleans, chunks, and creates vector embeddings from source documents.
2.  **Query Processing:** Employs a `Detect` -> `Translate` -> `HyDE` (Hypothetical Document Embedding) strategy for robust understanding of user queries.
3.  **Retrieval:** Searches a vector database (Pinecone) to find the most relevant information.
4.  **Synthesis:** Uses a powerful LLM (OpenAI or Gemini) to generate a final, source-cited answer in the user's original language.

## Table of Contents

1.  [Core Features](#core-features)
2.  [Getting Started](#getting-started)
    *   [Prerequisites](#prerequisites)
    *   [Installation & Setup](#installation--setup)
    *   [Running the Application](#running-the-application)
3.  [API Endpoints & Usage](#api-endpoints--usage)
    *   [Workflow Overview](#workflow-overview)
    *   [Ingestion Endpoints](#ingestion-endpoints)
    *   [Query Endpoint Reference](#query-endpoint-reference)
4.  [Technology Stack](#technology-stack)
5.  [Project Structure](#project-structure)
6.  [Testing](#testing)

---

## Core Features

-   **Cross-Lingual RAG:** Ask a question in one language (e.g., French) and get an answer from a document written in another (e.g., Urdu).
-   **Advanced Query Processing:** Uses a `Detect` -> `Translate` -> `HyDE` pipeline to understand user intent accurately, overcoming language and phrasing barriers.
-   **Pluggable LLMs:** Easily switch between `openai` and `gemini` providers and specific models via simple API parameters.
-   **Dynamic Persona:** Control the tone, style, and focus of the AI's response using the `role` parameter (e.g., `'Legal Analyst'`, `'Sales Engineer'`).
-   **Creativity Control:** Adjust the `temperature` parameter to get highly factual or more creative answers.
-   **Scoped Search:** Use metadata `filter` to ask questions about specific documents within your knowledge base.
-   **Multi-Format Document Ingestion:** Accepts `.pdf`, `.docx`, and `.txt` files, with robust text cleaning for source data.
-   **Interactive API Documentation**: A built-in Swagger UI to explore and test all API endpoints directly from the browser.

---

## Getting Started

Follow these instructions to get the project running locally for development and testing.

### Prerequisites

-   Python 3.12+
-   A Python virtual environment tool (`venv`)
-   [Postman](https://www.postman.com/downloads/) or another API client for testing.

### Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/HasnainAli47/Flask-Personal-Project
    cd https://github.com/HasnainAli47/Flask-Personal-Project
    ```

2.  **Create and activate a Python virtual environment:**
    ```bash
    # Create the virtual environment
    python3 -m venv venv

    # Activate it (on macOS/Linux)
    source venv/bin/activate
    
    # Or on Windows
    # venv\Scripts\activate
    ```

3.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure your environment variables:**
    -   Make a copy of `.env.example` (if it exists) or create a new file named `.env`.
    -   Fill in the required API keys and Pinecone details.

    **File:** `.env`
    ```env
    # --- Configuration ---
    # Set to 'development' or 'production'
    FLASK_ENV=development
    # You need a secret key for session management and other security features
    SECRET_KEY='a_very_secret_and_long_random_string_here'
    # --- API Keys ---
    # Get these from the respective platforms
    # --- Database ---
    # For development, we'll use a simple SQLite database
    DATABASE_URL="sqlite:///chat_app.db"
    PINECONE_API_KEY=your_pinecone_api_key_here
    PINECONE_ENVIRONMENT="The Region you selected in pinecone"
    PINECONE_INDEX_NAME=ai-chat-project 
    PROMPT_CONFIG_PATH=./prompts.yml
    DATABASE_URL="You neon db (postgres) url"
    ```

### Running the Application


 **Run the server:**
    ```bash
    python run.py
    ```
The API will be available at `http://127.0.0.1:5000`.

---

## API Endpoints & Usage

The API is fully documented with Swagger/OpenAPI. Once the server is running, you can explore and test all endpoints interactively at:

**[http://127.0.0.1:5000/docs/](http://127.0.0.1:5000/docs/)**

### Workflow Overview

A typical workflow involves two phases: **Ingestion** (populating the knowledge base) and **Querying** (asking questions).

### Ingestion Endpoints

First, add documents to your knowledge base by calling these endpoints in order.

1.  **`POST /api/process-document`**: Upload a file (`.pdf`, `.docx`, `.txt`). The API cleans the text and splits it into chunks.
2.  **`POST /api/generate-embedding`**: Take the `chunks` from the previous step and send them here to create vector embeddings.
3.  **`POST /api/upsert-chunks`**: Push the `processed_chunks` from the embedding step into your Pinecone vector database.

### Query Endpoint Reference

#### `POST /api/query`

This is the main endpoint for asking questions. It accepts a flexible JSON payload to control the entire RAG process.

**Request Body Parameters:**

| Parameter      | Type    | Required | Default                               | Description                                                                                                                                                                                                                                         |
| :------------- | :------ | :------- | :------------------------------------ | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `query`        | string  | **Yes**  | N/A                                   | The user's question. This can be in any language supported by the translation model (e.g., English, French, Urdu, Hindi).                                                                                                                                     |
| `role`         | string  | No       | `'General Assistant'`                 | Defines the AI's persona, which influences the tone, style, and focus of the final answer. Examples: `'Legal Analyst'`, `'Sales Engineer'`.                                                                                                           |
| `llm_provider` | string  | No       | `'openai'`                            | Selects the LLM provider for the final answer synthesis. **Accepted values:** `'openai'`, `'gemini'`.                                                                                                                                                 |
| `model`        | string  | No       | `'gpt-4o-mini'` or `'gemini-1.5-flash'` | The specific model name for the final answer generation. Use this to access more powerful models on demand. Example: `'gemini-1.5-pro-latest'`.                                                                                                       |
| `top_k`        | integer | No       | `5`                                   | The number of document chunks to retrieve from the vector database. A higher 'k' provides more context but can increase latency and noise.                                                                                                         |
| `temperature`  | float   | No       | `0.1` (service default)               | Controls the creativity of the final answer. **Range: 0.0 to 1.0**. Low values (~0.1-0.3) are factual and deterministic. High values (>0.7) are more creative.                                                                                          |
| `filter`       | object  | No       | `null`                                | A metadata filter to scope the search to specific documents. The syntax follows your vector DB's rules. Example: `{"source": "report_q1.pdf"}`                                                                                                          |

**Example Request:**
```json
{
  "query": "Qu’est-ce que l’auto-responsabilité ?",
  "role": "Legal Analyst",
  "llm_provider": "gemini",
  "model": "gemini-1.5-pro-latest",
  "top_k": 3,
  "filter": {
    "source": "ai_concepts_multilingual.txt"
  }
}
```

# Technology Stack
Backend Framework: Flask
Vector Database: Pinecone
LLM Orchestration: LangChain (for document loading and splitting)
LLM Providers: OpenAI, Google Gemini
API Documentation: Flasgger (Swagger/OpenAPI)
Testing: Pytest, Pytest-Mock
Server: Gunicorn

# Project Structure
```
chat_project/
├── app/                  # Main application package
│   ├── __init__.py         # Application factory
│   ├── config.py           # Configuration settings
│   ├── main/               # Main blueprint for core features
│   │   └── routes.py       # API routes and Swagger documentation
│   └── services/           # Business logic modules
│       ├── document_service.py
│       ├── embedding_service.py
│       ├── language_service.py
│       ├── llm_service.py
│       ├── query_processor_service.py
│       └── vector_service.py
├── tests/                # Pytest unit and integration tests
│   ├── test_services.py
│   └── test_rag_pipeline.py
├── uploads/              # Temporary storage for uploaded files
├── .env                  # Environment variables (!!! DO NOT COMMIT !!!)
├── requirements.txt      # Python dependencies
├── run.py                # Application entry point
└── run_gunicorn_dev.sh   # Development server script
```

# Testing
The project includes a comprehensive test suite using pytest.
Unit Tests (tests/test_services.py): These tests isolate and verify the logic of individual services in the app/services/ directory. They use mocking to test functions without making external API calls.
Integration Tests (tests/test_rag_pipeline.py): This suite tests the end-to-end /api/query RAG pipeline, ensuring all internal services work together correctly. It mocks the external boundaries (LLM and Vector DB calls) to validate the flow of data and logic.
To run the full test suite from the project root directory:
```bash
pytest
```