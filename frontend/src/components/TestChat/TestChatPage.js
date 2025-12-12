import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { chatbotService } from '../../services/chatbot.service';
import SimpleLoader from '../common/SimpleLoader';
import './TestChatPage.css';

const TestChatPage = () => {
  const { id: chatbotId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [chatbot, setChatbot] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  // Test chats are temporary - no conversation ID needed
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    console.log('TestChatPage - Loading chatbot and test conversation from localStorage');
    
    const token = user?.token || localStorage.getItem('authToken');
    
    if (!token) {
      console.log('Waiting for user authentication...');
      return;
    }
    
    console.log('Loading chatbot for test mode');
    loadChatbotWithToken(token);
    
    // Load test conversation from localStorage
    loadTestConversation();
  }, [chatbotId, user?.token]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };


  const loadChatbot = async () => {
    try {
      setLoading(true);
      const data = await chatbotService.getChatbot(chatbotId);
      setChatbot(data);
    } catch (err) {
      setError(err.message || 'Failed to load chatbot');
    } finally {
      setLoading(false);
    }
  };

  const loadChatbotWithToken = async (token) => {
    try {
      setLoading(true);
      const data = await chatbotService.getChatbot(chatbotId);
      setChatbot(data);
    } catch (err) {
      setError(err.message || 'Failed to load chatbot');
    } finally {
      setLoading(false);
    }
  };

  // Test mode - localStorage functions
  const getTestConversationKey = () => `test_conversation_${chatbotId}`;
  
  const loadTestConversation = () => {
    try {
      const key = getTestConversationKey();
      const savedMessages = localStorage.getItem(key);
      if (savedMessages) {
        const parsedMessages = JSON.parse(savedMessages);
        setMessages(parsedMessages);
        console.log('📱 Loaded test conversation from localStorage:', parsedMessages.length, 'messages');
      }
    } catch (error) {
      console.error('❌ Error loading test conversation from localStorage:', error);
    }
  };
  
  const saveTestConversation = (newMessages) => {
    try {
      const key = getTestConversationKey();
      localStorage.setItem(key, JSON.stringify(newMessages));
      console.log('💾 Saved test conversation to localStorage:', newMessages.length, 'messages');
    } catch (error) {
      console.error('❌ Error saving test conversation to localStorage:', error);
    }
  };
  
  const clearTestConversation = () => {
    if (!window.confirm('Are you sure you want to clear this test chat? This will remove all messages.')) {
      return;
    }
    
    try {
      const key = getTestConversationKey();
      localStorage.removeItem(key);
      setMessages([]);
      console.log('🧹 Cleared test conversation from localStorage');
    } catch (error) {
      console.error('❌ Error clearing test conversation from localStorage:', error);
    }
  };

  const handleSendMessage = async () => {
    if (!input.trim() || !chatbot) return;

    const userMessage = { message_type: 'user', content: input, created_at: new Date().toISOString() };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    saveTestConversation(updatedMessages);
    
    const currentInput = input;
    setInput('');
    setIsTyping(true);

    // Start timing
    const requestStartTime = performance.now();
    console.log('⏱️ [TEST CHAT] Request started at:', new Date().toISOString());
    console.log('⏱️ [TEST CHAT] Message:', currentInput);

    try {
      const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
      const token = user?.token || localStorage.getItem('authToken');
      console.log('🧪 Test mode - sending message with streaming');
      
      // Keep typing indicator while waiting for response
      // Don't create placeholder message yet - wait for actual content
      
      // Send streaming request to AI
      const response = await fetch(`${baseURL}/chatbots/${chatbotId}/test-message`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'Accept': 'text/event-stream'
        },
        body: JSON.stringify({ 
          message: currentInput,
          conversation_history: messages.map(msg => ({
            role: msg.message_type === 'user' ? 'user' : 'assistant',
            content: msg.content
          }))
        })
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        console.error('API Error:', response.status, errorData);
        throw new Error(errorData.error || 'Failed to send test message');
      }
      
      // Check if response is streaming or regular JSON
      const responseReceivedTime = performance.now();
      const timeToFirstByte = (responseReceivedTime - requestStartTime).toFixed(2);
      console.log(`⏱️ [TEST CHAT] Time to first byte: ${timeToFirstByte}ms`);
      
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
          if (done) {
            // Stream ended - save final state
            console.log('🏁 Stream ended, saving final conversation state');
            setMessages(prev => {
              const finalMessages = [...prev];
              if (finalMessages.length > 0 && finalMessages[finalMessages.length - 1].message_type === 'assistant') {
                finalMessages[finalMessages.length - 1] = {
                  ...finalMessages[finalMessages.length - 1],
                  content: accumulatedContent,
                  isStreaming: false
                };
              }
              saveTestConversation(finalMessages);
              return finalMessages;
            });
            break;
          }
          
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
                    console.log(`⏱️ [TEST CHAT] Time to first content: ${timeToFirstContent}ms`);
                    setIsTyping(false);
                    const assistantMessage = { 
                      message_type: 'assistant', 
                      content: accumulatedContent,
                      created_at: new Date().toISOString(),
                      isStreaming: true
                    };
                    const messagesWithAssistant = [...updatedMessages, assistantMessage];
                    setMessages(messagesWithAssistant);
                    assistantMessageCreated = true;
                  } else {
                    // Update existing assistant message
                    setMessages(prev => {
                      const newMessages = [...prev];
                      if (newMessages.length > 0 && newMessages[newMessages.length - 1].message_type === 'assistant') {
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
                  console.log(`⏱️ [TEST CHAT] ========== TIMING SUMMARY ==========`);
                  console.log(`⏱️ [TEST CHAT] Total response time: ${totalTime}ms (${(totalTime/1000).toFixed(2)}s)`);
                  console.log(`⏱️ [TEST CHAT] Time to first byte: ${timeToFirstByte}ms`);
                  console.log(`⏱️ [TEST CHAT] Time to first content: ${firstContentTime ? (firstContentTime - requestStartTime).toFixed(2) : 'N/A'}ms`);
                  console.log(`⏱️ [TEST CHAT] Streaming duration: ${streamingTime}ms`);
                  console.log(`⏱️ [TEST CHAT] Total chunks received: ${chunkCount}`);
                  console.log(`⏱️ [TEST CHAT] Response length: ${accumulatedContent.length} characters`);
                  console.log(`⏱️ [TEST CHAT] Average chars per chunk: ${(accumulatedContent.length / chunkCount).toFixed(2)}`);
                  console.log(`⏱️ [TEST CHAT] =====================================`);
                  
                  console.log('🤖 Streaming complete, final content:', accumulatedContent);
                  // Mark streaming as complete and save final state
                  setMessages(prev => {
                    const finalMessages = [...prev];
                    if (finalMessages.length > 0 && finalMessages[finalMessages.length - 1].message_type === 'assistant') {
                      finalMessages[finalMessages.length - 1] = {
                        ...finalMessages[finalMessages.length - 1],
                        content: accumulatedContent,
                        isStreaming: false
                      };
                    }
                    saveTestConversation(finalMessages);
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
        console.log(`⏱️ [TEST CHAT] ========== TIMING SUMMARY (JSON) ==========`);
        console.log(`⏱️ [TEST CHAT] Total response time: ${totalTime}ms (${(totalTime/1000).toFixed(2)}s)`);
        console.log(`⏱️ [TEST CHAT] Response length: ${data.response?.length || 0} characters`);
        console.log(`⏱️ [TEST CHAT] ==============================================`);
      console.log('🤖 AI Response received:', data);
      
      if (data.response) {
          setIsTyping(false);
        const aiMessage = { 
          message_type: 'assistant', 
          content: data.response,
            created_at: new Date().toISOString(),
            isStreaming: false
        };
        const finalMessages = [...updatedMessages, aiMessage];
        setMessages(finalMessages);
        saveTestConversation(finalMessages);
        }
      }
    } catch (error) {
      console.error('❌ Error in test mode:', error);
      setError(error.message || 'Failed to send test message');
      
      // Add error message to chat
      const errorMessage = { 
        message_type: 'assistant', 
        content: `Sorry, I encountered an error: ${error.message}. Please try again.`,
        created_at: new Date().toISOString()
      };
      const errorMessages = [...updatedMessages, errorMessage];
      setMessages(errorMessages);
      saveTestConversation(errorMessages);
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


  const getModelInfo = () => {
    if (!chatbot) return null;
    
    // Get the configured model from chatbot
    const config = chatbot.config || {};
    const configuredModel = chatbot.ai_model || chatbot.model || config.ai_model || config.model;
    
    console.log('Debug - Chatbot config:', config);
    console.log('Debug - Configured model:', configuredModel);
    
    // Determine provider based on model
    let provider = 'OpenAI'; // default
    let model = configuredModel || 'gpt-4o-mini';
    
    if (configuredModel) {
      if (configuredModel.startsWith('gpt-')) {
        provider = 'OpenAI';
      } else if (configuredModel.startsWith('gemini-') || configuredModel === 'gemini-pro') {
        provider = 'Google Gemini';
      }
      model = configuredModel;
    }
    
    console.log('Debug - Final provider:', provider, 'model:', model);
    
    return { provider, model };
  };

  if (loading) {
    return (
      <div className="test-chat-loading">
        <SimpleLoader message="Loading chatbot..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="test-chat-error">
        <div className="error-icon">⚠️</div>
        <h3>Error</h3>
        <p>{error}</p>
        <button onClick={() => navigate('/chatbot')} className="btn-back">
          Back to Chatbots
        </button>
      </div>
    );
  }

  if (!chatbot) {
    return (
      <div className="test-chat-error">
        <div className="error-icon">🤖</div>
        <h3>Chatbot Not Found</h3>
        <p>The chatbot you're looking for doesn't exist or you don't have permission to access it.</p>
        <button onClick={() => navigate('/chatbot')} className="btn-back">
          Back to Chatbots
        </button>
      </div>
    );
  }

  const modelInfo = getModelInfo();

  return (
    <div className="test-chat-page">
      {/* Header */}
      <div className="test-chat-header">
        <div className="header-left">
          <button onClick={() => navigate('/chatbot')} className="btn-back-header">
            ← Back
          </button>
          <div className="chatbot-info">
            <h1>{chatbot.name}</h1>
            <p className="chatbot-description">{chatbot.description || 'Test your chatbot here'}</p>
          </div>
        </div>
        <div className="header-right">
          <div className="model-info">
            <div className="model-badge">
              <span className="model-provider">{modelInfo.provider}</span>
              <span className="model-name">{modelInfo.model}</span>
            </div>
            <div className="model-settings">
              <span className="temperature">Temp: {chatbot.temperature || chatbot.config?.temperature || '0.7'}</span>
              <span className="status">{chatbot.status || 'active'}</span>
              {chatbot.config?.personality?.role && (
                <span className="role">Role: {chatbot.config.personality.role}</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Test Mode Notice */}
      <div className="test-mode-notice">
        🧪 <strong>Test Mode</strong> - Conversations stored locally (not in history)
        <button onClick={clearTestConversation} className="btn-clear-inline" title="Clear test chat">
          🗑️ Clear
        </button>
      </div>

      {/* Chat Container */}
      <div className="test-chat-container">
        <div className="chat-messages">
          {messages.length === 0 && (
            <div className="welcome-message">
              <div className="welcome-icon">🤖</div>
              <h3>Welcome to {chatbot.name}!</h3>
              <p>This is a test environment. Start a conversation to test your chatbot's responses.</p>
              <div className="test-info">
                <div className="config-display">
                  <h4>🔧 Test Configuration</h4>
                  <div className="config-items">
                    <div className="config-item">
                      <strong>Provider:</strong> {modelInfo.provider}
                    </div>
                    <div className="config-item">
                      <strong>Model:</strong> {modelInfo.model}
                    </div>
                    <div className="config-item">
                      <strong>Temperature:</strong> {chatbot.config?.temperature || '0.7'}
                    </div>
                    {chatbot.config?.personality?.role && (
                      <div className="config-item">
                        <strong>Role:</strong> {chatbot.config.personality.role}
                      </div>
                    )}
                  </div>
                </div>
                
                <div className="suggested-questions">
                  <h4>💬 Try asking:</h4>
                  <button onClick={() => setInput("Hello! How can you help me?")} className="suggested-btn">
                    Hello! How can you help me?
                  </button>
                  <button onClick={() => setInput("What can you do?")} className="suggested-btn">
                    What can you do?
                  </button>
                  <button onClick={() => setInput("Tell me about your knowledge base")} className="suggested-btn">
                    Tell me about your knowledge base
                  </button>
                </div>
              </div>
            </div>
          )}

          {messages.map((msg, index) => {
            // Don't render empty streaming messages
            if (msg.message_type === 'assistant' && msg.isStreaming && !msg.content) {
              return null;
            }
            
            return (
            <div key={index} className={`message ${msg.message_type}`}>
              <div className="message-avatar">
                {msg.message_type === 'user' ? '👤' : '🤖'}
              </div>
              <div className="message-content">
                  <div className="message-text">
                    {msg.content || (msg.isStreaming ? '...' : '')}
                  </div>
                <div className="message-time">
                  {new Date(msg.created_at).toLocaleTimeString()}
                </div>
              </div>
            </div>
            );
          })}

          {isTyping && (
            <div className="message assistant">
              <div className="message-avatar">🤖</div>
              <div className="message-content">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="chat-input-area">
          <div className="chat-input-container">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={`Test ${chatbot.name}... (Press Enter to send, Shift+Enter for new line)`}
              className="chat-input"
              rows={1}
              disabled={isTyping}
            />
            <button 
              onClick={handleSendMessage} 
              disabled={!input.trim() || isTyping}
              className="send-button"
            >
              {isTyping ? '⏳' : '➤'}
            </button>
          </div>
          <div className="input-footer">
            <span className="model-indicator">
              Powered by {modelInfo.provider} {modelInfo.model}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TestChatPage;
