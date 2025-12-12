import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import ChatWidget from '../ChatWidget/ChatWidget';
import './PublicChat.css';

const PublicChat = () => {
  const { chatbotId } = useParams();
  
  // Initialize conversationId from localStorage immediately to prevent disappearing on refresh
  const [conversationId, setConversationId] = useState(() => {
    if (chatbotId) {
      const storageKey = `embed_conversation_${chatbotId}`;
      const existing = localStorage.getItem(storageKey);
      return existing ? Number(existing) : null;
    }
    return null;
  });

  // Make body transparent for embed
  useEffect(() => {
    document.body.classList.add('public-chat-mode');
    document.documentElement.classList.add('public-chat-mode');
    document.body.style.background = 'transparent';
    document.documentElement.style.background = 'transparent';
    
    return () => {
      // Cleanup on unmount
      document.body.classList.remove('public-chat-mode');
      document.documentElement.classList.remove('public-chat-mode');
      document.body.style.background = '';
      document.documentElement.style.background = '';
    };
  }, []);

  return (
    <div className="public-chat-container">
      <ChatWidget 
        publicMode 
        chatbotId={chatbotId} 
        conversationId={conversationId}
      />
    </div>
  );
};

export default PublicChat;