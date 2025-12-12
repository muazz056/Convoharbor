import React, { useState, useEffect } from 'react';
import './Integrations.css';
import InnerNavbar from '../navbar/InnerNavbar';
import Sidebar from '../Sidebar/Sidebar';
import SimpleLoader from '../common/SimpleLoader';
import { useAuth } from '../../contexts/AuthContext';
import { chatbotService } from '../../services/chatbot.service';
import widgetService from '../../services/widget.service';
import EmbedScriptModal from '../EmbedScriptModal/EmbedScriptModal';

const Integrations = () => {
  const { user } = useAuth();
  const [chatbots, setChatbots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isEmbedOpen, setIsEmbedOpen] = useState(false);
  const [embedScript, setEmbedScript] = useState('');
  const [selectedChatbotId, setSelectedChatbotId] = useState(null);

  useEffect(() => {
    loadChatbots();
  }, []);

  const loadChatbots = async () => {
    try {
      setLoading(true);
      setError(null);
      
      console.log('🔗 Integrations: Loading chatbots...');
      const response = await chatbotService.getChatbots();
      
      if (response && response.chatbots) {
        setChatbots(response.chatbots);
        console.log(`✅ Integrations: Loaded ${response.chatbots.length} chatbots`);
      } else {
        setChatbots([]);
        console.log('⚠️ Integrations: No chatbots found');
      }
    } catch (err) {
      console.error('❌ Integrations: Error loading chatbots:', err);
      setError('Failed to load chatbots. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const loadEmbedScript = async (chatbotId) => {
    try {
      setError(null);
      if (user?.token) {
        widgetService.setAuthToken(user.token);
      }
      const script = await widgetService.generateScript(chatbotId);
      setEmbedScript(script);
      setSelectedChatbotId(chatbotId); // Store the chatbot ID for the modal
      setIsEmbedOpen(true);
    } catch (e) {
      console.error('Failed to generate embed script', e);
      setError(e.message || 'Failed to generate embed script');
    }
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      active: { label: 'Active', class: 'status-active' },
      inactive: { label: 'Inactive', class: 'status-inactive' },
      training: { label: 'Training', class: 'status-training' }
    };
    
    const config = statusConfig[status] || { label: status, class: 'status-unknown' };
    return (
      <span className={`status-badge ${config.class}`}>
        <span className="status-dot"></span>
        {config.label}
      </span>
    );
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    } catch (error) {
      return 'Invalid Date';
    }
  };

  if (loading) {
    return (
      <>
        <div className="layout-container">
          <Sidebar />
          
          <div className="main-content">
            <InnerNavbar />
            <div className="page" id="integrations">
              <SimpleLoader message="Loading chatbots..." />
            </div>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="layout-container">
        <Sidebar />
        
        <div className="main-content">
          <InnerNavbar />
          <div className="page" id="integrations">
            <div className="page-header">
              <h1 className="page-title">🔗 Integrations</h1>
              <p className="page-subtitle">
                Embed your chatbots on websites and applications
              </p>
            </div>

          {error && (
            <div className="error-message">
              <span className="error-icon">⚠️</span>
              {error}
              <button onClick={loadChatbots} className="retry-btn">
                🔄 Retry
              </button>
            </div>
          )}

          <div className="integrations-stats">
            <div className="stat-card">
              <div className="stat-number">{chatbots.length}</div>
              <div className="stat-label">Total Chatbots</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">
                {chatbots.filter(bot => bot.status === 'active').length}
              </div>
              <div className="stat-label">Active Chatbots</div>
            </div>
            {/* Only show inactive card if there are inactive chatbots */}
            {chatbots.filter(bot => bot.status === 'inactive').length > 0 && (
              <div className="stat-card">
                <div className="stat-number">
                  {chatbots.filter(bot => bot.status === 'inactive').length}
                </div>
                <div className="stat-label">Inactive</div>
              </div>
            )}
            {/* Only show training card if there are chatbots in training */}
            {chatbots.filter(bot => bot.status === 'training').length > 0 && (
              <div className="stat-card">
                <div className="stat-number">
                  {chatbots.filter(bot => bot.status === 'training').length}
                </div>
                <div className="stat-label">Training</div>
              </div>
            )}
          </div>

          {chatbots.length === 0 ? (
            <div className="no-chatbots">
              <div className="no-chatbots-icon">🤖</div>
              <h3>No Chatbots Found</h3>
              <p>Create your first chatbot to start integrating it into your applications.</p>
              <button 
                onClick={() => window.location.href = '/create-chatbot'} 
                className="create-chatbot-btn"
              >
                ➕ Create Your First Chatbot
              </button>
            </div>
          ) : (
            <div className="chatbots-grid">
              {chatbots.map((chatbot) => (
                <div key={chatbot.id} className="integration-card">
                  <div className="card-header">
                    <div className="chatbot-info">
                      <h3 className="chatbot-name">{chatbot.name}</h3>
                      <p className="chatbot-description">
                        {chatbot.description || 'No description provided'}
                      </p>
                    </div>
                    <div className="chatbot-status">
                      {getStatusBadge(chatbot.status)}
                    </div>
                  </div>

                  <div className="card-body">
                    <div className="chatbot-details">
                      <div className="detail-row">
                        <span className="detail-label">🤖 Type:</span>
                        <span className="detail-value">{chatbot.type || 'General'}</span>
                      </div>
                      <div className="detail-row">
                        <span className="detail-label">🧠 AI Model:</span>
                        <span className="detail-value">{chatbot.ai_model || 'Not configured'}</span>
                      </div>
                      <div className="detail-row">
                        <span className="detail-label">📅 Created:</span>
                        <span className="detail-value">{formatDate(chatbot.created_at)}</span>
                      </div>
                    </div>
                  </div>

                  <div className="card-footer">
                    <button
                      className={`embed-btn ${chatbot.status !== 'active' ? 'disabled' : ''}`}
                      onClick={() => loadEmbedScript(chatbot.id)}
                      disabled={chatbot.status !== 'active'}
                      title={chatbot.status !== 'active' ? 'Chatbot must be active to embed' : 'Get embed code'}
                    >
                      <span className="btn-icon">📋</span>
                      Get Embed Code
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
          </div>
        </div>
      </div>

      <EmbedScriptModal 
        isOpen={isEmbedOpen} 
        onClose={() => setIsEmbedOpen(false)} 
        script={embedScript}
        chatbotId={selectedChatbotId}
        publicAppUrl={process.env.REACT_APP_PUBLIC_APP_URL || window.location.origin}
      />
    </>
  );
};

export default Integrations;
