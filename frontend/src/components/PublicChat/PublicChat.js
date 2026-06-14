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

  // Make body and root transparent for embed
  useEffect(() => {
    document.body.classList.add('public-chat-mode');
    document.documentElement.classList.add('public-chat-mode');
    document.body.style.background = 'transparent';
    document.documentElement.style.background = 'transparent';

    // #root has background: #ffffff !important from index.css.
    // Inline style with !important via setProperty overrides CSS !important rules.
    const rootEl = document.getElementById('root');
    if (rootEl) {
      rootEl.style.setProperty('background', 'transparent', 'important');
    }

    return () => {
      document.body.classList.remove('public-chat-mode');
      document.documentElement.classList.remove('public-chat-mode');
      document.body.style.background = '';
      document.documentElement.style.background = '';
      if (rootEl) {
        rootEl.style.removeProperty('background');
      }
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