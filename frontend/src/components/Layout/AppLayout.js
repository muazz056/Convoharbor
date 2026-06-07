import React from 'react';
import Sidebar from '../Sidebar/Sidebar';
import InnerNavbar from '../navbar/InnerNavbar';
import ChatWidget from '../ChatWidget/ChatWidget';
import { useTestChat } from '../../contexts/TestChatContext';
import './AppLayout.css';

const AppLayout = ({ children }) => {
  const { activeTestChatId } = useTestChat();

  return (
    <div className="app-layout">
      <Sidebar />
      <div className="app-main">
        <InnerNavbar />
        <div className="app-content">
          {children}
        </div>
      </div>
      {/*
        Globally mounted test chat widget.
        - Persists across page navigation (mounted at layout level, not page level).
        - Shown only when the user has toggled ON test chat for some chatbot.
        - The widget's internal `isOpen` state controls whether the chat panel
          or the launcher bubble is visible; in test mode closing the panel
          (X button) only collapses to the launcher bubble — it does NOT
          unmount the widget. The widget is only fully removed when the
          user explicitly toggles the test chat OFF, or toggles ON a
          different chatbot's test chat.
      */}
      {activeTestChatId && (
        <ChatWidget
          key={activeTestChatId}
          chatbotId={activeTestChatId}
          testMode={true}
        />
      )}
    </div>
  );
};

export default AppLayout;
