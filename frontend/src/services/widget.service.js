import axios from 'axios';

class WidgetService {
  constructor() {
    this.API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
  }

  setAuthToken(token) {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    } else {
      delete axios.defaults.headers.common['Authorization'];
    }
  }

  getStoredToken() {
    try {
      return (
        localStorage.getItem('authToken') ||
        sessionStorage.getItem('authToken') ||
        null
      );
    } catch (e) {
      return null;
    }
  }

  async generateScript(chatbotId) {
    const token = this.getStoredToken();
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    const qp = token ? `?token=${encodeURIComponent(token)}` : '';
    const url = `${this.API_URL}/widget/generate-script/${chatbotId}${qp}`;
    const res = await axios.get(url, { headers });
    if (res.status !== 200 || !res.data?.script) {
      throw new Error('Failed to generate widget script');
    }
    return res.data.script;
  }
}

export default new WidgetService();
