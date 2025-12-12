import React, { useState, useEffect, useRef } from 'react';
import './ChatWidget.css';

/**
 * GeneralChatWidget - Standalone chat widget for general AI conversations
 * - Uses OpenAI GPT-4o via dedicated general-chat endpoint
 * - No database chatbot required
 * - Separate from embed chatbots
 * - Simple session-based conversation history
 */
const GeneralChatWidget = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isTyping, setIsTyping] = useState(false);
    const [sessionId, setSessionId] = useState(null);
    const messagesEndRef = useRef(null);

    // Initialize session ID and welcome message
    useEffect(() => {
        const storedSessionId = localStorage.getItem('general_chat_session_id');
        const newSessionId = storedSessionId || `general-${Date.now()}`;
        setSessionId(newSessionId);
        localStorage.setItem('general_chat_session_id', newSessionId);

        // Set welcome message
        setMessages([{
            role: 'assistant',
            content: 'Hello! I\'m your AI Assistant powered by OpenAI GPT-4o. How can I help you today?',
            timestamp: new Date().toISOString()
        }]);
    }, []);

    // Auto-scroll to bottom
    useEffect(() => {
        if (messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [messages]);

    const handleSendMessage = async () => {
        const currentInput = input.trim();
        if (!currentInput || isTyping) return;

        setInput('');
        setIsTyping(true);

        // Add user message
        const userMessage = {
            role: 'user',
            content: currentInput,
            timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, userMessage]);

        // Start timing
        const requestStartTime = performance.now();
        console.log('⏱️ [GENERAL CHAT] Request started at:', new Date().toISOString());

        try {
            const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
            console.log('🚀 Sending message with streaming to:', `${baseURL}/general-chat`);
            console.log('📦 Request payload:', { message: currentInput, session_id: sessionId });
            
            // Keep typing indicator while waiting for response
            // Don't create placeholder message yet - wait for actual content
            
            const response = await fetch(`${baseURL}/general-chat`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Accept': 'text/event-stream'
                },
                body: JSON.stringify({
                    message: currentInput,
                    session_id: sessionId
                })
            });

            console.log('📡 Response status:', response.status);

            if (!response.ok) {
                const errorText = await response.text();
                console.error('❌ Server error response:', errorText);
                throw new Error(`Server error: ${response.status} - ${errorText}`);
            }

            // Check if response is streaming or regular JSON
            const responseReceivedTime = performance.now();
            const timeToFirstByte = (responseReceivedTime - requestStartTime).toFixed(2);
            console.log(`⏱️ [GENERAL CHAT] Time to first byte: ${timeToFirstByte}ms`);
            
            const contentType = response.headers.get('content-type');
            console.log('📋 Response content-type:', contentType);
            
            if (contentType && contentType.includes('text/event-stream')) {
                console.log('🌊 Processing streaming response');
                // Handle streaming response
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let accumulatedContent = '';
                let assistantMessageCreated = false;
                let firstContentTime = null;
                let chunkCount = 0;
                
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    const chunk = decoder.decode(value, { stream: true });
                    const lines = chunk.split('\n');
                    
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.slice(6));
                                
                                if (data.content) {
                                    accumulatedContent += data.content;
                                    chunkCount++;
                                    
                                    // Create assistant message on first content and turn off typing
                                    if (!assistantMessageCreated) {
                                        firstContentTime = performance.now();
                                        const timeToFirstContent = (firstContentTime - requestStartTime).toFixed(2);
                                        console.log(`⏱️ [GENERAL CHAT] Time to first content: ${timeToFirstContent}ms`);
                                        setIsTyping(false);
                                        const assistantMessage = {
                                            role: 'assistant',
                                            content: accumulatedContent,
                                            timestamp: new Date().toISOString(),
                                            isStreaming: true
                                        };
                                        setMessages(prev => [...prev, assistantMessage]);
                                        assistantMessageCreated = true;
                                    } else {
                                        // Update existing assistant message
                                        setMessages(prev => {
                                            const newMessages = [...prev];
                                            if (newMessages.length > 0 && newMessages[newMessages.length - 1].role === 'assistant') {
                                                newMessages[newMessages.length - 1] = {
                                                    ...newMessages[newMessages.length - 1],
                                                    content: accumulatedContent,
                                                    isStreaming: true
                                                };
                                            }
                                            return newMessages;
                                        });
                                    }
                                }
                                
                                if (data.done) {
                                    const totalTime = (performance.now() - requestStartTime).toFixed(2);
                                    const streamingTime = firstContentTime ? (performance.now() - firstContentTime).toFixed(2) : 0;
                                    console.log(`⏱️ [GENERAL CHAT] ========== TIMING SUMMARY ==========`);
                                    console.log(`⏱️ [GENERAL CHAT] Total response time: ${totalTime}ms (${(totalTime/1000).toFixed(2)}s)`);
                                    console.log(`⏱️ [GENERAL CHAT] Time to first byte: ${timeToFirstByte}ms`);
                                    console.log(`⏱️ [GENERAL CHAT] Time to first content: ${firstContentTime ? (firstContentTime - requestStartTime).toFixed(2) : 'N/A'}ms`);
                                    console.log(`⏱️ [GENERAL CHAT] Streaming duration: ${streamingTime}ms`);
                                    console.log(`⏱️ [GENERAL CHAT] Total chunks received: ${chunkCount}`);
                                    console.log(`⏱️ [GENERAL CHAT] Response length: ${accumulatedContent.length} characters`);
                                    console.log(`⏱️ [GENERAL CHAT] Average chars per chunk: ${(accumulatedContent.length / chunkCount).toFixed(2)}`);
                                    console.log(`⏱️ [GENERAL CHAT] =====================================`);
                                    
                                    console.log('✅ General chat streaming complete:', accumulatedContent);
                                    // Mark streaming as complete
                                    setMessages(prev => {
                                        const finalMessages = [...prev];
                                        if (finalMessages.length > 0 && finalMessages[finalMessages.length - 1].role === 'assistant') {
                                            finalMessages[finalMessages.length - 1] = {
                                                ...finalMessages[finalMessages.length - 1],
                                                content: accumulatedContent,
                                                isStreaming: false
                                            };
                                        }
                                        return finalMessages;
                                    });
                                    break;
                                }
                            } catch (e) {
                                console.warn('Failed to parse SSE data:', line);
                            }
                        }
                    }
                }
            } else {
                console.log('📄 Processing regular JSON response');
                // Handle regular JSON response (fallback)
                const data = await response.json();
                const totalTime = (performance.now() - requestStartTime).toFixed(2);
                console.log(`⏱️ [GENERAL CHAT] ========== TIMING SUMMARY (JSON) ==========`);
                console.log(`⏱️ [GENERAL CHAT] Total response time: ${totalTime}ms (${(totalTime/1000).toFixed(2)}s)`);
                console.log(`⏱️ [GENERAL CHAT] Response length: ${data.response?.length || 0} characters`);
                console.log(`⏱️ [GENERAL CHAT] ===============================================`);
                console.log('✅ Response data:', data);

                // Turn off typing and add assistant response
                setIsTyping(false);
                const assistantMessage = {
                    role: 'assistant',
                    content: data.response,
                    timestamp: data.timestamp,
                    isStreaming: false
                };
                setMessages(prev => [...prev, assistantMessage]);
            }

        } catch (error) {
            console.error('❌ Error sending message:', error);
            console.error('❌ Error details:', error.message);
            
            // Show error message with details
            const errorMessage = {
                role: 'assistant',
                content: `Sorry, I encountered an error: ${error.message}. Please check the console for details.`,
                timestamp: new Date().toISOString(),
                isError: true
            };
            setMessages(prev => [...prev, errorMessage]);
        } finally {
            setIsTyping(false);
        }
    };

    const handleKeyPress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    };

    const clearChat = async () => {
        try {
            const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
            await fetch(`${baseURL}/general-chat/clear`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId })
            });

            // Create new session
            const newSessionId = `general-${Date.now()}`;
            setSessionId(newSessionId);
            localStorage.setItem('general_chat_session_id', newSessionId);

            // Reset messages with welcome message
            setMessages([{
                role: 'assistant',
                content: 'Hello! I\'m your AI Assistant powered by OpenAI GPT-4o. How can I help you today?',
                timestamp: new Date().toISOString()
            }]);
        } catch (error) {
            console.error('❌ Error clearing chat:', error);
        }
    };

    // Helper for rendering HTML with line breaks for multiline support
    function renderWithLineBreaks(text) {
      return text.split(/\r?\n/).map((line, idx) => (
        <React.Fragment key={idx}>
          {line}
          {idx !== text.split(/\r?\n/).length - 1 && <br />}
        </React.Fragment>
      ));
    }

    return (
        <div className="chat-widget-container bottom-right">
            {!isOpen && (
                <button
                    className="chat-toggle-button"
                    onClick={() => setIsOpen(true)}
                    style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}
                >
                </button>
            )}

            {isOpen && (
                <div className="chat-window">
                    <div className="chat-header" style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}>
                        <span>🤖 AI Assistant (GPT-4o)</span>
                        <div className="header-actions">
                            <button
                                className="clear-chat-button"
                                onClick={clearChat}
                                title="Clear Chat"
                            >
                                🧹
                            </button>
                            <button
                                className="close-button"
                                onClick={() => setIsOpen(false)}
                            >
                                ✕
                            </button>
                        </div>
                    </div>

                    <div className="chat-messages">
                        {messages.map((message, index) => {
                            // Don't render empty streaming messages
                            if (message.role === 'assistant' && message.isStreaming && !message.content) {
                                return null;
                            }
                            
                            return (
                                <div
                                    key={index}
                                    className={`message ${message.role} ${message.isError ? 'error' : ''}`}
                                >
                                    <div className="message-content">
                                        {message.role === 'assistant' ? (
                                            <>
                                                <span className="assistant-icon">🤖</span>
                                                <div>{renderWithLineBreaks(message.content || (message.isStreaming ? '...' : ''))}</div>
                                            </>
                                        ) : (
                                            <div>{renderWithLineBreaks(message.content)}</div>
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
                            style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}
                        >
                            ➤
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default GeneralChatWidget;

