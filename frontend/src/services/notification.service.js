// frontend/src/services/notification.service.js

import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';

class NotificationService {
    constructor() {
        this.apiClient = axios.create({
            baseURL: API_BASE_URL,
            headers: {
                'Content-Type': 'application/json',
            },
        });

        // Add auth token to requests
        this.apiClient.interceptors.request.use((config) => {
            const token = localStorage.getItem('token');
            if (token) {
                config.headers.Authorization = `Bearer ${token}`;
            }
            return config;
        });
    }

    /**
     * Get notifications for the current user
     */
    async getNotifications(params = {}) {
        try {
            const response = await this.apiClient.get('/notifications', { params });
            return response.data;
        } catch (error) {
            console.error('Error fetching notifications:', error);
            throw error;
        }
    }

    /**
     * Mark a notification as read
     */
    async markAsRead(notificationId) {
        try {
            const response = await this.apiClient.post(`/notifications/${notificationId}/read`);
            return response.data;
        } catch (error) {
            console.error('Error marking notification as read:', error);
            throw error;
        }
    }

    /**
     * Get notification preferences
     */
    async getPreferences() {
        try {
            const response = await this.apiClient.get('/notifications/preferences');
            return response.data;
        } catch (error) {
            console.error('Error fetching notification preferences:', error);
            throw error;
        }
    }

    /**
     * Update notification preferences
     */
    async updatePreferences(preferences) {
        try {
            const response = await this.apiClient.put('/notifications/preferences', preferences);
            return response.data;
        } catch (error) {
            console.error('Error updating notification preferences:', error);
            throw error;
        }
    }

    /**
     * Send a test notification
     */
    async sendTestNotification(type = 'in_app') {
        try {
            const response = await this.apiClient.post('/notifications/test', { type });
            return response.data;
        } catch (error) {
            console.error('Error sending test notification:', error);
            throw error;
        }
    }

    /**
     * Format notification for display
     */
    formatNotification(notification) {
        return {
            ...notification,
            timeAgo: this.getTimeAgo(notification.created_at),
            isUnread: !notification.read_at,
            priorityColor: this.getPriorityColor(notification.priority),
            categoryIcon: this.getCategoryIcon(notification.category)
        };
    }

    /**
     * Get time ago string
     */
    getTimeAgo(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffInSeconds = Math.floor((now - date) / 1000);

        if (diffInSeconds < 60) {
            return 'Just now';
        } else if (diffInSeconds < 3600) {
            const minutes = Math.floor(diffInSeconds / 60);
            return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
        } else if (diffInSeconds < 86400) {
            const hours = Math.floor(diffInSeconds / 3600);
            return `${hours} hour${hours > 1 ? 's' : ''} ago`;
        } else {
            return date.toLocaleDateString();
        }
    }

    /**
     * Get priority color
     */
    getPriorityColor(priority) {
        switch (priority) {
            case 'urgent':
                return '#dc3545'; // red
            case 'high':
                return '#fd7e14'; // orange
            case 'normal':
                return '#0d6efd'; // blue
            case 'low':
                return '#6c757d'; // gray
            default:
                return '#0d6efd';
        }
    }

    /**
     * Get category icon
     */
    getCategoryIcon(category) {
        switch (category) {
            case 'conversation_started':
                return '💬';
            case 'feedback_received':
                return '⭐';
            case 'usage_alerts':
                return '⚠️';
            case 'system_updates':
                return '🔧';
            case 'weekly_reports':
                return '📊';
            default:
                return '🔔';
        }
    }
}

// Create and export a singleton instance
const notificationService = new NotificationService();
export { notificationService };
