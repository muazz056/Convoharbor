# app/api/datasources.py

import os
import boto3
import uuid
from urllib.parse import urlparse
from datetime import datetime, timedelta
from flask import request, current_app, jsonify, g
from sqlalchemy.exc import IntegrityError
from . import api
from ..decorators import login_required
from ..models import Chatbot, DataSource
from .. import db
from flasgger.utils import swag_from
from werkzeug.utils import secure_filename


@api.route('/datasources/upload', methods=['POST'])
@login_required
@swag_from({
    'tags': ['Data Sources'],
    'summary': 'Generate secure upload URLs for files',
    'description': """
    ### 📤 Description
    Generates presigned URLs for secure direct upload to AWS S3. This endpoint supports uploading documents 
    that will be processed by the AI service and associated with a specific chatbot for training.
    
    The process works as follows:
    1. Client requests presigned URL with file metadata
    2. Server validates file and generates S3 presigned URL
    3. Client uploads directly to S3 using the presigned URL
    4. Server triggers AI processing after successful upload
    
    ---
    ### 🔒 Security Features
    - Direct upload to S3 (no server bandwidth usage)
    - Presigned URLs with expiration time
    - File type and size validation
    - Virus scanning integration (optional)
    
    ---
    ### 🔑 Authorization
    Requires authentication. Files are associated with user's tenant and optionally with a specific chatbot.
    """,
    'consumes': ['application/json'],
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'description': 'File upload request with metadata',
            'schema': {
                'type': 'object',
                'required': ['files', 'chatbot_id'],
                'properties': {
                    'files': {
                        'type': 'array',
                        'description': 'List of files to upload',
                        'items': {
                            'type': 'object',
                            'required': ['filename', 'content_type', 'size'],
                            'properties': {
                                'filename': {
                                    'type': 'string',
                                    'description': 'Name of the file',
                                    'example': 'company_manual.pdf'
                                },
                                'content_type': {
                                    'type': 'string',
                                    'description': 'MIME type of the file',
                                    'example': 'application/pdf'
                                },
                                'size': {
                                    'type': 'integer',
                                    'description': 'File size in bytes',
                                    'example': 1024000
                                }
                            }
                        }
                    },
                    'chatbot_id': {
                        'type': 'integer',
                        'description': 'Required ID of chatbot to associate files with',
                        'example': 1
                    },
                    'description': {
                        'type': 'string',
                        'description': 'Optional description of the upload batch',
                        'example': 'Company policy documents for HR chatbot'
                    }
                }
            }
        }
    ],
    'responses': {
        '200': {
            'description': 'Upload URLs generated successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'upload_batch_id': {'type': 'string', 'description': 'Unique ID for tracking this upload batch'},
                    'files': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'file_id': {'type': 'string', 'description': 'Unique ID for this file'},
                                'filename': {'type': 'string'},
                                'presigned_url': {'type': 'string', 'description': 'S3 presigned URL for upload'},
                                'expires_at': {'type': 'string', 'format': 'date-time', 'description': 'URL expiration time'},
                                'upload_fields': {'type': 'object', 'description': 'Additional fields required for S3 upload'}
                            }
                        }
                    },
                    'instructions': {
                        'type': 'object',
                        'properties': {
                            'method': {'type': 'string', 'example': 'POST'},
                            'content_type': {'type': 'string', 'example': 'multipart/form-data'},
                            'note': {'type': 'string'}
                        }
                    }
                }
            }
        },
        '400': {
            'description': 'Bad Request - Invalid files or configuration',
            'schema': {'$ref': '#/definitions/Error'}
        },
        '401': {
            'description': 'Unauthorized',
            'schema': {'$ref': '#/definitions/Error'}
        },
        '503': {
            'description': 'Service Unavailable - S3 not configured',
            'schema': {'$ref': '#/definitions/Error'}
        }
    }
})
def generate_upload_urls():
    """Generate presigned URLs for secure file upload to S3"""
    data = request.get_json()
    
    if not data or 'files' not in data or not isinstance(data['files'], list):
        return jsonify({
            'error': 'Invalid request',
            'message': 'Request must contain a "files" array with file metadata'
        }), 400
    
    files = data['files']
    if not files:
        return jsonify({
            'error': 'Empty files list',
            'message': 'At least one file must be provided'
        }), 400
    
    # Check S3 configuration
    # Check AWS configuration
    aws_config = {
        'AWS_ACCESS_KEY_ID': current_app.config.get('AWS_ACCESS_KEY_ID'),
        'AWS_SECRET_ACCESS_KEY': current_app.config.get('AWS_SECRET_ACCESS_KEY'),
        'AWS_S3_BUCKET': current_app.config.get('AWS_S3_BUCKET'),
        'AWS_S3_REGION': current_app.config.get('AWS_S3_REGION')
    }
    current_app.logger.info(f"🔑 Checking AWS config: {', '.join(k for k, v in aws_config.items() if v)}")
    
    if not all([aws_config['AWS_ACCESS_KEY_ID'], aws_config['AWS_SECRET_ACCESS_KEY'], aws_config['AWS_S3_BUCKET']]):
        missing = [k for k, v in aws_config.items() if not v and k != 'AWS_S3_REGION']
        current_app.logger.error(f"❌ Missing AWS config: {', '.join(missing)}")
        return jsonify({
            'error': 'S3 not configured',
            'message': f'AWS S3 configuration is missing: {", ".join(missing)}. Please contact your administrator.'
        }), 503
    
    # Required chatbot validation
    chatbot_id = data.get('chatbot_id')
    if not chatbot_id:
        return jsonify({
            'error': 'Chatbot selection required',
            'message': 'You must select a chatbot before uploading documents. Please choose which chatbot should use these documents.'
        }), 400
    
    chatbot = Chatbot.query.filter_by(
        id=chatbot_id,
        tenant_id=g.tenant_id
    ).first()
    
    if not chatbot:
        return jsonify({
            'error': 'Chatbot not found',
            'message': f'No chatbot found with ID {chatbot_id} in your organization'
        }), 400
    
    try:
        # Initialize S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=current_app.config['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=current_app.config['AWS_SECRET_ACCESS_KEY'],
            region_name=current_app.config['AWS_S3_REGION']
        )
        
        bucket_name = current_app.config['AWS_S3_BUCKET']
        upload_batch_id = str(uuid.uuid4())
        
        upload_results = []
        data_sources = []
        
        for file_info in files:
            # Validate file info
            if not all(key in file_info for key in ['filename', 'content_type', 'size']):
                return jsonify({
                    'error': 'Invalid file info',
                    'message': 'Each file must have filename, content_type, and size'
                }), 400
            
            filename = file_info['filename']
            content_type = file_info['content_type']
            file_size = file_info['size']
            
            # Validate file type
            file_ext = os.path.splitext(filename)[1].lower().lstrip('.')
            if file_ext not in current_app.config['ALLOWED_EXTENSIONS']:
                return jsonify({
                    'error': 'Invalid file type',
                    'message': f'File type "{file_ext}" is not allowed. Allowed types: {list(current_app.config["ALLOWED_EXTENSIONS"])}'
                }), 400
            
            # Validate file size
            max_size = current_app.config['MAX_CONTENT_LENGTH']
            if file_size > max_size:
                return jsonify({
                    'error': 'File too large',
                    'message': f'File "{filename}" ({file_size} bytes) exceeds maximum size of {max_size} bytes'
                }), 400
            
            # Generate unique file key
            file_id = str(uuid.uuid4())
            tenant_id = g.tenant_id
            file_key = f"tenant-{tenant_id}/uploads/{upload_batch_id}/{file_id}-{filename}"
            
            # Generate presigned URL
            presigned_data = s3_client.generate_presigned_post(
                Bucket=bucket_name,
                Key=file_key,
                Fields={
                    'Content-Type': content_type,
                    'x-amz-meta-tenant-id': str(tenant_id),
                    'x-amz-meta-upload-batch': upload_batch_id,
                    'x-amz-meta-original-name': filename
                },
                Conditions=[
                    {'Content-Type': content_type},
                    ['content-length-range', 1, max_size],
                    {'x-amz-meta-tenant-id': str(tenant_id)},
                    {'x-amz-meta-upload-batch': upload_batch_id},
                    {'x-amz-meta-original-name': filename}
                ],
                ExpiresIn=3600  # 1 hour
            )
            
            expires_at = datetime.utcnow() + timedelta(hours=1)
            
            upload_results.append({
                'file_id': file_id,
                'filename': filename,
                'presigned_url': presigned_data['url'],
                'expires_at': expires_at.isoformat(),
                'upload_fields': presigned_data['fields']
            })
            
            # Create data source record
            data_source = DataSource(
                tenant_id=tenant_id,
                chatbot_id=chatbot_id,
                source_type='upload',
                source_name=filename,
                source_url=f"s3://{bucket_name}/{file_key}",
                status='pending',
                meta_data={
                    'file_id': file_id,
                    'upload_batch_id': upload_batch_id,
                    'content_type': content_type,
                    'size': file_size,
                    'original_filename': filename,
                    's3_key': file_key,
                    'expires_at': expires_at.isoformat(),
                    'description': data.get('description', '')
                }
            )
            data_sources.append(data_source)
        
        # Save all data sources to database
        for ds in data_sources:
            db.session.add(ds)
        db.session.commit()
        
        current_app.logger.info(f"📤 Generated {len(upload_results)} upload URLs for tenant {g.tenant_id}, batch {upload_batch_id}")
        
        return jsonify({
            'message': 'Upload URLs generated successfully',
            'upload_batch_id': upload_batch_id,
            'files': upload_results,
            'instructions': {
                'method': 'POST',
                'content_type': 'multipart/form-data',
                'note': 'Upload each file using the provided presigned URL and fields. URLs expire in 1 hour.'
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Error generating upload URLs: {e}")
        return jsonify({
            'error': 'Upload URL generation failed',
            'message': 'An error occurred while generating upload URLs. Please try again.'
        }), 500


@api.route('/datasources/upload/callback', methods=['POST', 'OPTIONS'])
@login_required
@swag_from({
    'tags': ['Data Sources'],
    'summary': 'Callback for completed S3 uploads',
    'description': """
    ### 🔄 Description
    Callback endpoint that triggers AI processing after successful file upload to S3.
    This endpoint should be called by the client after successfully uploading files to S3.
    
    The endpoint will:
    1. Verify the files exist in S3
    2. Trigger AI service processing
    3. Update data source status
    4. Associate processed content with chatbot
    
    ---
    ### 🔑 Authorization
    Requires authentication and files must belong to user's tenant.
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
                'required': ['upload_batch_id', 'completed_files'],
                'properties': {
                    'upload_batch_id': {
                        'type': 'string',
                        'description': 'Upload batch ID from the upload URL generation'
                    },
                    'completed_files': {
                        'type': 'array',
                        'description': 'List of successfully uploaded files',
                        'items': {
                            'type': 'object',
                            'required': ['file_id'],
                            'properties': {
                                'file_id': {'type': 'string'},
                                's3_etag': {'type': 'string', 'description': 'S3 ETag from upload response'}
                            }
                        }
                    }
                }
            }
        }
    ],
    'responses': {
        '200': {
            'description': 'Processing started successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'batch_id': {'type': 'string'},
                    'processing_jobs': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'file_id': {'type': 'string'},
                                'filename': {'type': 'string'},
                                'status': {'type': 'string'},
                                'job_id': {'type': 'string'}
                            }
                        }
                    }
                }
            }
        },
        '400': {'description': 'Bad Request', 'schema': {'$ref': '#/definitions/Error'}},
        '404': {'description': 'Upload batch not found', 'schema': {'$ref': '#/definitions/Error'}}
    }
})
def upload_callback():
    """Process uploaded files after successful S3 upload"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
        
    data = request.get_json()
    
    if not data or 'upload_batch_id' not in data or 'completed_files' not in data:
        return jsonify({
            'error': 'Invalid request',
            'message': 'Request must contain upload_batch_id and completed_files'
        }), 400
    
    upload_batch_id = data['upload_batch_id']
    completed_files = data['completed_files']
    
    # Find data sources for this batch
    current_app.logger.info(f"🔍 Looking for data sources with batch ID {upload_batch_id} for tenant {g.tenant_id}")
    
    data_sources = DataSource.query.filter(
        DataSource.tenant_id == g.tenant_id,
        DataSource.meta_data['upload_batch_id'].as_string() == upload_batch_id,
        DataSource.status == 'pending'
    ).all()
    
    current_app.logger.info(f"📊 Found {len(data_sources)} data sources to process")
    
    if not data_sources:
        return jsonify({
            'error': 'Upload batch not found',
            'message': f'No pending uploads found for batch {upload_batch_id}'
        }), 404
    
    try:
        processing_jobs = []
        
        for file_info in completed_files:
            file_id = file_info['file_id']
            
            # Find matching data source
            data_source = next((ds for ds in data_sources if ds.meta_data.get('file_id') == file_id), None)
            if not data_source:
                current_app.logger.warning(f"⚠️ File ID {file_id} not found in batch {upload_batch_id}")
                continue
            
            # Update data source status
            data_source.status = 'processing'
            data_source.meta_data = {
                **data_source.meta_data,
                's3_etag': file_info.get('s3_etag'),
                'processed_at': datetime.utcnow().isoformat()
            }
            
            # Start AI processing using existing endpoints
            try:
                # LAZY IMPORT: Import services here to avoid circular dependencies
                from ..services import document_service
                from ..services import embedding_service

                current_app.logger.info(f"🤖 Starting AI processing for file: {data_source.source_name}")
                job_id = f"job-{uuid.uuid4()}"
                
                # Get S3 details
                s3_key = data_source.meta_data.get('s3_key')
                bucket_name = current_app.config['AWS_S3_BUCKET']
                
                if not s3_key:
                    raise Exception("S3 key not found in metadata")
                
                # Step 1: Download file from S3
                current_app.logger.info(f"📥 Downloading file from S3: {s3_key}")
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=current_app.config['AWS_ACCESS_KEY_ID'],
                    aws_secret_access_key=current_app.config['AWS_SECRET_ACCESS_KEY'],
                    region_name=current_app.config['AWS_S3_REGION']
                )
                
                # Create temporary file path with safe filename
                import re
                safe_filename = re.sub(r'[^\w\-_\.]', '_', data_source.source_name)  # Replace unsafe chars with underscore
                temp_filename = f"{job_id}_{safe_filename}"
                temp_filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], temp_filename)
                
                # Download from S3
                s3_client.download_file(bucket_name, s3_key, temp_filepath)
                current_app.logger.info(f"✅ Downloaded file to: {temp_filepath}")
                
                # Step 2: Process document directly using file path
                current_app.logger.info(f"🔧 Processing document: {data_source.source_name}")
                
                # Import document processing modules
                from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
                from ..services import text_cleaner_service, processing_service
                
                # Map file extensions to their loaders
                LOADER_MAPPING = {
                    '.pdf': PyPDFLoader,
                    '.txt': TextLoader,
                    '.docx': Docx2txtLoader
                }
                
                # Get file extension and validate
                file_ext = os.path.splitext(temp_filepath)[1].lower()
                if file_ext not in LOADER_MAPPING:
                    raise ValueError(f"Unsupported file type: {file_ext}. Supported types: {list(LOADER_MAPPING.keys())}")
                
                # Load and process document
                loader_class = LOADER_MAPPING[file_ext]
                current_app.logger.info(f"📄 Using {loader_class.__name__} for {file_ext} file")
                
                try:
                    loader = loader_class(temp_filepath)
                    documents = loader.load()
                    if not documents:
                        raise ValueError(f"No content extracted from file: {data_source.source_name}")
                    current_app.logger.info(f"📑 Successfully extracted {len(documents)} document(s)")
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
                current_app.logger.info(f"🧹 Cleaned {len(documents)} document(s)")
                
                # Generate document ID for this processing job
                doc_id = str(uuid.uuid4())
                
                # Chunk the documents
                chunks = processing_service.process_documents_into_chunks(
                    documents=documents,
                    source_name=data_source.source_name,
                    doc_id=doc_id
                )
                
                current_app.logger.info(f"✅ Processed into {len(chunks)} chunks")
                
                # Step 3: Generate embeddings using existing endpoint logic
                current_app.logger.info(f"🧠 Generating embeddings for {len(chunks)} chunks")
                
                # Convert chunks to the format expected by embedding service
                chunk_texts = [chunk.page_content for chunk in chunks]
                embedding_results = embedding_service.generate_embeddings_for_texts(chunk_texts)
                
                # Combine chunks with embeddings
                processed_chunks = []
                openai_embeddings = embedding_results.get("openai_embeddings", [])
                gemini_embeddings = embedding_results.get("gemini_embeddings", [])
                
                for i, chunk in enumerate(chunks):
                    processed_chunk = {
                        "metadata": chunk.metadata,
                        "page_content": chunk.page_content,
                        "embeddings": {}
                    }
                    if openai_embeddings and i < len(openai_embeddings):
                        processed_chunk["embeddings"]["openai"] = openai_embeddings[i]
                    if gemini_embeddings and i < len(gemini_embeddings):
                        processed_chunk["embeddings"]["gemini"] = gemini_embeddings[i]
                    processed_chunks.append(processed_chunk)
                
                current_app.logger.info(f"✅ Generated embeddings for {len(processed_chunks)} chunks")
                
                # Step 4: Store in vector database using existing service
                if current_app.vector_service:
                    current_app.logger.info(f"💾 Storing {len(processed_chunks)} chunks in vector database")
                    provider = current_app.config.get('DEFAULT_EMBEDDING_PROVIDER', 'openai')
                    vector_result = current_app.vector_service.upsert(processed_chunks, provider=provider)
                    current_app.logger.info(f"✅ Stored {vector_result.get('upserted_count', 0)} chunks in vector DB")
                else:
                    current_app.logger.warning("⚠️ Vector service not available, chunks not stored")
                
                # Step 5: Update status to completed
                data_source.status = 'completed'
                data_source.meta_data = {
                    **data_source.meta_data,
                    'processed_chunks': len(processed_chunks),
                    'completed_at': datetime.utcnow().isoformat(),
                    'job_id': job_id,
                    'doc_id': doc_id  # Save doc_id for chunk retrieval
                }
                
                # Clean up temporary file
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
                
                processing_jobs.append({
                    'file_id': file_id,
                    'filename': data_source.source_name,
                    'status': 'completed',
                    'job_id': job_id,
                    'processed_chunks': len(processed_chunks)
                })
                
                current_app.logger.info(f"🎉 Successfully processed {data_source.source_name}: {len(processed_chunks)} chunks")
                
            except Exception as e:
                current_app.logger.error(f"❌ Failed to process file {file_id}: {e}")
                data_source.status = 'failed'
                data_source.meta_data = {
                    **data_source.meta_data,
                    'error': str(e),
                    'failed_at': datetime.utcnow().isoformat()
                }
                processing_jobs.append({
                    'file_id': file_id,
                    'filename': data_source.source_name,
                    'status': 'failed',
                    'job_id': None,
                    'error': str(e)
                })
                
                # Clean up temporary file on error
                temp_filename = f"{job_id}_{data_source.source_name}" if 'job_id' in locals() else f"temp_{data_source.source_name}"
                temp_filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], temp_filename)
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
        
        db.session.commit()
        
        current_app.logger.info(f"✅ Upload callback processed for batch {upload_batch_id}, {len(processing_jobs)} files")
        
        return jsonify({
            'message': 'Files processed successfully',
            'batch_id': upload_batch_id,
            'processing_jobs': processing_jobs
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Error processing upload callback: {e}")
        return jsonify({
            'error': 'Processing failed',
            'message': 'An error occurred while processing uploaded files'
        }), 500


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
        
        # TODO: Delete from S3 if it's a file upload
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
    
    # Check if AI connector is available
    if not current_app.ai_connector:
        return jsonify({
            'error': 'AI service unavailable',
            'message': 'Web crawling service is currently unavailable. Please try again later.'
        }), 503
    
    try:
        crawl_job_id = str(uuid.uuid4())
        tenant_id = g.tenant_id
        
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
        
        # Start web content extraction using Gemini AI
        try:
            current_app.logger.info(f"🕷️ Starting web content extraction for: {url}")
            
            # Import the web extraction service
            from ..services.web_extraction_service import WebExtractionService
            
            # Create extraction service instance
            web_extractor = WebExtractionService()
            
            # Check if user wants full site crawl (default: true for comprehensive extraction)
            full_crawl = data.get('full_crawl', True)
            
            if full_crawl:
                current_app.logger.info(f"🕷️ Starting FULL WEBSITE CRAWL for: {url}")
                
                # Create progress callback for real-time updates
                def progress_callback(progress_data):
                    try:
                        socketio = getattr(current_app, 'socketio', None)
                        if socketio:
                            socketio.emit('crawl_progress', {
                                'data_source_id': data_source.id,
                                'chatbot_id': chatbot_id,
                                **progress_data
                            }, room=f"user_{g.user_id}", namespace='/')
                            current_app.logger.debug(f"📊 Progress: {progress_data['progress_percent']}%")
                    except Exception as e:
                        current_app.logger.warning(f"Progress update failed: {e}")
                
                # Extract content from entire website using full crawling
                extraction_result = web_extractor.crawl_full_website(
                    url,
                    description=data.get('description', ''),
                    tenant_id=tenant_id,
                    user_id=g.user_id,
                    progress_callback=progress_callback
                )
            else:
                current_app.logger.info(f"📄 Starting SINGLE PAGE extraction for: {url}")
                # Extract content from single page only
                extraction_result = web_extractor.extract_content_from_url(
                    url=url,
                    description=data.get('description', f'Content extraction for chatbot training'),
                    tenant_id=g.tenant_id,
                    user_id=g.user_id
                )
            
            if not extraction_result['success']:
                raise Exception(f"Content extraction failed: {extraction_result['error']}")
            
            if extraction_result and extraction_result.get('success'):
                content = extraction_result.get('content')
                
                if content:
                    from langchain_core.documents import Document
                    
                    metadata = extraction_result.get('metadata', {})
                    metadata.update({
                        'source': url,
                        'source_type': 'crawl',
                        'chatbot_id': chatbot_id,
                        'tenant_id': g.tenant_id,
                        'user_id': g.user_id,
                        'extraction_method': extraction_result.get('extraction_method', 'unknown'),
                        'crawl_stats': extraction_result.get('stats', {})
                    })

                    document = Document(page_content=content, metadata=metadata)
                    
                    # Process the document through the existing AI pipeline
                    _process_web_content_async(current_app._get_current_object(), db, data_source.id, document)
                    
                    estimated_completion = datetime.utcnow() + timedelta(minutes=2)
                    current_app.logger.info(f"🚀 Web extraction and processing started for {url}")
            
        except Exception as e:
            # Update data source with error
            data_source.status = 'failed'
            error_message = str(e)
            
            # Provide user-friendly error messages
            if "timeout" in error_message.lower():
                user_error = f"The website took too long to respond. This may be due to the website's anti-bot protection or server issues. Try a different page from the same domain."
            elif "failed to fetch page content" in error_message.lower():
                user_error = f"Unable to access the website. The site may be blocking automated requests or experiencing issues."
            elif "content extraction failed" in error_message.lower():
                user_error = f"Could not extract meaningful content from the page. Try a different URL with more text content."
            elif "content extraction returned empty content" in error_message.lower():
                user_error = f"The website content could not be extracted. This may be due to the site's structure or anti-bot protection."
            elif "api" in error_message.lower() and "key" in error_message.lower():
                user_error = f"Web extraction failed: API keys not configured. Please set OPENAI_API_KEY or GEMINI_API_KEY environment variables and restart the application."
            else:
                user_error = f"Web extraction failed: {error_message}"
            
            try:
                data_source.meta_data = {
                    **data_source.meta_data,
                    'error': error_message,
                    'user_error': user_error,
                    'failed_at': datetime.utcnow().isoformat()
                }
                db.session.commit()
            except Exception as db_error:
                current_app.logger.error(f"❌ Failed to update data source metadata: {db_error}")
        
            # Return user-friendly error
            return jsonify({
                'error': 'Web extraction failed',
                'message': user_error,
                'data_source_id': data_source.id if 'data_source' in locals() else None,
                'status': 'failed'
            }), 400
        
        return jsonify({
            'message': 'Web content extraction started successfully using Gemini AI',
            'crawl_job_id': crawl_job_id,
            'data_source_id': data_source.id,
            'url': url,
            'status': 'crawling',
            'estimated_completion': estimated_completion.isoformat(),
            'progress_url': f'/api/v1/datasources/{data_source.id}/status'
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

    if data_source.status != 'completed':
        return jsonify({
            'error': 'Processing incomplete',
            'message': f'Data source is in {data_source.status} state. Only completed sources can be inspected.'
        }), 400

    try:
        # Get chunks from vector store
        provider = current_app.config.get('DEFAULT_EMBEDDING_PROVIDER', 'openai')
        chunks = []
        
        if current_app.vector_service:
            # Get document ID from metadata
            doc_id = data_source.meta_data.get('doc_id')
            if not doc_id:
                return jsonify({
                    'error': 'Document ID not found',
                    'message': 'Could not find document ID in metadata'
                }), 404
            
            # Query vector store for chunks with this doc_id
            chunks = current_app.vector_service.get_chunks_by_doc_id(doc_id, provider=provider)
            
            # Format response
            chunk_data = []
            for chunk in chunks:
                chunk_info = {
                    'content': chunk.get('page_content', ''),
                    'metadata': chunk.get('metadata', {}),
                    'embedding_stats': {
                        'provider': provider,
                        'vector_length': len(chunk.get('embeddings', {}).get(provider, [])),
                        'has_embedding': bool(chunk.get('embeddings', {}).get(provider))
                    }
                }
                chunk_data.append(chunk_info)
            
            return jsonify({
                'data_source_id': data_source_id,
                'source_name': data_source.source_name,
                'chunk_count': len(chunk_data),
                'chunks': chunk_data,
                'embedding_provider': provider
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
                            raise e # Re-raise to be caught by the main handler

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
                
                # STEP 3: Chunking
                print("🔍 [BG-PRINT] STEP 3: Chunking document.")
                doc_id = str(uuid.uuid4())
                chunks = processing_service.process_documents_into_chunks(
                    documents=[document],
                    source_name=data_source.source_name,
                    doc_id=doc_id
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
                openai_embeddings = embedding_results.get("openai_embeddings", [])
                gemini_embeddings = embedding_results.get("gemini_embeddings", [])
                
                # Combine chunks with embeddings
                for i, chunk in enumerate(chunks):
                    chunk_data = {
                        "content": chunk.page_content,
                        "metadata": chunk.metadata,
                        "openai_embedding": openai_embeddings[i] if openai_embeddings and i < len(openai_embeddings) else None,
                        "gemini_embedding": gemini_embeddings[i] if gemini_embeddings and i < len(gemini_embeddings) else None
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
                            # Use OpenAI embedding if available, otherwise Gemini
                            embedding = chunk_data.get("openai_embedding") or chunk_data.get("gemini_embedding")
                            if embedding:
                                vector_id = f"{doc_id}_{i}"
                                vectors_to_store.append({
                                    "id": vector_id,
                                    "values": embedding,
                                    "metadata": {
                                        **chunk_data["metadata"],
                                        "page_content": chunk_data["content"],  # ✅ Use page_content key for consistency
                                        "doc_id": doc_id,
                                        "chunk_index": i
                                    }
                                })
                        
                        # Store vectors
                        if vectors_to_store:
                            vector_service.add_vectors(vectors_to_store)
                            current_app.logger.info(f"💾 [BG] Stored {len(vectors_to_store)} vectors in vector database")
                        
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
                        socketio.emit('crawl_completed', {
                            'data_source_id': data_source_id,
                            'chatbot_id': data_source.chatbot_id,
                            'status': 'completed',
                            'message': f'Successfully crawled and processed {data_source.source_name}',
                            'stats': data_source.meta_data.get('crawl_stats', {})
                        }, room=f"user_{data_source.user_id}", namespace='/')
                        current_app.logger.info(f"📡 [BG] Sent WebSocket crawl_completed notification to user_{data_source.user_id}")
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
                    except:
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
    from ..services import document_service, embedding_service, text_cleaner_service, processing_service

    with app.app_context():
        data_source = DataSource.query.get(data_source_id)
        if not data_source:
            app.logger.error(f"Background task failed: DataSource {data_source_id} not found.")
            return

        try:
            app.logger.info(f"🤖 [BG] Starting AI processing for file: {data_source.source_name}")
            
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
            from ..services import text_cleaner_service
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
            doc_id = str(uuid.uuid4())
            
            # Chunk the documents
            from ..services import processing_service
            chunks = processing_service.process_documents_into_chunks(
                documents=documents,
                source_name=data_source.source_name,
                doc_id=doc_id
            )

            app.logger.info(f"✅ [BG] Processed into {len(chunks)} chunks")

            # Step 3: Generate embeddings
            chunk_texts = [chunk.page_content for chunk in chunks]
            embedding_results = embedding_service.generate_embeddings_for_texts(chunk_texts)
            
            processed_chunks = []
            openai_embeddings = embedding_results.get("openai_embeddings", [])
            gemini_embeddings = embedding_results.get("gemini_embeddings", [])
            
            for i, chunk in enumerate(chunks):
                processed_chunk = {
                    "metadata": chunk.metadata,
                    "page_content": chunk.page_content,
                    "embeddings": {}
                }
                if openai_embeddings and i < len(openai_embeddings):
                    processed_chunk["embeddings"]["openai"] = openai_embeddings[i]
                if gemini_embeddings and i < len(gemini_embeddings):
                    processed_chunk["embeddings"]["gemini"] = gemini_embeddings[i]
                processed_chunks.append(processed_chunk)
            
            app.logger.info(f"✅ [BG] Generated embeddings for {len(processed_chunks)} chunks")

            # Step 4: Store in vector database
            if app.vector_service:
                provider = app.config.get('DEFAULT_EMBEDDING_PROVIDER', 'openai')
                vector_result = app.vector_service.upsert(processed_chunks, provider=provider)
                app.logger.info(f"✅ [BG] Stored {vector_result.get('upserted_count', 0)} chunks in vector DB")
            else:
                app.logger.warning("⚠️ [BG] Vector service not available, chunks not stored")

            # Step 5: Update status to completed
            data_source.status = 'completed'
            data_source.meta_data['processed_chunks'] = len(processed_chunks)
            data_source.meta_data['completed_at'] = datetime.utcnow().isoformat()
            data_source.meta_data['doc_id'] = doc_id  # Save doc_id for chunk retrieval
            
            # No need to clean up the temp file here as it's the permanent local storage for now

        except Exception as e:
            app.logger.error(f"❌ [BG] Failed to process file {data_source.id}: {e}", exc_info=True)
            data_source.status = 'failed'
            data_source.meta_data['error'] = str(e)
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
        'metadata': data_source.meta_data or {}
    }
