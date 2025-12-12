// frontend/src/services/datasource.service.js

import authService from './auth.service';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';

class DataSourceService {
  constructor() {
    this.baseURL = API_BASE_URL;
    this.uploadProgress = new Map(); // Track upload progress
    // Initialize auth headers if user is already logged in
    const currentUser = authService.getCurrentUser();
    if (currentUser?.token) {
      authService.setupAxiosInterceptors(currentUser.token);
    }
  }

  /**
   * Get authorization headers with JWT token
   */
  getAuthHeaders() {
    const currentUser = authService.getCurrentUser();
    if (!currentUser || !currentUser.token) {
      throw new Error('Authentication required');
    }
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${currentUser.token}`,
    };
  }

  /**
   * Handle API response and errors
   */
  async handleResponse(response) {
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || `HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Get supported file types and limits
   */
  getSupportedFileTypes() {
    return {
      types: ['pdf', 'docx', 'doc', 'txt'],
      maxSize: 16 * 1024 * 1024, // 16MB
      maxSizeDisplay: '16MB',
      mimeTypes: {
        'pdf': 'application/pdf',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'doc': 'application/msword',
        'txt': 'text/plain'
      }
    };
  }

  /**
   * Validate file before upload
   * @param {File} file - File to validate
   * @returns {Object} Validation result
   */
  validateFile(file) {
    const config = this.getSupportedFileTypes();
    const errors = [];

    // Check file size
    if (file.size > config.maxSize) {
      errors.push(`File size (${this.formatFileSize(file.size)}) exceeds maximum allowed size (${config.maxSizeDisplay})`);
    }

    // Check file type
    const extension = file.name.split('.').pop().toLowerCase();
    if (!config.types.includes(extension)) {
      errors.push(`File type "${extension}" is not supported. Supported types: ${config.types.join(', ')}`);
    }

    // Check MIME type
    const expectedMimeType = config.mimeTypes[extension];
    if (expectedMimeType && file.type !== expectedMimeType) {
      console.warn(`MIME type mismatch: expected ${expectedMimeType}, got ${file.type}`);
    }

    return {
      isValid: errors.length === 0,
      errors
    };
  }

  /**
   * Format file size for display
   * @param {number} bytes - File size in bytes
   * @returns {string} Formatted size
   */
  formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  /**
   * Generate presigned URLs for file upload
   * @param {Array<File>} files - Files to upload
   * @param {Object} options - Upload options (chatbot_id, description)
   * @returns {Promise<Object>} Upload URLs and metadata
   */
  async generateUploadUrls(files, options = {}) {
    try {
      // Validate all files first
      const validationErrors = [];
      files.forEach((file, index) => {
        const validation = this.validateFile(file);
        if (!validation.isValid) {
          validationErrors.push(`File ${index + 1} (${file.name}): ${validation.errors.join(', ')}`);
        }
      });

      if (validationErrors.length > 0) {
        throw new Error(`File validation failed:\n${validationErrors.join('\n')}`);
      }

      // Prepare file metadata
      const fileMetadata = files.map(file => ({
        filename: file.name,
        content_type: file.type,
        size: file.size
      }));

      const requestData = {
        files: fileMetadata,
        ...options
      };

      const response = await fetch(`${this.baseURL}/datasources/upload`, {
        method: 'POST',
        headers: this.getAuthHeaders(),
        body: JSON.stringify(requestData),
      });

      const result = await this.handleResponse(response);
      console.log(`📤 Generated upload URLs for ${files.length} files`);
      return result;
    } catch (error) {
      console.error('❌ Error generating upload URLs:', error.message);
      throw error;
    }
  }

  /**
   * Complete file upload process using S3 (generate URLs, upload, notify)
   * @param {Array<File>} files - Files to upload
   * @param {Object} options - Upload options (chatbot_id, description)
   * @param {Function} onProgress - Progress callback (fileIndex, progress, fileName)
   * @returns {Promise<Object>} Complete upload result
   */
  async uploadFiles(files, options = {}, onProgress = null) {
    try {
      // Step 1: Generate upload URLs
      const uploadInfo = await this.generateUploadUrls(files, options);
      
      // Step 2: Upload each file to S3
      const uploadResults = [];
      
      console.log(`[S3 UPLOAD] Starting to upload ${files.length} files for batch ${uploadInfo.upload_batch_id}`);

      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const fileUploadInfo = uploadInfo.files[i];
        
        const fileProgress = (percent, loaded, total) => {
          if (onProgress) {
            onProgress(i, percent, file.name, loaded, total);
          }
        };

        const uploadResult = await this.uploadFileToS3(file, fileUploadInfo, fileProgress);
        uploadResults.push(uploadResult);
      }

      console.log(`[S3 UPLOAD] Finished uploading ${uploadResults.length} files for batch ${uploadInfo.upload_batch_id}`);

      // Step 3: Notify backend of completion
      const completedFiles = uploadResults.map(result => ({
        file_id: result.file_id,
        s3_etag: result.etag
      }));

      console.log(`[S3 NOTIFY] Preparing to notify backend for batch ${uploadInfo.upload_batch_id}`);
      const processingResult = await this.notifyUploadComplete(
        uploadInfo.upload_batch_id, 
        completedFiles
      );

      return {
        upload_batch_id: uploadInfo.upload_batch_id,
        uploaded_files: uploadResults,
        processing_jobs: processingResult.processing_jobs,
        success: true
      };
    } catch (error) {
      console.error('❌ Complete S3 upload process failed:', error.message);
      throw error;
    }
  }

