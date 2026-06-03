// frontend/src/services/chatbot.service.js

import axios from 'axios';
import authService from './auth.service';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';

class ChatbotService {
  constructor() {
    this.baseURL = API_BASE_URL;
    // Initialize auth headers if user is already logged in
    const currentUser = authService.getCurrentUser();
    if (currentUser?.token) {
      authService.setupAxiosInterceptors(currentUser.token);
    }
  }

  /**
   * Set authorization token for API requests
   */
  setAuthToken(token) {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      console.log('✅ Auth token set for chatbot service');
    } else {
      delete axios.defaults.headers.common['Authorization'];
      console.log('⚠️ Auth token removed from chatbot service');
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
   * Create a new chatbot
   * @param {Object} chatbotData - Chatbot configuration
   * @returns {Promise<Object>} Created chatbot data
   */
  async createChatbot(chatbotData) {
    try {
      const response = await fetch(`${this.baseURL}/chatbots`, {
        method: 'POST',
        headers: this.getAuthHeaders(),
        body: JSON.stringify(chatbotData),
      });

      const result = await this.handleResponse(response);
      console.log('✅ Chatbot created successfully:', result.chatbot.name);
      return result;
    } catch (error) {
      console.error('❌ Error creating chatbot:', error.message);
      throw error;
    }
  }

  /**
   * Get ALL chatbots across all tenants (Super Admin only)
   * @param {string|Object} queryParamsOrOptions - Query parameters string or options object
   * @returns {Promise<Object>} All chatbots list with pagination and filters
   */
  async getAllChatbots(queryParamsOrOptions = {}) {
    try {
      let queryParams;
      
      // Support both string query params and options object for backward compatibility
      if (typeof queryParamsOrOptions === 'string') {
        queryParams = queryParamsOrOptions;
      } else {
        const options = queryParamsOrOptions;
        const params = new URLSearchParams();
        
        // Add pagination
        if (options.page) params.append('page', options.page);
        if (options.per_page) params.append('per_page', options.per_page);
        
        // Add filters
        if (options.type) params.append('type', options.type);
        if (options.status) params.append('status', options.status);
        if (options.email) params.append('email', options.email);
        if (options.search) params.append('search', options.search);
        
        queryParams = params.toString();
      }

      const url = `${this.baseURL}/chatbots/all${queryParams ? `?${queryParams}` : ''}`;
      const response = await fetch(url, {
        method: 'GET',
        headers: this.getAuthHeaders(),
      });

      const result = await this.handleResponse(response);
      console.log(`📋 Retrieved ${result.chatbots?.length || 0} chatbots (all tenants)`);
      return result;
    } catch (error) {
      console.error('❌ Error fetching all chatbots:', error.message);
      throw error;
    }
  }

  /**
   * Get list of chatbots with optional filters
   * @param {Object} options - Query options (page, per_page, type, status)
   * @returns {Promise<Object>} Chatbots list with pagination
   */
  async getChatbots(options = {}) {
    try {
      const queryParams = new URLSearchParams();
      
      // Add pagination
      if (options.page) queryParams.append('page', options.page);
      if (options.per_page) queryParams.append('per_page', options.per_page);
      
      // Add filters
      if (options.type) queryParams.append('type', options.type);
      if (options.status) queryParams.append('status', options.status);

      const url = `${this.baseURL}/chatbots${queryParams.toString() ? `?${queryParams}` : ''}`;
      const response = await fetch(url, {
        method: 'GET',
        headers: this.getAuthHeaders(),
      });

      const result = await this.handleResponse(response);
      console.log(`📋 Retrieved ${result.chatbots.length} chatbots`);
      return result;
    } catch (error) {
      console.error('❌ Error fetching chatbots:', error.message);
      throw error;
    }
  }

  /**
   * Get specific chatbot by ID (Super Admin - any tenant)
   * @param {number} chatbotId - Chatbot ID
   * @returns {Promise<Object>} Chatbot details
   */
  async getChatbotAdmin(chatbotId) {
    try {
      const response = await fetch(`${this.baseURL}/chatbots/${chatbotId}/admin`, {
        method: 'GET',
        headers: this.getAuthHeaders(),
      });

      const result = await this.handleResponse(response);
      console.log('🔍 Retrieved chatbot (admin):', result.name);
      return result;
    } catch (error) {
      console.error(`❌ Error fetching chatbot ${chatbotId} (admin):`, error.message);
      throw error;
    }
  }

  /**
   * Get specific chatbot by ID
   * @param {number} chatbotId - Chatbot ID
   * @returns {Promise<Object>} Chatbot details
   */
  async getChatbot(chatbotId) {
    try {
      const response = await fetch(`${this.baseURL}/chatbots/${chatbotId}`, {
        method: 'GET',
        headers: this.getAuthHeaders(),
      });

      const result = await this.handleResponse(response);
      console.log('🔍 Retrieved chatbot:', result.name);
      return result;
    } catch (error) {
      console.error(`❌ Error fetching chatbot ${chatbotId}:`, error.message);
      throw error;
    }
  }

  /**
   * Update chatbot configuration (Super Admin - any tenant)
   * @param {number} chatbotId - Chatbot ID
   * @param {Object} updateData - Updated chatbot data
   * @returns {Promise<Object>} Updated chatbot data
   */
  async updateChatbotAdmin(chatbotId, updateData) {
    try {
      const response = await fetch(`${this.baseURL}/chatbots/${chatbotId}/admin`, {
        method: 'PUT',
        headers: this.getAuthHeaders(),
        body: JSON.stringify(updateData),
      });

      const result = await this.handleResponse(response);
      console.log('✏️ Chatbot updated successfully (admin):', result.chatbot.name);
      return result;
    } catch (error) {
      console.error(`❌ Error updating chatbot ${chatbotId} (admin):`, error.message);
      throw error;
    }
  }

  /**
   * Update chatbot configuration
   * @param {number} chatbotId - Chatbot ID
   * @param {Object} updateData - Updated chatbot data
   * @returns {Promise<Object>} Updated chatbot data
   */
  async updateChatbot(chatbotId, updateData) {
    try {
      const response = await fetch(`${this.baseURL}/chatbots/${chatbotId}`, {
        method: 'PUT',
        headers: this.getAuthHeaders(),
        body: JSON.stringify(updateData),
      });

      const result = await this.handleResponse(response);
      console.log('✏️ Chatbot updated successfully:', result.chatbot.name);
      return result;
    } catch (error) {
      console.error(`❌ Error updating chatbot ${chatbotId}:`, error.message);
      throw error;
    }
  }

  /**
   * Delete chatbot permanently
   * @param {number} chatbotId - Chatbot ID
   * @returns {Promise<Object>} Deletion confirmation
   */
  async deleteChatbot(chatbotId) {
    try {
      const response = await fetch(`${this.baseURL}/chatbots/${chatbotId}`, {
        method: 'DELETE',
        headers: this.getAuthHeaders(),
      });

      const result = await this.handleResponse(response);
      console.log('🗑️ Chatbot deleted successfully');
      return result;
    } catch (error) {
      console.error(`❌ Error deleting chatbot ${chatbotId}:`, error.message);
      throw error;
    }
  }

  /**
   * Delete any chatbot (Super Admin only)
   * @param {number} chatbotId - ID of the chatbot to delete
   * @returns {Promise<Object>} Deletion confirmation
   */
  async deleteChatbotAdmin(chatbotId) {
    try {
      const response = await fetch(`${this.baseURL}/chatbots/${chatbotId}/admin`, {
        method: 'DELETE',
        headers: this.getAuthHeaders(),
      });

      const result = await this.handleResponse(response);
      console.log(`🗑️ Super admin deleted chatbot ${chatbotId} successfully`);
      return result;
    } catch (error) {
      console.error('❌ Error deleting chatbot (super admin):', error.message);
      throw error;
    }
  }

  /**
   * Get available AI models and their configurations
   * Only returns super admin-configured models from the DB
   * @returns {Promise<Object>} Available models by provider
   */
  async fetchAvailableModels() {
    try {
      const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
      const token = localStorage.getItem('authToken');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const response = await fetch(`${baseURL}/models`, { headers });

      if (!response.ok) return {};

      const result = await response.json();
      const dbModels = result.models || [];
      const grouped = {};

      for (const m of dbModels) {
        if (!m.is_active) continue;
        const providerKey = m.provider || 'other';
        if (!grouped[providerKey]) grouped[providerKey] = [];
        grouped[providerKey].push({
          value: `db:${m.id}`,
          label: m.display_name || m.model_name,
          description: `Configured model - ${m.provider}`,
          is_db_model: true,
          db_id: m.id
        });
      }

      return grouped;
    } catch {
      return {};
    }
  }

  /**
   * Synchronous wrapper for backwards compatibility.
   * Returns empty - always use fetchAvailableModels() for async data.
   * @returns {Object} Empty models (DB-driven)
   */
  getAvailableModels() {
    return {};
  }

  /**
   * Get chatbot types and their descriptions
   * @returns {Array} Available chatbot types
   */
  getChatbotTypes() {
    return [
      { value: 'support', label: 'Customer Support', description: 'Handle customer inquiries and support tickets' },
      { value: 'sales', label: 'Sales Assistant', description: 'Help with product information and sales' },
      { value: 'general', label: 'General Assistant', description: 'Multi-purpose conversational AI' },
      { value: 'hr', label: 'HR Assistant', description: 'Human resources and employee support' },
      { value: 'technical', label: 'Technical Support', description: 'Technical documentation and troubleshooting' }
    ];
  }

  /**
   * Validate chatbot configuration before submission
   * @param {Object} chatbotData - Chatbot configuration to validate
   * @returns {Object} Validation result with errors if any
   */
  validateChatbotData(chatbotData) {
    const errors = {};

    // Required fields
    if (!chatbotData.name || chatbotData.name.trim().length === 0) {
      errors.name = 'Chatbot name is required';
    } else if (chatbotData.name.length > 100) {
      errors.name = 'Chatbot name must be less than 100 characters';
    }

    // AI Model validation (must be from DB or empty)
    if (chatbotData.ai_model && !String(chatbotData.ai_model).startsWith('db:')) {
      errors.ai_model = 'Invalid AI model selected';
    }

    // Temperature validation
    if (chatbotData.temperature !== undefined) {
      const temp = parseFloat(chatbotData.temperature);
      if (isNaN(temp) || temp < 0 || temp > 1) {
        errors.temperature = 'Temperature must be a number between 0 and 1';
      }
    }

    // Max tokens validation
    if (chatbotData.max_tokens !== undefined) {
      const tokens = parseInt(chatbotData.max_tokens);
      if (isNaN(tokens) || tokens < 50 || tokens > 4000) {
        errors.max_tokens = 'Max tokens must be between 50 and 4000';
      }
    }

    // Type validation
    const validTypes = this.getChatbotTypes().map(t => t.value);
    if (chatbotData.type && !validTypes.includes(chatbotData.type)) {
      errors.type = 'Invalid chatbot type';
    }

    return {
      isValid: Object.keys(errors).length === 0,
      errors
    };
  }

  /**
   * Get default chatbot configuration
   * @returns {Object} Default configuration
   */
  getDefaultConfig() {
    return {
      name: '',
      description: '',
      type: 'general',
      ai_model: 'gpt-4o-mini',
      temperature: 0.3,
      max_tokens: 1000,
      status: 'active',
      personality: {
        role: 'Helpful Assistant',
        tone: 'friendly and professional',
        style: 'concise and informative'
      },
      prompts: {
        system_message: 'You are a helpful AI assistant. Provide accurate, helpful, and concise responses.',
        greeting: 'Hello! How can I assist you today?',
        fallback: 'I apologize, but I need more information to help you with that request.'
      }
    };
  }

  /**
   * Export chatbot configuration for backup/import
   * @param {number} chatbotId - Chatbot ID
   * @returns {Promise<Object>} Exportable configuration
   */
  async exportChatbotConfig(chatbotId) {
    try {
      const chatbot = await this.getChatbot(chatbotId);
      
      // Remove system fields for clean export
      const exportConfig = {
        name: chatbot.name,
        description: chatbot.description,
        type: chatbot.type,
        ai_model: chatbot.ai_model,
        temperature: chatbot.temperature,
        max_tokens: chatbot.max_tokens,
        fallback_model: chatbot.fallback_model,
        personality: chatbot.personality,
        prompts: chatbot.prompts,
        exported_at: new Date().toISOString(),
        version: '1.0'
      };

      console.log('📤 Chatbot configuration exported');
      return exportConfig;
    } catch (error) {
      console.error('❌ Error exporting chatbot config:', error.message);
      throw error;
    }
  }

  /**
   * Clone existing chatbot with new name
   * @param {number} sourceChatbotId - Source chatbot ID
   * @param {string} newName - New chatbot name
   * @returns {Promise<Object>} Cloned chatbot data
   */
  async cloneChatbot(sourceChatbotId, newName) {
    try {
      const sourceConfig = await this.exportChatbotConfig(sourceChatbotId);
      
      // Update name and create new chatbot
      sourceConfig.name = newName;
      delete sourceConfig.exported_at;
      delete sourceConfig.version;

      const result = await this.createChatbot(sourceConfig);
      console.log('👥 Chatbot cloned successfully:', newName);
      return result;
    } catch (error) {
      console.error('❌ Error cloning chatbot:', error.message);
      throw error;
    }
  }
}

// Export singleton instance
export const chatbotService = new ChatbotService();
