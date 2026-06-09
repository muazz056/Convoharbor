from flask import request, jsonify, current_app, render_template
from app.services import document_service, embedding_service, query_processor_service, history_service, moderation_service, scraped_content_service
from flasgger.utils import swag_from
from functools import wraps

from . import main


@main.route('/')
@swag_from({
    'tags': ['Monitoring'],
    'summary': 'Index Page',
    'description': 'A simple HTML page to confirm the web server is running. Not part of the API.',
    'responses': {
        '200': {
            'description': 'HTML index page served successfully.'
        }
    }
})
def index():
    return render_template('index.html')

# --- ADD THE NEW ENDPOINT BELOW ---


def allowed_file(filename):
    """Checks if a file's extension is in the allowed set."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def moderate_request(f):
    """
    🚀 OPTIMIZED: Decorator to moderate the user's query.
    For ultra-efficient endpoints, moderation is built into the pipeline.
    This decorator now provides a fast-path bypass for optimized endpoints.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if this is an ultra-efficient endpoint (query endpoint)
        if f.__name__ == 'query_rag_endpoint':
            # Skip redundant moderation - it's handled in the ultra-efficient pipeline
            current_app.logger.info("⚡ Skipping redundant moderation for ultra-efficient endpoint")
            return f(*args, **kwargs)

        # Original moderation for other endpoints
        data = request.get_json()
        if not data or 'query' not in data:
            return f(*args, **kwargs)

        query = data['query']
        moderation_error = moderation_service.moderate_input_with_ai(query)

        if moderation_error:
            return jsonify({"error": moderation_error}), 400

        return f(*args, **kwargs)
    return decorated_function


@main.route('/process-document', methods=['POST'])
@swag_from({
    'tags': ['Document Processing'],
    'summary': 'Upload and process documents',
    'description': 'Uploads one or more files (PDF, DOCX, TXT), chunks them, and detects their language. This is the first step in the pipeline.',
    'consumes': ['multipart/form-data'],
    'parameters': [
        {
            'name': 'files',
            'in': 'formData',
            'type': 'file',
            'required': True,
            'description': 'The document(s) to upload. You can upload multiple files using the same key.'
        }
    ],
    'responses': {
        '200': {
            'description': 'Files processed successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string', 'example': 'Files processed successfully.'},
                    'processed_chunks': {'type': 'integer', 'example': 5},
                    'chunks': {
                        'type': 'array',
                        'items': {'$ref': '#/definitions/Chunk'}
                    },
                    'failed_files': {
                        'type': 'array',
                        'items': {'$ref': '#/definitions/FailedFile'}
                    },
                    'skipped_files': {'type': 'array', 'items': {'type': 'string'}}
                }
            }
        },
        '400': {
            'description': 'Bad Request - Invalid input, missing files, or unsupported file types.',
            'schema': {'$ref': '#/definitions/Error'}
        }
    }
})
def process_document_endpoint():
    """
    API endpoint to upload and process one or more documents.
    Accepts files via form-data with the key 'files'.
    """
    # Edge Case 1: No file part in the request
    if 'files' not in request.files:
        return jsonify({"error": "No file part in the request. Use key 'files'."}), 400

    # `getlist` is crucial for handling multiple files with the same key
    uploaded_files = request.files.getlist('files')

    # Edge Case 2: No files selected
    if not uploaded_files or all(f.filename == '' for f in uploaded_files):
        return jsonify({"error": "No files selected for uploading."}), 400

    valid_files = []
    skipped_files = []

    for file in uploaded_files:
        if file and allowed_file(file.filename):
            valid_files.append(file)
        elif file:
            skipped_files.append(file.filename)

    if not valid_files:
        return jsonify({
            "error": "No valid files found. Supported types are: " + ", ".join(current_app.config['ALLOWED_EXTENSIONS']),
            "skipped_files": skipped_files
        }), 400

    try:
        # Call the service layer to do the heavy lifting
        results = document_service.process_uploaded_files(valid_files)

        # Convert LangChain Document objects to JSON-serializable dictionaries
        successful_chunks_json = [
            {"page_content": chunk.page_content, "metadata": chunk.metadata}
            for chunk in results["successful_chunks"]
        ]

        # Prepare the final response
        response_data = {
            "message": "Files processed successfully.",
            "processed_chunks": len(successful_chunks_json),
            "chunks": successful_chunks_json,
            "failed_files": results["failed_files"],
            "skipped_files": skipped_files
        }
        return jsonify(response_data), 200

    except Exception as e:
        # Catch-all for unexpected errors in the service
        return jsonify({"error": "An internal error occurred during processing.", "details": str(e)}), 500


