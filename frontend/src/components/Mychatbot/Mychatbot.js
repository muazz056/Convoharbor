import "./Mychatbot.css";
import SimpleLoader from '../common/SimpleLoader';
import AOS from 'aos';
import 'aos/dist/aos.css';
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { chatbotService } from '../../services/chatbot.service';
import { dataSourceService } from '../../services/datasource.service';
import widgetService from '../../services/widget.service';
import EmbedScriptModal from '../EmbedScriptModal/EmbedScriptModal';
import { useAuth } from '../../contexts/AuthContext';


  const Mychatbot = () => {
  const [chatbots, setChatbots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [knowledgeStats, setKnowledgeStats] = useState({});
  const [isEmbedOpen, setIsEmbedOpen] = useState(false);
  const [embedScript, setEmbedScript] = useState('');
  const [selectedChatbotId, setSelectedChatbotId] = useState(null);
    const { hasPermission, user } = useAuth();
    const navigate = useNavigate();

      useEffect(() => {
        AOS.init({
          duration: 800, // animation duration in ms
          easing: 'ease-in-out', // animation easing
          once: true, // animate only once
        });
      
        // Load chatbots from Sprint 2 API
        loadChatbots();
        
        // Listen for storage events to refresh when coming back from config
        const handleStorageChange = (e) => {
          if (e.key === 'chatbot_updated') {
            loadChatbots();
            localStorage.removeItem('chatbot_updated');
          }
        };
        
        window.addEventListener('storage', handleStorageChange);
        
        // Also check on focus (when returning to tab)
        const handleFocus = () => {
          if (localStorage.getItem('chatbot_updated')) {
            loadChatbots();
            localStorage.removeItem('chatbot_updated');
          }
        };
        
        window.addEventListener('focus', handleFocus);
        
        return () => {
          window.removeEventListener('storage', handleStorageChange);
          window.removeEventListener('focus', handleFocus);
        };
      }, []);

    const loadChatbots = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await chatbotService.getChatbots({ per_page: 50 });
        const chatbotList = response.chatbots || [];
        
        // Debug: Log the first chatbot to see what data we're getting
        if (chatbotList.length > 0) {
          console.log('🔍 First chatbot data:', JSON.stringify(chatbotList[0], null, 2));
        }
        
        setChatbots(chatbotList);
        
        // Load knowledge base stats for each chatbot
        const stats = {};
        await Promise.all(
          chatbotList.map(async (chatbot) => {
            try {
              const knowledgeData = await dataSourceService.getChatbotKnowledgeStats(chatbot.id);
              stats[chatbot.id] = knowledgeData;
            } catch (err) {
              console.error(`Error loading knowledge stats for chatbot ${chatbot.id}:`, err);
              stats[chatbot.id] = { total_sources: 0, total_chunks: 0, sources: [] };
            }
          })
        );
        setKnowledgeStats(stats);
      } catch (err) {
        if (err.message === 'Authentication required') {
          // Redirect to login
          window.location.href = '/login';
          return;
        }
        setError(err.message);
        console.error('Error loading chatbots:', err);
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

    const handleDelete = async (chatbotId) => {
      if (window.confirm('Are you sure you want to delete this chatbot? This action cannot be undone.')) {
        try {
          await chatbotService.deleteChatbot(chatbotId);
          // Refresh the list after deletion
          loadChatbots();
        } catch (err) {
          setError(err.message || 'Failed to delete chatbot');
        }
      }
    };

    const getStatusBadge = (status) => {
      const statusConfig = {
        active: { class: 'status-active', label: 'Active' },
        inactive: { class: 'status-inactive', label: 'Inactive' },
        training: { class: 'status-training', label: 'Training' }
      };
      
      const config = statusConfig[status] || { class: 'status-inactive', label: status };
      return (
        <span className={`status-badge ${config.class}`}>
          <span className="status-dot"></span>
          {config.label}
        </span>
      );
    };

    const getTypeBadge = (type) => {
      const typeConfig = {
        support: { label: 'Support', icon: '🎧' },
        sales: { label: 'Sales', icon: '💼' },
        general: { label: 'General', icon: '🤖' },
        hr: { label: 'HR', icon: '👥' },
        technical: { label: 'Technical', icon: '🔧' }
      };
      
      const config = typeConfig[type] || { label: type, icon: '🤖' };
      return `${config.icon} ${config.label}`;
    };

    const formatDate = (dateString) => {
      if (!dateString) return 'N/A';
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    };

    return (
      <>
            <div className="page" id="chatbots" >
              <div className="page-header">
                <h1 className="page-title">My Chatbots</h1>
                <p className="page-subtitle">Manage all your AI assistants</p>
                {hasPermission('manage_chatbots') && (
                  <Link to="/create-chatbot" className="primary-button">
                    <span>+ New Chatbot</span>
                  </Link>
                )}
              </div>

              {/* Error Message */}
              {error && (
                <div className="error-message">
                  <span>⚠️ {error}</span>
                  <button onClick={loadChatbots} className="retry-button">Retry</button>
                </div>
              )}

              {/* Loading State */}
              {loading ? (
                <div className="section-card">
                  <SimpleLoader message="Loading your chatbots..." />
              </div>
              ) : chatbots.length === 0 ? (
                /* Empty State */
              <div className="section-card">
                  <div className="empty-state">
                    <div className="empty-icon">🤖</div>
                    <h3>No Chatbots Yet</h3>
                    <p>Create your first AI assistant to get started!</p>
                    {hasPermission('manage_chatbots') && (
                      <Link to="/create-chatbot" className="primary-button">
                        Create Your First Chatbot
                      </Link>
                    )}
                  </div>
                </div>
              ) : (
                /* Chatbots Grid */
                <div className="chatbots-grid">
                  {chatbots.map(chatbot => {
                    const stats = knowledgeStats[chatbot.id] || { total_sources: 0, total_chunks: 0 };
                    const canEmbed = stats.total_sources > 0;
                    return (
                      <div key={chatbot.id} className="chatbot-card">
                        <div className="card-header">
                          <div className="chatbot-info">
                            <h3 className="chatbot-name">{chatbot.name}</h3>
                            <p className="chatbot-type">{getTypeBadge(chatbot.type)}</p>
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
                              <span className="label">AI Provider:</span>
                              <span className="value">
                                {(chatbot.ai_provider || (chatbot.config && (chatbot.config.ai_provider || chatbot.config.aiProvider)) || ((chatbot.model || chatbot.ai_model || (chatbot.config && chatbot.config.model) || '').startsWith('models/gemini') ? 'Google Gemini' : '') || 'Not configured')}
                              </span>
                            </div>
                            <div className="detail-row">
                              <span className="label">AI Model:</span>
                              <span className="value">{chatbot.model || chatbot.ai_model || (chatbot.config && (chatbot.config.model || chatbot.config.ai_model)) || 'Not configured'}</span>
                            </div>
                            <div className="detail-row">
                              <span className="label">Created:</span>
                              <span className="value">{formatDate(chatbot.created_at)}</span>
                            </div>
                            <div className="detail-row">
                              <span className="label">Temperature:</span>
                              <span className="value">{chatbot.temperature || 'Default'}</span>
                            </div>
                            <div className="detail-row knowledge-stats">
                              <span className="label">📚 Knowledge Base:</span>
                              <span className="value">
                                {stats.total_sources} documents, {stats.total_chunks} chunks
                              </span>
                            </div>
                          </div>
                        </div>

                        <div className="card-actions">
                          {hasPermission('manage_chatbots') && (
                            <Link 
                              to={`/configuration-design?id=${chatbot.id}`}
                              className="action-button primary"
                            >
                              ⚙️ Configure
                            </Link>
                          )}
                          <Link 
                            to={`/chatbot/${chatbot.id}/test`}
                            className="action-button secondary"
                          >
                            🧪 Test Chat
                          </Link>
                          {hasPermission('manage_chatbots') && (
                            <button 
                              onClick={() => handleDelete(chatbot.id)}
                              className="action-button danger"
                            >
                              🗑️ Delete
                            </button>
                          )}
                          {hasPermission('manage_chatbots') && canEmbed && (
                            <button 
                              onClick={() => loadEmbedScript(chatbot.id)}
                              className="action-button success"
                            >
                              📋 Embed
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
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

export default Mychatbot;