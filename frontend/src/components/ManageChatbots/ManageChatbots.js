import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { chatbotService } from '../../services/chatbot.service';
import Navbar from '../navbar/navbar';
import Sidebar from '../Sidebar/Sidebar';
import SimpleLoader from '../common/SimpleLoader';
import './ManageChatbots.css';

const ManageChatbots = () => {
    const navigate = useNavigate();
    const [chatbots, setChatbots] = useState([]);
    const [filteredChatbots, setFilteredChatbots] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [user, setUser] = useState(null);
    const [deleteLoading, setDeleteLoading] = useState(null); // Track which chatbot is being deleted
    
    // Filter and search states
    const [searchTerm, setSearchTerm] = useState('');
    const [emailFilter, setEmailFilter] = useState('');
    const [uniqueEmails, setUniqueEmails] = useState([]);

    useEffect(() => {
        // Check if user is super admin
        const userData = localStorage.getItem('userData');
        if (userData) {
            const parsedUser = JSON.parse(userData);
            setUser(parsedUser);
            
            if (parsedUser.role !== 'super_admin') {
                navigate('/overview'); // Redirect if not super admin
                return;
            }
        } else {
            navigate('/login');
            return;
        }

        loadAllChatbots();
    }, [navigate]);

    // Reload data when filters change
    useEffect(() => {
        if (!loading) {
            loadAllChatbots();
        }
    }, [emailFilter, searchTerm]);

    // Listen for chatbot updates and refresh data
    useEffect(() => {
        const handleStorageChange = () => {
            if (localStorage.getItem('chatbot_updated')) {
                console.log('🔄 Chatbot updated, refreshing data...');
                localStorage.removeItem('chatbot_updated');
                loadAllChatbots();
            }
        };

        window.addEventListener('storage', handleStorageChange);
        
        // Also check on focus (when returning from config page)
        const handleFocus = () => {
            if (localStorage.getItem('chatbot_updated')) {
                console.log('🔄 Page focused, checking for updates...');
                localStorage.removeItem('chatbot_updated');
                loadAllChatbots();
            }
        };

        window.addEventListener('focus', handleFocus);

        return () => {
            window.removeEventListener('storage', handleStorageChange);
            window.removeEventListener('focus', handleFocus);
        };
    }, []);

    const loadAllChatbots = async () => {
        try {
            setLoading(true);
            console.log('🔄 ManageChatbots: Loading all chatbots...');
            
            // Build query parameters for filtering and search
            const params = new URLSearchParams();
            if (emailFilter) params.append('email', emailFilter);
            if (searchTerm) params.append('search', searchTerm);
            
            const response = await chatbotService.getAllChatbots(params.toString());
            console.log('📋 ManageChatbots: API response:', response);
            console.log('📋 ManageChatbots: Chatbots array:', response.chatbots);
            
            setChatbots(response.chatbots || []);
            setFilteredChatbots(response.chatbots || []);
            setUniqueEmails(response.filters?.unique_emails || []);
        } catch (err) {
            console.error('❌ Error loading chatbots:', err);
            setError('Failed to load chatbots');
        } finally {
            setLoading(false);
        }
    };

    const handleEditChatbot = (chatbotId) => {
        console.log('🔧 ManageChatbots: Navigating to edit chatbot:', chatbotId);
        console.log('🔧 ManageChatbots: Navigate function:', typeof navigate);
        
        try {
            // Navigate to configuration with super admin flag
            const url = `/configuration-design?chatbot_id=${chatbotId}&super_admin=true`;
            console.log('🔧 ManageChatbots: Navigating to URL:', url);
            navigate(url);
            console.log('🔧 ManageChatbots: Navigation completed');
        } catch (error) {
            console.error('❌ ManageChatbots: Navigation error:', error);
        }
    };

    const handleDeleteChatbot = async (chatbotId, chatbotName) => {
        // Show confirmation dialog
        const confirmDelete = window.confirm(
            `⚠️ Are you sure you want to permanently delete the chatbot "${chatbotName}"?\n\n` +
            `This action cannot be undone and will:\n` +
            `• Delete all conversations and chat history\n` +
            `• Remove all uploaded documents and knowledge base\n` +
            `• Delete all configuration settings\n\n` +
            `Type "DELETE" to confirm this action.`
        );

        if (!confirmDelete) {
            return;
        }

        // Additional confirmation for super admin
        const confirmText = prompt(
            `🚨 FINAL CONFIRMATION\n\n` +
            `You are about to permanently delete "${chatbotName}".\n` +
            `This will affect the tenant and all their data.\n\n` +
            `Type "DELETE" exactly to proceed:`
        );

        if (confirmText !== 'DELETE') {
            alert('❌ Deletion cancelled. You must type "DELETE" exactly to confirm.');
            return;
        }

                try {
                    setDeleteLoading(chatbotId);
                    console.log('🗑️ ManageChatbots: Super admin deleting chatbot:', chatbotId);
                    
                    // Use super admin delete endpoint
                    await chatbotService.deleteChatbotAdmin(chatbotId);
                    
                    // Remove from local state
                    setChatbots(prevChatbots => 
                        prevChatbots.filter(chatbot => chatbot.id !== chatbotId)
                    );
                    setFilteredChatbots(prevChatbots => 
                        prevChatbots.filter(chatbot => chatbot.id !== chatbotId)
                    );
                    
                    console.log('✅ ManageChatbots: Super admin deleted chatbot successfully');
                    alert(`✅ Chatbot "${chatbotName}" has been permanently deleted.`);
                    
                } catch (error) {
                    console.error('❌ ManageChatbots: Super admin delete error:', error);
                    alert(`❌ Failed to delete chatbot: ${error.message}`);
                } finally {
                    setDeleteLoading(null);
        }
    };

    const formatDate = (dateString) => {
        if (!dateString) return 'N/A';
        return new Date(dateString).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    };

    if (loading) {
        return (
            <div className="manage-chatbots-page">
                <Navbar />
                <div className="manage-chatbots-container">
                    <Sidebar />
                    <div className="manage-chatbots-content">
                        <SimpleLoader message="Loading all chatbots..." />
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="manage-chatbots-page">
            <Navbar />
            <div className="manage-chatbots-container">
                <Sidebar />
                <div className="manage-chatbots-content">
                    <div className="manage-chatbots-header">
                        <h1>🤖 Manage All Chatbots</h1>
                        <p className="header-subtitle">
                            Manage all chatbots across all tenants
                        </p>
                        
                        {/* Search and Filter Controls */}
                        <div className="search-filter-controls">
                            <div className="search-bar">
                                <input
                                    type="text"
                                    placeholder="🔍 Search chatbots, users, or tenants..."
                                    value={searchTerm}
                                    onChange={(e) => setSearchTerm(e.target.value)}
                                    className="search-input"
                                />
                            </div>
                            
                            <div className="filter-controls">
                                <select
                                    value={emailFilter}
                                    onChange={(e) => setEmailFilter(e.target.value)}
                                    className="email-filter"
                                >
                                    <option value="">👥 All Users</option>
                                    {uniqueEmails.map((email) => (
                                        <option key={email} value={email}>
                                            📧 {email}
                                        </option>
                                    ))}
                                </select>
                                
                                <button 
                                    onClick={() => {
                                        setSearchTerm('');
                                        setEmailFilter('');
                                    }}
                                    className="clear-filters-btn"
                                    disabled={!searchTerm && !emailFilter}
                                >
                                    🗑️ Clear Filters
                                </button>
                                
                        <button 
                            onClick={() => {
                                console.log('🔄 Manual refresh triggered');
                                loadAllChatbots();
                            }}
                                    className="refresh-btn"
                                >
                                    🔄 Refresh
                        </button>
                            </div>
                        </div>
                    </div>

                    {error && (
                        <div className="error-message">
                            <span className="error-icon">⚠️</span>
                            {error}
                        </div>
                    )}

                    <div className="chatbots-stats">
                        <div className="stat-card">
                            <div className="stat-number">{filteredChatbots.length}</div>
                            <div className="stat-label">
                                {searchTerm || emailFilter ? 'Filtered' : 'Total'} Chatbots
                            </div>
                        </div>
                        <div className="stat-card">
                            <div className="stat-number">
                                {new Set(filteredChatbots.map(bot => bot.tenant_name)).size}
                            </div>
                            <div className="stat-label">Active Tenants</div>
                        </div>
                        <div className="stat-card">
                            <div className="stat-number">
                                {new Set(filteredChatbots.map(bot => bot.created_by_email).filter(email => email !== 'Unknown')).size}
                            </div>
                            <div className="stat-label">Unique Users</div>
                        </div>
                    </div>

                    <div className="chatbots-grid">
                        {filteredChatbots.length === 0 ? (
                            <div className="no-chatbots">
                                <div className="no-chatbots-icon">🤖</div>
                                <h3>No Chatbots Found</h3>
                                <p>
                                    {searchTerm || emailFilter 
                                        ? 'No chatbots match your current filters. Try adjusting your search or filter criteria.'
                                        : 'No chatbots have been created yet across all tenants.'
                                    }
                                </p>
                                {(searchTerm || emailFilter) && (
                                    <button 
                                        onClick={() => {
                                            setSearchTerm('');
                                            setEmailFilter('');
                                        }}
                                        className="clear-filters-btn"
                                        style={{ marginTop: '1rem' }}
                                    >
                                        🗑️ Clear All Filters
                                    </button>
                                )}
                            </div>
                        ) : (
                            filteredChatbots.map((chatbot) => {
                                // Normalize provider/model so UI reflects latest configuration regardless of where it's stored
                                const config = chatbot.config || {};
                                const normalizedProvider = chatbot.ai_provider || config.ai_provider || config.aiProvider || (
                                    (config.model || chatbot.model || chatbot.ai_model || '').startsWith('models/gemini') ? 'Google Gemini' : undefined
                                ) || 'Unknown';
                                const normalizedModel = chatbot.model || chatbot.ai_model || config.model || config.ai_model || 'Not configured';

                                return (
                                <div key={chatbot.id} className="chatbot-card">
                                    <div className="chatbot-card-header">
                                        <div className="chatbot-info">
                                            <h3 className="chatbot-name">{chatbot.name}</h3>
                                            <p className="chatbot-tenant">
                                                <span className="tenant-icon">🏢</span>
                                                {chatbot.tenant_name}
                                            </p>
                                        </div>
                                        <div className="chatbot-status">
                                            <span className={`status-badge ${chatbot.status}`}>
                                                {chatbot.status}
                                            </span>
                                        </div>
                                    </div>

                                    <div className="chatbot-card-body">
                                        <div className="chatbot-details">
                                            <div className="detail-row">
                                                <span className="detail-label">📝 Description:</span>
                                                <span className="detail-value">
                                                    {chatbot.description || 'No description'}
                                                </span>
                                            </div>
                                            <div className="detail-row">
                                                <span className="detail-label">👤 Created by:</span>
                                                <span className="detail-value created-by-email">
                                                    {chatbot.created_by_email || 'Unknown'}
                                                </span>
                                            </div>
                                            <div className="detail-row">
                                                <span className="detail-label">🧠 AI Provider:</span>
                                                <span className="detail-value">
                                                    {normalizedProvider}
                                                </span>
                                            </div>
                                            <div className="detail-row">
                                                <span className="detail-label">🤖 AI Model:</span>
                                                <span className="detail-value">
                                                    {normalizedModel}
                                                </span>
                                            </div>
                                            <div className="detail-row">
                                                <span className="detail-label">📊 Top K:</span>
                                                <span className="detail-value top-k-value">
                                                    {chatbot.top_k || 10} chunks
                                                </span>
                                            </div>
                                            <div className="detail-row">
                                                <span className="detail-label">🎯 Mode:</span>
                                                <span className={`detail-value mode-${chatbot.mode}`}>
                                                    {chatbot.mode || 'strict'}
                                                </span>
                                            </div>
                                            <div className="detail-row">
                                                <span className="detail-label">📅 Created:</span>
                                                <span className="detail-value">
                                                    {formatDate(chatbot.created_at)}
                                                </span>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="chatbot-card-footer">
                                        <button
                                            className="edit-chatbot-btn"
                                            onClick={(e) => {
                                                console.log('🔧 Button clicked! Event:', e);
                                                console.log('🔧 Chatbot object:', chatbot);
                                                console.log('🔧 Chatbot ID:', chatbot.id);
                                                e.preventDefault();
                                                e.stopPropagation();
                                                
                                                if (!chatbot.id) {
                                                    console.error('❌ No chatbot ID found!');
                                                    return;
                                                }
                                                
                                                handleEditChatbot(chatbot.id);
                                            }}
                                            type="button"
                                        >
                                            <span className="btn-icon">⚙️</span>
                                            Edit Configuration
                                        </button>
                                        
                                        <button
                                            className="delete-chatbot-btn"
                                            onClick={(e) => {
                                                console.log('🗑️ Delete button clicked! Event:', e);
                                                console.log('🗑️ Chatbot object:', chatbot);
                                                console.log('🗑️ Chatbot ID:', chatbot.id);
                                                e.preventDefault();
                                                e.stopPropagation();
                                                
                                                if (!chatbot.id) {
                                                    console.error('❌ No chatbot ID found!');
                                                    return;
                                                }
                                                
                                                handleDeleteChatbot(chatbot.id, chatbot.name);
                                            }}
                                            type="button"
                                            disabled={deleteLoading === chatbot.id}
                                        >
                                            {deleteLoading === chatbot.id ? (
                                                <>
                                                    <span className="btn-icon">⏳</span>
                                                    Deleting...
                                                </>
                                            ) : (
                                                <>
                                                    <span className="btn-icon">🗑️</span>
                                                    Delete Chatbot
                                                </>
                                            )}
                                        </button>
                                    </div>
                                </div>
                            )})
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ManageChatbots;
