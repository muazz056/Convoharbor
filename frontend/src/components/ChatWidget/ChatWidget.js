import React, { useState, useEffect, useRef } from 'react';
import { useWebSocket } from '../../contexts/WebSocketContext';
import { useAuth } from '../../contexts/AuthContext';
import MarkdownMessage from '../common/MarkdownMessage';
import './ChatWidget.css';

const ChatWidget = ({ publicMode = false, testMode = false, chatbotId, conversationId: externalConversationId, externalSocket = null, onClose }) => {
    console.log('🚀🚀🚀 ChatWidget MOUNTING - Props:', { publicMode, testMode, chatbotId, externalConversationId });

    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isTyping, setIsTyping] = useState(false);
    const [conversationId, setConversationId] = useState(externalConversationId || null);
    const [chatbotInfo, setChatbotInfo] = useState(null);
    const [themeConfig, setThemeConfig] = useState(null);
    const [showRating, setShowRating] = useState(false);
    const [ratingMessage, setRatingMessage] = useState('');
    const [selectedRating, setSelectedRating] = useState(0);
    const [ratingStep, setRatingStep] = useState('none'); // 'none' | 'stars' | 'feedback' | 'thankyou'
    const [ratingFeedback, setRatingFeedback] = useState('');
    const [ratingSubmitting, setRatingSubmitting] = useState(false);
    const ratingSubmittedRef = useRef(false);
    const { socket: contextSocket, isConnected } = useWebSocket();
    const { user } = useAuth();
    const socket = externalSocket || contextSocket;
    const messagesEndRef = useRef(null);
    const messagesContainerRef = useRef(null);
    const loadedFromAPI = useRef(false);
    const [descriptionExpanded, setDescriptionExpanded] = useState(false);
    const descriptionTimerRef = useRef(null);

    // Storage key for test mode (local-only messages)
    const getTestStorageKey = () => `test_widget_messages_${chatbotId}`;

    const handleClose = () => {
        setIsOpen(false);
        // In test mode, do NOT call onClose() — the toggle in Mychatbot
        // should stay ON. The X button only collapses the chat panel back
        // to the launcher bubble. The widget is only fully removed when
        // the user explicitly toggles the test chat OFF (or switches to
        // a different chatbot's test chat).
        if (!testMode && onClose) {
            onClose();
        }
    };

    const toggleDescription = () => {
        if (descriptionExpanded) {
            setDescriptionExpanded(false);
            if (descriptionTimerRef.current) {
                clearTimeout(descriptionTimerRef.current);
                descriptionTimerRef.current = null;
            }
        } else {
            setDescriptionExpanded(true);
            if (descriptionTimerRef.current) {
                clearTimeout(descriptionTimerRef.current);
            }
            descriptionTimerRef.current = setTimeout(() => {
                setDescriptionExpanded(false);
                descriptionTimerRef.current = null;
            }, 12000);
        }
    };

    // Cleanup timer on unmount
    useEffect(() => {
        return () => {
            if (descriptionTimerRef.current) {
                clearTimeout(descriptionTimerRef.current);
            }
        };
    }, []);

    // Persist rating prompt across re-mounts (when stream closes and widget rerenders)
    const getRatingStorageKey = (convId) => convId ? `convoharbor_rating_prompt_${convId}` : null;

    // NEW: Website context capture function
    const getWebsiteContext = () => {
        try {
            // Check if we're in an iframe and have website context from URL params
            const urlParams = new URLSearchParams(window.location.search);
            const contextParam = urlParams.get('website_context');
            
            if (contextParam) {
                console.log('🌐 Found website context from URL params:', contextParam);
                const parsed = JSON.parse(decodeURIComponent(contextParam));
                console.log('🌐 Parsed URL context:', parsed);
                return parsed;
            }
            
            // Check sessionStorage for context
            const storedContext = sessionStorage.getItem('convoharbor_website_context');
            if (storedContext) {
                console.log('🌐 Found website context from sessionStorage');
                return JSON.parse(storedContext);
            }
            
            // Fallback: capture current context
            console.log('🌐 Using fallback website context');
            return {
                domain: window.location.hostname,
                url: window.location.href,
                path: window.location.pathname,
                referrer: document.referrer,
                title: document.title,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            console.warn('⚠️ Failed to get website context:', error);
            return {};
        }
    };

    // Fetch chatbot info or use defaults
    useEffect(() => {
        const fetchChatbotInfo = async () => {
            const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
            
            // If no chatbotId provided, try to fetch the first available chatbot or use fallback
            if (!chatbotId) {
                console.log('🤖 No chatbotId provided - trying to fetch first available chatbot');
                try {
                    // Try to get first active chatbot for testing
                    const res = await fetch(`${baseURL}/chatbots?page=1&per_page=1`);
                    if (res.ok) {
                        const data = await res.json();
                        if (data.chatbots && data.chatbots.length > 0) {
                            const firstBot = data.chatbots[0];
                            console.log('✅ Using first available chatbot:', firstBot);
                            
                            const config = firstBot.config || {};
                            const theme = config.theme || {};
                            
                            const themeSettings = {
                                position: theme.position || 'bottom-right',
                                primaryColor: theme.primaryColor || '#6366F1',
                                welcomeMessage: theme.welcomeMessage || config.prompts?.greeting || `Hello! I'm ${firstBot.name || 'AI Assistant'}. How can I help you today?`
                            };
                            
                            setThemeConfig(themeSettings);
                            setChatbotInfo(firstBot);
                            
                            // Set initial welcome message only if no messages loaded from API
                            if (messages.length === 0 && !loadedFromAPI.current) {
                                setMessages([{
                                    message_type: 'assistant',
                                    content: themeSettings.welcomeMessage,
                                    timestamp: new Date().toISOString()
                                }]);
                            }
                            return;
                        }
                    }
                } catch (error) {
                    console.warn('⚠️ Could not fetch default chatbot:', error);
                }
                
                // Fallback: use default config without specific chatbot
                console.log('🤖 Using fallback default config (no specific chatbot)');
                const defaultTheme = {
                    position: 'bottom-right',
                    primaryColor: '#6366F1',
                    welcomeMessage: 'Hello! I\'m your AI Assistant. How can I help you today?'
                };
                setThemeConfig(defaultTheme);
                setChatbotInfo({ 
                    id: null, // No specific chatbot
                    name: 'AI Assistant', 
                    config: {
                        ai_provider: 'OpenAI',
                        ai_model: 'gpt-4o',
                        theme: defaultTheme
                    }
                });
                
                // Set initial welcome message only if no messages loaded from API
                if (messages.length === 0 && !loadedFromAPI.current) {
                    setMessages([{
                        message_type: 'assistant',
                        content: defaultTheme.welcomeMessage,
                        timestamp: new Date().toISOString()
                    }]);
                }
                return;
            }

            try {
                console.log('🤖 Fetching chatbot info for ID:', chatbotId);
                const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
                const res = await fetch(`${baseURL}/chatbots/${chatbotId}/public`);
                const data = await res.json();
                console.log('🤖 Chatbot info loaded:', data.chatbot);
                setChatbotInfo(data.chatbot);
                
                // Load theme configuration from admin settings
                const config = data.chatbot?.config || {};
                const theme = config.theme;
                
                console.log('🎨 Theme debug - Full config:', config);
                console.log('🎨 Theme debug - Theme object:', theme);
                
                // Always set theme config - use admin settings or fallback defaults
                const themeSettings = {
                    position: theme?.position || 'bottom-right',
                    primaryColor: theme?.primaryColor || '#6366F1',
                    welcomeMessage: theme?.welcomeMessage || config.prompts?.greeting || `Hello! I'm ${data.chatbot?.name || 'Assistant'}. How can I help you today?`
                };
                
                console.log('🎨 Theme debug - Final theme settings:', themeSettings);
                setThemeConfig(themeSettings);

                // Set initial welcome message when theme loads (only if no messages exist and none loaded from API)
                if (messages.length === 0 && !loadedFromAPI.current) {
                    if (testMode) {
                        // Load from localStorage in test mode
                        try {
                            const stored = localStorage.getItem(getTestStorageKey());
                            if (stored) {
                                const parsed = JSON.parse(stored);
                                if (Array.isArray(parsed) && parsed.length > 0) {
                                    console.log('📦 Loaded test messages from localStorage:', parsed.length);
                                    setMessages(parsed);
                                    return;
                                }
                            }
                        } catch (e) {
                            console.warn('⚠️ Failed to load test messages:', e);
                        }
                    }
                    setMessages([{
                        message_type: 'assistant',
                        content: themeSettings.welcomeMessage,
                        timestamp: new Date().toISOString()
                    }]);
                }

            } catch (error) {
                console.error('❌ Failed to fetch chatbot info:', error);
                // Fallback theme settings
                const fallbackTheme = {
                    position: 'bottom-right',
                    primaryColor: '#6366F1',
                    welcomeMessage: `Hello! I'm your assistant. How can I help you today?`
                };
                setThemeConfig(fallbackTheme);

                // Set fallback welcome message only if no messages loaded from API
                if (messages.length === 0 && !loadedFromAPI.current) {
                    if (testMode) {
                        try {
                            const stored = localStorage.getItem(getTestStorageKey());
                            if (stored) {
                                const parsed = JSON.parse(stored);
                                if (Array.isArray(parsed) && parsed.length > 0) {
                                    setMessages(parsed);
                                    return;
                                }
                            }
                        } catch (e) {}
                    }
                    setMessages([{
                        message_type: 'assistant',
                        content: fallbackTheme.welcomeMessage,
                        timestamp: new Date().toISOString()
                    }]);
                }
            }
        };

            fetchChatbotInfo();
    }, [chatbotId]);

    // Generate URL-based storage key for conversation persistence
    const getStorageKey = () => {
        // Use URL + chatbot ID (or 'default') for unique conversation per URL
        const currentUrl = window.location.href.split('?')[0]; // Remove query params
        const botKey = chatbotId || 'default';
        return `embed_conversation_${botKey}_${btoa(currentUrl).replace(/[^a-zA-Z0-9]/g, '')}`;
    };

    // Load conversation ID from localStorage on mount
    useEffect(() => {
        if (conversationId) return; // Skip if already have conversation ID
        
        const storageKey = getStorageKey();
        const stored = localStorage.getItem(storageKey);
        if (stored) {
            const storedId = Number(stored);
            console.log('🔄 Loading conversation from localStorage for URL:', window.location.href, 'ID:', storedId);
            setConversationId(storedId);
        }
    }, [chatbotId, conversationId]);
    // Restore pending rating prompt if it exists (handles widget re-mounts)
    useEffect(() => {
        try {
            if (!conversationId) return;
            const key = getRatingStorageKey(conversationId);
            const stored = key ? localStorage.getItem(key) : null;
            if (stored) {
                const parsed = JSON.parse(stored);
                if (parsed && parsed.show_rating && parsed.conversation_id === conversationId) {
                    setShowRating(true);
                    setRatingStep('stars');
                    setRatingMessage(parsed.rating_message || 'How would you rate your experience?');
                }
            }
        } catch (_) {}
        // Only run when conversationId changes
    }, [conversationId]);

    // Validate any pre-existing conversation (may have been deleted in admin)
    useEffect(() => {
        const validateExistingConversation = async () => {
            try {
                if (!chatbotId) return;
                const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
                const storageKey = getStorageKey();
                const stored = localStorage.getItem(storageKey);
                const candidateId = conversationId || (stored ? Number(stored) : null);
                if (!candidateId) return;

                const res = await fetch(`${baseURL}/conversations/${candidateId}`);
                if (res.status === 404) {
                    console.warn('⚠️ Conversation not found (404), clearing stored conversation');
                    localStorage.removeItem(storageKey);
                    setConversationId(null);
                    return;
                }
                if (!res.ok) {
                    console.warn('⚠️ Conversation validation returned ' + res.status + ', keeping conversation');
                    return;
                }
                const data = await res.json();
                const status = data?.conversation?.status || data?.status;
                if (status === 'deleted') {
                    console.warn('⚠️ Conversation was deleted, clearing stored conversation');
                    localStorage.removeItem(storageKey);
                    setConversationId(null);
                } else {
                    // Valid conversation found - set it to state if not already set
                    if (!conversationId && candidateId) {
                        setConversationId(candidateId);
                        console.log('✅ Restored conversation from localStorage:', candidateId);
                    }
                }
            } catch (err) {
                console.warn('⚠️ Conversation validation network error, keeping conversation:', err.message);
                // DON'T clear conversation on network errors — messages were already loaded
                // Only clear on explicit 404/deleted status
            }
        };
        validateExistingConversation();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [chatbotId]);

    // Load existing messages when conversation ID is available
    useEffect(() => {
        const loadExistingMessages = async () => {
            if (!conversationId || !chatbotId) return;
            // Don't load from DB while a message is being sent — the local state
            // has the latest user message and streaming response that aren't in DB yet
            if (isTyping) return;
            // Don't overwrite while a message is still streaming
            if (messages.some(m => m.isStreaming)) return;
            
            try {
                console.log('📥 Loading existing messages for conversation:', conversationId);
                const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
                const res = await fetch(`${baseURL}/conversations/${conversationId}/messages/public`);
                
                if (!res.ok) {
                    console.warn('⚠️ Failed to load messages:', res.status);
                    return;
                }
                
                const data = await res.json();
                const existingMessages = data.messages || [];
                
                if (existingMessages.length > 0) {
                    console.log('✅ Loaded', existingMessages.length, 'existing messages');
                    
                    // Convert API messages to widget format
                    const formattedMessages = existingMessages.map(msg => ({
                        message_type: msg.message_type,
                        content: msg.content,
                        timestamp: msg.created_at || msg.timestamp
                    }));
                    
                    // If the first message is not the welcome message, prepend it
                    const welcomeText = themeConfig?.welcomeMessage || '';
                    const firstMsg = formattedMessages[0];
                    if (welcomeText && firstMsg && firstMsg.content !== welcomeText) {
                        formattedMessages.unshift({
                            message_type: 'assistant',
                            content: welcomeText,
                            timestamp: formattedMessages[0]?.timestamp || new Date().toISOString()
                        });
                    }
                    
                    // Replace welcome message with actual conversation history
                    loadedFromAPI.current = true;
                    setMessages(formattedMessages);
                } else {
                    console.log('📝 No existing messages found, keeping welcome message');
                }
                
            } catch (error) {
                console.error('❌ Error loading existing messages:', error);
                // Keep welcome message on error
            }
        };
        
        loadExistingMessages();
    }, [conversationId, chatbotId, isTyping]);

    // Auto-scroll to bottom when messages change — use scrollTop on the
    // messages container directly instead of scrollIntoView which can
    // bubble up and scroll the wrong ancestor (causing blank-area bug).
    useEffect(() => {
        const container = messagesContainerRef.current;
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    }, [messages]);

    // Send ideal dimensions to parent iframe for resize.
    // Embed script clamps to host viewport and adds 20px for position offset.
    useEffect(() => {
        if (!publicMode) return;
        const dims = isOpen
            ? { width: 380, height: 620 }
            : { width: 48, height: 48 };
        const send = () => {
            if (window.parent !== window) {
                window.parent.postMessage(
                    { type: 'convoharbor_resize', ...dims },
                    '*'
                );
            }
        };
        send();
        const t1 = setTimeout(send, 100);
        const t2 = setTimeout(send, 400);
        const t3 = setTimeout(send, 1000);
        return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
    }, [isOpen, publicMode]);

    const handleRatingSubmit = async (rating, feedback = '') => {
        if (ratingSubmitting) return;
        setRatingSubmitting(true);
        try {
            console.log(`🌟 Submitting rating: ${rating}/5 for conversation ${conversationId}`);
            console.log(`📝 Feedback: "${feedback}"`);
            console.log(`🧪 Test mode: ${testMode}`);

            // In test mode, don't call API — just show thank you
            if (testMode) {
                console.log('🧪 Test mode — rating not saved to database');
                setRatingStep('thankyou');
                setTimeout(() => {
                    ratingSubmittedRef.current = true;
                    setShowRating(false);
                    setRatingStep('none');
                    setSelectedRating(0);
                    setRatingFeedback('');
                    setRatingSubmitting(false);
                }, 2500);
                return;
            }

            // Embed chat — save to database
            const response = await fetch(`${process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1'}/conversations/${conversationId}/satisfaction`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    rating: rating,
                    feedback: feedback
                })
            });

            console.log(`📡 Rating submission response status: ${response.status}`);
            
            if (response.ok) {
                const result = await response.json();
                console.log('✅ Satisfaction rating submitted successfully:', result);
                setRatingStep('thankyou');
                setTimeout(() => {
                    ratingSubmittedRef.current = true;
                    setShowRating(false);
                    setRatingStep('none');
                    setSelectedRating(0);
                    setRatingFeedback('');
                    setRatingSubmitting(false);
                    // Clear persisted rating prompt
                    try {
                        const key = getRatingStorageKey(conversationId);
                        if (key) localStorage.removeItem(key);
                    } catch (_) {}
                }, 2500);
            } else {
                const errorData = await response.json();
                console.error('❌ Failed to submit rating:', errorData);
                setRatingSubmitting(false);
                alert(`Failed to submit rating: ${errorData.error || 'Unknown error'}`);
            }
        } catch (error) {
            console.error('❌ Error submitting rating:', error);
            setRatingSubmitting(false);
            alert(`Error submitting rating: ${error.message}`);
        }
    };

    const renderRatingUI = () => {
        if (ratingSubmittedRef.current || ratingStep === 'none') return null;
        if (ratingStep === 'thankyou') {
            return (
                <div className="rating-prompt">
                    <div className="rating-thankyou">
                        <div className="rating-thankyou-icon">✅</div>
                        <div className="rating-thankyou-title">
                            {testMode ? 'Thanks for rating! (Test mode — not saved)' : 'Thank you for your feedback!'}
                        </div>
                        <div className="rating-thankyou-subtitle">
                            {testMode ? 'Your rating helps us improve the chatbot experience.' : 'Your feedback helps us serve you better.'}
                        </div>
                    </div>
                </div>
            );
        }
        if (ratingStep === 'feedback') {
            return (
                <div className="rating-prompt">
                    <div className="rating-feedback-step">
                        <div className="rating-message">Any additional feedback? (optional)</div>
                        <textarea
                            className="rating-feedback-input"
                            placeholder="Tell us more about your experience..."
                            value={ratingFeedback}
                            onChange={(e) => setRatingFeedback(e.target.value)}
                            rows={3}
                            maxLength={500}
                        />
                        <div className="rating-feedback-charcount">{ratingFeedback.length}/500</div>
                        <div className="rating-actions">
                            <button
                                className="rating-submit highlighted"
                                onClick={() => handleRatingSubmit(selectedRating, ratingFeedback)}
                                disabled={ratingSubmitting}
                            >
                                {ratingSubmitting ? <span className="rating-spinner" /> : 'Submit Feedback'}
                            </button>
                            <button
                                className="rating-skip"
                                onClick={() => handleRatingSubmit(selectedRating, '')}
                                disabled={ratingSubmitting}
                            >
                                {ratingSubmitting ? <span className="rating-spinner" /> : 'Skip'}
                            </button>
                        </div>
                    </div>
                </div>
            );
        }
        return (
            <div className="rating-prompt">
                <div className="rating-stars-step">
                    <div className="rating-message">{ratingMessage || 'How was your experience?'}</div>
                    <div className="rating-stars">
                        {[1, 2, 3, 4, 5].map(star => (
                            <button
                                key={star}
                                className={`rating-star ${selectedRating >= star ? 'selected' : ''}`}
                                onClick={() => {
                                    console.log(`⭐ Star ${star} clicked!`);
                                    setSelectedRating(star);
                                }}
                                title={['Poor', 'Fair', 'Good', 'Great', 'Excellent'][star - 1]}
                            >
                                ⭐
                            </button>
                        ))}
                    </div>
                    <div className="rating-star-labels">
                        <span>Poor</span>
                        <span>Fair</span>
                        <span>Good</span>
                        <span>Great</span>
                        <span>Excellent</span>
                    </div>
                    <div className="rating-actions">
                        <button
                            className={`rating-submit ${selectedRating > 0 ? 'highlighted' : ''}`}
                            onClick={() => {
                                if (selectedRating > 0) {
                                    setRatingStep('feedback');
                                }
                            }}
                            disabled={selectedRating === 0}
                        >
                            Continue
                        </button>
                    </div>
                </div>
            </div>
        );
    };

    const handleSendMessage = async () => {
        const currentInput = input.trim();
        if (!currentInput || isTyping) return;

        setInput('');
        setIsTyping(true);

        // Start timing
        const requestStartTime = performance.now();
        const logTag = testMode ? '[TEST WIDGET]' : '[EMBED CHAT]';
        console.log(`⏱️ ${logTag} Request started at:`, new Date().toISOString());
        console.log(`⏱️ ${logTag} Message:`, currentInput);

        // Add user message to UI immediately
        const userMessage = {
            message_type: 'user',
            content: currentInput,
            timestamp: new Date().toISOString()
        };
        const newMessages = [...messages, userMessage];
        setMessages(newMessages);

        // Persist to localStorage in test mode
        if (testMode) {
            try {
                localStorage.setItem(getTestStorageKey(), JSON.stringify(newMessages));
            } catch (e) {}
        }

        try {
            const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
            const storageKey = getStorageKey();
            let currentConversationId = conversationId;

            // Build auth headers for test mode (test endpoint requires authentication)
            const authToken = testMode ? (user?.token || localStorage.getItem('authToken')) : null;

            // Optimistic path: do not pre-validate conversation on every send
            // We will try sending first; only if server says not found, we create a new conversation and retry once.
            if (!currentConversationId && !testMode) {
                console.log('🔍 No existing conversation ID, will create new one');
            }

            // Create conversation if needed (only for first message) - skip in test mode
            if (!currentConversationId && !testMode) {
                console.log('🔗 Creating new conversation...');

                // Get website context for tracking
                const websiteContext = getWebsiteContext();
                console.log('🌐 Website context for conversation:', websiteContext);

                try {
                    // Use chatbotInfo.id if available (from auto-fetch), otherwise use prop chatbotId
                    const effectiveChatbotId = chatbotInfo?.id || chatbotId;
                    if (!effectiveChatbotId) {
                        throw new Error('No chatbot available for conversation');
                    }

                    const res = await fetch(`${baseURL}/conversations`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            chatbot_id: Number(effectiveChatbotId),
                            is_embed: true,
                            website_context: websiteContext,
                            welcome_message: themeConfig?.welcomeMessage || null
                        })
                    });

                    if (!res.ok) {
                        const errorText = await res.text();
                        let errorMessage = 'Failed to create conversation';
                        try {
                            const errorData = JSON.parse(errorText);
                            errorMessage = errorData.error || errorMessage;
                        } catch (e) {
                            errorMessage = `Server error: ${res.status} ${res.statusText}`;
                        }
                        throw new Error(errorMessage);
                    }

                    const data = await res.json();
                    if (!data.conversation_id) {
                        throw new Error('No conversation ID returned from server');
                    }

                    console.log('✅ Conversation created:', data);
                    currentConversationId = data.conversation_id;
                    setConversationId(currentConversationId);

                    // Store in localStorage for persistence
                    localStorage.setItem(storageKey, currentConversationId.toString());
                } catch (error) {
                    console.error('❌ Failed to create conversation:', error);
                    throw new Error(`Failed to start conversation: ${error.message}`);
                }
            } else if (!currentConversationId && !testMode) {
                throw new Error('No conversation ID available');
            }
            
            // Streaming support: if backend supports 'Accept: text/event-stream', consume incremental tokens
            const effectiveChatbotId = chatbotInfo?.id || chatbotId;
            const tryStream = async (convId) => {
                // Test mode: use /test-message endpoint, no DB conversation
                const streamUrl = testMode
                    ? `${baseURL}/chatbots/${effectiveChatbotId}/test-message`
                    : `${baseURL}/conversations/${convId}/messages`;
                const streamBody = testMode
                    ? {
                        message: currentInput,
                        conversation_history: messages.map(msg => ({
                            role: msg.message_type === 'user' ? 'user' : 'assistant',
                            content: msg.content
                        }))
                      }
                    : { content: currentInput, chatbot_id: Number(effectiveChatbotId) };

                const streamRes = await fetch(streamUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'text/event-stream',
                        ...(authToken && { 'Authorization': `Bearer ${authToken}` })
                    },
                    body: JSON.stringify(streamBody)
                });

                if (streamRes.ok && streamRes.headers.get('content-type')?.includes('text/event-stream')) {
                    const responseReceivedTime = performance.now();
                    const timeToFirstByte = (responseReceivedTime - requestStartTime).toFixed(2);
                    console.log(`⏱️ ${logTag} Time to first byte: ${timeToFirstByte}ms`);
                    console.log('🌊 Streaming response detected!');

                    const reader = streamRes.body.getReader();
                    const decoder = new TextDecoder();
                    let buffer = '';
                    let accumulatedContent = '';

                    // Keep typing indicator while waiting for response
                    // Don't create placeholder message yet - wait for actual content
                    let assistantMessageCreated = false;
                    const placeholderIndex = messages.length + 1; // after userMessage
                    let firstContentTime = null;
                    let chunkCount = 0;

                    // Read chunks
                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) {
                            console.log('✅ Streaming complete - Final content length:', accumulatedContent.length);
                            // Final update: ensure content is set and mark streaming as done
                            setMessages(prev => {
                                const updated = [...prev];
                                if (updated[placeholderIndex]) {
                                    updated[placeholderIndex].content = accumulatedContent;
                                    updated[placeholderIndex].isStreaming = false;
                                }
                                // Persist test mode messages
                                if (testMode) {
                                    try { localStorage.setItem(getTestStorageKey(), JSON.stringify(updated)); } catch (e) {}
                                }
                                return updated;
                            });
                            break;
                        }
                        
                        buffer += decoder.decode(value, { stream: true });
                        
                        // Process complete SSE messages (split by double newline)
                        const lines = buffer.split('\n\n');
                        buffer = lines.pop(); // Keep incomplete message in buffer
                        
                        for (const line of lines) {
                            if (line.startsWith('data: ')) {
                                try {
                                    const jsonStr = line.substring(6).trim();
                                    if (!jsonStr) continue; // Skip empty data
                                    
                                    const data = JSON.parse(jsonStr);
                                    
                                    if (data.error) {
                                        console.error('❌ Stream error:', data.error);
                                        throw new Error(data.error);
                                    }
                                    
                                    // Handle rating event from backend
                                    if (data.type === 'rating' && data.data) {
                                        console.log('🌟 Rating prompt received from stream!', {
                                            fullData: data,
                                            ratingData: data.data,
                                            ratingMessage: data.data.rating_message,
                                            currentShowRating: showRating
                                        });
                                        setShowRating(true);
                                        setRatingStep('stars');
                                        setSelectedRating(0);
                                        setRatingFeedback('');
                                        setRatingSubmitting(false);
                                        ratingSubmittedRef.current = false;
                                        setRatingMessage(data.data.rating_message || 'How would you rate your experience?');

                                        // Remove any old rating messages and insert fresh one
                                        setMessages(prev => {
                                            let updated = prev.filter(m => m.message_type !== 'rating');
                                            // Find last user message index
                                            let lastUserIdx = -1;
                                            for (let i = updated.length - 1; i >= 0; i--) {
                                                if (updated[i].message_type === 'user') {
                                                    lastUserIdx = i;
                                                    break;
                                                }
                                            }
                                            const insertIdx = lastUserIdx !== -1 ? lastUserIdx + 1 : updated.length;
                                            updated.splice(insertIdx, 0, {
                                                message_type: 'rating',
                                                rating_message: data.data.rating_message || 'How would you rate your experience?',
                                                timestamp: new Date().toISOString()
                                            });
                                            if (testMode) {
                                                try { localStorage.setItem(getTestStorageKey(), JSON.stringify(updated)); } catch (e) {}
                                            }
                                            return updated;
                                        });

                                        // Persist so a re-mount still shows the rating
                                        try {
                                            const key = getRatingStorageKey(conversationId || currentConversationId);
                                            if (key) {
                                                localStorage.setItem(key, JSON.stringify({
                                                    show_rating: true,
                                                    rating_message: data.data.rating_message || 'How would you rate your experience?',
                                                    conversation_id: (conversationId || currentConversationId)
                                                }));
                                            }
                                        } catch (_) {}
                                        console.log('✅ Rating state updated - showRating should now be true');
                                        continue; // Skip further processing for this event
                                    }
                                    
                                    if (data.accumulated) {
                                        // Use accumulated text for smooth display
                                        accumulatedContent = data.accumulated;
                                    } else if (data.content) {
                                        // Append chunk
                                        accumulatedContent += data.content;
                                    }

                                    // Track chunks
                                    if (data.accumulated || data.content) {
                                        chunkCount++;
                                    }

                                    // Create assistant message on first content and turn off typing
                                    if ((data.accumulated || data.content) && !assistantMessageCreated) {
                                        firstContentTime = performance.now();
                                        const timeToFirstContent = (firstContentTime - requestStartTime).toFixed(2);
                                        console.log(`⏱️ ${logTag} Time to first content: ${timeToFirstContent}ms`);
                                        setIsTyping(false);
                                        setMessages(prev => {
                                            const updated = [...prev, {
                                                message_type: 'assistant',
                                                content: accumulatedContent,
                                                timestamp: new Date().toISOString(),
                                                isStreaming: true
                                            }];
                                            if (testMode) {
                                                try { localStorage.setItem(getTestStorageKey(), JSON.stringify(updated)); } catch (e) {}
                                            }
                                            return updated;
                                        });
                                        assistantMessageCreated = true;
                                    } else if ((data.accumulated || data.content) && assistantMessageCreated) {
                                        // Update existing assistant message
                                        setMessages(prev => {
                                            const updated = [...prev];
                                            if (updated[placeholderIndex]) {
                                                updated[placeholderIndex].content = accumulatedContent;
                                            }
                                            if (testMode) {
                                                try { localStorage.setItem(getTestStorageKey(), JSON.stringify(updated)); } catch (e) {}
                                            }
                                            return updated;
                                        });
                                    }
                                    
                                    if (data.done) {
                                        const totalTime = (performance.now() - requestStartTime).toFixed(2);
                                        const streamingTime = firstContentTime ? (performance.now() - firstContentTime).toFixed(2) : 0;
                                        console.log(`⏱️ ${logTag} ========== TIMING SUMMARY ==========`);
                                        console.log(`⏱️ ${logTag} Total response time: ${totalTime}ms (${(totalTime/1000).toFixed(2)}s)`);
                                        console.log(`⏱️ ${logTag} Time to first byte: ${timeToFirstByte}ms`);
                                        console.log(`⏱️ ${logTag} Time to first content: ${firstContentTime ? (firstContentTime - requestStartTime).toFixed(2) : 'N/A'}ms`);
                                        console.log(`⏱️ ${logTag} Streaming duration: ${streamingTime}ms`);
                                        console.log(`⏱️ ${logTag} Total chunks received: ${chunkCount}`);
                                        console.log(`⏱️ ${logTag} Response length: ${accumulatedContent.length} characters`);
                                        console.log(`⏱️ ${logTag} Average chars per chunk: ${chunkCount > 0 ? (accumulatedContent.length / chunkCount).toFixed(2) : 'N/A'}`);
                                        console.log(`⏱️ ${logTag} ====================================`);

                                        console.log('✅ Stream done signal received');
                                        // Final update with complete content
                                        setMessages(prev => {
                                            const updated = [...prev];
                                            if (updated[placeholderIndex]) {
                                                updated[placeholderIndex].content = accumulatedContent;
                                                updated[placeholderIndex].isStreaming = false;
                                            }
                                            if (testMode) {
                                                try { localStorage.setItem(getTestStorageKey(), JSON.stringify(updated)); } catch (e) {}
                                            }
                                            return updated;
                                        });
                                        break;
                                    }
                                } catch (e) {
                                    // Silently skip JSON parse errors - they're common at stream boundaries
                                    // Only log to console for debugging, never show to user
                                    console.debug('⚠️ Skipping malformed SSE chunk (this is normal):', line.substring(0, 50));
                                    // Don't update UI with error message - streaming will complete successfully
                                }
                            }
                        }
                    }
                    return { ok: true };
                }
                return { ok: false, res: streamRes };
            };

            // Helper to send message
            const sendToConversation = async (convId) => {
                if (testMode) {
                    return fetch(`${baseURL}/chatbots/${chatbotId}/test-message`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            ...(authToken && { 'Authorization': `Bearer ${authToken}` })
                        },
                        body: JSON.stringify({
                            message: currentInput,
                            conversation_history: messages.map(msg => ({
                                role: msg.message_type === 'user' ? 'user' : 'assistant',
                                content: msg.content
                            }))
                        })
                    });
                }
                return fetch(`${baseURL}/conversations/${convId}/messages`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: currentInput, chatbot_id: Number(chatbotId) })
                });
            };

            // Send message (no pre-check)
            console.log(`🔗 Sending message to conversation ${currentConversationId}...`);
            // First, attempt streaming (non-breaking; if server doesn't support, fallback to JSON once)
            let streamAttempt = await tryStream(currentConversationId);
            
            // If streaming succeeded, we're done - skip JSON parsing
            if (streamAttempt.ok) {
                console.log('✅ Streaming completed successfully, skipping JSON response');
                return; // Exit early - streaming already handled everything
            }
            
            // Streaming not supported, fallback to JSON
            console.log('📄 Streaming not supported, using regular JSON response');
            let response = await sendToConversation(currentConversationId);

            if (!response.ok) {
                // Try to read response as text first, then attempt JSON parse
                const responseText = await response.text();
                let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                
                try {
                    const errorData = JSON.parse(responseText);
                    errorMessage = errorData.error || errorMessage;
                } catch (e) {
                    // If it's not JSON, check if it's HTML (likely an error page)
                    if (responseText.includes('<!doctype') || responseText.includes('<html')) {
                        errorMessage = `HTTP ${response.status}: NOT FOUND`;
                        console.log('❌ Message send failed (non-JSON response):', response.status, responseText.substring(0, 200));
                    } else {
                        errorMessage = responseText || errorMessage;
                    }
                }
                
                // If the conversation was not found/invalid, create and retry once
                if (
                    !testMode && (
                    response.status === 404 ||
                    errorMessage.includes('NOT FOUND') ||
                    errorMessage.toLowerCase().includes('conversation')
                )) {
                    console.log('♻️ Conversation likely invalid/missing. Creating a new one and retrying once...');
                    // Create conversation (only now)
                    const websiteContext = getWebsiteContext();
                    const createRes = await fetch(`${baseURL}/conversations`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ chatbot_id: Number(chatbotId), is_embed: true, website_context: websiteContext })
                    });
                    if (createRes.ok) {
                        const created = await createRes.json();
                        currentConversationId = created.conversation_id;
                        setConversationId(currentConversationId);
                        localStorage.setItem(storageKey, currentConversationId.toString());
                        console.log('✅ New conversation created:', currentConversationId);
                        response = await sendToConversation(currentConversationId);
                        if (!response.ok) {
                            const text = await response.text();
                            throw new Error(text || `HTTP ${response.status}`);
                        }
                    } else {
                        const text = await createRes.text();
                        throw new Error(text || 'Failed to create conversation');
                    }
                } else {
                throw new Error(errorMessage);
                }
            }

            const data = await response.json();
            const totalTime = (performance.now() - requestStartTime).toFixed(2);
            console.log(`⏱️ [EMBED CHAT] ========== TIMING SUMMARY (JSON) ==========`);
            console.log(`⏱️ [EMBED CHAT] Total response time: ${totalTime}ms (${(totalTime/1000).toFixed(2)}s)`);
            console.log(`⏱️ [EMBED CHAT] Response length: ${data.assistant_message?.content?.length || 0} characters`);
            console.log(`⏱️ [EMBED CHAT] =============================================`);
            
            if (data.assistant_message) {
                // Turn off typing indicator and add assistant message
                setIsTyping(false);
                const assistantMessage = {
                    message_type: 'assistant',
                    content: data.assistant_message.content,
                    timestamp: data.assistant_message.created_at || new Date().toISOString(),
                    isStreaming: false
                };
                setMessages(prev => {
                    const updated = [...prev, assistantMessage];
                    if (testMode) {
                        try { localStorage.setItem(getTestStorageKey(), JSON.stringify(updated)); } catch (e) {}
                    }
                    return updated;
                });

                // Check if we should show rating prompt (only in non-test mode)
                if (!testMode && data.show_rating) {
                    console.log('🌟 Rating prompt triggered!', {
                        conversationId: currentConversationId,
                        ratingMessage: data.rating_message
                    });
                    ratingSubmittedRef.current = false;
                    setRatingSubmitting(false);
                    setShowRating(true);
                    setRatingStep('stars');
                    setRatingMessage(data.rating_message || 'How would you rate your experience?');
                } else if (testMode && data.show_rating) {
                    // Test mode also shows rating but won't save
                    ratingSubmittedRef.current = false;
                    setRatingSubmitting(false);
                    setShowRating(true);
                    setRatingStep('stars');
                    setRatingMessage(data.rating_message || 'How would you rate your experience? (Test mode)');
                } else {
                    console.log('📝 No rating prompt in response');
                }
            } else if (data.response) {
                // Test mode JSON response format
                setIsTyping(false);
                const assistantMessage = {
                    message_type: 'assistant',
                    content: data.response,
                    timestamp: new Date().toISOString(),
                    isStreaming: false
                };
                setMessages(prev => {
                    const updated = [...prev, assistantMessage];
                    if (testMode) {
                        try { localStorage.setItem(getTestStorageKey(), JSON.stringify(updated)); } catch (e) {}
                    }
                    return updated;
                });

                // Check for rating prompt in test mode JSON response
                if (data.show_rating) {
                    console.log('🌟 Test mode: Rating prompt triggered!');
                    ratingSubmittedRef.current = false;
                    setRatingSubmitting(false);
                    setShowRating(true);
                    setRatingStep('stars');
                    setRatingMessage(data.rating_message || 'How would you rate your experience? (Test mode)');
                }
            } else {
                console.warn('⚠️ No assistant message in response:', data);
            }

        } catch (error) {
            console.error('❌ Error sending message:', error);

            // Clean up empty placeholder assistant message if streaming failed
            setMessages(prev => {
                let updated = [...prev];
                // Remove the empty placeholder message that was created during streaming
                const placeholderIdx = updated.findIndex(
                    m => m.message_type === 'assistant' && (!m.content || m.content.trim() === '') && m.isStreaming
                );
                if (placeholderIdx !== -1) {
                    updated.splice(placeholderIdx, 1);
                }
                // Add error message
                updated.push({
                    message_type: 'assistant',
                    content: `Sorry, I encountered an error: ${error.message}. Please try again.`,
                    timestamp: new Date().toISOString(),
                    isError: true
                });
                if (testMode) {
                    try { localStorage.setItem(getTestStorageKey(), JSON.stringify(updated)); } catch (e) {}
                }
                return updated;
            });
        } finally {
            setIsTyping(false);
        }
    };

    const clearChat = async () => {
        if (!window.confirm(testMode ? 'Are you sure you want to clear this test chat?' : 'Are you sure you want to clear this chat? This will start a new conversation.')) {
            return;
        }

        if (!testMode) {
            try {
                // Mark current conversation as inactive if it exists
                if (conversationId) {
                    const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
                    await fetch(`${baseURL}/conversations/${conversationId}/status`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ status: 'inactive' })
                    });
                }
            } catch (error) {
                console.error('Failed to mark conversation as inactive:', error);
            }
        }

        // Clear local state
        loadedFromAPI.current = false;
        ratingSubmittedRef.current = false;
        setMessages([{
            message_type: 'assistant',
            content: themeConfig?.welcomeMessage || `Hello! I'm ${chatbotInfo?.name || 'Assistant'}. How can I help you today?`,
            timestamp: new Date().toISOString()
        }]);
        setConversationId(null);
        setInput('');

        // Clear localStorage
        if (testMode) {
            try { localStorage.removeItem(getTestStorageKey()); } catch (e) {}
        } else {
            const storageKey = getStorageKey();
            localStorage.removeItem(storageKey);
        }
    };

    const handleKeyPress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    };

    // Show nothing while loading the widget
    if (!themeConfig) {
        return null;
    }

    return (
        <div
            className={`chat-widget-container ${themeConfig.position} ${testMode ? 'test-mode-widget' : ''}`}
            style={{ '--cw-user-bg': themeConfig.primaryColor }}
        >
            {!isOpen && (
                <button
                    className="chat-toggle-button"
                    onClick={() => setIsOpen(true)}
                >
                    <svg viewBox="0 0 24 24" fill="none" stroke={themeConfig.primaryColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                    </svg>
                </button>
            )}

            {isOpen && (
                <div className="chat-window">
                    <div className="chat-header" style={{ background: themeConfig.primaryColor }}>
                        <div className="chat-header-info">
                            <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
                                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                            </svg>
                            <div className="chat-header-text">
                                <div className="chat-header-name">
                                    {chatbotInfo?.name || 'Assistant'}
                                    {testMode && <span className="test-mode-badge">🧪 Test</span>}
                                </div>
                                {chatbotInfo?.description && (
                                    <div
                                        className={'chat-header-description' + (descriptionExpanded ? ' expanded' : '')}
                                        onClick={toggleDescription}
                                        title={descriptionExpanded ? 'Click to collapse' : 'Click to expand'}
                                    >
                                        {chatbotInfo.description}
                                    </div>
                                )}
                            </div>
                        </div>
                        <div className="header-actions">
                            <button
                                className="clear-chat-button"
                                onClick={clearChat}
                                title="Reset Chat"
                                aria-label="Reset Chat"
                            >
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                    <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
                                    <path d="M3 3v5h5"/>
                                </svg>
                            </button>
                            <button
                                className="close-button"
                                onClick={handleClose}
                            >
                                ✕
                            </button>
                        </div>
                    </div>

                    <div className="chat-messages" ref={messagesContainerRef}>
                        {messages.map((message, index) => {
                            // Don't render empty streaming messages
                            if (message.message_type === 'assistant' && message.isStreaming && !message.content) {
                                return null;
                            }

                            // Render rating prompt inline as a message
                            if (message.message_type === 'rating') {
                                return (
                                    <div key={index} className="rating-inline">
                                        {renderRatingUI()}
                                    </div>
                                );
                            }

                            const isAssistant = message.message_type === 'assistant';
                            // While the response is actively streaming we keep
                            // the plain-text renderer to avoid KaTeX / markdown
                            // re-parsing on every chunk (and to dodge
                            // half-finished block-fence crashes). As soon as
                            // streaming finishes we switch to the rich-text
                            // renderer so headings, code, math, etc. show up.
                            const showRich = isAssistant && !message.isStreaming;
                            return (
                                <div
                                    key={index}
                                    className={`message ${message.message_type} ${message.isError ? 'error' : ''}`}
                                >
                                    <div className="message-content">
                                        {isAssistant && <span className="assistant-icon">🤖</span>}
                                        {showRich && message.content ? (
                                            <MarkdownMessage content={message.content} />
                                        ) : (
                                            <span>{message.content || (message.isStreaming ? '...' : '')}</span>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                        {/* Fallback: show rating after messages if loaded from localStorage on reload
                            but the rating message isn't in the messages array */}
                        {showRating && !messages.some(m => m.message_type === 'rating') && (
                            <div className="rating-inline">
                                {renderRatingUI()}
                            </div>
                        )}
                        {isTyping && (
                            <div className="message assistant typing">
                                <div className="message-content">
                                    <span className="assistant-icon">🤖</span>
                                    <span className="typing-indicator">
                                        <span></span>
                                        <span></span>
                                        <span></span>
                                    </span>
                                </div>
                            </div>
                        )}
                        
                        <div ref={messagesEndRef} />
                    </div>

                    <div className="chat-input">
                        <input
                            type="text"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyPress={handleKeyPress}
                            placeholder="Type your message..."
                            disabled={isTyping}
                        />
                        <button
                            className="send-button"
                            onClick={handleSendMessage}
                            disabled={!input.trim() || isTyping}
                            style={{ background: themeConfig.primaryColor }}
                        >
                            ➤
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ChatWidget;

// DEBUG: Log component definition
console.log('✅ ChatWidget component defined and exported');