import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';

class TenantService {
    // Tenant Management
    async createTenant(tenantData) {
        const response = await axios.post(`${API_URL}/tenants`, tenantData);
        return response.data;
    }
    
    async getTenants(page = 1, perPage = 20, filters = {}) {
        const params = new URLSearchParams({
            page: page.toString(),
            per_page: perPage.toString(),
            ...filters
        });
        
        const response = await axios.get(`${API_URL}/tenants?${params}`);
        return response.data;
    }
    
    async getTenant(tenantId) {
        const response = await axios.get(`${API_URL}/tenants/${tenantId}`);
        return response.data;
    }
    
    async updateTenant(tenantId, updates) {
        const response = await axios.put(`${API_URL}/tenants/${tenantId}`, updates);
        return response.data;
    }
    
    async deleteTenant(tenantId) {
        const response = await axios.delete(`${API_URL}/tenants/${tenantId}`);
        return response.data;
    }
    
    // User Management within Tenant
    async getUsers(page = 1, perPage = 20, filters = {}) {
        const params = new URLSearchParams({
            page: page.toString(),
            per_page: perPage.toString(),
            ...filters
        });
        
        const response = await axios.get(`${API_URL}/users?${params}`);
        return response.data;
    }
    
    async createUser(userData) {
        const response = await axios.post(`${API_URL}/users`, userData);
        return response.data;
    }
    
    async updateUser(userId, updates) {
        const response = await axios.put(`${API_URL}/users/${userId}`, updates);
        return response.data;
    }
    
    async deleteUser(userId) {
        const response = await axios.delete(`${API_URL}/users/${userId}`);
        return response.data;
    }
    
    // Tenant Analytics
    async getTenantStats(tenantId) {
        const response = await axios.get(`${API_URL}/tenants/${tenantId}/stats`);
        return response.data;
    }
    
    async getTenantRevenue(tenantId, period = 'month') {
        const response = await axios.get(`${API_URL}/tenants/${tenantId}/revenue?period=${period}`);
        return response.data;
    }
    
    // Tenant Configuration
    async getTenantConfig(tenantId) {
        const response = await axios.get(`${API_URL}/tenants/${tenantId}/config`);
        return response.data;
    }
    
    async updateTenantConfig(tenantId, config) {
        const response = await axios.put(`${API_URL}/tenants/${tenantId}/config`, config);
        return response.data;
    }
    
    // Tenant Features
    async updateTenantFeatures(tenantId, features) {
        const response = await axios.put(`${API_URL}/tenants/${tenantId}/features`, features);
        return response.data;
    }
    
    async getTenantFeatures(tenantId) {
        const response = await axios.get(`${API_URL}/tenants/${tenantId}/features`);
        return response.data;
    }
    
    // Tenant Limits
    async updateTenantLimits(tenantId, limits) {
        const response = await axios.put(`${API_URL}/tenants/${tenantId}/limits`, limits);
        return response.data;
    }
    
    async getTenantLimits(tenantId) {
        const response = await axios.get(`${API_URL}/tenants/${tenantId}/limits`);
        return response.data;
    }
    
    // Tenant Status
    async suspendTenant(tenantId, reason) {
        const response = await axios.post(`${API_URL}/tenants/${tenantId}/suspend`, { reason });
        return response.data;
    }
    
    async activateTenant(tenantId) {
        const response = await axios.post(`${API_URL}/tenants/${tenantId}/activate`);
        return response.data;
    }
    
    // Error Handling
    handleError(error) {
        if (error.response) {
            // Server responded with error
            const { status, data } = error.response;
            switch (status) {
                case 400:
                    return { error: 'Invalid request', details: data.error };
                case 401:
                    return { error: 'Authentication required' };
                case 403:
                    return { error: 'Access denied', details: data.error };
                case 404:
                    return { error: 'Resource not found' };
                case 409:
                    return { error: 'Resource conflict', details: data.error };
                default:
                    return { error: 'Server error', details: data.error };
            }
        }
        // Network error
        return { error: 'Network error', details: error.message };
    }
}

export default new TenantService();
