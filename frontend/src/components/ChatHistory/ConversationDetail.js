import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

import conversationService from '../../services/conversation.service';
import MarkdownMessage from '../common/MarkdownMessage';
import './ChatHistory.css';

const ConversationDetail = () => {
    const { conversationId } = useParams();
    const navigate = useNavigate();

    const [state, setState] = useState({
        loading: true,
        error: null,
        messages: [],
        conversation: null,
    });

    useEffect(() => {
        const load = async () => {
            const token = localStorage.getItem('authToken');
            if (!token) {
                navigate('/login');
                return;
            }
            conversationService.setAuthToken(token);
            try {
                const res = await conversationService.getConversationMessages(conversationId);
                setState({ loading: false, error: null, messages: res.messages || [], conversation: res.conversation || null });
            } catch (err) {
                console.error('ConversationDetail error:', err);
                const errorMsg = err.response?.data?.error || err.message || 'Failed to load conversation.';
                setState({ loading: false, error: `Error loading conversation ${conversationId}: ${errorMsg}`, messages: [], conversation: null });
            }
        };
        load();
    }, [conversationId, navigate]);

    const formatDate = (d) => new Date(d).toLocaleString();
    const assistantColor = '#F3F4F6';
    const userColor = '#8B5CF6';

    return (
        <div className="page" id="conversation-detail">
            <div className="page-header">
                <div>
                    <h1 className="page-title">Conversation Details</h1>
                    <p className="page-subtitle">
                        {state.conversation?.title || `Conversation ${conversationId}`}
                        {state.conversation?.created_at && (
                            <span> • Started {formatDate(state.conversation.created_at)}</span>
                        )}
                    </p>
                </div>
                <button className="primary-button" onClick={() => navigate(-1)}>
                    ← Back
                </button>
            </div>

            {state.error && (
                <div className="error-message">
                    <span>⚠️ {state.error}</span>
                </div>
            )}

            {state.loading ? (
                <div className="section-card">
                    <div className="loading-state">
                        <div className="spinner"></div>
                        <p>Loading conversation...</p>
                    </div>
                </div>
            ) : (
                <div className="conv-detail-chat-container">
                    {state.messages.length === 0 ? (
                        <div className="empty-state">
                            <div className="empty-icon">💬</div>
                            <h3>No Messages</h3>
                            <p>This conversation doesn't have any messages yet.</p>
                        </div>
                    ) : (
                        <div className="conv-detail-messages">
                            <div className="conv-detail-header-info">
                                <span className="conv-detail-msg-count">{state.messages.length} messages</span>
                            </div>
                            {state.messages.map(msg => (
                                <div key={msg.id} className={`conv-message ${msg.message_type === 'user' ? 'conv-message-user' : 'conv-message-assistant'}`}>
                                    {msg.message_type !== 'user' && (
                                        <div className="conv-message-avatar">AI</div>
                                    )}
                                    <div className="conv-message-bubble" style={{
                                        background: msg.message_type === 'user' ? userColor : assistantColor,
                                        color: msg.message_type === 'user' ? '#FFFFFF' : '#111827',
                                    }}>
                                        <div className="conv-message-text">
                                            <MarkdownMessage content={msg.content || ''} />
                                        </div>
                                        <div className="conv-message-time">{formatDate(msg.created_at)}</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default ConversationDetail;
