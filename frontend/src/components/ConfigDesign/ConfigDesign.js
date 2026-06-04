import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import "./ConfigDesign.css";
import { chatbotService } from '../../services/chatbot.service';
import widgetService from '../../services/widget.service';

  const ConfigDesign = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const chatbotId = searchParams.get('chatbot_id') || searchParams.get('id');
  const isSuperAdminMode = searchParams.get('super_admin') === 'true';

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [formData, setFormData] = useState(null);
  const [user, setUser] = useState(null);

  // List mode states (when no chatbot id is provided)
  const [chatbots, setChatbots] = useState([]);
  const isListMode = !chatbotId;

  // New state for model selection
  const [availableModels, setAvailableModels] = useState({ openai: [], gemini: [] });
  const [selectedProvider, setSelectedProvider] = useState('');

  // Theme customization state
  const [themeConfig, setThemeConfig] = useState({
    position: '',
    primaryColor: '',
    welcomeMessage: ''
  });

  // Mode state
  const [mode, setMode] = useState('strict');


  useEffect(() => {
    console.log('🔍 ConfigDesign: URL params:', Object.fromEntries(searchParams));
    console.log('🔍 ConfigDesign: chatbotId extracted:', chatbotId);

    // Load models from DB (super admin-configured models only)
    chatbotService.fetchAvailableModels().then(dbModels => {
      setAvailableModels(dbModels);
    });

    // Load user data to check permissions
    const userData = localStorage.getItem('userData');
    if (userData) {
      setUser(JSON.parse(userData));
    }

    // If no chatbot id, show list of chatbots for quick navigation to configure
    const fetchChatbotsList = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await chatbotService.getChatbots({ per_page: 50 });
        setChatbots(response.chatbots || []);
      } catch (err) {
        setError(err.message || 'Failed to load chatbots');
      } finally {
        setLoading(false);
      }
    };

    const fetchChatbot = async () => {
      try {
        console.log('🔍 ConfigDesign: isSuperAdminMode:', isSuperAdminMode);
        const response = isSuperAdminMode 
          ? await chatbotService.getChatbotAdmin(chatbotId)
          : await chatbotService.getChatbot(chatbotId);
        // Normalize fields for the form
        const config = response.config || {};
        const aiModelId = config.ai_model_id || response.ai_model_id;
        const normalized = {
          ...response,
          // ensure form uses `model` key - use db:id if configured via ai_model_id
          model: aiModelId ? `db:${aiModelId}` : (response.ai_model || response.model || ''),
          // ensure form keys align
          maxTokens: response.max_tokens || response.maxTokens || 2048,
          temperature: response.temperature ?? 0.7,
          topK: response.top_k || response.topK || 10,
        };
        setFormData(normalized);

        // Load theme configuration from config
        const theme = config.theme || {};
        setThemeConfig({
          position: theme.position || 'bottom-right',
          primaryColor: theme.primaryColor || '#6366F1',
          welcomeMessage: theme.welcomeMessage || config.prompts?.greeting || 'Hi! How can I help you today?'
        });

        // Load mode configuration
        setMode(config.mode || 'strict');

        // Store raw provider for matching when models load
        setSelectedProvider((response.ai_provider || '').toLowerCase());
      } catch (err) {
        setError(err.message || 'Failed to fetch chatbot data');
      } finally {
        setLoading(false);
      }
    };

    if (isListMode) {
      fetchChatbotsList();
    } else {
    fetchChatbot();
    }
  }, [chatbotId, navigate]);

  // Match selectedProvider to availableModels once both are loaded
  useEffect(() => {
    if (!formData || !formData.model || Object.keys(availableModels).length === 0) return;
    const modelVal = formData.model;
    if (modelVal.startsWith('db:')) {
      const matched = Object.keys(availableModels).find(provider =>
        availableModels[provider]?.some(m => m.value === modelVal)
      );
      if (matched) setSelectedProvider(matched);
    } else {
      const lower = modelVal.toLowerCase();
      const matched = Object.keys(availableModels).find(key => lower.includes(key));
      if (matched) setSelectedProvider(matched);
    }
  }, [formData, availableModels]);


  const handleUpdate = async (e) => {
    e.preventDefault();
    
    if (!formData) {
      setError('Form data not loaded yet. Please wait.');
      return;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      // Build payload mapping to backend keys
      const payload = {
        name: formData.name,
        description: formData.description,
        type: formData.type,
        // Send canonical model key
        ai_model: formData.model && formData.model.startsWith('db:') ? undefined : formData.model,
        ai_model_id: formData.model && formData.model.startsWith('db:') ? parseInt(formData.model.replace('db:', ''), 10) : undefined,
        // Normalise provider label
        ai_provider: selectedProvider ? selectedProvider.charAt(0).toUpperCase() + selectedProvider.slice(1) : formData.ai_provider,
        temperature: formData.temperature,
        max_tokens: formData.maxTokens,
        fallback_model: formData.fallback_model,
        personality: formData.personality,
        prompts: {
          ...formData.prompts,
          greeting: themeConfig.welcomeMessage
        },
        status: formData.status,
        // Include theme configuration
        theme: themeConfig,
        // Include mode configuration
        mode: mode,
        // Include top_k configuration
        top_k: formData.topK
      };

      console.log('🚀 Updating chatbot with payload:', JSON.stringify(payload, null, 2));
      console.log('🔗 Making request to chatbot service... (Super Admin Mode:', isSuperAdminMode, ')');
      console.log('🔍 Current formData.topK:', formData.topK);
      console.log('🔍 Payload top_k:', payload.top_k);
      
      const result = isSuperAdminMode 
        ? await chatbotService.updateChatbotAdmin(chatbotId, payload)
        : await chatbotService.updateChatbot(chatbotId, payload);
      console.log('✅ Update result:', JSON.stringify(result, null, 2));
      console.log('✅ Updated chatbot top_k:', result.chatbot?.top_k);
      // Signal that chatbot was updated so list can refresh
      localStorage.setItem('chatbot_updated', 'true');
      // After saving, always navigate to /configuration-design
      navigate('/configuration-design');
    } catch (err) {
      setError(err.message || 'Failed to update chatbot');
    } finally {
      setLoading(false);
    }
  };
  
  if (loading || (!isListMode && !formData)) {
    return (
          <div className="page">
            <div className="loading-state">
              <div className="spinner"></div>
              <p>{isListMode ? 'Loading your chatbots...' : 'Loading chatbot configuration...'}</p>
            </div>
          </div>
    );
  }

  if (error) {
    return (
          <div className="page">
            <div className="error-state">
              <div className="error-icon">⚠️</div>
              <h3>{isListMode ? 'Chatbots Load Error' : 'Configuration Error'}</h3>
              <p>{error}</p>
              <div className="error-actions">
                {isListMode ? (
                  <button onClick={() => window.location.reload()} className="btn btn-secondary">🔄 Retry</button>
                ) : (
                <button 
                  onClick={() => navigate('/chatbot')} 
                  className="btn btn-primary"
                >
                  ← Back to Chatbots
                </button>
                )}
                <button 
                  onClick={() => window.location.reload()} 
                  className="btn btn-secondary"
                >
                  🔄 Retry
                </button>
              </div>
            </div>
          </div>
    );
  }

  // List mode UI: show all chatbots with Configure button
  if (isListMode) {
    return (
      <>
            <div className="page" id="config-design">
              <div className="page-header">
                <h1 className="page-title">Configuration & Design</h1>
                <p className="page-subtitle">Select a chatbot to configure its settings</p>
              </div>

              <div className="section-card">
                {chatbots.length === 0 ? (
                  <div className="empty-state">
                    <div className="empty-icon">🤖</div>
                    <h3>No Chatbots Found</h3>
                    <p>Create a chatbot to start configuring it.</p>
                    <Link to="/create-chatbot" className="primary-button">+ New Chatbot</Link>
                  </div>
                ) : (
                  <div className="chatbots-grid">
                    {chatbots.map((bot) => (
                      <div key={bot.id} className="chatbot-card">
                        <div className="card-header">
                          <div className="chatbot-info">
                            <h3 className="chatbot-name">{bot.name}</h3>
                            <p className="chatbot-description">{bot.description || 'No description provided'}</p>
                          </div>
                        </div>
                        <div className="card-actions">
                          <Link to={`/configuration-design?id=${bot.id}`} className="action-button primary">Configure</Link>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
      </>
    );
  }

    return (
      <>
          <div className="page" id="config-design">
            <div className="page-header">
              <h1 className="page-title">Configure Chatbot: {formData?.name || 'Loading...'}</h1>
              <p className="page-subtitle">Update your AI assistant's settings</p>
            </div>
            <div className="section-card">
              <form onSubmit={handleUpdate}>
                {/* Form fields similar to CreateBot, pre-filled with formData */}
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
                      value={formData?.name || ''}
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
                      value={formData.description || ''}
                      onChange={(e) => setFormData({...formData, description: e.target.value})}
                      placeholder="What will this chatbot help with?"
                      rows="3"
                    />
                    <span className="helper-text">Describe the purpose and capabilities of your chatbot</span>
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
                        value={formData.type || 'general'}
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
                          value={formData.model || ''}
                          onChange={(e) => {
                            const modelValue = e.target.value;
                            const model = availableModels[selectedProvider]?.find(m => m.value === modelValue);
                            const defaults = model?.fullData || {};
                            setFormData({
                              ...formData,
                              model: modelValue,
                              temperature: defaults.temperature ?? formData.temperature ?? 0.7,
                              maxTokens: defaults.max_tokens ?? formData.maxTokens ?? 2048,
                              topK: defaults.top_k ?? formData.topK ?? 10
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


                {/* Advanced Settings (Super Admin only) */}
                {(isSuperAdminMode || user?.role === 'super_admin') && (
                <div className="form-section">
                  <h3 className="form-section-title">⚙️ Advanced Settings</h3>
                  <div className="form-grid">
                    <div className="form-group">
                      <label>
                        <span className="field-icon">📊</span>
                        Top K
                      </label>
                      <input
                        type="number"
                        className="form-control"
                        value={formData?.topK ?? 10}
                        onChange={(e) => setFormData({...formData, topK: parseInt(e.target.value) || 0})}
                        min="1"
                        max="100"
                        placeholder="10"
                      />
                      <span className="helper-text">Number of knowledge base chunks to retrieve (1-100)</span>
                    </div>

                    <div className="form-group">
                      <label>
                        <span className="field-icon">🎯</span>
                        Mode
                      </label>
                      <select
                        className="form-control"
                        value={mode}
                        onChange={(e) => setMode(e.target.value)}
                      >
                        <option value="strict">🔒 Strict (KB only)</option>
                        <option value="permissive">🔓 Permissive (KB + general knowledge)</option>
                      </select>
                      <span className="helper-text">Strict mode only answers from knowledge base; permissive mode also uses general AI knowledge</span>
                    </div>

                    <div className="form-group">
                      <label>
                        <span className="field-icon">🌡️</span>
                        Temperature
                      </label>
                      <div className="form-range-wrapper">
                        <input
                          type="range"
                          className="form-range"
                          value={formData?.temperature ?? 0.7}
                          onChange={(e) => setFormData({...formData, temperature: parseFloat(e.target.value)})}
                          min="0"
                          max="2"
                          step="0.1"
                        />
                        <span className="range-value">{formData?.temperature ?? 0.7}</span>
                      </div>
                      <span className="helper-text">Controls randomness: lower = more focused, higher = more creative (0-2)</span>
                    </div>

                    <div className="form-group">
                      <label>
                        <span className="field-icon">📏</span>
                        Max Tokens
                      </label>
                      <input
                        type="number"
                        className="form-control"
                        value={formData?.maxTokens ?? 2048}
                        onChange={(e) => setFormData({...formData, maxTokens: parseInt(e.target.value) || 0})}
                        min="64"
                        max="32000"
                        step="64"
                        placeholder="2048"
                      />
                      <span className="helper-text">Maximum length of the AI response in tokens (64-32000)</span>
                    </div>
                  </div>
                </div>
                )}

                {/* Theme Customization */}
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
                          onChange={(e) => setThemeConfig({...themeConfig, position: e.target.value})}
                        >
                          <option value="bottom-right">Bottom Right</option>
                          <option value="bottom-left">Bottom Left</option>
                          <option value="top-right">Top Right</option>
                          <option value="top-left">Top Left</option>
                        </select>
                        <span className="helper-text">Choose where the chatbot appears on your website</span>
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
                            onChange={(e) => setThemeConfig({...themeConfig, primaryColor: e.target.value})}
                          />
                          <input
                            type="text"
                            className="form-control color-text"
                            value={themeConfig.primaryColor}
                            onChange={(e) => setThemeConfig({...themeConfig, primaryColor: e.target.value})}
                            placeholder="#6366F1"
                          />
                        </div>
                        <span className="helper-text">Choose the main color for your chatbot interface</span>
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
                          onChange={(e) => setThemeConfig({...themeConfig, welcomeMessage: e.target.value})}
                          placeholder="Hi! How can I help you today?"
                          rows="3"
                        />
                        <span className="helper-text">The first message users see when they open the chat</span>
                      </div>
                    </div>

                    <div className="theme-preview">
                      <h4>Live Preview</h4>
                      <div className="preview-container">
                        <div className={`chatbot-preview ${themeConfig.position}`}>
                          <div className="chat-widget-preview" style={{ backgroundColor: themeConfig.primaryColor }}>
                            <div className="chat-header-preview">
                              <span>Support Bot</span>
                              <button className="close-btn-preview">✕</button>
                            </div>
                            <div className="chat-messages-preview">
                              <div className="message-preview assistant">
                                {themeConfig.welcomeMessage}
                              </div>
                            </div>
                            <div className="chat-input-preview">
                              <input type="text" placeholder="Type your message..." disabled />
                              <button style={{ backgroundColor: themeConfig.primaryColor }}>➤</button>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="form-actions">
                  <button type="button" onClick={() => navigate('/configuration-design')} className="btn btn-secondary">Cancel</button>
                  <button type="submit" className="btn btn-primary" disabled={loading}>
                    {loading ? 'Saving...' : 'Save Changes'}
                  </button>
                </div>
              </form>
            </div>
          </div>
      </>
    );
  };

export default ConfigDesign;