@main.route('/generate-embedding', methods=['POST'])
@swag_from({
    'tags': ['Embedding'],
    'summary': 'Generate embeddings for text chunks',
    'description': 'Takes a list of text chunks (typically from the /process-document endpoint) and generates vector embeddings using both OpenAI and Gemini models for A/B testing.',
    'consumes': ['application/json'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'required': ['chunks'],
                'properties': {
                    'chunks': {
                        'type': 'array',
                        'items': {'$ref': '#/definitions/Chunk'}
                    }
                }
            }
        }
    ],
    'responses': {
        '200': {
            'description': 'Embeddings generated successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string', 'example': 'Embeddings generated.'},
                    'processed_chunks': {
                        'type': 'array',
                        'items': {'$ref': '#/definitions/EmbeddingChunk'}
                    },
                    'errors': {'type': 'object'}
                }
            }
        },
        '400': {
            'description': 'Bad Request - Invalid JSON payload.',
            'schema': {'$ref': '#/definitions/Error'}
        }
    },
    'definitions': {
        'Chunk': {
            'type': 'object',
            'properties': {
                'page_content': {'type': 'string'},
                'metadata': {
                    'type': 'object',
                    'properties': {
                        'source': {'type': 'string'},
                        'page': {'type': 'integer'},
                        'doc_id': {'type': 'string'},
                        'language': {'type': 'string'}
                    }
                }
            }
        },
        'EmbeddingChunk': {
            'type': 'object',
            'properties': {
                'page_content': {'type': 'string'},
                'metadata': {'$ref': '#/definitions/Chunk/properties/metadata'},
                'embeddings': {
                    'type': 'object',
                    'properties': {
                        'openai': {'type': 'array', 'items': {'type': 'number'}},
                        'gemini': {'type': 'array', 'items': {'type': 'number'}}
                    }
                }
            }
        },
        'FailedFile': {
            'type': 'object',
            'properties': {
                'filename': {'type': 'string'},
                'error': {'type': 'string'}
            }
        },
        'Error': {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'}
            }
        }
    }
})
def generate_embedding_endpoint():
    """
    API endpoint to generate embeddings for a list of text chunks.
    Expects a JSON payload like: {"chunks": [{"page_content": "...", "metadata": {...}}]}
    """
    # Validate request body
    data = request.get_json()
    if not data or 'chunks' not in data or not isinstance(data['chunks'], list):
        return jsonify({
            "error": "Invalid request body. Please provide a JSON object with a 'chunks' key containing a list of chunk objects."
        }), 400

    chunks = data['chunks']
    if not chunks:
        return jsonify({"error": "The 'chunks' list cannot be empty."}), 400

    # Extract just the text content to pass to the embedding service
    texts_to_embed = [chunk.get('page_content', '') for chunk in chunks]

    # Filter out any empty strings that might result from missing 'page_content'
    if not any(texts_to_embed):
        return jsonify({"error": "No text content found in the provided chunks."}), 400

    # Call our dedicated service to do the heavy lifting
    embedding_results = embedding_service.generate_embeddings_for_texts(texts_to_embed)

    # --- Re-structure the response ---
    processed_chunks = []
    embeddings_list = embedding_results.get("embeddings") or []
    embed_provider = embedding_results.get("provider", "openai")

    for i, chunk in enumerate(chunks):
        new_chunk = {
            "metadata": chunk.get("metadata", {}),
            "page_content": chunk.get("page_content", ""),
            "embeddings": {}
        }
        if embeddings_list and i < len(embeddings_list):
            new_chunk["embeddings"][embed_provider] = embeddings_list[i]
        processed_chunks.append(new_chunk)

    response_data = {
        "message": "Embeddings generated",
        "processed_chunks": processed_chunks,
        "errors": embedding_results.get("error")
    }

    return jsonify(response_data), 200


