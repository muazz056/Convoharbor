import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';

class AnalyticsService {
    constructor() {
        // Set up axios interceptors for auth
        this.setupAxiosInterceptors();
    }

    setupAxiosInterceptors() {
        axios.interceptors.request.use(
            (config) => {
                const token = localStorage.getItem('authToken');
                if (token) {
                    config.headers.Authorization = `Bearer ${token}`;
                }
                return config;
            },
            (error) => {
                return Promise.reject(error);
            }
        );
    }

    async getOverview(params = {}) {
        try {
            const response = await axios.get(`${API_URL}/analytics/overview`, {
                params: {
                    chatbot_id: params.chatbot_id,
                    days: params.days || 30
                }
            });
            return response.data;
        } catch (error) {
            console.error('Error fetching analytics overview:', error);
            throw error;
        }
    }

    async getTimeseries(params = {}) {
        try {
            const response = await axios.get(`${API_URL}/analytics/timeseries`, {
                params: {
                    chatbot_id: params.chatbot_id,
                    days: params.days || 30,
                    granularity: params.granularity || 'day'
                }
            });
            return response.data;
        } catch (error) {
            console.error('Error fetching timeseries analytics:', error);
            throw error;
        }
    }

    async getPerformance(params = {}) {
        try {
            const response = await axios.get(`${API_URL}/analytics/performance`, {
                params: {
                    chatbot_id: params.chatbot_id,
                    days: params.days || 30
                }
            });
            return response.data;
        } catch (error) {
            console.error('Error fetching performance analytics:', error);
            throw error;
        }
    }

    async getSources(params = {}) {
        try {
            const response = await axios.get(`${API_URL}/analytics/sources`, {
                params: {
                    chatbot_id: params.chatbot_id,
                    days: params.days || 30
                }
            });
            return response.data;
        } catch (error) {
            console.error('Error fetching source analytics:', error);
            throw error;
        }
    }

    async exportData(exportParams) {
        try {
            const response = await axios.post(`${API_URL}/analytics/export`, exportParams);
            return response.data;
        } catch (error) {
            console.error('Error exporting analytics data:', error);
            throw error;
        }
    }

    async getSystemMetrics() {
        try {
            const response = await axios.get(`${API_URL}/metrics`);
            return response.data;
        } catch (error) {
            console.error('Error fetching system metrics:', error);
            throw error;
        }
    }

    async checkHealth() {
        try {
            const response = await axios.get(`${API_URL}/health/live`);
            return response.data;
        } catch (error) {
            console.error('Error checking health:', error);
            throw error;
        }
    }

    // Helper method to format chart data
    formatTimeseriesForChart(timeseriesData, label = 'Count') {
        if (!timeseriesData || !Array.isArray(timeseriesData)) {
            // Return sample data for empty state
            const days = 7;
            const labels = Array.from({length: days}, (_, i) => {
                const date = new Date();
                date.setDate(date.getDate() - (days - i - 1));
                return date.toLocaleDateString('en-US', { 
                    month: 'short', 
                    day: 'numeric' 
                });
            });
            
            return {
                labels,
                datasets: [{
                    label,
                    data: Array(days).fill(0),
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            };
        }

        const labels = timeseriesData.map(item => {
            const date = new Date(item.period);
            return date.toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric' 
            });
        });

        // Handle response times specifically
        const data = timeseriesData.map(item => {
            if (label.toLowerCase().includes('response')) {
                // For response times, use avg_response_time and round to 2 decimal places
                return item.avg_response_time ? Number(item.avg_response_time.toFixed(2)) : 0;
            }
            return item.count || 0;
        });

        return {
            labels,
            datasets: [{
                label,
                data,
                borderColor: '#6366f1',
                backgroundColor: 'rgba(99, 102, 241, 0.1)',
                fill: true,
                tension: 0.4
            }]
        };
    }

    // Helper method to format bar chart data
    formatBarChartData(data, labelKey, valueKey, label = 'Value') {
        if (!data || !Array.isArray(data)) {
            return { labels: [], datasets: [] };
        }

        const labels = data.map(item => item[labelKey] || 'Unknown');
        const values = data.map(item => item[valueKey] || 0);

        return {
            labels,
            datasets: [{
                label,
                data: values,
                backgroundColor: [
                    '#6366f1',
                    '#10b981', 
                    '#f59e0b',
                    '#f43f5e',
                    '#8b5cf6'
                ].slice(0, values.length)
            }]
        };
    }

    // Helper method to format pie chart data
    formatPieChartData(data, labelKey, valueKey) {
        if (!data || !Array.isArray(data)) {
            return { labels: [], datasets: [] };
        }

        const labels = data.map(item => item[labelKey] || 'Unknown');
        const values = data.map(item => item[valueKey] || 0);

        return {
            labels,
            datasets: [{
                data: values,
                backgroundColor: [
                    '#6366f1',
                    '#10b981',
                    '#f59e0b', 
                    '#f43f5e',
                    '#8b5cf6',
                    '#06b6d4',
                    '#84cc16'
                ].slice(0, values.length)
            }]
        };
    }
}

export default new AnalyticsService();