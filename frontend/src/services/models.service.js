import axios from 'axios';
import authService from './auth.service';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';

class ModelService {
  constructor() {
    this.baseURL = API_BASE_URL;
    const currentUser = authService.getCurrentUser();
    if (currentUser?.token) {
      authService.setupAxiosInterceptors(currentUser.token);
    }
  }

  getAuthHeaders() {
    const user = authService.getCurrentUser();
    return user?.token ? { Authorization: `Bearer ${user.token}` } : {};
  }

  async getProviders() {
    const response = await axios.get(`${this.baseURL}/admin/providers`, {
      headers: this.getAuthHeaders()
    });
    return response.data;
  }

  async getAllModels(params = {}) {
    const response = await axios.get(`${this.baseURL}/admin/models`, {
      headers: this.getAuthHeaders(),
      params
    });
    return response.data;
  }

  async getModel(id) {
    const response = await axios.get(`${this.baseURL}/admin/models/${id}`, {
      headers: this.getAuthHeaders()
    });
    return response.data;
  }

  async createModel(data) {
    const response = await axios.post(`${this.baseURL}/admin/models`, data, {
      headers: this.getAuthHeaders()
    });
    return response.data;
  }

  async updateModel(id, data) {
    const response = await axios.put(`${this.baseURL}/admin/models/${id}`, data, {
      headers: this.getAuthHeaders()
    });
    return response.data;
  }

  async deleteModel(id) {
    const response = await axios.delete(`${this.baseURL}/admin/models/${id}`, {
      headers: this.getAuthHeaders()
    });
    return response.data;
  }

  async getActiveModels() {
    const response = await axios.get(`${this.baseURL}/models`, {
      headers: this.getAuthHeaders()
    });
    return response.data;
  }
}

export const modelService = new ModelService();