  /**
   * Upload a single file to S3 using presigned URL
   * @param {File} file - File to upload
   * @param {Object} uploadInfo - Upload information from backend
   * @param {Function} onProgress - Progress callback
   * @returns {Promise<Object>} Upload result
   */
  async uploadFileToS3(file, uploadInfo, onProgress = null) {
    try {
      const formData = new FormData();
      
      // Add upload fields (required by S3)
      if (uploadInfo.upload_fields) {
        Object.entries(uploadInfo.upload_fields).forEach(([key, value]) => {
          formData.append(key, value);
        });
      }
      
      // Add the file (must be last)
      formData.append('file', file);

      console.log(`[S3] Uploading ${file.name} to S3...`);

      // Use XMLHttpRequest for progress tracking
      const uploadResult = await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();

        // Track upload progress
        if (onProgress) {
          xhr.upload.addEventListener('progress', (event) => {
            if (event.lengthComputable) {
              const percentComplete = (event.loaded / event.total) * 100;
              onProgress(percentComplete, event.loaded, event.total);
            }
          });
        }

        xhr.addEventListener('load', () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            console.log(`[S3] ✅ Successfully uploaded ${file.name}`);
            resolve({
              file_id: uploadInfo.file_id,
              filename: file.name,
              etag: xhr.getResponseHeader('ETag')?.replace(/"/g, '') || 'unknown',
              status: 'uploaded'
            });
          } else {
            console.error(`[S3] ❌ Failed to upload ${file.name}:`, xhr.responseText);
            reject(new Error(`S3 upload failed with status ${xhr.status}: ${xhr.responseText}`));
          }
        });

        xhr.addEventListener('error', () => {
          console.error(`[S3] ❌ Network error uploading ${file.name}`);
          reject(new Error('S3 upload failed due to a network error.'));
        });

        xhr.open('POST', uploadInfo.presigned_url);
        xhr.send(formData);
      });

      return uploadResult;
    } catch (error) {
      console.error(`[S3] ❌ Error uploading ${file.name} to S3:`, error.message);
      throw error;
    }
  }

  /**
   * Notify backend that S3 upload is complete
   * @param {string} uploadBatchId - Upload batch ID
   * @param {Array} completedFiles - Array of completed file info
   * @returns {Promise<Object>} Processing result
   */
  async notifyUploadComplete(uploadBatchId, completedFiles) {
    try {
      console.log(`[S3 NOTIFY] Notifying backend of completed upload for batch ${uploadBatchId}`);
      
      const requestData = {
        upload_batch_id: uploadBatchId,
        completed_files: completedFiles
      };

      const response = await fetch(`${this.baseURL}/datasources/upload/callback`, {
        method: 'POST',
        headers: this.getAuthHeaders(),
        body: JSON.stringify(requestData),
      });

      const result = await this.handleResponse(response);
      console.log(`[S3 NOTIFY] ✅ Backend notified successfully for batch ${uploadBatchId}`);
      return result;
    } catch (error) {
      console.error(`[S3 NOTIFY] ❌ Error notifying backend for batch ${uploadBatchId}:`, error.message);
      throw error;
    }
  }

  /**
   * (DEPRECATED FOR LOCAL TESTING)
   * Complete file upload process (generate URLs, upload, notify)
   * @param {Array<File>} files - Files to upload
   * @param {Object} options - Upload options
   * @param {Function} onProgress - Progress callback (fileIndex, progress, fileName)
   * @returns {Promise<Object>} Complete upload result
   */
  /*
  async uploadFiles_S3(files, options = {}, onProgress = null) {
    try {
      // Step 1: Generate upload URLs
      const uploadInfo = await this.generateUploadUrls(files, options);
      
      // Step 2: Upload each file to S3
      const uploadResults = [];
      
      console.log(`[UPLOAD] Starting to upload ${files.length} files for batch ${uploadInfo.upload_batch_id}`);

      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const fileUploadInfo = uploadInfo.files[i];
        
        const fileProgress = (percent, loaded, total) => {
          if (onProgress) {
            onProgress(i, percent, file.name, loaded, total);
          }
        };

        const uploadResult = await this.uploadFileToS3(file, fileUploadInfo, fileProgress);
        uploadResults.push(uploadResult);
      }

      console.log(`[UPLOAD] Finished uploading ${uploadResults.length} files for batch ${uploadInfo.upload_batch_id}`);

      // Step 3: Notify backend of completion
      const completedFiles = uploadResults.map(result => ({
        file_id: result.file_id,
        s3_etag: result.etag
      }));

      // No longer suppressing errors from the callback
      console.log(`[NOTIFY] Preparing to notify backend for batch ${uploadInfo.upload_batch_id}`);
      const processingResult = await this.notifyUploadComplete(
        uploadInfo.upload_batch_id, 
        completedFiles
      );

      return {
        upload_batch_id: uploadInfo.upload_batch_id,
        uploaded_files: uploadResults,
        processing_jobs: processingResult.processing_jobs,
        success: true
      };
    } catch (error) {
      console.error('❌ Complete upload process failed:', error.message);
      throw error;
    }
  }
  */

  /**
   * Trigger web crawling for a URL
   * @param {string} url - URL to crawl
   * @param {Object} options - Crawling options
   * @returns {Promise<Object>} Crawl job info
   */
  async crawlWebsite(url, options = {}) {
    try {
      // Validate URL
      if (!this.isValidUrl(url)) {
        throw new Error('Please provide a valid HTTP or HTTPS URL');
      }

      const requestData = {
        url: url.trim(),
        ...options
      };

      const response = await fetch(`${this.baseURL}/datasources/crawl`, {
        method: 'POST',
        headers: this.getAuthHeaders(),
        body: JSON.stringify(requestData),
      });

      const result = await this.handleResponse(response);
      console.log(`🕷️ Web crawling started for: ${url}`);
      return result;
    } catch (error) {
      console.error('❌ Error starting web crawl:', error.message);
      throw error;
    }
  }

  /**
   * Validate URL format
   * @param {string} url - URL to validate
   * @returns {boolean} Is valid URL
   */
  isValidUrl(url) {
    try {
      const urlObj = new URL(url);
      return urlObj.protocol === 'http:' || urlObj.protocol === 'https:';
    } catch {
      return false;
    }
  }

  /**
   * Get list of data sources with filters
   * @param {Object} options - Query options
   * @returns {Promise<Object>} Data sources list
   */
  async getDataSources(options = {}) {
    try {
      const queryParams = new URLSearchParams();
      
      // Add pagination
      if (options.page) queryParams.append('page', options.page);
      if (options.per_page) queryParams.append('per_page', options.per_page);
      
      // Add filters
      if (options.source_type) queryParams.append('source_type', options.source_type);
      if (options.status) queryParams.append('status', options.status);
      if (options.chatbot_id) queryParams.append('chatbot_id', options.chatbot_id);

      const url = `${this.baseURL}/datasources${queryParams.toString() ? `?${queryParams}` : ''}`;
      const response = await fetch(url, {
        method: 'GET',
        headers: this.getAuthHeaders(),
      });

      const result = await this.handleResponse(response);
      console.log(`📊 Retrieved ${result.data_sources.length} data sources`);
      return result;
    } catch (error) {
      console.error('❌ Error fetching data sources:', error.message);
      throw error;
    }
  }

  /**
   * Get data source processing status
   * @param {number} dataSourceId - Data source ID
   * @returns {Promise<Object>} Status information
   */
  async getDataSourceStatus(dataSourceId) {
    try {
      const response = await fetch(`${this.baseURL}/datasources/${dataSourceId}/status`, {
        method: 'GET',
        headers: this.getAuthHeaders(),
      });

      const result = await this.handleResponse(response);
      return result;
    } catch (error) {
      console.error(`❌ Error fetching status for data source ${dataSourceId}:`, error.message);
      throw error;
    }
  }

  /**
   * Poll data source status until completion
   * @param {number} dataSourceId - Data source ID
   * @param {Function} onStatusUpdate - Status update callback
   * @param {number} maxAttempts - Maximum polling attempts
   * @returns {Promise<Object>} Final status
   */
  async pollDataSourceStatus(dataSourceId, onStatusUpdate = null, maxAttempts = 30) {
    let attempts = 0;
    
    const poll = async () => {
      try {
        const status = await this.getDataSourceStatus(dataSourceId);
        
        if (onStatusUpdate) {
          onStatusUpdate(status);
        }

        // Check if processing is complete
        if (status.status === 'completed' || status.status === 'failed') {
          return status;
        }

        attempts++;
        if (attempts >= maxAttempts) {
          throw new Error('Polling timeout: Processing is taking longer than expected');
        }

        // Wait 2 seconds before next poll
        await new Promise(resolve => setTimeout(resolve, 2000));
        return poll();
      } catch (error) {
        console.error('❌ Error polling data source status:', error.message);
        throw error;
      }
    };

    return poll();
  }

  /**
   * Get crawling options template
   * @returns {Object} Default crawling options
   */
  getDefaultCrawlOptions() {
    return {
      max_depth: 1,
      follow_links: false,
      content_selectors: ['article', '.content', 'main', '.post'],
      exclude_selectors: ['.ads', '.sidebar', 'nav', 'header', 'footer', '.comments']
    };
  }

  /**
   * Get data source type information
   * @returns {Object} Data source types and their descriptions
   */
  getDataSourceTypes() {
    return {
      upload: {
        label: 'File Upload',
        description: 'Upload documents (PDF, DOCX, TXT)',
        icon: '📄'
      },
      crawl: {
        label: 'Web Crawling',
        description: 'Extract content from websites',
        icon: '🕷️'
      },
      api: {
        label: 'API Integration',
        description: 'Connect external data sources',
        icon: '🔗'
      }
    };
  }

  /**
   * Get processing status information
   * @returns {Object} Status types and their descriptions
   */
  getProcessingStatuses() {
    return {
      pending: {
        label: 'Pending',
        description: 'Waiting to be processed',
        color: 'orange',
        icon: '⏳'
      },
      processing: {
        label: 'Processing',
        description: 'Currently being processed',
        color: 'blue',
        icon: '⚙️'
      },
      completed: {
        label: 'Completed',
        description: 'Successfully processed',
        color: 'green',
        icon: '✅'
      },
      failed: {
        label: 'Failed',
        description: 'Processing failed',
        color: 'red',
        icon: '❌'
      }
    };
  }

  /**
   * Get processed chunks for a data source
   * @param {number} dataSourceId - ID of data source
   * @returns {Promise<Object>} Chunks data
   */
  async getDataSourceChunks(dataSourceId) {
    try {
      const response = await fetch(`${this.baseURL}/datasources/${dataSourceId}/chunks`, {
        method: 'GET',
        headers: this.getAuthHeaders(),
      });

      const result = await this.handleResponse(response);
      console.log(`📚 Retrieved ${result.chunk_count} chunks for data source ${dataSourceId}`);
      return result;
    } catch (error) {
      console.error('❌ Error fetching chunks:', error.message);
      throw error;
    }
  }

  /**
   * Get knowledge base statistics for a chatbot
   * @param {number} chatbotId - ID of chatbot
   * @returns {Promise<Object>} Knowledge base stats
   */
  async getChatbotKnowledgeStats(chatbotId) {
    try {
      const response = await this.getDataSources({
        chatbot_id: chatbotId,
        status: 'completed',
        per_page: 100
      });

      const completedSources = response.data_sources || [];
      const totalChunks = completedSources.reduce((sum, source) => {
        return sum + (source.metadata?.processed_chunks || 0);
      }, 0);

      return {
        total_sources: completedSources.length,
        total_chunks: totalChunks,
        sources: completedSources
      };
    } catch (error) {
      console.error('❌ Error fetching chatbot knowledge stats:', error.message);
      return { total_sources: 0, total_chunks: 0, sources: [] };
    }
  }

  /**
   * Delete a data source
   * @param {number} dataSourceId - ID of data source to delete
   * @returns {Promise<Object>} Delete result
   */
  async deleteDataSource(dataSourceId) {
    try {
      const response = await fetch(`${this.baseURL}/datasources/${dataSourceId}`, {
        method: 'DELETE',
        headers: this.getAuthHeaders(),
      });

      const result = await this.handleResponse(response);
      console.log(`🗑️ Deleted data source ${dataSourceId}`);
      return result;
    } catch (error) {
      console.error('❌ Error deleting data source:', error.message);
      throw error;
    }
  }
}

// Export singleton instance
export const dataSourceService = new DataSourceService();
