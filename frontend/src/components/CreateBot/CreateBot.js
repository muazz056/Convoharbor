import "./CreateBot.css";
// Reuse the exact preview styles from configuration screen
import "../ConfigDesign/ConfigDesign.css";
// import ChatWindow from '../ChatWindow/ChatWindow'
import AOS from 'aos';
import 'aos/dist/aos.css';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { chatbotService } from '../../services/chatbot.service';


  const CreateBot = () => {
      const navigate = useNavigate();
      const [loading, setLoading] = useState(false);
      const [error, setError] = useState(null);
      const [user, setUser] = useState(null);
      
      // New state for model selection
      const [availableModels, setAvailableModels] = useState({ openai: [], gemini: [] });
      const [selectedProvider, setSelectedProvider] = useState('');
      const [modelDefaults, setModelDefaults] = useState({});

      const [formData, setFormData] = useState({
        name: '',
        description: '',
        type: 'general',
        temperature: 0.7,
        maxTokens: 2048,
        model: '', // Default to empty
        topK: 10 // Default top K chunks
      });

      // Optional theme configuration during creation (does not disturb existing flow)
      const [themeConfig, setThemeConfig] = useState({
        position: 'bottom-right',
        primaryColor: '#6366F1',
        welcomeMessage: 'Hello! How can I help you today?'
      });
      const [mode, setMode] = useState('strict');

      useEffect(() => {
        AOS.init({
          duration: 800,
          easing: 'ease-in-out',
          once: true,
        });
        // Load models from DB (super admin-configured models only)
        chatbotService.fetchAvailableModels().then(dbModels => {
          setAvailableModels(dbModels);
          // Store full model data for defaults
          const defaults = {};
          Object.values(dbModels).flat().forEach(m => {
            if (m.db_id && m.fullData) {
              defaults[m.value] = m.fullData;
            }
          });
          setModelDefaults(defaults);
        });
        
        // Load user data to check permissions
        const userData = localStorage.getItem('userData');
        if (userData) {
            setUser(JSON.parse(userData));
        }
      }, []);
    return (
      <>
            <div className="page" id="chatbots" data-aos="fade-up" data-aos-delay="200">
              <div className="page-header">
                <h1 className="page-title">Create a new chatbot</h1>
                <p className="page-subtitle">Configure your personalized AI assistant</p>
              </div>
              <div className="section-card">
                {error && (
                  <div className="alert alert-danger" role="alert">
                    {error}
                  </div>
                )}

                <form onSubmit={async (e) => {
                  e.preventDefault();
                  setLoading(true);
                  setError(null);
                  
                  try {
                    // Map to backend schema and include optional theme
                    const modelValue = formData.model || '';
                    const payload = {
                      name: formData.name,
                      description: formData.description,
                      type: formData.type,
                      // Send canonical model key
                      ai_model: modelValue.startsWith('db:') ? undefined : modelValue || undefined,
                      ai_model_id: modelValue.startsWith('db:') ? parseInt(modelValue.replace('db:', ''), 10) : undefined,
                      ai_provider: selectedProvider ? selectedProvider.charAt(0).toUpperCase() + selectedProvider.slice(1) : undefined,
                      temperature: formData.temperature,
                      max_tokens: formData.maxTokens,
                      prompts: {
                        greeting: themeConfig.welcomeMessage
                      },
                      theme: themeConfig,
                      mode: mode,
                      top_k: formData.topK
                    };

                    const response = await chatbotService.createChatbot(payload);
                    navigate('/data-sources');
                  } catch (err) {
                    setError(err.message || 'Failed to create chatbot');
                  } finally {
                    setLoading(false);
                  }
                }}>
                  {/* Basic Information */}
                  <div className="form-section">
                    <h3 className="form-section-title">🤖 Basic Information</h3>
                    <div className="form-group">
                      <label htmlFor="name">
                        <span className="field-icon">📝</span>
                        Chatbot Name *
                      </label>
                      <input
                        type="text"
                        id="name"
                        className="form-control"
                        value={formData.name}
                        onChange={(e) => setFormData({...formData, name: e.target.value})}
                        required
                        placeholder="e.g., Support Assistant"
                      />
                      <span className="helper-text">Choose a descriptive name for your chatbot</span>
                    </div>

                    <div className="form-group">
                      <label htmlFor="description">
                        <span className="field-icon">📄</span>
                        Description
                      </label>
                      <textarea
                        id="description"
                        className="form-control"
                        value={formData.description}
                        onChange={(e) => setFormData({...formData, description: e.target.value})}
                        placeholder="What will this chatbot help with?"
                        rows="3"
                      />
                      <span className="helper-text">Name and description will be shown to users on the chatbot embed/widget</span>
                    </div>

                    <div className="form-grid">
                      <div className="form-group">
                        <label htmlFor="type">
                          <span className="field-icon">🎯</span>
                          Type *
                        </label>
                        <select
                          id="type"
                          className="form-control"
                          value={formData.type}
                          onChange={(e) => setFormData({...formData, type: e.target.value})}
                          required
                        >
                          <option value="general">🤖 General Purpose</option>
                          <option value="support">🎧 Customer Support</option>
                          <option value="sales">💼 Sales</option>
                          <option value="hr">👥 HR Assistant</option>
                          <option value="technical">🔧 Technical Support</option>
                        </select>
                        <span className="helper-text">Select the primary function of your chatbot</span>
                      </div>

                      <div className="form-group">
                        <label htmlFor="provider">
                          <span className="field-icon">🤖</span>
                          AI Provider *
                        </label>
                        <select
                          id="provider"
                          className="form-control"
                          value={selectedProvider}
                          onChange={(e) => {
                            setSelectedProvider(e.target.value);
                            // Reset model when provider changes
                            setFormData({...formData, model: ''});
                          }}
                          required
                        >
                          <option value="">Select a provider...</option>
                          {Object.keys(availableModels).map(providerKey => (
                            <option key={providerKey} value={providerKey}>
                              {providerKey.charAt(0).toUpperCase() + providerKey.slice(1)}
                            </option>
                          ))}
                        </select>
                        <span className="helper-text">Choose the AI provider</span>
                      </div>
                    </div>

                    {/* AI Model dropdown (conditional) */}
                    {selectedProvider && (
                      <div className="form-group" style={{ marginTop: '1rem' }}>
                        <label htmlFor="model">
                          <span className="field-icon">🧠</span>
                          AI Model *
                        </label>
                        <select
                          id="model"
                          className="form-control"
                          value={formData.model}
                          onChange={(e) => {
                            const modelValue = e.target.value;
                            const defaults = modelDefaults[modelValue] || {};
                            setFormData({
                              ...formData,
                              model: modelValue,
                              temperature: defaults.temperature ?? 0.7,
                              maxTokens: defaults.max_tokens ?? 2048,
                              topK: defaults.top_k ?? 10
                            });
                          }}
                          required
                        >
                          <option value="">Select a model...</option>
                          {availableModels[selectedProvider]?.map(model => (
                            <option key={model.value} value={model.value}>
                              {model.label}
                            </option>
                          ))}
                        </select>
                        <span className="helper-text">
                          {
                            formData.model && availableModels[selectedProvider]?.find(m => m.value === formData.model)?.description
                          }
                        </span>
                      </div>
                    )}
                  </div>


                  {/* Theme Customization (Optional) */}
                  <div className="form-section">
                    <h3 className="form-section-title">🎨 Appearance Settings</h3>
                    <div className="theme-customization">
                      <div className="theme-settings">
                        <div className="form-group">
                          <label htmlFor="position">
                            <span className="field-icon">📍</span>
                            Position
                          </label>
                          <select
                            id="position"
                            className="form-control"
                            value={themeConfig.position}
                            onChange={(e) => setThemeConfig({ ...themeConfig, position: e.target.value })}
                          >
                            <option value="bottom-right">Bottom Right</option>
                            <option value="bottom-left">Bottom Left</option>
                            <option value="top-right">Top Right</option>
                            <option value="top-left">Top Left</option>
                          </select>
                        </div>

                        <div className="form-group">
                          <label htmlFor="primaryColor">
                            <span className="field-icon">🎨</span>
                            Primary Color
                          </label>
                          <div className="color-input-group">
                            <input
                              type="color"
                              id="primaryColor"
                              className="color-picker"
                              value={themeConfig.primaryColor}
                              onChange={(e) => setThemeConfig({ ...themeConfig, primaryColor: e.target.value })}
                            />
                            <input
                              type="text"
                              className="form-control color-text"
                              value={themeConfig.primaryColor}
                              onChange={(e) => setThemeConfig({ ...themeConfig, primaryColor: e.target.value })}
                              placeholder="#6366F1"
                            />
                          </div>
                        </div>

                        <div className="form-group">
                          <label htmlFor="welcomeMessage">
                            <span className="field-icon">💬</span>
                            Welcome Message
                          </label>
                          <textarea
                            id="welcomeMessage"
                            className="form-control"
                            value={themeConfig.welcomeMessage}
                            onChange={(e) => setThemeConfig({ ...themeConfig, welcomeMessage: e.target.value })}
                            placeholder="Hi! How can I help you today?"
                            rows="3"
                          />
                        </div>
                      </div>

                      {/* Live Preview – match ConfigDesign preview */}
                      <div className="theme-preview" style={{ marginTop: '1rem' }}>
                        <h4>Live Preview</h4>
                        <div className="preview-container">
                          <div className={`chatbot-preview ${themeConfig.position}`}>
                            <div className="chat-widget-preview" style={{ borderColor: themeConfig.primaryColor }}>
                              <div className="chat-header-preview" style={{ background: themeConfig.primaryColor }}>
                                <span>{formData.name || 'Support Bot'}</span>
                                <button className="close-btn-preview" type="button">✕</button>
                              </div>
                              <div className="chat-messages-preview">
                                <div className="message-preview assistant">
                                  {themeConfig.welcomeMessage}
                                </div>
                              </div>
                              <div className="chat-input-preview">
                                <input type="text" placeholder="Type your message..." disabled />
                                <button type="button" style={{ backgroundColor: themeConfig.primaryColor }}>➤</button>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="form-actions">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => navigate('/chatbot')}
                      disabled={loading}
                    >
                      ← Cancel
                    </button>
                    <button
                      type="submit"
                      className="btn btn-primary"
                      disabled={loading}
                    >
                      {loading ? '🔄 Creating...' : '✨ Create Chatbot'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
      </>
    );
  };

export default CreateBot;