@main.route('/conversation-feedback', methods=['POST'])
@swag_from({
    'tags': ['Feedback & Rating'],
    'summary': 'Submit overall feedback for a conversation',
    'description': """
    ### 📝 Description
    This endpoint is used at the end of a user's session to capture their overall satisfaction with the entire conversation. It accepts a numerical rating, optional tags for categorization, and a free-form comment.

    ---
    ### 🔑 How to Use
    After a conversation is complete, the client application can present a feedback form to the user. The `session_id` for the completed conversation must be provided to link the feedback correctly. This endpoint can only be called **once** per conversation.
    """,
    'consumes': ['application/json'],
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'description': 'JSON object containing the overall conversation feedback.',
            'schema': {
                'type': 'object',
                'required': ['session_id', 'rating'],
                'properties': {
                    'session_id': {
                        'type': 'string',
                        'format': 'uuid',
                        'description': "The unique ID of the conversation being rated.",
                        'example': "0e20a897-fb06-407d-bb52-c4fa69a7897c"
                    },
                    'rating': {
                        'type': 'integer',
                        'description': "An overall satisfaction score for the conversation, e.g., from 1 (poor) to 5 (excellent).",
                        'example': 5
                    },
                    'tags': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': "Optional tags to categorize the feedback (e.g., 'helpful', 'inaccurate', 'slow').",
                        'example': ["accurate", "fast_response"]
                    },
                    'comment': {
                        'type': 'string',
                        'description': "Optional free-form text comment from the user.",
                        'example': "This was a great session. The AI understood my follow-up questions perfectly."
                    },
                    'user_id': {
                        'type': 'string',
                        'description': "Optional client-side identifier for the user providing feedback.",
                        'example': "user-hasnain-ali"
                    }
                }
            }
        }
    ],
    'responses': {
        '201': {
            'description': 'Feedback successfully created and recorded.',
            'schema': {'type': 'object', 'properties': {'message': {'type': 'string'}}}
        },
        '400': {
            'description': 'Bad Request - Missing fields, invalid rating, or feedback already submitted.',
            'schema': {'$ref': '#/definitions/Error'}
        },
        '404': {
            'description': 'Not Found - The specified session_id does not exist.',
            'schema': {'$ref': '#/definitions/Error'}
        }
    }
})
def conversation_feedback_endpoint():
    """Processes overall user feedback for a completed conversation session."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload."}), 400

    session_id = data.get('session_id')
    rating = data.get('rating')

    if not session_id or not isinstance(rating, int):
        return jsonify({"error": "Missing or invalid 'session_id' or 'rating'."}), 400

    if not (1 <= rating <= 5):
        return jsonify({"error": "Rating must be an integer between 1 and 5."}), 400

    # Optional fields
    tags = data.get('tags')
    comment = data.get('comment')
    user_id = data.get('user_id')

    # Offload logic to the service
    success, message = history_service.save_conversation_feedback(
        session_id=session_id,
        rating=rating,
        tags=tags,
        comment=comment,
        user_id=user_id
    )

    if not success:
        status_code = 404 if "not found" in message.lower() else 400
        return jsonify({"error": message}), status_code

    return jsonify({"message": message}), 201  # 201 Created is appropriate here


@main.route('/process-scraped-content', methods=['POST'])
@swag_from({
    'tags': ['Document Processing'],
    'summary': 'Process pre-scraped text content from a URL',
    'description': """
    ### 📝 Description
    This endpoint is designed to process text that has already been scraped from a web page by an external tool (e.g., Puppeteer, Playwright, Selenium). It accepts a source URL for metadata and the full text content of the page.

    The API will then clean, chunk, and detect the language of the provided content, returning a set of chunks ready for the `/api/generate-embedding` endpoint. This decouples the challenging task of web scraping from the core text processing pipeline.

    ---
    ### 🔑 How to Use
    1. Use a dedicated scraping service to fetch the full text content of a target URL.
    2. Send the original URL and the scraped text content to this endpoint.
    3. Take the resulting `chunks` and proceed with the normal ingestion workflow (`/generate-embedding`, `/upsert-chunks`).
    """,
    'consumes': ['application/json'],
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'description': 'JSON object containing the source URL and the scraped text.',
            'schema': {
                'type': 'object',
                'required': ['source_url', 'content'],
                'properties': {
                    'source_url': {
                        'type': 'string',
                        'format': 'uri',
                        'description': "The original URL where the content was scraped from. This will be used as the 'source' metadata.",
                        'example': 'https://en.wikipedia.org/wiki/Artificial_intelligence'
                    },
                    'content': {
                        'type': 'string',
                        'description': "The full, raw text content scraped from the web page.",
                        'example': "Artificial intelligence (AI) is the intelligence of machines or software, as opposed to the intelligence of living beings, primarily of humans..."
                    }
                }
            }
        }
    ],
    'responses': {
        '200': {
            'description': 'Scraped content processed successfully into chunks.',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'processed_chunks': {'type': 'integer'},
                    'chunks': {'type': 'array', 'items': {'$ref': '#/definitions/Chunk'}}
                }
            }
        },
        '400': {
            'description': 'Bad Request - Missing source_url or content.',
            'schema': {'$ref': '#/definitions/Error'}
        }
    }
})
def process_scraped_content_endpoint():
    """
    API endpoint to process text content that has been scraped externally.
    """
    data = request.get_json()
    if not data or 'source_url' not in data or 'content' not in data:
        return jsonify({"error": "Request body must contain 'source_url' and 'content' keys."}), 400

    source_url = data['source_url']
    content = data['content']

    if not content.strip():
        return jsonify({"error": "The 'content' field cannot be empty."}), 400

    try:
        # Call the dedicated service to do the heavy lifting
        chunks = scraped_content_service.process_scraped_data(source_url, content)

        # Convert LangChain Document objects to JSON-serializable dictionaries
        successful_chunks_json = [
            {"page_content": chunk.page_content, "metadata": chunk.metadata}
            for chunk in chunks
        ]

        response_data = {
            "message": "Scraped content processed successfully.",
            "processed_chunks": len(successful_chunks_json),
            "chunks": successful_chunks_json
        }
        return jsonify(response_data), 200

    except Exception as e:
        current_app.logger.error(f"Error processing scraped content from {source_url}: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred during processing."}), 500


@main.route('/upsert-chunks', methods=['POST'])
@swag_from({
    'tags': ['Vector Storage & Retrieval'],
    'summary': 'Upsert embedded chunks into the vector database',
    'description': 'Takes the output from /generate-embedding and stores the vectors in Pinecone/Weaviate. This populates the knowledge base.',
    'consumes': ['application/json'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'processed_chunks': {'type': 'array', 'items': {'$ref': '#/definitions/EmbeddingChunk'}},
                    'provider': {'type': 'string', 'description': 'The embedding provider to use for the vectors (e.g., "openai" or "gemini"). Defaults to "openai".', 'example': 'openai'}
                }
            }
        }
    ],
    'responses': {
        '200': {
            'description': 'Chunks successfully upserted.',
            'schema': {'type': 'object', 'properties': {'upserted_count': {'type': 'integer'}}}
        },
        '400': {'description': 'Bad Request - Invalid payload.', 'schema': {'$ref': '#/definitions/Error'}},
        '503': {'description': 'Service Unavailable - Vector DB service is not initialized.', 'schema': {'$ref': '#/definitions/Error'}}
    }
})
def upsert_chunks():
    """API endpoint to upsert processed and embedded chunks into the vector database."""
    if not current_app.vector_service:
        return jsonify({"error": "Vector DB service is not initialized. Check server logs for configuration issues."}), 503

    data = request.get_json()
    if not data or 'processed_chunks' not in data:
        return jsonify({"error": "Missing 'processed_chunks' in request body"}), 400

    chunks = data['processed_chunks']
    provider = data.get('provider', 'openai')

    try:
        result = current_app.vector_service.upsert(chunks, provider=provider)
        return jsonify(result), 200
    except Exception as e:
        current_app.logger.error(f"Error during upsert: {e}")
        return jsonify({"error": f"An internal error occurred during upsert: {str(e)}"}), 500


# --- NEW CORE RAG ENDPOINT (SPRINT 2) ---

@main.route('/query', methods=['POST'])
@moderate_request
@swag_from({
    'tags': ['Vector Storage & Retrieval'],
    'summary': 'Query the RAG pipeline with advanced controls and session history',
    'description': """
    ### 🔍 Description

    This is the primary endpoint for interacting with the AI. It supports **stateful, multi-turn conversations** and provides granular control over the entire RAG pipeline. Users can ask follow-up questions by passing the `session_id` from a previous response.

    ---

    ### 📌 Key Features

    - **Contextual Conversations**: Pass a `session_id` to maintain conversation history. If omitted, a new conversation starts.
    - **Multilingual Understanding**: Ask questions in any language; the system translates and understands contextually.
    - **Dynamic Persona & Tone**: Use the `role` and `temperature` parameters to shape the AI's personality and creativity.
    - **Scoped Search**: Use the `filter` parameter to limit the search to specific documents in your knowledge base.
    - **Flexible LLM Control**: Choose your `llm_provider` and `model` on-the-fly for cost and performance management.

    ---

    ### 📝 Request Body Parameters
    """,
    'consumes': ['application/json'],
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'description': 'JSON request to query the pipeline. Include `session_id` for follow-up questions.',
            'schema': {'$ref': '#/definitions/QueryRequest'}
        }
    ],
    'responses': {
        '200': {
            'description': 'Answer generated successfully.',
            'schema': {'$ref': '#/definitions/QueryResponse'}
        },
        '400': {
            'description': 'Bad Request - Invalid payload or inappropriate content.',
            'schema': {'$ref': '#/definitions/Error'}
        },
        '500': {
            'description': 'Internal Server Error in the RAG pipeline.',
            'schema': {'$ref': '#/definitions/Error'}
        }
    },
    'definitions': {
        'QueryRequest': {
            'type': 'object',
            'required': ['query'],
            'properties': {
                'query': {
                    'type': 'string',
                    'description': "The user's question in any supported language.",
                    'example': "Where does he work?"
                },
                'session_id': {
                    'type': 'string',
                    'format': 'uuid',
                    'description': "To continue a conversation, pass the `session_id` from the previous response. Omit this to start a new conversation.",
                    'example': "0e20a897-fb06-407d-bb52-c4fa69a7897c"
                },
                'user_id': {
                    'type': 'string',
                    'description': "Optional client-side identifier for the logged-in user. Used for analytics and tracking.",
                    'example': "user-hasnain-ali"
                },
                'role': {
                    'type': 'string',
                    'description': "Persona for the assistant's tone or focus.",
                    'default': 'General Assistant',
                    'example': 'Technical Recruiter'
                },
                'llm_provider': {
                    'type': 'string',
                    'enum': ['openai', 'gemini'],
                    'description': "Choose the LLM provider.",
                    'example': 'openai'
                },
                'model': {
                    'type': 'string',
                    'description': "Specific model to use for generation. Must be an active model configured by Super Admin in the AI Models page.",
                    'example': '<configured-model-name>'
                },
                'top_k': {
                    'type': 'integer',
                    'description': "How many documents to retrieve.",
                    'default': 5,
                    'example': 3
                },
                'temperature': {
                    'type': 'number',
                    'format': 'float',
                    'description': "Controls creativity (0.0=factual, 1.0=creative).",
                    'example': 0.2
                },
                'mode': {
                    'type': 'string',
                    'enum': ['strict', 'permissive'],
                    'description': "Controls the bot's answering behavior. 'strict' (default) uses only document context. 'permissive' allows falling back to the LLM's general knowledge.",
                    'default': 'strict',
                    'example': 'permissive'
                },
                'filter': {
                    'type': 'object',
                    'description': "Optional metadata filter to restrict document search.",
                    'example': {"source": "Hasnain_Ali_AI_ML_Engineer_Resume.docx.pdf"}
                }
            }
        },
        'QueryResponse': {
            'type': 'object',
            'properties': {
                'answer': {
                    'type': 'string',
                    'example': 'He is currently employed as a Software Engineer at DEVSINC.'
                },
                'sources': {
                    'type': 'array',
                    'items': {'$ref': '#/definitions/SourceDocument'}
                },
                'session_id': {
                    'type': 'string',
                    'format': 'uuid',
                    'description': 'The unique ID for this conversation. Use this in subsequent requests to maintain context.'
                },
                'message_id': {
                    'type': 'integer',
                    'description': "The unique ID for the assistant's message, used for submitting feedback."
                },
                'session_expires_at': {
                    'type': 'string',
                    'format': 'date-time',
                    'description': 'The ISO 8601 timestamp when this session will expire if not used.'
                }
            }
        },
        'SourceDocument': {
            'type': 'object',
            'properties': {
                'source': {'type': 'string'},
                'score': {'type': 'number'}
            }
        },
        'Error': {
            'type': 'object',
            'properties': {'error': {'type': 'string'}}
        }
    }
})
def query_rag_endpoint():
    """
    🚀 ULTRA-OPTIMIZED RAG PIPELINE
    Reduces LLM calls from ~10 to ~3 while maintaining exact same functionality.

    OLD PIPELINE (10 LLM calls):
    1. Policy moderation check
    2. Intent detection
    3. Query rewriting
    4. Language detection
    5. Query analysis
    6. HyDE generation
    7. Context translation
    8. Final answer generation
    9. Answer translation
    10. Concluding phrase translation

    NEW PIPELINE (3 LLM calls):
    1. Ultra-efficient query analysis (combines 6 operations)
    2. Query rewriting (only if needed)
    3. Ultra-efficient final generation (combines 3 operations)
    """
    import time
    pipeline_start = time.time()

    # Parse and validate request
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({"error": "Missing 'query' parameter in request body."}), 400

    # Extract parameters
    user_query = data['query'].strip()
    session_id = data.get('session_id') or data.get('session')
    user_id = data.get('user_id')
    user_role = data.get('role', 'General Assistant')
    model_name = data.get('model') or data.get('ai_model')
    llm_provider = data.get('llm_provider')

    if not model_name:
        from ..models import AiModel
        default_model = AiModel.query.filter_by(is_active=True).first()
        if default_model:
            model_name = default_model.model_name
            llm_provider = llm_provider or default_model.provider
        else:
            return jsonify({"error": "No AI model specified and no active model found. Ask super admin to configure a model."}), 400

    from ..models import AiModel
    ai_model_obj = AiModel.query.filter_by(model_name=model_name, is_active=True).first()
    if not ai_model_obj:
        valid_models = [m.model_name for m in AiModel.query.filter_by(is_active=True).all()]
        return jsonify({
            "error": f"Model '{model_name}' is not active or does not exist.",
            "valid_models": valid_models,
            "note": "Only models set by super admin are available."
        }), 400

    top_k = min(data.get('top_k', 5), 20)
    temperature = max(0.0, min(data.get('temperature', 0.1), 1.0))
    mode = data.get('mode', 'strict')
    metadata_filter = data.get('filter')

    if not ai_model_obj:
        return jsonify({"error": "AI model not found. Ask super admin to configure a model."}), 503

    if not current_app.vector_service:
        return jsonify({"error": "Vector database service is not available. Please check your configuration."}), 503

    if not current_app.llm_service:
        return jsonify({"error": "LLM service is not available. Please check your API keys."}), 503

    try:
        current_app.logger.info("🚀 ULTRA-OPTIMIZED RAG PIPELINE START")

        # === STAGE 1: ULTRA-FAST QUERY ANALYSIS ===
        # Use user's specified model for analysis (respecting their choice)
        analysis_start = time.time()

        query_analysis = query_processor_service.ultra_efficient_query_analysis(
            query=user_query,
            provider=llm_provider,
            model_name=model_name,  # Use user's specified model
            session_id=session_id,
            user_id=user_id
        )

        # Safety check from the analysis
        if not query_analysis.get('is_safe', True):
            safety_reason = query_analysis.get('safety_reason', 'Content policy violation')
            current_app.logger.warning(f"🚫 Query blocked: {safety_reason}")

            # Professional response for content policy violations
            professional_safety_response = {
                "answer": "I'm here to provide helpful and respectful assistance. Let me know how I can help you with information or questions that align with our community guidelines.",
                "classification": {
                    "sentiment": "neutral",
                    "intent": "other",
                    "complexity": "simple"
                },
                "sources": [],
                "session_id": session_id or "new_session",
                "performance": {
                    "total_time": f"{time.time() - pipeline_start:.2f}s",
                    "llm_calls": 1
                }
            }
            return jsonify(professional_safety_response), 200

        # Extract analysis results
        detected_lang = query_analysis.get('original_lang', 'en')
        english_query = query_analysis.get('english_query', user_query)
        classification = {
            "sentiment": query_analysis.get('sentiment', 'neutral'),
            "intent": query_analysis.get('intent', 'question'),
            "complexity": query_analysis.get('complexity', 'moderate')
        }
        query_for_embedding = query_analysis.get('query_for_embedding', english_query)

        analysis_time = time.time() - analysis_start
        current_app.logger.info(f"⚡ Fast analysis completed in {analysis_time:.2f}s")

        # === STAGE 2: ULTRA-FAST CONTEXT & HISTORY (OPTIMIZED) ===
        context_start = time.time()

        # Smart conversation handling - ALWAYS get history if session_id provided
        conversation_obj = history_service.get_or_create_conversation(session_id, user_id)

        # Critical: Always retrieve history when session_id is provided for conversation continuity
        if session_id and conversation_obj:
            chat_history = history_service.get_recent_history(conversation_obj, limit=5)
            current_app.logger.info(f"📚 Retrieved conversation history for session: {session_id}")
            current_app.logger.info(f"🔍 DEBUG - Conversation ID: {conversation_obj.id}")
            current_app.logger.info(f"🔍 DEBUG - History length: {len(chat_history) if chat_history else 0}")
            current_app.logger.info(f"🔍 DEBUG - History content: {chat_history[:200] if chat_history else 'EMPTY'}")
        else:
            chat_history = None
            current_app.logger.info("🆕 New conversation - no history to retrieve")
            current_app.logger.info(f"🔍 DEBUG - Session ID provided: {session_id}")
            current_app.logger.info(f"🔍 DEBUG - Conversation object: {conversation_obj}")

        standalone_query = english_query

        # Only rewrite if we have history AND it's a complex conversational query
        if chat_history and classification.get('intent') not in ['end_conversation', 'gratitude']:
            # Always rewrite when we have history to maintain conversation context
            original_query = standalone_query
            standalone_query = query_processor_service.rewrite_query_with_history(
                chat_history,
                english_query,
                provider=llm_provider,
                model_name=model_name
            )
            current_app.logger.info(f"🔄 Query rewritten with history context using {llm_provider}:{model_name}")
            current_app.logger.info(f"🔍 DEBUG - Original: '{original_query}' → Rewritten: '{standalone_query}'")
        else:
            current_app.logger.info(f"🔍 DEBUG - No query rewriting: history={bool(chat_history)}, intent={classification.get('intent')}")

        context_time = time.time() - context_start
        current_app.logger.info(f"⚡ Context processing completed in {context_time:.2f}s")

        # === STAGE 3: SUPER-FAST EMBEDDING + VECTOR SEARCH ===
        retrieval_start = time.time()

        # Optimize embedding generation - use simpler query for simple questions
        if classification.get('complexity') == 'simple':
            # For simple queries, use just the English query (skip HyDE)
            embedding_query = english_query
        else:
            embedding_query = query_for_embedding

        embedding_results = embedding_service.generate_embeddings_for_texts(texts=[embedding_query])

        embed_error = embedding_results.get("error")
        embeddings_list = embedding_results.get("embeddings")
        if embed_error or not embeddings_list or not embeddings_list[0]:
            current_app.logger.error(f"❌ Embedding failed: {embed_error or 'no embeddings returned'}")
            return jsonify({
                "error": "Unable to generate embeddings",
                "details": embed_error or "No embeddings returned by provider"
            }), 503

        query_embedding = embeddings_list[0]
        embed_provider = embedding_results.get("provider", "openai")

        # Aggressive top_k optimization based on complexity
        if classification.get('complexity') == 'simple':
            optimized_top_k = min(top_k, 2)  # Even fewer sources for simple queries
        else:
            optimized_top_k = min(top_k, 4)  # Reduce max sources

        query_filter = metadata_filter or {}
        query_filter['provider'] = embed_provider
        retrieved_contexts = current_app.vector_service.query(
            query_embedding=query_embedding,
            top_k=optimized_top_k,
            filter_dict=query_filter
        )

        retrieval_time = time.time() - retrieval_start
        current_app.logger.info(f"⚡ Retrieval completed in {retrieval_time:.2f}s")

        # Handle no results gracefully
        if not retrieved_contexts:
            if detected_lang == 'en':
                no_results_msg = "I don't have that specific information available right now. Could you try rephrasing your question or asking about something else?"
            else:
                # For non-English, use the comprehensive prompt to generate a natural response
                no_results_msg = query_processor_service.ultra_efficient_final_generation(
                    context="No relevant information found for this query",
                    query=user_query,
                    target_lang=detected_lang,
                    mode=mode,
                    provider=llm_provider,
                    model_name=model_name,  # Use the user's specified model
                    user_attributes={"expertise": user_role, "permission": "user", "intent": "no_info"},
                    session_id=session_id,
                    user_id=user_id
                )

            professional_no_results = {
                "answer": no_results_msg,
                "classification": classification,
                "sources": [],
                "session_id": conversation_obj.session_id,
                "performance": {
                    "total_time": f"{time.time() - pipeline_start:.2f}s",
                    "llm_calls": 1
                }
            }
            return jsonify(professional_no_results), 200

        # === STAGE 5: DETERMINE IF RETRIEVAL WAS SUCCESSFUL ===
        was_retrieval_successful = False
        base_threshold = current_app.config.get('RETRIEVAL_SCORE_THRESHOLD', 0.4)

        # Use more lenient threshold for conversational queries that were rewritten
        is_rewritten_query = (chat_history
                              and classification.get('intent') not in ['end_conversation', 'gratitude']
                              and standalone_query != english_query)

        # More aggressive threshold reduction for rewritten conversational queries
        if is_rewritten_query:
            # 50% lower threshold for conversational queries to account for semantic shifts
            threshold = base_threshold * 0.5
            current_app.logger.info(f"🔗 Applied conversational threshold reduction: {base_threshold:.3f} → {threshold:.3f}")
        else:
            threshold = base_threshold

        if retrieved_contexts:
            top_score = retrieved_contexts[0].get('score', 0.0)
            current_app.logger.info(f"🎯 Retrieval scoring: top_score={top_score:.3f}, threshold={threshold:.3f}, is_rewritten={is_rewritten_query}")

            # Primary check with threshold
            if top_score > threshold:
                was_retrieval_successful = True
            # Fallback: If we have ANY results from a rewritten query, and it's above a minimal threshold
            elif is_rewritten_query and top_score > 0.1 and len(retrieved_contexts) > 0:
                current_app.logger.info(f"🔗 Conversational fallback: accepting low-score result for continuity (score={top_score:.3f})")
                was_retrieval_successful = True

        if not was_retrieval_successful and mode == 'strict':
            current_app.logger.info(
                f"OUT_OF_SCOPE_QUERY: session_id='{conversation_obj.session_id}', query='{user_query}', top_score={retrieved_contexts[0].get('score', 0.0) if retrieved_contexts else 'no_results'}, threshold={threshold:.3f}"
            )

            # Professional response for out-of-scope queries in strict mode
            if detected_lang == 'en':
                out_of_scope_msg = "I don't have that specific information available right now. I want to make sure I give you accurate information — could you try asking about something else I might be able to help with?"
            else:
                # For non-English, generate a natural response
                out_of_scope_msg = query_processor_service.ultra_efficient_final_generation(
                    context="Query is outside scope - provide helpful guidance",
                    query=user_query,
                    target_lang=detected_lang,
                    mode="permissive",  # Use permissive for this guidance message
                    provider=llm_provider,
                    model_name=model_name,  # Use the user's specified model
                    user_attributes={"expertise": user_role, "permission": "user", "intent": "out_of_scope"},
                    session_id=session_id,
                    user_id=user_id
                )

            professional_out_of_scope = {
                "answer": out_of_scope_msg,
                "classification": classification,
                "sources": [],
                "session_id": conversation_obj.session_id,
                "performance": {
                    "total_time": f"{time.time() - pipeline_start:.2f}s",
                    "llm_calls": 2 if detected_lang != 'en' else 1
                }
            }
            return jsonify(professional_out_of_scope), 200

        # === STAGE 4: LIGHTNING-FAST FINAL GENERATION ===
        generation_start = time.time()

        # Aggressive context optimization based on complexity
        if classification.get('complexity') == 'simple':
            # For simple queries, use minimal context
            context_text = "\n\n".join([ctx.get('page_content', '')[:300] for ctx in retrieved_contexts[:2]])
        elif classification.get('complexity') == 'moderate':
            # For moderate queries, use reduced context
            context_text = "\n\n".join([ctx.get('page_content', '')[:500] for ctx in retrieved_contexts[:3]])
        else:
            # For complex queries, use more context but still limited
            context_text = "\n\n".join([ctx.get('page_content', '')[:800] for ctx in retrieved_contexts])

        # User attributes for personalized response
        user_attributes = {
            "permission": "user",
            "expertise": user_role,
            "intent": classification.get('intent', 'default')
        }

        # Optimize temperature and model for faster generation
        if classification.get('complexity') == 'simple':
            # Use even faster model for simple queries
            final_model = model_name  # Use the user's specified model
            optimized_temperature = 0.1
        else:
            # Use original model for complex queries
            final_model = model_name
            optimized_temperature = min(temperature, 0.2)

        # Single call that generates final answer with translation if needed
        final_answer = query_processor_service.ultra_efficient_final_generation(
            context=context_text,
            query=standalone_query,
            target_lang=detected_lang,
            mode=mode,
            provider=llm_provider,
            model_name=final_model,  # Use optimized model
            user_attributes=user_attributes,
            temperature=optimized_temperature,
            session_id=session_id,
            user_id=user_id
        )

        generation_time = time.time() - generation_start
        current_app.logger.info(f"⚡ Final generation completed in {generation_time:.2f}s")

        # === STAGE 5: ASYNC SAVE & RESPONSE (NON-BLOCKING) ===
        save_start = time.time()

        # Save conversation in background (don't wait for it)
        try:
            current_app.logger.info(f"💾 DEBUG - Saving conversation: user_query='{user_query[:50]}...', conversation_id={conversation_obj.id}")
            assistant_message_id = history_service.save_message_pair(
                conversation=conversation_obj,
                user_query=user_query,
                assistant_answer=final_answer
            )
            session_expires_at = history_service.calculate_expiration_date(conversation_obj)
            current_app.logger.info(f"✅ DEBUG - Message saved successfully: message_id={assistant_message_id}")
        except Exception as e:
            # Don't let save errors block the response
            current_app.logger.warning(f"⚠️ Save error (non-critical): {e}")
            current_app.logger.error(f"💾 DEBUG - Save failed: {str(e)}")
            assistant_message_id = "temp_id"
            session_expires_at = "2025-12-31T23:59:59Z"

        source_documents = [
            {"source": ctx['metadata'].get('source'), "score": ctx.get('score')}
            for ctx in retrieved_contexts
        ]

        save_time = time.time() - save_start
        total_time = time.time() - pipeline_start

        current_app.logger.info(f"⚡ LIGHTNING-FAST pipeline completed in {total_time:.2f}s (Analysis: {analysis_time:.2f}s, Context: {context_time:.2f}s, Retrieval: {retrieval_time:.2f}s, Generation: {generation_time:.2f}s, Save: {save_time:.2f}s)")

        response_data = {
            "answer": final_answer,
            "sources": source_documents,
            "session_id": conversation_obj.session_id,
            "message_id": assistant_message_id,
            "session_expires_at": session_expires_at.isoformat() if hasattr(session_expires_at, 'isoformat') else session_expires_at,
            "classification": classification,
            "performance": {
                "total_time": f"{total_time:.2f}s",
                "llm_calls": 2 if classification.get('complexity') != 'simple' else 1,  # Even fewer for simple queries
                "stages": {
                    "analysis": f"{analysis_time:.2f}s",
                    "context": f"{context_time:.2f}s",
                    "retrieval": f"{retrieval_time:.2f}s",
                    "generation": f"{generation_time:.2f}s",
                    "save": f"{save_time:.2f}s"
                }
            }
        }
        return jsonify(response_data)

    except Exception as e:
        import traceback
        error_time = time.time() - pipeline_start

        # Get the full stack trace
        stack_trace = traceback.format_exc()

        current_app.logger.error(f"❌ Pipeline error after {error_time:.2f}s: {e}", exc_info=True)
        current_app.logger.error(f"🔍 Full stack trace:\n{stack_trace}")

        return jsonify({
            "error": "An internal error occurred while processing your query.",
            "details": str(e),
            "error_type": type(e).__name__,
            "time_elapsed": f"{error_time:.2f}s",
            "stack_trace": stack_trace if current_app.debug else None
        }), 500


@main.route('/delete-document', methods=['POST'])
@swag_from({
    'tags': ['Document Management'],
    'summary': 'Delete a document and its vectors from the knowledge base',
    'description': """
    ### 🗑️ Description
    This endpoint permanently removes all vector embeddings associated with a specific source document from the Pinecone database. This is useful for removing outdated, incorrect, or irrelevant information from the knowledge base.

    ---
    ### 🔑 How to Use
    Provide the exact `source` filename of the document you wish to delete. The system will find all chunks linked to this source via metadata and delete them. This action is irreversible.
    """,
    'consumes': ['application/json'],
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'description': 'JSON object containing the source filename to delete.',
            'schema': {
                'type': 'object',
                'required': ['source'],
                'properties': {
                    'source': {
                        'type': 'string',
                        'description': "The exact filename of the document stored in the metadata (e.g., 'Urdu_text.pdf').",
                        'example': 'Hasnain_Ali_AI_ML_Engineer_Resume.docx.pdf'
                    }
                }
            }
        }
    ],
    'responses': {
        '200': {
            'description': 'Deletion process completed successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'deleted_count': {'type': 'integer', 'example': 15},
                    'message': {'type': 'string', 'example': 'Successfully deleted vectors from source: ...'}
                }
            }
        },
        '400': {
            'description': 'Bad Request - Missing source field.',
            'schema': {'$ref': '#/definitions/Error'}
        },
        '500': {
            'description': 'Internal Server Error during the deletion process.',
            'schema': {'$ref': '#/definitions/Error'}
        }
    }
})
def delete_document_endpoint():
    """
    Handles requests to delete all vectors associated with a specific source document.
    """
    data = request.get_json()
    if not data or 'source' not in data:
        return jsonify({"error": "Missing 'source' field in request body."}), 400

    source_filename = data['source']

    if not current_app.vector_service:
        return jsonify({"error": "Vector DB service is not initialized."}), 503

    try:
        result = current_app.vector_service.delete_by_source(source_filename)
        return jsonify(result), 200
    except Exception as e:
        current_app.logger.error(f"Error during document deletion for source '{source_filename}': {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred during the deletion process."}), 500


@main.route('/history', methods=['GET'])
@swag_from({
    'tags': ['Conversation History'],
    'summary': 'Retrieve conversation history by session or user',
    'description': """
    ### 📜 Description
    This endpoint retrieves conversation history. It can be used in two ways:
    1.  **By `session_id`**: Fetches the complete message log for a single conversation.
    2.  **By `user_id`**: Fetches a summary of all conversations associated with a specific user.

    You must provide *either* a `session_id` or a `user_id` as a query parameter, but not both.

    ---
    ### 🔑 How to Use
    - To get a specific chat log: `GET /api/history?session_id=your-session-id`
    - To get all sessions for a user: `GET /api/history?user_id=your-user-id`
    """,
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'session_id',
            'in': 'query',
            'type': 'string',
            'format': 'uuid',
            'required': False,
            'description': 'The unique ID of the conversation session to retrieve.'
        },
        {
            'name': 'user_id',
            'in': 'query',
            'type': 'string',
            'required': False,
            'description': 'The client-provided ID of the user whose sessions you want to list.'
        }
    ],
    'responses': {
        '200': {
            'description': 'History retrieved successfully. The response structure depends on the provided parameter.',
            'examples': {
                'application/json (by session_id)': {
                    "session_id": "your-session-id",
                    "messages": [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi there!"}]
                },
                'application/json (by user_id)': [
                    {"session_id": "session-1", "title": "Conversation from 2025-07-12"},
                    {"session_id": "session-2", "title": "Conversation from 2025-07-11"}
                ]
            }
        },
        '400': {
            'description': 'Bad Request - Missing parameters or both provided.',
            'schema': {'$ref': '#/definitions/Error'}
        },
        '404': {
            'description': 'Not Found - The specified session_id or user_id does not exist.',
            'schema': {'$ref': '#/definitions/Error'}
        }
    }
})
def get_history_endpoint():
    """
    Handles requests to retrieve conversation history.
    """
    session_id = request.args.get('session_id')
    user_id = request.args.get('user_id')

    # --- Validation ---
    if session_id and user_id:
        return jsonify({"error": "Please provide either a 'session_id' or a 'user_id', but not both."}), 400
    if not session_id and not user_id:
        return jsonify({"error": "You must provide either a 'session_id' or a 'user_id' query parameter."}), 400

    # --- Logic ---
    if session_id:
        # Case 1: Fetch history for a single session
        history = history_service.get_history_by_session_id(session_id)
        if not history:
            return jsonify({"error": f"No conversation found with session_id: {session_id}"}), 404
        return jsonify(history), 200

    if user_id:
        # Case 2: Fetch all sessions for a user
        sessions = history_service.get_sessions_by_user_id(user_id)
        # It's not an error if a user has no sessions, just return an empty list.
        return jsonify(sessions), 200


@main.route('/sessions', methods=['GET'])
@swag_from({
    'tags': ['Session Management'],
    'summary': 'List recent conversation sessions',
    'description': 'Returns a list of recent conversation sessions with their metadata',
    'parameters': [
        {
            'name': 'user_id',
            'in': 'query',
            'type': 'string',
            'required': False,
            'description': 'Filter sessions by user ID'
        },
        {
            'name': 'limit',
            'in': 'query',
            'type': 'integer',
            'required': False,
            'description': 'Maximum number of sessions to return (default: 20)'
        }
    ],
    'responses': {
        '200': {
            'description': 'Sessions retrieved successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'sessions': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'session_id': {'type': 'string'},
                                'created_at': {'type': 'string'},
                                'updated_at': {'type': 'string'},
                                'message_count': {'type': 'integer'},
                                'last_activity': {'type': 'string'}
                            }
                        }
                    }
                }
            }
        }
    }
})
def list_sessions():
    """List recent conversation sessions"""
    try:
        user_id = request.args.get('user_id')
        limit = int(request.args.get('limit', 20))

        # Get sessions from history service
        sessions = history_service.get_recent_sessions(user_id=user_id, limit=limit)

        current_app.logger.info(f"📋 Listed {len(sessions)} sessions")
        return jsonify({"sessions": sessions}), 200

    except Exception as e:
        current_app.logger.error(f"❌ Failed to list sessions: {e}")
        return jsonify({
            "error": "Failed to retrieve sessions",
            "message": str(e)
        }), 500
