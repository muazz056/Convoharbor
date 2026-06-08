# app/api/datasources.py

import os
import uuid
from urllib.parse import urlparse
from datetime import datetime, timedelta
from flask import request, current_app, jsonify, g
from . import api
from ..decorators import login_required
from ..models import Chatbot, DataSource, AiModel
from ..models.ai_model import SUPPORTED_PROVIDERS
from .. import db
from flasgger.utils import swag_from
from werkzeug.utils import secure_filename


def _get_provider_api_type(provider_id):
    for p in SUPPORTED_PROVIDERS:
        if p['id'] == provider_id:
            return p['api_type']
    return 'openai'


def resolve_chatbot_api_keys(chatbot_id):
    if not chatbot_id:
        return None
    chatbot = Chatbot.query.get(chatbot_id)
    if not chatbot or not chatbot.config:
        return None
    ai_model_id = chatbot.config.get('ai_model_id')
    if not ai_model_id:
        return None
    ai_model = AiModel.query.get(ai_model_id)
    if not ai_model or not ai_model.is_active:
        return None
    api_key = ai_model.get_api_key()
    if not api_key:
        return None
    api_type = _get_provider_api_type(ai_model.provider)
    return {api_type: api_key}


@api.route('/datasources/upload', methods=['POST'])
@login_required
@swag_from({
    'tags': ['Data Sources'],
    'summary': 'Upload files for processing',
    'description': """
    Upload files that will be processed by the AI service and associated with a specific chatbot for training.
    Files are stored temporarily in Cloudinary, processed for embeddings, then deleted.
    """,
    'consumes': ['multipart/form-data'],
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'required': ['chatbot_id'],
                'properties': {
                    'chatbot_id': {
                        'type': 'integer',
                        'description': 'Required ID of chatbot to associate files with',
                        'example': 1
                    },
                    'description': {
                        'type': 'string',
                        'description': 'Optional description of the upload batch'
                    }
                }
            }
        }
    ],
    'responses': {
        '200': {'description': 'Files uploaded and processing started'},
        '400': {'description': 'Bad Request'},
        '401': {'description': 'Unauthorized'}
    }
})
def upload_files():
    """Upload files for AI processing"""
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400

    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'No files provided'}), 400

    chatbot_id = request.form.get('chatbot_id')
    if not chatbot_id:
        return jsonify({'error': 'chatbot_id is required'}), 400

    chatbot = Chatbot.query.filter_by(
        id=chatbot_id,
        tenant_id=g.tenant_id
    ).first()

    if not chatbot:
        return jsonify({'error': 'Chatbot not found'}), 400

    try:
        upload_batch_id = str(uuid.uuid4())
        data_sources = []

        for file in files:
            filename = secure_filename(file.filename)
            file_ext = os.path.splitext(filename)[1].lower().lstrip('.')
            if file_ext not in current_app.config['ALLOWED_EXTENSIONS']:
                return jsonify({
                    'error': f'File type "{file_ext}" is not allowed. Allowed types: {list(current_app.config["ALLOWED_EXTENSIONS"])}'
                }), 400

            data_source = DataSource(
                tenant_id=g.tenant_id,
                chatbot_id=chatbot_id,
                source_type='upload',
                source_name=filename,
                status='uploading',
                meta_data={
                    'file_id': str(uuid.uuid4()),
                    'upload_batch_id': upload_batch_id,
                    'description': request.form.get('description', '')
                }
            )
            db.session.add(data_source)
            db.session.flush()
            data_sources.append(data_source)

        # Format response data BEFORE committing to avoid expired attribute errors
        response_data_sources = [_format_data_source_response(ds) for ds in data_sources]

        db.session.commit()

        from threading import Thread
        import tempfile

        # Save uploaded files to temp directory before the thread loses access
        # (request.files is only available during the request lifecycle)
        _app = current_app._get_current_object()
        saved_files = []

        for file in files:
            if file.filename:
                safe_name = secure_filename(file.filename)
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f'_{safe_name}')
                file.save(tmp.name)
                saved_files.append({'path': tmp.name, 'filename': safe_name, 'original': file.filename})
                tmp.close()

        def process_files():
            """Background processing: re-query sources, process each file."""
            import os
            # Use a NEW session bound to this thread's context
            with _app.app_context():
                try:
                    from ..services.document_service import process_uploaded_files
                except Exception:
                    from ..services import document_service as _ds
                    process_uploaded_files = _ds.process_uploaded_files

                for sf in saved_files:
                    matching_ds = None
                    try:
                        # Find the DataSource that was created for THIS file
                        # in THIS upload batch. We match on source_name and
                        # then disambiguate by upload_batch_id in Python
                        # (the JSON column is generic JSON, not JSONB, so
                        # `.astext` is not portable across dialects).
                        candidates = DataSource.query.filter_by(
                            source_name=sf['filename'],
                        ).all()
                        matching_ds = next(
                            (
                                ds for ds in candidates
                                if ds.meta_data
                                and ds.meta_data.get('upload_batch_id') == upload_batch_id
                            ),
                            None,
                        )

                        if not matching_ds:
                            _app.logger.error(
                                f"❌ Upload: no DataSource row found for "
                                f"filename={sf['filename']!r} "
                                f"upload_batch_id={upload_batch_id}"
                            )
                            continue

                        matching_ds.status = 'processing'
                        matching_ds.meta_data = {
                            **(matching_ds.meta_data or {}),
                            'processing_started_at': datetime.utcnow().isoformat(),
                        }
                        db.session.commit()

                        api_keys = resolve_chatbot_api_keys(matching_ds.chatbot_id)

                        with open(sf['path'], 'rb') as fh:
                            from werkzeug.datastructures import FileStorage
                            from io import BytesIO
                            file_storage = FileStorage(
                                stream=BytesIO(fh.read()),
                                filename=sf['original'],
                                content_type=None
                            )
                            result = process_uploaded_files([file_storage], api_keys=api_keys)

                        # Generate embeddings and store in vector database
                        chunks = result.get('successful_chunks', [])
                        if chunks and current_app.vector_service:
                            try:
                                from ..services import embedding_service
                                chunk_texts = [c.page_content for c in chunks]
                                embedding_results = embedding_service.generate_embeddings_for_texts(chunk_texts)
                                embeddings_list = embedding_results.get("embeddings") or []
                                embed_provider = embedding_results.get("provider", "openai")

                                processed_chunks = []
                                for i, chunk in enumerate(chunks):
                                    chunk_meta = dict(chunk.metadata) if chunk.metadata else {}
                                    chunk_meta['chatbot_id'] = int(matching_ds.chatbot_id)
                                    chunk_meta['tenant_id'] = int(matching_ds.tenant_id)
                                    pc = {
                                        "metadata": chunk_meta,
                                        "page_content": chunk.page_content,
                                        "embeddings": {}
                                    }
                                    if embeddings_list and i < len(embeddings_list):
                                        pc["embeddings"][embed_provider] = embeddings_list[i]
                                    processed_chunks.append(pc)

                                if processed_chunks:
                                    current_app.vector_service.upsert(processed_chunks, provider=embed_provider)
                                    _app.logger.info(f"✅ Stored {len(processed_chunks)} chunks in vector DB for {sf['filename']} (chatbot_id={matching_ds.chatbot_id})")
                            except Exception as embed_err:
                                _app.logger.error(f"Embedding/vector error for {sf['filename']}: {embed_err}")
                                # IMPORTANT: do NOT swallow this. Embedding
                                # failure means the data is NOT in the
                                # vector DB, so we must mark the source
                                # as failed rather than completed.
                                raise

                        matching_ds.status = 'completed'
                        ds_doc_id = result.get('doc_ids', {}).get(sf['filename'])
                        matching_ds.meta_data = {
                            **(matching_ds.meta_data or {}),
                            'processed_chunks': len(result.get('successful_chunks', [])),
                            'doc_id': ds_doc_id,
                            'completed_at': datetime.utcnow().isoformat()
                        }
                        db.session.commit()

                    except Exception as e:
                        _app.logger.error(
                            f"❌ File processing error for {sf['filename']!r}: {e}",
                            exc_info=True,
                        )
                        # ALWAYS set status to 'failed' on any error so the
                        # UI does not get stuck in 'uploading' / 'processing'
                        # forever. If the DataSource row was deleted by the
                        # user mid-upload we still try, and silently skip if
                        # it is gone.
                        try:
                            if matching_ds is None:
                                candidates = DataSource.query.filter_by(
                                    source_name=sf['filename'],
                                ).all()
                                matching_ds = next(
                                    (
                                        ds for ds in candidates
                                        if ds.meta_data
                                        and ds.meta_data.get('upload_batch_id') == upload_batch_id
                                    ),
                                    None,
                                )
                            if matching_ds is not None:
                                matching_ds.status = 'failed'
                                matching_ds.meta_data = {
                                    **(matching_ds.meta_data or {}),
                                    'error': str(e),
                                    'failed_at': datetime.utcnow().isoformat(),
                                }
                                db.session.commit()
                                _app.logger.info(
                                    f"📛 Marked data source {matching_ds.id} "
                                    f"({sf['filename']!r}) as 'failed'"
                                )
                        except Exception as mark_err:
                            _app.logger.error(
                                f"Could not mark data source as failed: {mark_err}",
                                exc_info=True,
                            )
                    finally:
                        # Clean up temp file
                        try:
                            os.unlink(sf['path'])
                        except Exception:
                            pass

        thread = Thread(target=process_files)
        thread.daemon = True
        thread.start()

        return jsonify({
            'message': 'Files uploaded and processing started',
            'upload_batch_id': upload_batch_id,
            'data_sources': response_data_sources
        }), 202

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error uploading files: {e}")
        return jsonify({'error': 'Upload failed'}), 500


