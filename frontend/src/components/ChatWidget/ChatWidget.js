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
    const { socket: contextSocket, isConnected } = useWebSocket();
    const { user } = useAuth();
    const socket = externalSocket || contextSocket;
    const messagesEndRef = useRef(null);

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
                            
                            // Set initial welcome message
                            if (messages.length === 0) {
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
                
                // Set initial welcome message
                if (messages.length === 0) {
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

                // Set initial welcome message when theme loads (only if no messages exist)
                if (messages.length === 0) {
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

                // Set fallback welcome message
                if (messages.length === 0) {
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
                if (!res.ok) {
                    // Not found or error → clear
                    localStorage.removeItem(storageKey);
                    setConversationId(null);
                    return;
                }
                const data = await res.json();
                const status = data?.conversation?.status || data?.status;
                if (status === 'deleted') {
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
                // Fail-open: clear invalid state to allow fresh conversation
                try {
                    const storageKey = getStorageKey();
                    localStorage.removeItem(storageKey);
                } catch (_) {}
                setConversationId(null);
            }
        };
        validateExistingConversation();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [chatbotId]);

    // Load existing messages when conversation ID is available
    useEffect(() => {
        const loadExistingMessages = async () => {
            if (!conversationId || !chatbotId) return;
            
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
                    
                    // Replace welcome message with actual conversation history
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
    }, [conversationId, chatbotId]);

    // Auto-scroll to bottom when messages change
    useEffect(() => {
        if (messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [messages]);

    const handleRatingSubmit = async (rating, feedback = '') => {
        try {
            console.log(`🌟 Submitting rating: ${rating}/5 for conversation ${conversationId}`);
            console.log(`📝 Feedback: "${feedback}"`);
            
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
                setShowRating(false);
                setSelectedRating(0);
                // Clear persisted rating prompt
                try {
                    const key = getRatingStorageKey(conversationId);
                    if (key) localStorage.removeItem(key);
                } catch (_) {}
            } else {
                const errorData = await response.json();
                console.error('❌ Failed to submit rating:', errorData);
                alert(`Failed to submit rating: ${errorData.error || 'Unknown error'}`);
            }
        } catch (error) {
            console.error('❌ Error submitting rating:', error);
            alert(`Error submitting rating: ${error.message}`);
        }
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
                            website_context: websiteContext  // Let backend create title from website context
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
                                        setRatingMessage(data.data.rating_message || 'How would you rate your experience?');
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
                    setShowRating(true);
                    setRatingMessage(data.rating_message || 'How would you rate your experience?');
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
            } else {
                console.warn('⚠️ No assistant message in response:', data);
            }

        } catch (error) {
            console.error('❌ Error sending message:', error);

            // Add error message to UI
            const errorMessage = {
                message_type: 'assistant',
                content: `Sorry, I encountered an error: ${error.message}. Please try again.`,
                timestamp: new Date().toISOString(),
                isError: true
            };
            setMessages(prev => {
                const updated = [...prev, errorMessage];
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

    // Show loading state if theme is not loaded yet
    if (!themeConfig) {
        return (
            <div className="chat-widget-container bottom-right" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100vw', height: '100vh', pointerEvents: 'none', zIndex: 2147483647 }}>
                {/* <div style={{ pointerEvents: 'none' }}>
                    <button className="chat-toggle-button" tabIndex="-1" aria-label="Loading chat widget" style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', pointerEvents: 'none', boxShadow: '0 8px 32px rgba(102, 126, 234, 0.25)' }} disabled>
                        💬
                    </button>
                </div> */}
            </div>
        );
    }

    return (
        <div className={`chat-widget-container ${themeConfig.position} ${testMode ? 'test-mode-widget' : ''}`}>
            {!isOpen && (
                <button
                    className="chat-toggle-button"
                    onClick={() => setIsOpen(true)}
                    style={{ background: themeConfig.primaryColor }}
                >
                </button>
            )}

            {isOpen && (
                <div className="chat-window">
                    <div className="chat-header" style={{ background: themeConfig.primaryColor }}>
                        <span>
                            🤖 {chatbotInfo?.name || 'Assistant'}
                            {testMode && <span className="test-mode-badge">🧪 Test</span>}
                        </span>
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

                    <div className="chat-messages">
                        {messages.map((message, index) => {
                            // Don't render empty streaming messages
                            if (message.message_type === 'assistant' && message.isStreaming && !message.content) {
                                return null;
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
                        
                        {/* Rating Prompt */}
                        {console.log('🎨 Rendering - showRating:', showRating, 'ratingMessage:', ratingMessage)}
                        {showRating && (
                            <div className="rating-prompt">
                                <div className="rating-message">{ratingMessage}</div>
                                <div className="rating-stars">
                                    {[1, 2, 3, 4, 5].map(star => (
                                        <button
                                            key={star}
                                            className={`rating-star ${selectedRating >= star ? 'selected' : ''}`}
                                            onClick={() => {
                                                console.log(`⭐ Star ${star} clicked! Previous rating: ${selectedRating}`);
                                                setSelectedRating(star);
                                                console.log(`⭐ New rating should be: ${star}`);
                                            }}
                                        >
                                            ⭐
                                        </button>
                                    ))}
                                </div>
                                <div className="rating-actions">
                                    <button 
                                        className={`rating-submit ${selectedRating > 0 ? 'highlighted' : ''}`}
                                        onClick={() => handleRatingSubmit(selectedRating)}
                                        disabled={selectedRating === 0}
                                    >
                                        Submit Rating
                                    </button>
                                    <button 
                                        className="rating-skip"
                                        onClick={() => {
                                            setShowRating(false);
                                            try {
                                                const key = getRatingStorageKey(conversationId);
                                                if (key) localStorage.removeItem(key);
                                            } catch (_) {}
                                        }}
                                    >
                                        Skip
                                    </button>
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