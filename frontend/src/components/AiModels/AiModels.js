import React, { useState, useEffect } from 'react';
import './AiModels.css';
import Navbar from '../navbar/navbar';
import Sidebar from '../Sidebar/Sidebar';
import SimpleLoader from '../common/SimpleLoader';
import { useAuth } from '../../contexts/AuthContext';

  const AiModels = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState('models');
  const [models, setModels] = useState([]);
  const [modelHealth, setModelHealth] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Playground states
  const [selectedModel, setSelectedModel] = useState('');
  const [testPrompt, setTestPrompt] = useState('');
  const [testResponse, setTestResponse] = useState('');
  const [testLoading, setTestLoading] = useState(false);
  
  // Comparison states
  const [comparisonModels, setComparisonModels] = useState(['', '']);
  const [comparisonPrompt, setComparisonPrompt] = useState('');
  const [comparisonResults, setComparisonResults] = useState([null, null]);
  const [comparisonLoading, setComparisonLoading] = useState(false);



  useEffect(() => {
    loadModels();
    checkModelHealth();
    // Set up periodic health checks
    const healthInterval = setInterval(checkModelHealth, 30000); // Every 30 seconds
    return () => clearInterval(healthInterval);
  }, []);

  const loadModels = async () => {
    try {
      setLoading(true);
      const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
      const token = localStorage.getItem('authToken');

      const response = await fetch(`${baseURL}/models`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });

      if (!response.ok) throw new Error(`API error: ${response.status}`);

      const result = await response.json();
      const apiModels = result.models || [];

      const mapped = apiModels.map(m => ({
        id: String(m.id),
        name: m.display_name || m.model_name,
        model_name: m.model_name,
        provider: m.provider,
        category: 'General',
        contextLength: m.context_window || 128000,
        maxTokens: m.max_tokens || 4096,
        pricing: { input: 0, output: 0 },
        capabilities: ['Text Generation'],
        description: `${m.provider} - ${m.model_name}`,
        status: m.is_active ? 'active' : 'inactive',
        speed: 'N/A',
        quality: 'N/A'
      }));

      setModels(mapped);
      if (mapped.length > 0) {
        setSelectedModel(String(mapped[0].id));
        setComparisonModels([String(mapped[0].id), mapped[1] ? String(mapped[1].id) : '']);
      }
    } catch (err) {
      setError('Failed to load models');
    } finally {
      setLoading(false);
    }
  };

  const checkModelHealth = async () => {
    try {
      const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
      const token = localStorage.getItem('authToken');
      
      if (!token) {
        console.warn('No auth token for health check');
        return;
      }

      console.log('🏥 Checking model health...');
      
      const response = await fetch(`${baseURL}/ai-models/health`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const result = await response.json();
        console.log('✅ Health check results:', result);
        
        if (result.models) {
          // Convert the API response to the format expected by the UI
          const healthData = {};
          Object.entries(result.models).forEach(([modelId, health]) => {
            healthData[modelId] = {
              status: health.status,
              responseTime: health.response_time,
              lastChecked: health.last_checked,
              uptime: health.uptime || 0,
              error: health.error
            };
          });
          setModelHealth(healthData);
        }
      } else {
        console.error('Health check API failed:', response.status);
        const healthData = {};
        for (const model of models) {
          healthData[model.id] = {
            status: 'unknown',
            responseTime: 0,
            lastChecked: new Date().toISOString(),
            uptime: 0,
            error: 'Health check API unavailable'
          };
        }
        setModelHealth(healthData);
      }
    } catch (err) {
      console.error('Health check failed:', err);
      const healthData = {};
      for (const model of models) {
        healthData[model.id] = {
          status: 'unknown',
          responseTime: 0,
          lastChecked: new Date().toISOString(),
          uptime: 0,
          error: err.message
        };
      }
      setModelHealth(healthData);
    }
  };

  const testModel = async () => {
    if (!selectedModel || !testPrompt.trim()) return;
    
    setTestLoading(true);
    setTestResponse('');
    
    try {
      const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
      const token = localStorage.getItem('authToken');
      
      if (!token) {
        setTestResponse('Error: Authentication token not found. Please log in again.');
        return;
      }

      console.log('🧪 Testing model:', selectedModel, 'with prompt:', testPrompt);
      
      // Make API call to test the model
      const response = await fetch(`${baseURL}/ai-models/test`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          model: selectedModel,
          prompt: testPrompt,
          temperature: 0.7,
          max_tokens: 1000
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      console.log('✅ Model test response:', result);
      
      if (result.success && result.response) {
        setTestResponse(result.response);
      } else {
        setTestResponse(result.error || 'No response received from model');
      }
    } catch (err) {
      console.error('❌ Model test error:', err);
      setTestResponse(`Error: ${err.message}`);
    } finally {
      setTestLoading(false);
    }
  };

  const compareModels = async () => {
    if (!comparisonModels[0] || !comparisonModels[1] || !comparisonPrompt.trim()) return;
    
    setComparisonLoading(true);
    setComparisonResults([null, null]);
    
    try {
      const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
      const token = localStorage.getItem('authToken');
      
      if (!token) {
        setComparisonResults([
          { error: 'Authentication token not found. Please log in again.' },
          { error: 'Authentication token not found. Please log in again.' }
        ]);
        return;
      }

      console.log('🔄 Comparing models:', comparisonModels, 'with prompt:', comparisonPrompt);
      
      // Make parallel API calls for both models
      const promises = comparisonModels.map(async (modelId, index) => {
        const startTime = Date.now();
        
        try {
          const response = await fetch(`${baseURL}/ai-models/test`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
              model: modelId,
              prompt: comparisonPrompt,
              temperature: 0.7,
              max_tokens: 1000
            })
          });

          const endTime = Date.now();
          const responseTime = endTime - startTime;

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
          }

          const result = await response.json();
          const modelInfo = models.find(m => m.id === modelId);
          
          return {
            model: modelInfo?.name || modelId,
            response: result.success ? result.response : (result.error || 'No response received'),
            responseTime,
            tokens: result.tokens || 0,
            success: result.success
          };
        } catch (err) {
          console.error(`❌ Model ${modelId} comparison error:`, err);
          const modelInfo = models.find(m => m.id === modelId);
          return {
            model: modelInfo?.name || modelId,
            error: err.message,
            responseTime: Date.now() - startTime,
            success: false
          };
        }
      });

      const results = await Promise.all(promises);
      console.log('✅ Model comparison results:', results);
      setComparisonResults(results);
      
    } catch (err) {
      console.error('❌ Model comparison error:', err);
      setComparisonResults([
        { error: `Comparison failed: ${err.message}` },
        { error: `Comparison failed: ${err.message}` }
      ]);
    } finally {
      setComparisonLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy': return '#10b981';
      case 'degraded': return '#f59e0b';
      case 'down': return '#ef4444';
      default: return '#6b7280';
    }
  };

  const getCategoryColor = (category) => {
    switch (category) {
      case 'Premium': return '#8b5cf6';
      case 'Balanced': return '#3b82f6';
      case 'Economy': return '#10b981';
      default: return '#6b7280';
    }
  };

  if (loading) {
    return (
      <div className="ai-models-page">
        <Navbar />
        <div className="ai-models-container">
          <Sidebar />
          <div className="ai-models-content">
            <SimpleLoader message="Loading AI models..." />
          </div>
        </div>
      </div>
    );
  }

    return (
    <div className="ai-models-page">
      <Navbar />
      <div className="ai-models-container">
          <Sidebar />
        <div className="ai-models-content">
          <div className="ai-models-header">
            <h1>🧠 AI Models</h1>
            <p className="header-subtitle">
              Manage and test AI models for your chatbots
            </p>
          </div>

          {error && (
            <div className="error-message">
              <span className="error-icon">⚠️</span>
              {error}
            </div>
          )}

          {/* Tab Navigation */}
          <div className="tab-navigation">
            <button 
              className={`tab-btn ${activeTab === 'models' ? 'active' : ''}`}
              onClick={() => setActiveTab('models')}
            >
              📊 Available Models
            </button>
            <button 
              className={`tab-btn ${activeTab === 'health' ? 'active' : ''}`}
              onClick={() => setActiveTab('health')}
            >
              💚 Health Monitoring
            </button>
            <button 
              className={`tab-btn ${activeTab === 'playground' ? 'active' : ''}`}
              onClick={() => setActiveTab('playground')}
            >
              🎮 Model Playground
            </button>
            <button 
              className={`tab-btn ${activeTab === 'comparison' ? 'active' : ''}`}
              onClick={() => setActiveTab('comparison')}
            >
              ⚖️ Model Comparison
            </button>
          </div>

          {/* Available Models Tab */}
          {activeTab === 'models' && (
            <div className="tab-content">
              <div className="models-grid">
                {models.map((model) => (
                  <div key={model.id} className="model-card">
                    <div className="model-header">
                      <div className="model-info">
                        <h3 className="model-name">{model.name}</h3>
                        <p className="model-provider">{model.provider}</p>
                      </div>
                      <div className="model-badges">
                        <span 
                          className="category-badge"
                          style={{ backgroundColor: getCategoryColor(model.category) }}
                        >
                          {model.category}
                        </span>
                        <span 
                          className="status-badge"
                          style={{ backgroundColor: getStatusColor(modelHealth[model.id]?.status || 'unknown') }}
                        >
                          {modelHealth[model.id]?.status || 'unknown'}
                        </span>
                      </div>
                    </div>
                    
                    <div className="model-body">
                      <p className="model-description">{model.description}</p>
                      
                      <div className="model-specs">
                        <div className="spec-row">
                          <span className="spec-label">Context Length:</span>
                          <span className="spec-value">{model.contextLength.toLocaleString()} tokens</span>
                        </div>
                        <div className="spec-row">
                          <span className="spec-label">Max Output:</span>
                          <span className="spec-value">{model.maxTokens.toLocaleString()} tokens</span>
                        </div>
                        <div className="spec-row">
                          <span className="spec-label">Speed:</span>
                          <span className="spec-value">{model.speed}</span>
                        </div>
                        <div className="spec-row">
                          <span className="spec-label">Quality:</span>
                          <span className="spec-value">{model.quality}</span>
                        </div>
                      </div>
                      
                      <div className="pricing-info">
                        <div className="pricing-row">
                          <span className="pricing-label">Input:</span>
                          <span className="pricing-value">${model.pricing.input}/1K tokens</span>
                        </div>
                        <div className="pricing-row">
                          <span className="pricing-label">Output:</span>
                          <span className="pricing-value">${model.pricing.output}/1K tokens</span>
                        </div>
                      </div>
                      
                      <div className="capabilities">
                        <h4>Capabilities:</h4>
                        <div className="capability-tags">
                          {model.capabilities.map((capability, index) => (
                            <span key={index} className="capability-tag">
                              {capability}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Health Monitoring Tab */}
          {activeTab === 'health' && (
            <div className="tab-content">
              <div className="health-header">
                <h2>Real-Time Model Health</h2>
                <button onClick={checkModelHealth} className="refresh-btn">
                  🔄 Refresh Status
                </button>
              </div>
              
              <div className="health-grid">
                {models.map((model) => {
                  const health = modelHealth[model.id];
                  return (
                    <div key={model.id} className="health-card">
                      <div className="health-card-header">
                        <h3>{model.name}</h3>
                        <span 
                          className="health-status"
                          style={{ backgroundColor: getStatusColor(health?.status || 'unknown') }}
                        >
                          {health?.status || 'unknown'}
                        </span>
                      </div>
                      
                      <div className="health-metrics">
                        <div className="metric">
                          <span className="metric-label">Response Time:</span>
                          <span className="metric-value">
                            {health?.responseTime ? `${health.responseTime}ms` : 'N/A'}
                          </span>
                        </div>
                        <div className="metric">
                          <span className="metric-label">Uptime:</span>
                          <span className="metric-value">
                            {health?.uptime ? `${health.uptime.toFixed(1)}%` : 'N/A'}
                          </span>
                        </div>
                        <div className="metric">
                          <span className="metric-label">Last Checked:</span>
                          <span className="metric-value">
                            {health?.lastChecked ? new Date(health.lastChecked).toLocaleTimeString() : 'N/A'}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Model Playground Tab */}
          {activeTab === 'playground' && (
            <div className="tab-content">
              <div className="playground-container">
                <h2>Interactive Model Testing</h2>
                
                <div className="playground-controls">
                  <div className="control-group">
                    <label htmlFor="model-select">Select Model:</label>
                    <select 
                      id="model-select"
                      value={selectedModel} 
                      onChange={(e) => setSelectedModel(e.target.value)}
                      className="model-select"
                    >
                      {models.map((model) => (
                        <option key={model.id} value={model.id}>
                          {model.name} ({model.provider})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                
                <div className="playground-interface">
                  <div className="prompt-section">
                    <label htmlFor="test-prompt">Test Prompt:</label>
                    <textarea
                      id="test-prompt"
                      value={testPrompt}
                      onChange={(e) => setTestPrompt(e.target.value)}
                      placeholder="Enter your test prompt here..."
                      className="prompt-textarea"
                      rows={4}
                    />
                    <button 
                      onClick={testModel}
                      disabled={testLoading || !selectedModel || !testPrompt.trim()}
                      className="test-btn"
                    >
                      {testLoading ? '🔄 Testing...' : '🚀 Test Model'}
                    </button>
                  </div>
                  
                  <div className="response-section">
                    <label>Model Response:</label>
                    <div className="response-container">
                      {testLoading ? (
                        <div className="response-loading">
                          <div className="spinner"></div>
                          <p>Generating response...</p>
                        </div>
                      ) : (
                        <pre className="response-text">{testResponse || 'No response yet. Enter a prompt and click "Test Model".'}</pre>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Model Comparison Tab */}
          {activeTab === 'comparison' && (
            <div className="tab-content">
              <div className="comparison-container">
                <h2>Model Comparison Tool</h2>
                
                <div className="comparison-controls">
                  <div className="model-selectors">
                    <div className="model-selector">
                      <label>Model A:</label>
                      <select 
                        value={comparisonModels[0]} 
                        onChange={(e) => setComparisonModels([e.target.value, comparisonModels[1]])}
                        className="model-select"
                      >
                        {models.map((model) => (
                          <option key={model.id} value={model.id}>
                            {model.name}
                          </option>
                        ))}
                      </select>
                    </div>
                    
                    <div className="vs-divider">VS</div>
                    
                    <div className="model-selector">
                      <label>Model B:</label>
                      <select 
                        value={comparisonModels[1]} 
                        onChange={(e) => setComparisonModels([comparisonModels[0], e.target.value])}
                        className="model-select"
                      >
                        {models.map((model) => (
                          <option key={model.id} value={model.id}>
                            {model.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                  
                  <div className="comparison-prompt">
                    <label htmlFor="comparison-prompt">Comparison Prompt:</label>
                    <textarea
                      id="comparison-prompt"
                      value={comparisonPrompt}
                      onChange={(e) => setComparisonPrompt(e.target.value)}
                      placeholder="Enter a prompt to test both models..."
                      className="prompt-textarea"
                      rows={3}
                    />
                    <button 
                      onClick={compareModels}
                      disabled={comparisonLoading || !comparisonModels[0] || !comparisonModels[1] || !comparisonPrompt.trim()}
                      className="compare-btn"
                    >
                      {comparisonLoading ? '🔄 Comparing...' : '⚖️ Compare Models'}
                    </button>
                  </div>
          </div>

                <div className="comparison-results">
                  {comparisonLoading ? (
                    <div className="comparison-loading">
                      <div className="spinner"></div>
                      <p>Comparing models...</p>
                    </div>
                  ) : (
                    <div className="results-grid">
                      {comparisonResults.map((result, index) => (
                        <div key={index} className="result-card">
                          <h3>{result?.model || models.find(m => m.id === comparisonModels[index])?.name || `Model ${index + 1}`}</h3>
                          {result ? (
                            result.error ? (
                              <div className="error-result">
                                <div className="error-icon">❌</div>
                                <div className="error-text">{result.error}</div>
                                {result.responseTime && (
                                  <div className="error-time">Response time: {result.responseTime}ms</div>
                                )}
                              </div>
                            ) : (
                              <div className="result-content">
                                <div className="result-metrics">
                                  <span className="metric">⏱️ {result.responseTime}ms</span>
                                  <span className="metric">🎯 {result.tokens || 0} tokens</span>
                                  {result.success !== undefined && (
                                    <span className={`metric ${result.success ? 'success' : 'error'}`}>
                                      {result.success ? '✅ Success' : '❌ Failed'}
                                    </span>
                                  )}
                                </div>
                                <pre className="result-response">{result.response}</pre>
                              </div>
                            )
                          ) : (
                            <div className="no-result">No comparison result yet.</div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
        </div>
    );
  };

export default AiModels;