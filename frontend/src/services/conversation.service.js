import axios from 'axios';

class ConversationService {
    constructor() {
        this.API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
        
        // Configure axios defaults
        axios.defaults.headers.common['Content-Type'] = 'application/json';
    }

    /**
     * Set authorization header for authenticated requests
     */
    setAuthToken(token) {
        if (token) {
            axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
            console.log('✅ Auth token set for conversation service');
        } else {
            delete axios.defaults.headers.common['Authorization'];
            console.log('⚠️ Auth token removed from conversation service');
        }
    }

    /**
     * Handle API response and extract data
     */
    async handleResponse(response) {
        if (response.data.success === false) {
            throw new Error(response.data.error || 'API request failed');
        }
        return response.data;
    }

    /**
     * Get list of conversations with optional filters
     * @param {Object} filters - Filter options
     * @param {number} filters.chatbot_id - Filter by chatbot ID
     * @param {string} filters.status - Filter by status (active, archived, deleted)
     * @param {string} filters.start_date - Start date (YYYY-MM-DD)
     * @param {string} filters.end_date - End date (YYYY-MM-DD)
     * @param {number} filters.page - Page number (default: 1)
     * @param {number} filters.per_page - Items per page (default: 20)
     */
    async getConversations(filters = {}) {
        try {
            const params = new URLSearchParams();
            
            if (filters.chatbot_id) params.append('chatbot_id', filters.chatbot_id);
            if (filters.status) params.append('status', filters.status);
            if (filters.start_date) params.append('start_date', filters.start_date);
            if (filters.end_date) params.append('end_date', filters.end_date);
            if (filters.page) params.append('page', filters.page);
            if (filters.per_page) params.append('per_page', filters.per_page);
            
            const queryString = params.toString();
            const url = `${this.API_URL}/conversations${queryString ? `?${queryString}` : ''}`;
            
            console.log('📋 Fetching conversations:', url);
            
            const response = await axios.get(url);
            const data = await this.handleResponse(response);
            
            console.log(`✅ Retrieved ${data.conversations?.length || 0} conversations`);
            return data;
            
        } catch (error) {
            console.error('❌ Error fetching conversations:', error.response?.data?.error || error.message);
            throw error;
        }
    }

    /**
     * Get messages for a specific conversation
     * @param {number} conversationId - The conversation ID
     */
    async getConversationMessages(conversationId) {
        try {
            console.log(`💬 Fetching messages for conversation ${conversationId}`);
            
            const response = await axios.get(`${this.API_URL}/conversations/${conversationId}/messages`);
            const data = await this.handleResponse(response);
            
            console.log(`✅ Retrieved ${data.messages?.length || 0} messages`);
            return data;
            
        } catch (error) {
            console.error('❌ Error fetching conversation messages:', error.response?.data?.error || error.message);
            throw error;
        }
    }

    /**
     * Add feedback to a conversation
     * @param {number} conversationId - The conversation ID
     * @param {Object} feedbackData - Feedback information
     * @param {string} feedbackData.feedback_type - Type of feedback (thumbs_up, thumbs_down, rating, comment)
     * @param {number} feedbackData.rating - Rating (1-5, required for rating type)
     * @param {string} feedbackData.feedback_text - Optional feedback comment
     * @param {number} feedbackData.message_id - Optional specific message ID
     */
    async addConversationFeedback(conversationId, feedbackData) {
        try {
            console.log(`👍 Adding feedback to conversation ${conversationId}:`, feedbackData.feedback_type);
            
            const response = await axios.post(
                `${this.API_URL}/conversations/${conversationId}/feedback`,
                feedbackData
            );
            const data = await this.handleResponse(response);
            
            console.log('✅ Feedback added successfully');
            return data;
            
        } catch (error) {
            console.error('❌ Error adding feedback:', error.response?.data?.error || error.message);
            throw error;
        }
    }

    /**
     * Delete a conversation (soft delete)
     * @param {number} conversationId - The conversation ID to delete
     */
    async deleteConversation(conversationId) {
        try {
            console.log(`🗑️ Deleting conversation ${conversationId}`);
            
            const response = await axios.delete(`${this.API_URL}/conversations/${conversationId}`);
            const data = await this.handleResponse(response);
            
            console.log('✅ Conversation deleted successfully');
            return data;
            
        } catch (error) {
            console.error('❌ Error deleting conversation:', error.response?.data?.error || error.message);
            throw error;
        }
    }

    /**
     * Get conversation statistics for dashboard
     * @param {Object} filters - Optional filters
     */
    async getConversationStats(filters = {}) {
        try {
            // Get conversations with filters and calculate stats
            const data = await this.getConversations({ ...filters, per_page: 1000 });
            
            const stats = {
                total: data.pagination?.total || 0,
                active: 0,
                archived: 0,
                deleted: 0,
                today: 0,
                thisWeek: 0,
                thisMonth: 0
            };
            
            const now = new Date();
            const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
            const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
            const monthAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
            
            data.conversations?.forEach(conv => {
                // Count by status
                stats[conv.status] = (stats[conv.status] || 0) + 1;
                
                // Count by time periods
                const createdAt = new Date(conv.created_at);
                if (createdAt >= today) stats.today++;
                if (createdAt >= weekAgo) stats.thisWeek++;
                if (createdAt >= monthAgo) stats.thisMonth++;
            });
            
            return stats;
            
        } catch (error) {
            console.error('❌ Error fetching conversation stats:', error.message);
            throw error;
        }
    }

    /**
     * Format conversation data for display
     * @param {Object} conversation - Raw conversation data
     */
    formatConversationForDisplay(conversation) {
        return {
            ...conversation,
            created_at_formatted: new Date(conversation.created_at).toLocaleString(),
            updated_at_formatted: new Date(conversation.updated_at).toLocaleString(),
            status_badge: this.getStatusBadge(conversation.status),
            message_preview: conversation.latest_message?.content || 'No messages yet'
        };
    }

    /**
     * Get status badge configuration
     * @param {string} status - Conversation status
     */
    getStatusBadge(status) {
        const badges = {
            active: { color: 'success', text: 'Active' },
            archived: { color: 'secondary', text: 'Archived' },
            deleted: { color: 'danger', text: 'Deleted' }
        };
        return badges[status] || { color: 'secondary', text: 'Unknown' };
    }
}

// Export singleton instance
export default new ConversationService();
