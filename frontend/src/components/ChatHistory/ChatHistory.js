import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

import conversationService from '../../services/conversation.service';
import { chatbotService } from '../../services/chatbot.service';
import './ChatHistory.css';

const ChatHistory = () => {
    const navigate = useNavigate();
    const [state, setState] = useState({
        chatbots: [],
        conversations: [],
        selectedChatbotId: null,
        loading: true,
        conversationsLoading: false,
        error: null
    });

    // Atomic state update function to prevent race conditions
    const updateState = useCallback((updates) => {
        setState(prevState => ({ ...prevState, ...updates }));
    }, []);

    // Refresh conversations for selected chatbot
    const refreshConversations = useCallback(async () => {
        if (!state.selectedChatbotId) return;
        updateState({ conversationsLoading: true });
        try {
            const res = await conversationService.getConversations({ chatbot_id: state.selectedChatbotId, page: 1, per_page: 200 });
            console.log(`📋 Raw API response for chatbot ${state.selectedChatbotId}:`, res.conversations);
            
            // Filter to only show embed chats (exclude admin test chats and deleted conversations)
            const embedConversations = (res.conversations || []).filter(conv => {
                console.log(`🔍 Filtering conversation: ID=${conv.id}, Title="${conv.title}", Status="${conv.status}", Domain="${conv.source_domain}"`);
                const isEmbedChat = conv.title && conv.title.includes('Embed Chat');
                const isNotDeleted = conv.status !== 'deleted';
                console.log(`   ├─ Is Embed Chat: ${isEmbedChat}`);
                console.log(`   ├─ Is Not Deleted: ${isNotDeleted}`);
                console.log(`   ├─ Source Domain: ${conv.source_domain || 'None'}`);
                console.log(`   └─ Will Include: ${isEmbedChat && isNotDeleted}`);
                return isEmbedChat && isNotDeleted;
            });
            
            console.log('🔄 Refreshed conversations with website data:', embedConversations.map(c => ({ 
                id: c.id, 
                status: c.status, 
                domain: c.source_domain, 
                title: c.title 
            })));
            updateState({ conversations: embedConversations, conversationsLoading: false });
        } catch (err) {
            updateState({ error: 'Failed to refresh conversations.', conversationsLoading: false });
        }
    }, [state.selectedChatbotId]);

    // Select chatbot → load its conversations
    const handleSelectChatbot = useCallback(async (chatbotId) => {
        if (state.selectedChatbotId === chatbotId) return;
        updateState({ selectedChatbotId: chatbotId, conversationsLoading: true, conversations: [] });
        try {
            const res = await conversationService.getConversations({ chatbot_id: chatbotId, page: 1, per_page: 200 });
            console.log(`📋 Raw API response for chatbot ${chatbotId}:`, res.conversations);
            
            // Filter to only show embed chats (exclude admin test chats and deleted conversations)
            const embedConversations = (res.conversations || []).filter(conv => {
                console.log(`🔍 Filtering conversation: ID=${conv.id}, Title="${conv.title}", Status="${conv.status}", Domain="${conv.source_domain}"`);
                const isEmbedChat = conv.title && conv.title.includes('Embed Chat');
                const isNotDeleted = conv.status !== 'deleted';
                console.log(`   ├─ Is Embed Chat: ${isEmbedChat}`);
                console.log(`   ├─ Is Not Deleted: ${isNotDeleted}`);
                console.log(`   ├─ Source Domain: ${conv.source_domain || 'None'}`);
                console.log(`   └─ Will Include: ${isEmbedChat && isNotDeleted}`);
                return isEmbedChat && isNotDeleted;
            });
            
            console.log('📋 Loaded conversations with website data:', embedConversations.map(c => ({ 
                id: c.id, 
                status: c.status, 
                domain: c.source_domain, 
                title: c.title 
            })));
            updateState({ conversations: embedConversations, conversationsLoading: false });
        } catch (err) {
            updateState({ error: 'Failed to load conversations.', conversationsLoading: false });
        }
    }, [state.selectedChatbotId]);

    // Load chatbots once
    useEffect(() => {
        const loadChatbots = async () => {
            const token = localStorage.getItem('authToken');
            if (!token) {
                navigate('/login');
                return;
            }
            chatbotService.setAuthToken(token);
            conversationService.setAuthToken(token);

            try {
                const res = await chatbotService.getChatbots({ page: 1, per_page: 100 });
                updateState({ chatbots: res.chatbots || [], loading: false });
            } catch (err) {
                updateState({ error: 'Failed to load chatbots.', loading: false });
            }
        };
        loadChatbots();
    }, [navigate]);

    // Auto-refresh conversations when window gains focus (user returns from embed chat)
            useEffect(() => {
        const handleFocus = () => {
            if (state.selectedChatbotId && !state.conversationsLoading) {
                console.log('🔄 Window focused - refreshing conversations');
                refreshConversations();
            }
        };

        window.addEventListener('focus', handleFocus);
        return () => window.removeEventListener('focus', handleFocus);
    }, [state.selectedChatbotId, state.conversationsLoading, refreshConversations]);

    // Select conversation → navigate to detail page
    const handleSelectConversation = useCallback((conversationId) => {
        navigate(`/chat-history/conversation/${conversationId}`);
    }, [navigate]);

    const formatDate = (dateString) => new Date(dateString).toLocaleString();


    const cleanupConversations = async (type = 'empty') => {
        if (!window.confirm(`Are you sure you want to delete ${type === 'all' ? 'ALL' : type} embed conversations? This cannot be undone.`)) {
            return;
        }

        try {
            const token = localStorage.getItem('authToken');
            const response = await fetch(`${process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1'}/conversations/cleanup`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ type })
            });

            const data = await response.json();
            
            if (response.ok) {
                alert(`✅ ${data.message}`);
                // Refresh the current view
                if (state.selectedChatbotId) {
                    handleSelectChatbot(state.selectedChatbotId);
                }
            } else {
                alert(`❌ Error: ${data.error}`);
            }
        } catch (error) {
            console.error('Cleanup error:', error);
            alert('❌ Failed to cleanup conversations');
        }
    };

    if (state.loading) {
  return (
                    <div className="loading-container">
                            <div className="spinner" />
                            <p>Loading…</p>
                        </div>
        );
    }

    return (
                <div className="page" id="chat-history">
            <div className="page-header">
                        <div>
                            <h1 className="page-title">Embed Conversation History</h1>
                            <p className="page-subtitle">Review and manage conversations from your embed widgets</p>
            </div>
                    <div className="header-buttons">
                            {state.selectedChatbotId && (
                                <>
                                  <button 
                                      className="primary-button" 
                                      onClick={() => updateState({ selectedChatbotId: null, conversations: [] })}
                                  >
                                      ← Back to Chatbots
                                  </button>
                                  <div className="dropdown" style={{ marginLeft: 12 }}>
                                      <button className="btn btn-outline-danger dropdown-toggle" type="button" data-bs-toggle="dropdown">
                                          🧹 Cleanup
                                      </button>
                                      <ul className="dropdown-menu">
                                          <li>
                                            <button className="dropdown-item text-danger" onClick={() => cleanupConversations('all')}>
                                              Delete All embeded chats
                                            </button>
                                          </li>
                                      </ul>
                                  </div>
                                </>
                            )}
                    </div>
                  </div>

                    {state.error && (
                        <div className="error-message">
                            <span>⚠️ {state.error}</span>
                        </div>
                    )}

                    <div className="content">
                        <div className="chatbot-grid">
                            {!state.selectedChatbotId ? (
                                // Chatbots list
                                state.chatbots.length > 0 ? (
                                    state.chatbots.map(chatbot => (
                                        <div
                                            key={chatbot.id}
                                            className="chatbot-card clickable"
                                            onClick={() => handleSelectChatbot(chatbot.id)}
                                        >
                                            <div className="card-header">
                                                <div className="chatbot-info">
                                                    <h3 className="chatbot-name">{chatbot.name}</h3>
                                                    <p className="chatbot-description">{chatbot.description || 'No description'}</p>
                                                </div>
                                                <div className="chatbot-meta">
                                                    <span className="chatbot-type">{chatbot.type || 'general'}</span>
                                                    <span className="chatbot-model">{chatbot.ai_provider || 'AI'}: {chatbot.ai_model || 'model'}</span>
                                                </div>
                                            </div>
                                        </div>
                                    ))
                                ) : (
                                    <div className="empty-state">
                                        <div className="empty-icon">🤖</div>
                                        <h3>No Chatbots Found</h3>
                                        <p>Create a chatbot first to see its conversations here.</p>
                                    </div>
                                )
                            ) : (
                                // Conversations list for selected bot
                                state.conversationsLoading ? (
                                    <div className="loading-state">
                                        <div className="spinner"></div>
                                        <p>Loading conversations...</p>
                </div>
                                ) : state.conversations.length > 0 ? (
                                    state.conversations.map(conv => {
                                        console.log(`🏷️ Rendering conversation ${conv.id} with status: "${conv.status}"`);
                                        return (
                                            <div
                                                key={conv.id}
                                                className="chatbot-card conversation-card"
                                            >
                                                <div className="card-header">
                                                    <div 
                                                        className="chatbot-info clickable"
                                                        onClick={() => handleSelectConversation(conv.id)}
                                                    >
                                                        <h3 className="chatbot-name">
                                                            {conv.source_domain ? (
                                                                <>
                                                                    🌐 {conv.source_domain}
                                                                    {conv.source_metadata?.path && (
                                                                        <small className="domain-path">{conv.source_metadata.path}</small>
                                                                    )}
                                                                </>
                                                            ) : (
                                                                conv.title || `Session ${conv.session_id?.substring(0,8)}`
                                                            )}
                                                        </h3>
                                                        <p className="chatbot-description">
                                                            <span className="conversation-date">{formatDate(conv.created_at)}</span>
                                                            {conv.source_domain && (
                                                                <span className="website-info">
                                                                    from {conv.source_domain}
                                                                </span>
                                                            )}
                                                            {!conv.source_domain && conv.title && (
                                                                <span className="conversation-type">
                                                                    {conv.title.replace('Embed Chat - ', '')}
                                                                </span>
                                                            )}
                                                        </p>
                                                    </div>
                                                    <div className="conversation-actions">
                                                        <div className="conversation-status">
                                                            <span className={`status-tag ${conv.status === 'active' ? 'status-active' : 'status-inactive'}`}>
                                                                {conv.status === 'active' ? 'ACTIVE' : (conv.status === 'inactive' ? 'INACTIVE' : conv.status?.toUpperCase() || 'UNKNOWN')}
                                                            </span>
                                                        </div>
                                                        <div className="conversation-buttons">
                                                            <button
                                                                className="btn-view"
                                                                onClick={() => handleSelectConversation(conv.id)}
                                                                title="View conversation"
                                                            >
                                                                👁️
                                                            </button>
                                                            <button
                                                                className="btn-delete"
                                                                onClick={async (e) => {
                                                                    console.log('🗑️ Delete button clicked for conversation:', conv.id);
                                                                    e.stopPropagation();
                                                                    e.preventDefault();
                                                                    
                                                                    const title = conv.source_domain || conv.title || `Session ${conv.session_id?.substring(0,8)}`;
                                                                    console.log('🗑️ Showing confirmation dialog for:', title);
                                                                    
                                                                    if (!window.confirm(`Are you sure you want to delete "${title}"? This cannot be undone.`)) {
                                                                        console.log('🗑️ Delete cancelled by user');
                                                                        return;
                                                                    }
                                                                    
                                                                    console.log('🗑️ User confirmed deletion, proceeding...');
                                                                    
                                                                    try {
                                                                        console.log('🗑️ Calling deleteConversation API...');
                                                                        await conversationService.deleteConversation(conv.id);
                                                                        console.log('🗑️ Delete API call successful, refreshing conversations...');
                                                                        await refreshConversations();
                                                                        console.log('✅ Conversation deleted and refreshed successfully');
                                                                        alert('✅ Conversation deleted successfully');
                                                                    } catch (error) {
                                                                        console.error('❌ Delete failed:', error);
                                                                        alert(`❌ Delete failed: ${error.response?.data?.error || error.message}`);
                                                                    }
                                                                }}
                                                                title="Delete conversation"
                                                                style={{ zIndex: 1000, position: 'relative' }}
                                                            >
                                                                🗑️
                                                            </button>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })
                                ) : (
                                    <div className="empty-state">
                                        <div className="empty-icon">💬</div>
                                        <h3>No Embed Conversations Yet</h3>
                                        <p>No embed conversations found for this chatbot. Conversations from the embed widget will appear here.</p>
                                    </div>
                                )
                            )}
              </div>
            </div>
          </div>
  );
};

export default ChatHistory;