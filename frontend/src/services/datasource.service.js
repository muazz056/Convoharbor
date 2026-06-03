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
   * Upload files directly to the backend for Cloudinary processing
   * @param {Array<File>} files - Files to upload
   * @param {Object} options - Upload options (chatbot_id, description)
   * @param {Function} onProgress - Progress callback (fileIndex, progress, fileName, loaded, total)
   * @returns {Promise<Object>} Upload result with batch info and processing jobs
   */
  async uploadFiles(files, options = {}, onProgress = null) {
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

      const formData = new FormData();
      formData.append('chatbot_id', options.chatbot_id);
      if (options.description) formData.append('description', options.description);
      
      files.forEach(file => {
        formData.append('files', file, file.name);
      });

      const headers = this.getAuthHeaders();
      // Remove Content-Type so fetch/browser sets it with boundary for FormData
      delete headers['Content-Type'];

      const response = await fetch(`${this.baseURL}/datasources/upload`, {
        method: 'POST',
        headers,
        body: formData,
      });

      const result = await this.handleResponse(response);
      console.log(`📤 Uploaded ${files.length} files for chatbot ${options.chatbot_id}`);
      
      // Start poll for processing progress
      this._pollProcessingProgress(result.upload_batch_id, result.data_sources, onProgress);
      
      return result;
    } catch (error) {
      console.error('❌ Error uploading files:', error.message);
      throw error;
    }
  }

  /**
   * Poll backend for file processing progress
   */
  async _pollProcessingProgress(uploadBatchId, dataSources, onProgress) {
    try {
      for (let i = 0; i < 60; i++) { // Poll up to 5 min (60 × 5s)
        await new Promise(resolve => setTimeout(resolve, 5000));
        
        const response = await fetch(`${this.baseURL}/datasources?upload_batch_id=${uploadBatchId}`, {
          headers: this.getAuthHeaders()
        });
        
        if (!response.ok) continue;
        
        const result = await response.json();
        const sources = result.data_sources || [];
        
        if (sources.length > 0) {
          let completed = sources.filter(s => s.status === 'completed').length;
          let failed = sources.filter(s => s.status === 'failed').length;
          let processing = sources.filter(s => s.status === 'processing').length;
          let total = sources.length;
          
          if (onProgress) {
            onProgress(-1, total > 0 ? Math.round((completed / total) * 100) : 0, 
                       `${completed}/${total} completed, ${processing} processing, ${failed} failed`);
          }
          
          if (completed + failed === total) break; // All done
        }
      }
    } catch (e) {
      console.warn('⚠️ Processing poll interrupted:', e.message);
    }
  }

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