@api.route('/datasources/upload/callback', methods=['POST', 'OPTIONS'])
@login_required
def upload_callback():
    """Process uploaded files after upload completion"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = request.get_json()

    if not data or 'upload_batch_id' not in data:
        return jsonify({'error': 'Invalid request'}), 400

    upload_batch_id = data['upload_batch_id']

    data_sources = DataSource.query.filter(
        DataSource.tenant_id == g.tenant_id,
        DataSource.status == 'pending'
    ).all()
    data_sources = [ds for ds in data_sources if ds.meta_data and ds.meta_data.get('upload_batch_id') == upload_batch_id]

    if not data_sources:
        return jsonify({'error': 'Upload batch not found'}), 404

    try:
        processing_jobs = []

        for data_source in data_sources:
            data_source.status = 'processing'
            db.session.commit()

            try:
                from ..services import embedding_service
                from ..services import text_cleaner_service, processing_service
                from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
                import re

                job_id = f"job-{uuid.uuid4()}"
                safe_name = re.sub(r'[^\w\-_\.]', '_', data_source.source_name)
                temp_filepath = os.path.join(
                    current_app.config['UPLOAD_FOLDER'],
                    f"{job_id}_{safe_name}"
                )

                LOADER_MAPPING = {'.pdf': PyPDFLoader, '.txt': TextLoader, '.docx': Docx2txtLoader}
                file_ext = os.path.splitext(temp_filepath)[1].lower()

                if not os.path.exists(temp_filepath):
                    raise FileNotFoundError(f"File not found locally: {temp_filepath}")

                loader = LOADER_MAPPING[file_ext](temp_filepath)
                documents = loader.load()

                cleaned_docs = []
                for doc in documents:
                    cleaned_text = text_cleaner_service.clean_extracted_text(doc.page_content)
                    if cleaned_text.strip():
                        doc.page_content = cleaned_text
                        cleaned_docs.append(doc)
                documents = cleaned_docs

                api_keys = resolve_chatbot_api_keys(data_source.chatbot_id)

                doc_id = str(uuid.uuid4())
                chunks = processing_service.process_documents_into_chunks(
                    documents=documents,
                    source_name=data_source.source_name,
                    doc_id=doc_id,
                    api_keys=api_keys
                )

                chunk_texts = [chunk.page_content for chunk in chunks]
                embedding_results = embedding_service.generate_embeddings_for_texts(chunk_texts)

                processed_chunks = []
                embeddings_list = embedding_results.get("embeddings") or []
                embed_provider = embedding_results.get("provider", "openai")
                for i, chunk in enumerate(chunks):
                    chunk_meta = dict(chunk.metadata) if chunk.metadata else {}
                    chunk_meta['chatbot_id'] = int(data_source.chatbot_id)
                    chunk_meta['tenant_id'] = int(data_source.tenant_id)
                    processed_chunk = {
                        "metadata": chunk_meta,
                        "page_content": chunk.page_content,
                        "embeddings": {}
                    }
                    if embeddings_list and i < len(embeddings_list):
                        processed_chunk["embeddings"][embed_provider] = embeddings_list[i]
                    processed_chunks.append(processed_chunk)

                if current_app.vector_service:
                    current_app.vector_service.upsert(processed_chunks, provider=embed_provider)

                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)

                data_source.status = 'completed'
                data_source.meta_data['processed_chunks'] = len(processed_chunks)
                data_source.meta_data['completed_at'] = datetime.utcnow().isoformat()
                data_source.meta_data['doc_id'] = doc_id
                data_source.meta_data['job_id'] = job_id

                processing_jobs.append({
                    'file_id': data_source.meta_data.get('file_id'),
                    'filename': data_source.source_name,
                    'status': 'completed'
                })

            except Exception as e:
                data_source.status = 'failed'
                data_source.meta_data['error'] = str(e)
                processing_jobs.append({
                    'file_id': data_source.meta_data.get('file_id'),
                    'filename': data_source.source_name,
                    'status': 'failed',
                    'error': str(e)
                })

            db.session.commit()

        return jsonify({
            'message': 'Files processed successfully',
            'batch_id': upload_batch_id,
            'processing_jobs': processing_jobs
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing upload callback: {e}")
        return jsonify({'error': 'Processing failed'}), 500


@api.route('/datasources/<int:datasource_id>', methods=['DELETE', 'OPTIONS'])
@login_required
@swag_from({
    'tags': ['Data Sources'],
    'summary': 'Delete a data source',
    'description': 'Permanently delete a data source and its associated content',
    'parameters': [
        {
            'name': 'datasource_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'ID of the data source to delete'
        }
    ],
    'responses': {
        '200': {
            'description': 'Data source deleted successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'deleted_id': {'type': 'integer'}
                }
            }
        },
        '404': {'description': 'Data source not found', 'schema': {'$ref': '#/definitions/Error'}},
        '403': {'description': 'Access denied', 'schema': {'$ref': '#/definitions/Error'}}
    }
})
def delete_datasource(datasource_id):
    """Delete a data source and its content"""
    # Handle OPTIONS preflight request
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    # Manual authentication check for DELETE requests
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Authentication required'}), 401

    token = auth_header.split(' ')[1]
    payload = current_app.auth_service.verify_token(token)
    if not payload:
        return jsonify({'error': 'Invalid token'}), 401

    # Set up g context
    g.user_id = payload['user_id']
    g.user_role = payload['role']

    # Convert tenant UUID to integer ID for database queries
    from ..models import Tenant
    tenant = Tenant.query.filter_by(tenant_id=payload['tenant_id']).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404
    g.tenant_id = tenant.id  # Use integer ID for database queries

    try:
        # Find data source
        datasource = DataSource.query.filter_by(
            id=datasource_id,
            tenant_id=g.tenant_id
        ).first()

        if not datasource:
            return jsonify({'error': 'Data source not found'}), 404

        # TODO: Delete from vector database
        # TODO: Notify AI service to remove content

        # Delete from database
        db.session.delete(datasource)
        db.session.commit()

        current_app.logger.info(f"🗑️ Deleted data source {datasource_id} for tenant {g.tenant_id}")

        return jsonify({
            'message': 'Data source deleted successfully',
            'deleted_id': datasource_id
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Error deleting data source {datasource_id}: {e}")
        return jsonify({
            'error': 'Delete failed',
            'message': 'An error occurred while deleting the data source'
        }), 500


@api.route('/datasources/crawl', methods=['POST'])
@login_required
@swag_from({
    'tags': ['Data Sources'],
    'summary': 'Trigger web crawling for URL',
    'description': """
    ### 🕷️ Description
    **NEW: Powered by Gemini AI!** This endpoint extracts meaningful content from web pages using Google's Gemini AI model.
    Instead of traditional web scraping, Gemini intelligently reads the entire webpage and extracts only the useful content,
    automatically filtering out navigation, ads, and other non-essential elements.

    **How it works:**
    1. Fetches the raw HTML from the provided URL
    2. Sends the HTML to Gemini AI with instructions to extract meaningful content
    3. Gemini returns clean, structured content ready for chatbot training
    4. Content is processed through the AI pipeline (chunking, embeddings, vector storage)

    **Supported content types:**
    - Web articles and blogs
    - Documentation pages
    - Product pages
    - Knowledge base articles
    - Company websites
    - News articles
    - Educational content

    ---
    ### 🤖 AI-Powered Features
    - **Gemini AI content extraction** - Understands page context and extracts relevant information
    - **Smart content filtering** - Automatically removes ads, navigation, and irrelevant content
    - **Structure preservation** - Maintains headings, paragraphs, and logical content flow
    - **Automatic content cleaning** - Removes HTML artifacts and normalizes text
    - **Intelligent chunking** - Optimally splits content for vector search and retrieval
    - **Multi-model embeddings** - Generates both OpenAI and Gemini embeddings for better search

    ---
    ### 🔑 Authorization
    Requires authentication. Extracted content is associated with user's tenant and specified chatbot.
    """,
    'consumes': ['application/json'],
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'required': ['url'],
                'properties': {
                    'url': {
                        'type': 'string',
                        'format': 'uri',
                        'description': 'URL to crawl and extract content from',
                        'example': 'https://example.com/help/getting-started'
                    },
                    'chatbot_id': {
                        'type': 'integer',
                        'description': 'ID of chatbot to associate content with',
                        'example': 1
                    },
                    'crawl_options': {
                        'type': 'object',
                        'description': 'Optional crawling configuration',
                        'properties': {
                            'max_depth': {
                                'type': 'integer',
                                'minimum': 1,
                                'maximum': 3,
                                'description': 'Maximum crawl depth (1 = single page)',
                                'example': 1
                            },
                            'follow_links': {
                                'type': 'boolean',
                                'description': 'Whether to follow internal links',
                                'example': False
                            },
                            'content_selectors': {
                                'type': 'array',
                                'description': 'CSS selectors for content extraction',
                                'items': {'type': 'string'},
                                'example': ['article', '.content', '#main']
                            },
                            'exclude_selectors': {
                                'type': 'array',
                                'description': 'CSS selectors for elements to exclude',
                                'items': {'type': 'string'},
                                'example': ['.ads', '.sidebar', 'nav']
                            }
                        }
                    },
                    'description': {
                        'type': 'string',
                        'description': 'Optional description of the crawled content',
                        'example': 'Company help documentation for customer support'
                    }
                }
            }
        }
    ],
    'responses': {
        '202': {
            'description': 'Crawling started successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'crawl_job_id': {'type': 'string', 'description': 'Unique ID for tracking the crawl job'},
                    'data_source_id': {'type': 'integer', 'description': 'Database ID of the created data source'},
                    'url': {'type': 'string'},
                    'status': {'type': 'string', 'example': 'crawling'},
                    'estimated_completion': {'type': 'string', 'description': 'Estimated completion time'},
                    'progress_url': {'type': 'string', 'description': 'URL to check crawl progress'}
                }
            }
        },
        '400': {
            'description': 'Bad Request - Invalid URL or configuration',
            'schema': {'$ref': '#/definitions/Error'}
        },
        '401': {
            'description': 'Unauthorized',
            'schema': {'$ref': '#/definitions/Error'}
        },
        '503': {
            'description': 'Service Unavailable - AI service not available',
            'schema': {'$ref': '#/definitions/Error'}
        }
    }
})
def trigger_web_crawl():
    """Trigger web crawling for a URL"""
    data = request.get_json()

    if not data or 'url' not in data:
        return jsonify({
            'error': 'Missing URL',
            'message': 'Request must contain a valid URL to crawl'
        }), 400

    url = data['url'].strip()

    # Validate URL format
    try:
        parsed_url = urlparse(url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            raise ValueError("Invalid URL format")
        if parsed_url.scheme not in ['http', 'https']:
            raise ValueError("Only HTTP and HTTPS URLs are supported")
    except Exception:
        return jsonify({
            'error': 'Invalid URL',
            'message': 'Please provide a valid HTTP or HTTPS URL'
        }), 400

    # Optional chatbot validation
    chatbot_id = data.get('chatbot_id')
    if chatbot_id:
        chatbot = Chatbot.query.filter_by(
            id=chatbot_id,
            tenant_id=g.tenant_id
        ).first()

        if not chatbot:
            return jsonify({
                'error': 'Chatbot not found',
                'message': f'No chatbot found with ID {chatbot_id} in your organization'
            }), 400

    # Resolve chatbot's AI model for structuring
    structure_model_name = None
    structure_model_provider = None
    if chatbot_id:
        from ..services.model_resolver import resolve_model
        try:
            structure_model_name, structure_model_provider = resolve_model(
                chatbot.config or {}
            )
        except Exception as e:
            current_app.logger.warning(
                f"⚠️ Could not resolve chatbot model for structuring: {e}"
            )

    # Check if AI connector is available
    if not current_app.ai_connector:
        return jsonify({
            'error': 'AI service unavailable',
            'message': 'Web crawling service is currently unavailable. Please try again later.'
        }), 503

    try:
        crawl_job_id = str(uuid.uuid4())
        tenant_id = g.tenant_id
        user_id = g.user_id

        # Create data source record
        data_source = DataSource(
            tenant_id=tenant_id,
            chatbot_id=chatbot_id,
            source_type='crawl',
            source_name=url,
            source_url=url,
            status='crawling',
            meta_data={
                'crawl_job_id': crawl_job_id,
                'crawl_options': data.get('crawl_options', {}),
                'description': data.get('description', ''),
                'started_at': datetime.utcnow().isoformat(),
                'domain': parsed_url.netloc,
                'original_url': url
            }
        )

        db.session.add(data_source)
        db.session.commit()

        data_source_id = data_source.id

        # Run crawl in background thread so the response returns immediately
        from threading import Thread
        from flask import copy_current_request_context

        _app = current_app._get_current_object()
        _db = db
        _url = url
        _full_crawl = data.get('full_crawl', True)
        _description = data.get('description', '')
        _chatbot_id = chatbot_id
        _structure_model_name = structure_model_name
        _structure_model_provider = structure_model_provider

        def _run_crawl():
            with _app.app_context():
                try:
                    current_app.logger.info(
                        f"🕷️ Starting web content extraction for: {_url}"
                    )

                    from ..services.web_extraction_service import (
                        WebExtractionService,
                    )
                    web_extractor = WebExtractionService()

                    def progress_callback(progress_data):
                        try:
                            socketio = getattr(
                                current_app, 'socketio', None
                            )
                            if socketio:
                                socketio.emit('crawl_progress', {
                                    'data_source_id': data_source_id,
                                    'chatbot_id': _chatbot_id,
                                    **progress_data
                                }, room=f"user_{user_id}", namespace='/')
                        except Exception as e:
                            current_app.logger.warning(
                                f"Progress update failed: {e}"
                            )

                    if _full_crawl:
                        extraction_result = web_extractor.crawl_full_website(
                            _url,
                            description=_description,
                            tenant_id=tenant_id,
                            user_id=user_id,
                            progress_callback=progress_callback,
                            model_name=_structure_model_name,
                            model_provider=_structure_model_provider
                        )
                    else:
                        extraction_result = (
                            web_extractor.extract_content_from_url(
                                url=_url,
                                description=_description,
                                tenant_id=tenant_id,
                                user_id=user_id
                            )
                        )

                    if not extraction_result['success']:
                        raise Exception(
                            f"Content extraction failed: "
                            f"{extraction_result['error']}"
                        )

                    content = extraction_result.get('content')
                    if not content:
                        raise Exception("Content extraction returned empty")

                    from langchain_core.documents import Document

                    metadata = extraction_result.get('metadata', {})
                    metadata.update({
                        'source': _url,
                        'source_type': 'crawl',
                        'chatbot_id': _chatbot_id,
                        'tenant_id': tenant_id,
                        'user_id': user_id,
                        'extraction_method': (
                            extraction_result.get(
                                'extraction_method', 'unknown'
                            )
                        ),
                        'crawl_stats': (
                            extraction_result.get('stats', {})
                        )
                    })

                    document = Document(
                        page_content=content, metadata=metadata
                    )
                    _process_web_content_async(
                        _app, _db, data_source_id, document
                    )

                    current_app.logger.info(
                        f"🚀 Web extraction and processing started "
                        f"for {_url}"
                    )

                except Exception as e:
                    current_app.logger.error(
                        f"❌ Background crawl failed: {e}"
                    )
                    try:
                        ds = DataSource.query.get(data_source_id)
                        if ds:
                            ds.status = 'failed'
                            ds.meta_data = {
                                **(ds.meta_data or {}),
                                'error': str(e),
                                'failed_at': (
                                    datetime.utcnow().isoformat()
                                )
                            }
                            _db.session.commit()
                        socketio = getattr(
                            current_app, 'socketio', None
                        )
                        if socketio:
                            socketio.emit('crawl_failed', {
                                'data_source_id': data_source_id,
                                'chatbot_id': _chatbot_id,
                                'message': str(e)
                            }, room=f"user_{user_id}", namespace='/')
                    except Exception as db_err:
                        current_app.logger.error(
                            f"Failed to update failed status: {db_err}"
                        )

        thread = Thread(target=_run_crawl, daemon=True)
        thread.start()

        estimated_completion = (
            datetime.utcnow() + timedelta(minutes=2)
        )

        return jsonify({
            'message': 'Web crawl started',
            'crawl_job_id': crawl_job_id,
            'data_source_id': data_source_id,
            'url': url,
            'status': 'crawling',
            'estimated_completion': estimated_completion.isoformat(),
            'progress_url': (
                f'/api/v1/datasources/{data_source_id}/status'
            )
        }), 202

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Error starting web crawl: {e}")
        return jsonify({
            'error': 'Crawl initiation failed',
            'message': 'An error occurred while starting the web crawl. Please try again.'
        }), 500


@api.route('/datasources', methods=['GET'])
@login_required
@swag_from({
    'tags': ['Data Sources'],
    'summary': 'List data sources for tenant',
    'description': """
    ### 📊 Description
    Lists all data sources (uploaded files and crawled URLs) for the authenticated user's tenant.
    Supports filtering by type, status, and chatbot association.

    ---
    ### 🔑 Authorization
    Requires authentication. Only shows data sources owned by user's tenant.
    """,
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'page',
            'in': 'query',
            'type': 'integer',
            'minimum': 1,
            'description': 'Page number for pagination'
        },
        {
            'name': 'per_page',
            'in': 'query',
            'type': 'integer',
            'minimum': 1,
            'maximum': 100,
            'description': 'Items per page (max 100)'
        },
        {
            'name': 'source_type',
            'in': 'query',
            'type': 'string',
            'enum': ['upload', 'crawl', 'api'],
            'description': 'Filter by source type'
        },
        {
            'name': 'status',
            'in': 'query',
            'type': 'string',
            'enum': ['pending', 'processing', 'completed', 'failed'],
            'description': 'Filter by processing status'
        },
        {
            'name': 'chatbot_id',
            'in': 'query',
            'type': 'integer',
            'description': 'Filter by associated chatbot'
        }
    ],
    'responses': {
        '200': {
            'description': 'Data sources retrieved successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'data_sources': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'id': {'type': 'integer'},
                                'source_type': {'type': 'string'},
                                'source_name': {'type': 'string'},
                                'source_url': {'type': 'string'},
                                'status': {'type': 'string'},
                                'chatbot_id': {'type': 'integer'},
                                'created_at': {'type': 'string'},
                                'updated_at': {'type': 'string'},
                                'metadata': {'type': 'object'}
                            }
                        }
                    },
                    'pagination': {'type': 'object'}
                }
            }
        }
    }
})
def list_data_sources():
    """List data sources for the current tenant"""
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    # Filters
    source_type = request.args.get('source_type')
    status = request.args.get('status')
    chatbot_id = request.args.get('chatbot_id', type=int)

    # Build query
    query = DataSource.query.filter_by(tenant_id=g.tenant_id)

    if source_type:
        query = query.filter_by(source_type=source_type)
    if status:
        query = query.filter_by(status=status)
    if chatbot_id:
        query = query.filter_by(chatbot_id=chatbot_id)

    # Order by creation date (newest first)
    query = query.order_by(DataSource.created_at.desc())

    # Paginate
    pagination = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    data_sources = pagination.items

    return jsonify({
        'data_sources': [_format_data_source_response(ds) for ds in data_sources],
        'pagination': {
            'page': pagination.page,
            'pages': pagination.pages,
            'total': pagination.total,
            'per_page': pagination.per_page
        }
    }), 200


@api.route('/datasources/<int:data_source_id>/chunks', methods=['GET'])
@login_required
@swag_from({
    'tags': ['Data Sources'],
    'summary': 'Get processed chunks and embeddings for a data source',
    'description': 'Get processed chunks and embeddings for a data source',
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'data_source_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'ID of the data source'
        }
    ],
    'responses': {
        '200': {
            'description': 'Chunks retrieved successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'data_source_id': {'type': 'integer'},
                    'source_name': {'type': 'string'},
                    'chunk_count': {'type': 'integer'},
                    'chunks': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'content': {'type': 'string'},
                                'metadata': {'type': 'object'},
                                'embedding_stats': {
                                    'type': 'object',
                                    'properties': {
                                        'provider': {'type': 'string'},
                                        'vector_length': {'type': 'integer'},
                                        'has_embedding': {'type': 'boolean'}
                                    }
                                }
                            }
                        }
                    },
                    'embedding_provider': {'type': 'string'}
                }
            }
        },
        '404': {'description': 'Data source not found', 'schema': {'$ref': '#/definitions/Error'}}
    }
})
def get_data_source_chunks(data_source_id):
    """Get processed chunks and embeddings for a data source"""
    data_source = DataSource.query.filter_by(
        id=data_source_id,
        tenant_id=g.tenant_id
    ).first()

    if not data_source:
        return jsonify({
            'error': 'Data source not found',
            'message': f'No data source found with ID {data_source_id}'
        }), 404

    # Allow inspection of completed AND failed sources. For failed
    # sources we return an empty list plus the error message so the UI
    # can show "no chunks" instead of a 400 toast.
    if data_source.status not in ('completed', 'failed'):
        return jsonify({
            'error': 'Processing incomplete',
            'message': f'Data source is in {data_source.status} state. Only completed or failed sources can be inspected.',
            'status': data_source.status,
        }), 400

    try:
        # Get chunks from vector store
        chunks = []

        # If the source is failed, there is nothing in the vector store.
        # Return an empty list (with a hint) so the UI does not show a
        # 400 toast for failed sources.
        if data_source.status == 'failed':
            return jsonify({
                'data_source_id': data_source.id,
                'status': data_source.status,
                'error': (data_source.meta_data or {}).get('error'),
                'chunks': [],
                'total_chunks': 0,
            }), 200

        if current_app.vector_service:
            # Get embedding provider from config (what was used when storing these)
            embed_provider = current_app.config.get('EMBEDDINGS_SERVICE_USE', 'openai')

            # Get document ID from metadata
            doc_id = data_source.meta_data.get('doc_id')
            if not doc_id:
                return jsonify({
                    'error': 'Document ID not found',
                    'message': 'Could not find document ID in metadata'
                }), 404

            # Query vector store for chunks with this doc_id
            chunks = current_app.vector_service.get_chunks_by_doc_id(doc_id, provider=embed_provider)

            # Format response
            chunk_data = []
            for chunk in chunks:
                chunk_info = {
                    'content': chunk.get('page_content', ''),
                    'metadata': chunk.get('metadata', {}),
                    'embedding_stats': {
                        'provider': embed_provider,
                        'vector_length': len(chunk.get('embeddings', {}).get(embed_provider, [])),
                        'has_embedding': chunk.get('embeddings', {}).get(embed_provider) is not None
                    }
                }
                chunk_data.append(chunk_info)

            return jsonify({
                'data_source_id': data_source_id,
                'source_name': data_source.source_name,
                'chunk_count': len(chunk_data),
                'chunks': chunk_data,
                'embedding_provider': embed_provider
            }), 200
        else:
            return jsonify({
                'error': 'Vector service unavailable',
                'message': 'Vector database service is not configured'
            }), 503

    except Exception as e:
        current_app.logger.error(f"❌ Error retrieving chunks for data source {data_source_id}: {e}")
        return jsonify({
            'error': 'Chunk retrieval failed',
            'message': str(e)
        }), 500


@api.route('/datasources/<int:data_source_id>/status', methods=['GET'])
@login_required
@swag_from({
    'tags': ['Data Sources'],
    'summary': 'Get data source processing status',
    'description': 'Get detailed status and progress information for a data source',
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'data_source_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'ID of the data source'
        }
    ],
    'responses': {
        '200': {
            'description': 'Status retrieved successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'id': {'type': 'integer'},
                    'status': {'type': 'string'},
                    'progress': {'type': 'object'},
                    'metadata': {'type': 'object'},
                    'created_at': {'type': 'string'},
                    'updated_at': {'type': 'string'}
                }
            }
        },
        '404': {'description': 'Data source not found', 'schema': {'$ref': '#/definitions/Error'}}
    }
})
def get_data_source_status(data_source_id):
    """Get status of a specific data source"""
    data_source = DataSource.query.filter_by(
        id=data_source_id,
        tenant_id=g.tenant_id
    ).first()

    if not data_source:
        return jsonify({
            'error': 'Data source not found',
            'message': f'No data source found with ID {data_source_id}'
        }), 404

    return jsonify(_format_data_source_response(data_source)), 200


def _process_web_content_async(app, db, data_source_id, document):
    """Process extracted web content through the AI pipeline in a background thread."""
    from threading import Thread

    def process_content():
        with app.app_context():
            try:
                print(f"🚀 [BG-PRINT] THREAD STARTED for data source {data_source_id}")
                current_app.logger.info(f"🚀 [BG-FIRST] THREAD STARTED for data source {data_source_id}")

                # STEP 1: Check the incoming document object immediately
                print(f"🔍 [BG-PRINT] STEP 1: Checking document object.")
                print(f"🔍 [BG-PRINT] Document type: {type(document)}")
                print(f"🔍 [BG-PRINT] Document is None: {document is None}")

                if document is not None:
                    print(f"🔍 [BG-PRINT] Document.page_content is None: {document.page_content is None}")
                    if document.page_content is not None:
                        print(f"🔍 [BG-PRINT] Document.page_content type: {type(document.page_content)}")
                        # This is the first len() call, let's wrap it
                        try:
                            print(f"📄 [BG-PRINT] Document.page_content length: {len(document.page_content)}")
                        except Exception as e:
                            print(f"❌ [BG-PRINT] FAILED at len(document.page_content): {e}")
                            raise e  # Re-raise to be caught by the main handler

                # --- START FINAL PROCESSING PIPELINE ---

                # Setup: Get DataSource, set status, and import services
                data_source = DataSource.query.get(data_source_id)
                if not data_source:
                    print(f"❌ [BG-PRINT] FAILED: DataSource {data_source_id} not found in database.")
                    current_app.logger.error(f"Background task failed: DataSource {data_source_id} not found.")
                    return
                data_source.status = 'processing'
                db.session.commit()
                from ..services import text_cleaner_service, processing_service, embedding_service
                import uuid

                # STEP 2: Text Cleaning
                print("🔍 [BG-PRINT] STEP 2: Cleaning text.")
                cleaned_text = text_cleaner_service.clean_extracted_text(document.page_content)
                if not cleaned_text or not cleaned_text.strip():
                    print("❌ [BG-PRINT] FAILED after text cleaning: No valid content.")
                    raise ValueError("No valid content remained after cleaning")
                print("✅ [BG-PRINT] STEP 2: Text cleaning successful.")
                document.page_content = cleaned_text

                api_keys = resolve_chatbot_api_keys(data_source.chatbot_id)

                # STEP 3: Chunking
                print("🔍 [BG-PRINT] STEP 3: Chunking document.")
                doc_id = str(uuid.uuid4())
                chunks = processing_service.process_documents_into_chunks(
                    documents=[document],
                    source_name=data_source.source_name,
                    doc_id=doc_id,
                    api_keys=api_keys
                )
                if not chunks:
                    print("❌ [BG-PRINT] FAILED after chunking: No chunks returned.")
                    raise ValueError("Document chunking returned no chunks")
                print(f"✅ [BG-PRINT] STEP 3: Chunking successful. {len(chunks)} chunks created.")

                # STEP 4: Embedding Generation
                print("🔍 [BG-PRINT] STEP 4: Generating embeddings.")
                chunk_texts = [chunk.page_content for chunk in chunks if chunk and chunk.page_content]
                if not chunk_texts:
                    print("❌ [BG-PRINT] FAILED before embeddings: No valid chunk texts.")
                    raise ValueError("No valid chunk texts found for embedding generation")

                embedding_results = embedding_service.generate_embeddings_for_texts(chunk_texts)
                if not embedding_results:
                    print("❌ [BG-PRINT] FAILED after embeddings: No results returned.")
                    raise ValueError("Embedding service returned no results")
                print("✅ [BG-PRINT] STEP 4: Embedding generation successful.")

                # STEP 5: Store results
                processed_chunks = []
                embeddings_list = embedding_results.get("embeddings") or []
                embed_provider = embedding_results.get("provider", "openai")

                # Combine chunks with embeddings
                for i, chunk in enumerate(chunks):
                    embedding = embeddings_list[i] if embeddings_list and i < len(embeddings_list) else None
                    chunk_data = {
                        "content": chunk.page_content,
                        "metadata": chunk.metadata,
                        embed_provider: embedding
                    }
                    processed_chunks.append(chunk_data)

                current_app.logger.info(f"🔮 [BG] Generated embeddings for {len(processed_chunks)} chunks")

                # Store in vector database
                vector_service = getattr(current_app, 'vector_service', None)
                if vector_service:
                    try:
                        # Prepare vectors for storage
                        vectors_to_store = []
                        for i, chunk_data in enumerate(processed_chunks):
                            # Use the embedding from the configured provider
                            embedding = chunk_data.get(embed_provider)
                            if embedding:
                                vector_id = f"{doc_id}_{i}"
                                base_meta = dict(chunk_data.get("metadata") or {})
                                base_meta['chatbot_id'] = int(data_source.chatbot_id)
                                base_meta['tenant_id'] = int(data_source.tenant_id)
                                base_meta['source'] = data_source.source_name
                                vectors_to_store.append({
                                    "id": vector_id,
                                    "values": embedding,
                                    "metadata": {
                                        **base_meta,
                                        "page_content": chunk_data["content"],
                                        "doc_id": doc_id,
                                        "chunk_index": i
                                    }
                                })

                        # Store vectors
                        if vectors_to_store:
                            # Pass embed_provider so add_vectors stores in the correct column
                            vector_service.add_vectors(vectors_to_store, provider=embed_provider)
                            current_app.logger.info(f"💾 [BG] Stored {len(vectors_to_store)} vectors in vector database (provider={embed_provider})")

                    except Exception as e:
                        current_app.logger.error(f"❌ [BG] Vector storage failed: {e}")
                        # Continue processing even if vector storage fails

                # Update data source with completion
                data_source.status = 'completed'
                data_source.meta_data = {
                    **data_source.meta_data,
                    'doc_id': doc_id,
                    'processed_chunks': len(processed_chunks),
                    'completed_at': datetime.utcnow().isoformat(),
                    'processing_method': 'gemini_web_extraction'
                }
                db.session.commit()

                current_app.logger.info(f"✅ [BG] Web content processing completed for data source {data_source_id}")

                # Send WebSocket notification for completion
                try:
                    socketio = getattr(current_app, 'socketio', None)
                    if socketio and data_source and data_source.chatbot_id:
                        from ..models import Chatbot, User
                        chatbot = Chatbot.query.get(data_source.chatbot_id)
                        owner = User.query.get(chatbot.user_id) if chatbot else None
                        room = f"user_{owner.id}" if owner else f"tenant_{data_source.tenant_id}"
                        socketio.emit('crawl_completed', {
                            'data_source_id': data_source_id,
                            'chatbot_id': data_source.chatbot_id,
                            'status': 'completed',
                            'message': f'Successfully crawled and processed {data_source.source_name}',
                            'stats': data_source.meta_data.get('crawl_stats', {})
                        }, room=room, namespace='/')
                        current_app.logger.info(f"📡 [BG] Sent WebSocket crawl_completed notification to {room}")
                except Exception as ws_error:
                    current_app.logger.warning(f"⚠️ [BG] Failed to send WebSocket notification: {ws_error}")

            except Exception as e:
                print(f"❌ [BG-PRINT] EXCEPTION CAUGHT: {e}")
                current_app.logger.error(f"❌ [BG] Web content processing failed: {e}")
                current_app.logger.error(f"❌ [BG] Exception type: {type(e).__name__}")
                current_app.logger.error(f"❌ [BG] Exception details: {repr(e)}")

                # Update data source with error
                try:
                    data_source = DataSource.query.get(data_source_id)
                    if data_source:
                        data_source.status = 'failed'
                        data_source.meta_data = {
                            **data_source.meta_data,
                            'error': str(e),
                            'error_type': type(e).__name__,
                            'failed_at': datetime.utcnow().isoformat()
                        }
                        db.session.commit()

                        # Send WebSocket notification for failure
                        try:
                            socketio = getattr(current_app, 'socketio', None)
                            if socketio and data_source.chatbot_id:
                                socketio.emit('crawl_failed', {
                                    'data_source_id': data_source_id,
                                    'chatbot_id': data_source.chatbot_id,
                                    'status': 'failed',
                                    'message': f'Failed to crawl {data_source.source_name}: {str(e)[:100]}',
                                    'error': str(e)
                                }, room=f"user_{data_source.user_id}", namespace='/')
                                current_app.logger.info(f"📡 [BG] Sent WebSocket crawl_failed notification to user_{data_source.user_id}")
                        except Exception as ws_error:
                            current_app.logger.warning(f"⚠️ [BG] Failed to send WebSocket notification: {ws_error}")
                        current_app.logger.info(f"✅ [BG] Updated data source {data_source_id} status to failed")
                except Exception as db_error:
                    current_app.logger.error(f"❌ [BG] Failed to update data source status: {db_error}")
                    try:
                        db.session.rollback()
                    except Exception:
                        pass

    # Start background processing
    thread = Thread(target=process_content)
    thread.daemon = True
    thread.start()


def _run_ai_processing(app, db, data_source_id):
    """Helper function to run the AI pipeline in a background thread."""
    # Import required modules
    import os
    from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
    from ..services import embedding_service, text_cleaner_service, processing_service

    def _persist_progress(stage, **fields):
        """Write progress to the DataSource row + push a WebSocket event.

        This is the only place the DataSource row is mutated during
        processing, so the frontend always sees a consistent state.
        """
        try:
            ds = DataSource.query.get(data_source_id)
            if not ds:
                return
            ds.meta_data = dict(ds.meta_data or {})
            ds.meta_data['progress_stage'] = stage
            ds.meta_data['progress_updated_at'] = datetime.utcnow().isoformat()
            for key, value in fields.items():
                ds.meta_data[key] = value
            db.session.commit()
        except Exception as exc:
            try:
                db.session.rollback()
            except Exception:
                pass
            app.logger.warning(f"[BG] failed to persist progress: {exc}")

        # Fire a real-time event so the UI can update without polling.
        try:
            socketio = getattr(app, 'socketio', None)
            if socketio is not None:
                payload = {
                    'data_source_id': data_source_id,
                    'stage': stage,
                    'updated_at': datetime.utcnow().isoformat(),
                    **fields,
                }
                socketio.emit('datasource_progress', payload, namespace='/')
        except Exception as exc:
            app.logger.debug(f"[BG] websocket emit failed (non-fatal): {exc}")

    with app.app_context():
        data_source = DataSource.query.get(data_source_id)
        if not data_source:
            app.logger.error(f"Background task failed: DataSource {data_source_id} not found.")
            return

        try:
            app.logger.info(f"🤖 [BG] Starting AI processing for file: {data_source.source_name}")
            _persist_progress('extracting')

            # Use the local file path directly
            local_filepath = data_source.meta_data.get('local_filepath')
            if not local_filepath or not os.path.exists(local_filepath):
                raise Exception(f"Local file not found at path: {local_filepath}")

            # Step 2: Process document using the appropriate loader

            # Map file extensions to their loaders
            LOADER_MAPPING = {
                '.pdf': PyPDFLoader,
                '.txt': TextLoader,
                '.docx': Docx2txtLoader
            }

            # Get file extension and validate
            file_ext = os.path.splitext(local_filepath)[1].lower()
            if file_ext not in LOADER_MAPPING:
                raise ValueError(f"Unsupported file type: {file_ext}. Supported types: {list(LOADER_MAPPING.keys())}")

            # Select and use appropriate loader
            loader_class = LOADER_MAPPING[file_ext]
            app.logger.info(f"📄 [BG] Using {loader_class.__name__} for {file_ext} file")

            try:
                loader = loader_class(local_filepath)
                documents = loader.load()
                if not documents:
                    raise ValueError(f"No content extracted from file: {data_source.source_name}")
                app.logger.info(f"📑 [BG] Successfully extracted {len(documents)} document(s)")
            except Exception as e:
                raise ValueError(f"Failed to load {file_ext} file: {str(e)}")

            # Clean the text
            cleaned_docs = []
            for doc in documents:
                cleaned_text = text_cleaner_service.clean_extracted_text(doc.page_content)
                if cleaned_text.strip():  # Only keep non-empty documents
                    doc.page_content = cleaned_text
                    cleaned_docs.append(doc)

            if not cleaned_docs:
                raise ValueError("No valid content remained after cleaning")

            documents = cleaned_docs
            app.logger.info(f"🧹 [BG] Cleaned {len(documents)} document(s)")

            # Generate document ID for this processing job
            api_keys = resolve_chatbot_api_keys(data_source.chatbot_id)

            doc_id = str(uuid.uuid4())

            # Chunk the documents
            _persist_progress('chunking', total_chunks_estimate=None)
            chunks = processing_service.process_documents_into_chunks(
                documents=documents,
                source_name=data_source.source_name,
                doc_id=doc_id,
                api_keys=api_keys
            )

            total_chunks = len(chunks)
            app.logger.info(f"✅ [BG] Processed into {total_chunks} chunks")

            # Pre-compute the number of API batches the embedding service
            # will need (Gemini hard limit is 100 per request, OpenAI is
            # larger but we still chunk to keep memory bounded).
            gemini_batch_limit = 100
            provider = app.config.get('EMBEDDINGS_SERVICE_USE', 'openai')
            rate_limit_per_min = int(app.config.get('GEMINI_RATE_LIMIT_PER_MINUTE', 100))

            if provider == 'gemini':
                total_batches = (total_chunks + gemini_batch_limit - 1) // gemini_batch_limit
            else:
                # For non-Gemini providers we still send one batch but
                # the UI should not show a multi-batch progress bar.
                total_batches = 1

            _persist_progress(
                'embedding',
                total_chunks=total_chunks,
                total_batches=total_batches,
                provider=provider,
                rate_limit_per_minute=rate_limit_per_min,
                chunks_embedded=0,
                current_batch=0,
            )

            # Step 3: Generate embeddings — with rate-limit-aware progress
            chunk_texts = [chunk.page_content for chunk in chunks]

            def on_batch_start(batch_index, total_batches, wait_seconds, used, capacity):
                app.logger.info(
                    f"[BG] Waiting for Gemini rate-limit token before batch "
                    f"{batch_index + 1}/{total_batches} ({wait_seconds:.1f}s; "
                    f"used {used}/{capacity} in current window)"
                )
                _persist_progress(
                    'embedding',
                    total_chunks=total_chunks,
                    total_batches=total_batches,
                    provider=provider,
                    rate_limit_per_minute=rate_limit_per_min,
                    chunks_embedded=batch_index * gemini_batch_limit,
                    current_batch=batch_index,
                    wait_seconds=round(wait_seconds, 1),
                    rate_used=used,
                    rate_capacity=capacity,
                )

            def on_batch_done(batch_index, total_batches, batch_size, embeddings_so_far):
                app.logger.info(
                    f"[BG] Batch {batch_index + 1}/{total_batches} complete: "
                    f"{embeddings_so_far}/{total_chunks} chunks embedded"
                )
                _persist_progress(
                    'embedding',
                    total_chunks=total_chunks,
                    total_batches=total_batches,
                    provider=provider,
                    rate_limit_per_minute=rate_limit_per_min,
                    chunks_embedded=embeddings_so_far,
                    current_batch=batch_index + 1,
                )

            embedding_results = embedding_service.generate_embeddings_for_texts(
                chunk_texts,
                on_batch_start=on_batch_start,
                on_batch_done=on_batch_done,
            )

            processed_chunks = []
            embeddings_list = embedding_results.get("embeddings") or []
            embed_provider = embedding_results.get("provider", "openai")

            for i, chunk in enumerate(chunks):
                chunk_meta = dict(chunk.metadata) if chunk.metadata else {}
                chunk_meta['chatbot_id'] = int(data_source.chatbot_id)
                chunk_meta['tenant_id'] = int(data_source.tenant_id)
                chunk_meta['source'] = data_source.source_name
                processed_chunk = {
                    "metadata": chunk_meta,
                    "page_content": chunk.page_content,
                    "embeddings": {}
                }
                if embeddings_list and i < len(embeddings_list):
                    processed_chunk["embeddings"][embed_provider] = embeddings_list[i]
                processed_chunks.append(processed_chunk)

            app.logger.info(f"✅ [BG] Generated embeddings for {len(processed_chunks)} chunks")

            # Guard: if NO embeddings were produced (every provider failed)
            # do NOT silently insert empty rows. Mark the source as failed
            # with the underlying error and bail out before vector storage.
            if not embeddings_list or any(
                not p.get("embeddings", {}).get(embed_provider)
                for p in processed_chunks
                if embeddings_list
            ) and not any(
                p.get("embeddings", {}).get(embed_provider)
                for p in processed_chunks
            ):
                err = embedding_results.get("error") or "Embedding generation returned no vectors"
                app.logger.error(
                    f"❌ [BG] Embedding generation produced 0 vectors for "
                    f"data source {data_source_id}: {err}"
                )
                _persist_progress(
                    'failed',
                    total_chunks=total_chunks,
                    total_batches=total_batches,
                    provider=embed_provider,
                    error=err,
                )
                data_source.status = 'failed'
                data_source.meta_data['error'] = err
                data_source.meta_data['progress_stage'] = 'failed'
                db.session.commit()
                return

            # Step 4: Store in vector database
            _persist_progress(
                'storing',
                total_chunks=total_chunks,
                total_batches=total_batches,
                provider=embed_provider,
                chunks_embedded=len(embeddings_list),
            )
            if app.vector_service:
                vector_result = app.vector_service.upsert(processed_chunks, provider=embed_provider)
                app.logger.info(f"✅ [BG] Stored {vector_result.get('upserted_count', 0)} chunks in vector DB")
            else:
                app.logger.warning("⚠️ [BG] Vector service not available, chunks not stored")

            # Step 5: Update status to completed
            data_source.status = 'completed'
            data_source.meta_data['processed_chunks'] = len(processed_chunks)
            data_source.meta_data['completed_at'] = datetime.utcnow().isoformat()
            data_source.meta_data['doc_id'] = doc_id  # Save doc_id for chunk retrieval
            data_source.meta_data['progress_stage'] = 'completed'
            data_source.meta_data['chunks_embedded'] = len(embeddings_list)
            data_source.meta_data['embed_provider'] = embed_provider
            db.session.commit()

            # No need to clean up the temp file here as it's the permanent local storage for now
            try:
                socketio = getattr(app, 'socketio', None)
                if socketio is not None:
                    socketio.emit(
                        'datasource_progress',
                        {
                            'data_source_id': data_source_id,
                            'stage': 'completed',
                            'updated_at': datetime.utcnow().isoformat(),
                            'total_chunks': total_chunks,
                            'chunks_embedded': len(embeddings_list),
                            'provider': embed_provider,
                        },
                        namespace='/',
                    )
            except Exception as exc:
                app.logger.debug(f"[BG] final websocket emit failed: {exc}")

        except Exception as e:
            app.logger.error(f"❌ [BG] Failed to process file {data_source.id}: {e}", exc_info=True)
            data_source.status = 'failed'
            data_source.meta_data['error'] = str(e)
            data_source.meta_data['progress_stage'] = 'failed'
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
            try:
                socketio = getattr(app, 'socketio', None)
                if socketio is not None:
                    socketio.emit(
                        'datasource_progress',
                        {
                            'data_source_id': data_source_id,
                            'stage': 'failed',
                            'updated_at': datetime.utcnow().isoformat(),
                            'error': str(e),
                        },
                        namespace='/',
                    )
            except Exception:
                pass
            data_source.meta_data['failed_at'] = datetime.utcnow().isoformat()

        finally:
            db.session.commit()


# COMMENTED OUT: Local upload endpoint - reverting to S3-only upload
# @api.route('/datasources/upload/local', methods=['POST'])
# @login_required
# def upload_local_file():
#     """Handle local file uploads, bypassing S3 for testing."""
#     if 'file' not in request.files:
#         return jsonify({'error': 'No file part in the request'}), 400
#
#     file = request.files['file']
#     if file.filename == '':
#         return jsonify({'error': 'No file selected for upload'}), 400
#
#     chatbot_id = request.form.get('chatbot_id')
#     if not chatbot_id:
#         return jsonify({'error': 'chatbot_id is required'}), 400
#
#     chatbot = Chatbot.query.filter_by(id=chatbot_id, tenant_id=g.tenant_id).first()
#     if not chatbot:
#         return jsonify({'error': 'Chatbot not found'}), 404
#
#     if file:
#         filename = secure_filename(file.filename)
#         # Create a unique path for the file to avoid overwrites
#         unique_id = str(uuid.uuid4())
#         save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"{unique_id}-{filename}")
#         file.save(save_path)
#
#         # Create DataSource record
#         data_source = DataSource(
#             tenant_id=g.tenant_id,
#             chatbot_id=chatbot_id,
#             source_type='upload',
#             source_name=filename,
#             source_url=f"local://{save_path}",
#             status='processing', # Set to processing immediately
#             meta_data={
#                 'local_filepath': save_path,
#                 'original_filename': filename,
#                 'size': os.path.getsize(save_path),
#                 'content_type': file.content_type,
#                 'description': request.form.get('description', '')
#             }
#         )
#         db.session.add(data_source)
#         db.session.commit()
#
#         # Run AI processing in a background thread to avoid request timeouts
#         from threading import Thread
#         thread = Thread(target=_run_ai_processing, args=(current_app._get_current_object(), db, data_source.id))
#         thread.daemon = True
#         thread.start()
#
#         return jsonify({
#             'message': 'File uploaded and processing started.',
#             'data_source': _format_data_source_response(data_source)
#         }), 202
#
#     return jsonify({'error': 'File upload failed'}), 500


def _format_data_source_response(data_source: DataSource) -> dict:
    """Format data source model for API response"""
    meta = dict(data_source.meta_data or {})

    # Build a derived `progress` block the frontend can render directly
    # without having to dig through the raw `metadata` JSON. The shape
    # is stable so the React component can do a simple `progress.bar`.
    progress = {
        'stage': meta.get('progress_stage'),
        'total_chunks': meta.get('total_chunks'),
        'chunks_embedded': meta.get('chunks_embedded'),
        'total_batches': meta.get('total_batches'),
        'current_batch': meta.get('current_batch'),
        'provider': meta.get('provider') or meta.get('embed_provider'),
        'rate_limit_per_minute': meta.get('rate_limit_per_minute'),
        'rate_used': meta.get('rate_used'),
        'rate_capacity': meta.get('rate_capacity'),
        'wait_seconds': meta.get('wait_seconds'),
        'updated_at': meta.get('progress_updated_at'),
    }

    return {
        'id': data_source.id,
        'source_type': data_source.source_type,
        'source_name': data_source.source_name,
        'source_url': data_source.source_url,
        'status': data_source.status,
        'chatbot_id': data_source.chatbot_id,
        'created_at': data_source.created_at.isoformat() if data_source.created_at else None,
        'updated_at': data_source.updated_at.isoformat() if data_source.updated_at else None,
        'processed_at': data_source.processed_at.isoformat() if data_source.processed_at else None,
        'metadata': meta,
        'progress': progress,
    }


# =============================================================
# Debug / repair helpers for RAG retrieval issues.
# =============================================================
@api.route('/debug/embeddings', methods=['GET'])
@login_required
def debug_embeddings():
    """
    Diagnose why a query is or is not retrieving expected chunks.

    Returns a per-source breakdown of how many embeddings exist for each
    chatbot_id in the database. Use this to spot:
      - embeddings with chatbot_id = NULL (would be excluded by the filter)
      - embeddings tied to the wrong chatbot
      - duplicate chunks (same content / source)
    """
    from sqlalchemy import func
    from ..models.document_embedding import DocumentEmbedding
    from ..models.datasource import DataSource

    chatbot_id = request.args.get('chatbot_id', type=int)

    # 1. Per-source / per-chatbot breakdown
    rows = (
        db.session.query(
            DocumentEmbedding.source,
            DocumentEmbedding.chatbot_id,
            func.count(DocumentEmbedding.id).label('chunk_count'),
        )
        .group_by(DocumentEmbedding.source, DocumentEmbedding.chatbot_id)
        .order_by(DocumentEmbedding.source)
        .all()
    )
    breakdown = [
        {
            'source': r.source,
            'chatbot_id': r.chatbot_id,
            'chunk_count': int(r.chunk_count),
        }
        for r in rows
    ]

    # 2. Distinct chatbot_id values
    distinct_chatbots = [
        r[0] for r in db.session.query(DocumentEmbedding.chatbot_id)
        .distinct().all()
    ]

    # 3. Data sources for the requested chatbot (if any)
    ds_for_chatbot = []
    if chatbot_id is not None:
        for ds in DataSource.query.filter_by(chatbot_id=chatbot_id).all():
            ds_for_chatbot.append({
                'id': ds.id,
                'source_name': ds.source_name,
                'source_type': ds.source_type,
                'status': ds.status,
                'meta_data': ds.meta_data or {},
            })

    # 4. NULL-chatbot_id embedding count (the usual culprit)
    null_chatbot_count = (
        db.session.query(func.count(DocumentEmbedding.id))
        .filter(DocumentEmbedding.chatbot_id.is_(None))
        .scalar() or 0
    )

    return jsonify({
        'distinct_chatbot_ids': distinct_chatbots,
        'null_chatbot_id_count': int(null_chatbot_count),
        'breakdown_by_source_and_chatbot': breakdown,
        'data_sources_for_chatbot': ds_for_chatbot,
    })


@api.route('/debug/embeddings/repair', methods=['POST'])
@login_required
def debug_repair_embeddings():
    """
    Repair embeddings whose ``chatbot_id`` is NULL by joining them to the
    DataSource that owns the matching ``doc_id``.

    Background: older ingestion paths did not set ``chatbot_id`` on the
    embedding rows, which caused RAG search to silently drop them when
    filtering by chatbot. This endpoint back-fills the column from the
    corresponding DataSource row so retrieval works correctly.
    """
    from ..models.document_embedding import DocumentEmbedding
    from ..models.datasource import DataSource

    body = request.get_json(silent=True) or {}
    chatbot_id = body.get('chatbot_id')

    try:
        # Find embeddings with NULL chatbot_id
        null_rows = DocumentEmbedding.query.filter(
            DocumentEmbedding.chatbot_id.is_(None)
        ).all()

        repaired = 0
        per_source: dict = {}
        for row in null_rows:
            meta = row.meta_data or {}
            doc_id = meta.get('doc_id') or row.doc_id
            # The DataSource row's doc_id is stored in meta_data.doc_id
            ds = None
            if doc_id:
                # Match doc_id in Python because the JSON column is generic
                # JSON, not JSONB (no portable `.astext`).
                candidates = DataSource.query.all()
                ds = next(
                    (d for d in candidates
                     if d.meta_data
                     and str(d.meta_data.get('doc_id', '')) == str(doc_id)),
                    None,
                )
            if ds and ds.chatbot_id is not None:
                if chatbot_id is None or int(ds.chatbot_id) == int(chatbot_id):
                    row.chatbot_id = int(ds.chatbot_id)
                    if ds.tenant_id is not None:
                        row.tenant_id = int(ds.tenant_id)
                    repaired += 1
                    key = (row.source, row.chatbot_id)
                    per_source[key] = per_source.get(key, 0) + 1

        db.session.commit()

        return jsonify({
            'success': True,
            'repaired_count': repaired,
            'remaining_null_chatbot_id': (
                DocumentEmbedding.query
                .filter(DocumentEmbedding.chatbot_id.is_(None))
                .count()
            ),
            'per_source': [
                {'source': s, 'chatbot_id': c, 'count': n}
                for (s, c), n in per_source.items()
            ],
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Repair failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/debug/embedding-columns', methods=['GET'])
@login_required
def debug_embedding_columns():
    """
    Show the actual column values of all embeddings for a given chatbot_id.

    Critical because the production filter uses the *column* `chatbot_id`,
    `provider`, and the embedding column (`embedding_openai` / `embedding_gemini`)
    — NOT the values in `meta_data`. If the columns are NULL while meta_data
    has the correct value, retrieval will silently return 0.
    """
    from ..models.document_embedding import DocumentEmbedding
    from sqlalchemy import func as _sa_func

    chatbot_id = request.args.get('chatbot_id', type=int)
    if chatbot_id is None:
        return jsonify({'success': False, 'error': 'chatbot_id query param is required'}), 400

    rows = (
        db.session.query(DocumentEmbedding)
        .filter(DocumentEmbedding.chatbot_id == chatbot_id)
        .limit(10)
        .all()
    )

    samples = []
    for r in rows:
        samples.append({
            'id': r.id,
            'vector_id': r.vector_id,
            'doc_id': r.doc_id,
            'chunk_index': r.chunk_index,
            'source': r.source,
            'chatbot_id_column': r.chatbot_id,
            'tenant_id_column': r.tenant_id,
            'provider_column': r.provider,
            'meta_data_chatbot_id': (r.meta_data or {}).get('chatbot_id'),
            'meta_data_tenant_id': (r.meta_data or {}).get('tenant_id'),
            'embedding_openai_is_null': r.embedding_openai is None,
            'embedding_gemini_is_null': r.embedding_gemini is None,
            'embedding_openai_dim': len(r.embedding_openai) if r.embedding_openai is not None else 0,
            'embedding_gemini_dim': len(r.embedding_gemini) if r.embedding_gemini is not None else 0,
        })

    # Aggregate: how many rows for this chatbot have each embedding populated?
    openai_count = (
        db.session.query(_sa_func.count(DocumentEmbedding.id))
        .filter(DocumentEmbedding.chatbot_id == chatbot_id)
        .filter(DocumentEmbedding.embedding_openai.isnot(None))
        .scalar() or 0
    )
    gemini_count = (
        db.session.query(_sa_func.count(DocumentEmbedding.id))
        .filter(DocumentEmbedding.chatbot_id == chatbot_id)
        .filter(DocumentEmbedding.embedding_gemini.isnot(None))
        .scalar() or 0
    )
    total = (
        db.session.query(_sa_func.count(DocumentEmbedding.id))
        .filter(DocumentEmbedding.chatbot_id == chatbot_id)
        .scalar() or 0
    )
    null_chatbot_id = (
        db.session.query(_sa_func.count(DocumentEmbedding.id))
        .filter(DocumentEmbedding.chatbot_id.is_(None))
        .scalar() or 0
    )

    return jsonify({
        'success': True,
        'chatbot_id': chatbot_id,
        'total_chunks_for_chatbot': int(total),
        'chunks_with_openai_embedding': int(openai_count),
        'chunks_with_gemini_embedding': int(gemini_count),
        'global_null_chatbot_id_chunks': int(null_chatbot_id),
        'samples': samples,
        'active_embedding_provider_config': current_app.config.get('EMBEDDINGS_SERVICE_USE', 'openai'),
    })


@api.route('/debug/retrieval', methods=['POST'])
@login_required
def debug_retrieval():
    """
    End-to-end diagnostic for the RAG retrieval pipeline.

    Takes a chatbot_id and a query text, then reports:
      - whether the query embedding could be generated, with which provider,
        and the resulting embedding dimension.
      - per-provider count of chunks that match chatbot_id (with and without
        the embedding column populated).
      - sample chunks from each provider column (if any).
      - the actual top-k matches returned by the production search code,
        with similarity scores.
      - timing for each phase.

    Use this to pinpoint exactly which step is broken when the LLM gives
    an "out of scope" refusal even though the document is in the KB.
    """
    from ..models.document_embedding import DocumentEmbedding
    from ..services.vector_service import VectorService
    from sqlalchemy import func as _sa_func

    body = request.get_json(silent=True) or {}
    chatbot_id = body.get('chatbot_id')
    query_text = body.get('query', '').strip()
    top_k = int(body.get('top_k', 5))

    if chatbot_id is None:
        return jsonify({'success': False, 'error': 'chatbot_id is required'}), 400
    if not query_text:
        return jsonify({'success': False, 'error': 'query is required'}), 400

    out: dict = {'chatbot_id': chatbot_id, 'query': query_text, 'top_k': top_k, 'phases': {}}

    # --- Phase 1: per-provider chunk counts for this chatbot_id ------------
    counts = {}
    for prov in ('openai', 'gemini'):
        col = DocumentEmbedding.embedding_openai if prov == 'openai' else DocumentEmbedding.embedding_gemini
        with_emb = (
            db.session.query(_sa_func.count(DocumentEmbedding.id))
            .filter(DocumentEmbedding.chatbot_id == chatbot_id)
            .filter(col.isnot(None))
            .scalar() or 0
        )
        total = (
            db.session.query(_sa_func.count(DocumentEmbedding.id))
            .filter(DocumentEmbedding.chatbot_id == chatbot_id)
            .scalar() or 0
        )
        counts[prov] = {'total_chunks_for_chatbot': int(total), 'chunks_with_embedding': int(with_emb)}
    out['phases']['per_provider_counts'] = counts

    # --- Phase 2: generate query embedding ---------------------------------
    import time as _t
    t0 = _t.time()
    embedding_result = current_app.embedding_service.generate_embeddings_for_texts([query_text])
    t1 = _t.time()
    embeddings_list = embedding_result.get("embeddings")
    embed_provider = embedding_result.get("provider", "openai")
    query_embedding = embeddings_list[0] if embeddings_list else None
    out['phases']['query_embedding'] = {
        'provider': embed_provider,
        'embedding_dim': len(query_embedding) if query_embedding else 0,
        'embedding_sample_first_5': (
            [round(float(x), 5) for x in query_embedding[:5]] if query_embedding else None
        ),
        'error': embedding_result.get("error"),
        'elapsed_ms': int((t1 - t0) * 1000),
    }

    if not query_embedding:
        out['diagnosis'] = (
            'QUERY EMBEDDING FAILED - retrieval will return 0. '
            'Check EMBEDDINGS_SERVICE_USE, OPENAI_API_KEY, GEMINI_API_KEY.'
        )
        return jsonify(out)

    # --- Phase 3: run production query() for the active provider ------------
    vs = VectorService()
    active_results = vs.query(query_embedding, top_k=top_k,
                              filter_dict={'provider': embed_provider, 'chatbot_id': chatbot_id})
    out['phases']['active_provider_query'] = {
        'provider': embed_provider,
        'result_count': len(active_results),
        'top_scores': [round(m['score'], 3) for m in active_results[:5]],
        'top_sources': [m['metadata'].get('source') for m in active_results[:5]],
        'top_chunks_preview': [
            m['page_content'][:200].replace('\n', ' ') for m in active_results[:3]
        ],
    }

    # --- Phase 4: run with the OTHER provider as a fallback test ------------
    other_provider = 'openai' if embed_provider != 'openai' else 'gemini'
    other_results = vs.query(query_embedding, top_k=top_k,
                             filter_dict={'provider': other_provider, 'chatbot_id': chatbot_id})
    out['phases']['other_provider_query'] = {
        'provider': other_provider,
        'result_count': len(other_results),
        'top_scores': [round(m['score'], 3) for m in other_results[:5]],
    }

    # --- Phase 5: diagnosis ------------------------------------------------
    if counts[embed_provider]['chunks_with_embedding'] == 0 and counts[other_provider]['chunks_with_embedding'] == 0:
        out['diagnosis'] = (
            f'NO CHUNKS HAVE EMBEDDINGS for chatbot_id={chatbot_id}. '
            f'Re-upload the document(s) for this chatbot.'
        )
    elif counts[embed_provider]['chunks_with_embedding'] > 0 and len(active_results) == 0:
        out['diagnosis'] = (
            f'Chunks exist for {embed_provider} but the query returned 0. '
            f'Likely cause: the query_embedding is in a different vector space '
            f'from the stored embeddings, OR the cosine distance ordering is broken. '
            f'Check the raw_results count in [VECTOR_QUERY] log lines.'
        )
    elif len(active_results) == 0 and len(other_results) > 0:
        out['diagnosis'] = (
            f'Active provider {embed_provider} returned 0 but {other_provider} returned '
            f'{len(other_results)}. The search_similar fallback should catch this — '
            f'but it uses the {embed_provider} embedding to score {other_provider} '
            f'vectors, so the results are essentially noise. Fix by re-embedding the '
            f'document with the active provider.'
        )
    elif len(active_results) > 0:
        out['diagnosis'] = f'OK - {len(active_results)} chunks retrieved via {embed_provider}.'
    else:
        out['diagnosis'] = 'Unknown issue - inspect [VECTOR_QUERY] log lines for details.'

    return jsonify(out)


# =============================================================
# Stuck-source watchdog
# =============================================================
def sweep_stuck_data_sources(max_age_seconds: int = 600) -> dict:
    """
    Mark any DataSource that has been in 'pending' or 'processing' for
    longer than ``max_age_seconds`` as 'failed'.

    This is the safety net that prevents the UI from getting stuck on
    "uploading…" / "updating…" when a background thread dies before it
    can finalize the row.

    Returns a dict with the count of rows updated and their ids.
    """
    from datetime import datetime, timedelta

    cutoff = datetime.utcnow() - timedelta(seconds=max_age_seconds)

    stuck = (
        DataSource.query
        .filter(DataSource.status.in_(['pending', 'processing']))
        .filter(DataSource.updated_at < cutoff)
        .all()
    )

    marked = []
    for ds in stuck:
        ds.status = 'failed'
        ds.meta_data = {
            **(ds.meta_data or {}),
            'error': f"Watchdog: source was stuck in '{ds.status}' for over {max_age_seconds}s",
            'failed_at': datetime.utcnow().isoformat(),
        }
        marked.append(ds.id)

    if marked:
        db.session.commit()
        current_app.logger.warning(
            f"🧹 Sweep: marked {len(marked)} stuck data source(s) as 'failed': {marked}"
        )

    return {
        'marked_failed': len(marked),
        'ids': marked,
        'cutoff': cutoff.isoformat(),
    }


@api.route('/admin/datasources/sweep', methods=['POST', 'GET'])
@login_required
def admin_sweep_stuck_data_sources():
    """
    Manually trigger the stuck-data-source sweep.

    Useful when a source has been stuck in 'processing' and the user
    wants to mark it as 'failed' so the UI moves on. Returns the list
    of ids that were updated.
    """
    try:
        result = sweep_stuck_data_sources(max_age_seconds=600)
        return jsonify({
            'success': True,
            **result,
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Sweep failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@api.route('/datasources/<int:data_source_id>/mark-failed', methods=['POST', 'OPTIONS'])
@login_required
def mark_data_source_failed(data_source_id):
    """
    Manually mark a single stuck data source as 'failed'.

    Use this when the user wants to abandon a stuck upload. The next
    time they re-upload the same file it will be processed normally.
    """
    try:
        ds = DataSource.query.filter_by(
            id=data_source_id,
            tenant_id=g.tenant_id,
        ).first()
        if not ds:
            return jsonify({'error': 'Data source not found'}), 404

        ds.status = 'failed'
        ds.meta_data = {
            **(ds.meta_data or {}),
            'error': 'Manually marked as failed by user',
            'failed_at': datetime.utcnow().isoformat(),
        }
        db.session.commit()

        return jsonify({
            'success': True,
            'id': ds.id,
            'status': ds.status,
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"mark-failed failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
