import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider } from './contexts/AuthContext';
import { WebSocketProvider } from './contexts/WebSocketContext';
import ProtectedRoute from './components/common/ProtectedRoute';

// Import components
import Home from './components/home/home';
import Login from './components/Login/Login';
import Create from './components/CreateAccount/CreateAccount';
import ForgotPassword from './components/Forgot_password/Forgot_password';
import VerifyCode from './components/VerifyCode/VerifyCode';
import SetPassword from './components/SetPassword/SetPassword';
import EmailConfirmation from './components/EmailConfirmation/EmailConfirmation';
import ChatWidget from './components/ChatWidget/ChatWidget';
import GeneralChatWidget from './components/ChatWidget/GeneralChatWidget';
import Mychatbot from './components/Mychatbot/Mychatbot';
import Analytics from './components/Analytics/Analytics';
import CreateBot from './components/CreateBot/CreateBot';
import Overview from './components/Overview/Overview';
import ConfigDesign from './components/ConfigDesign/ConfigDesign';
import DataSource from './components/DataSource/DataSource';
import KnowledgeBasePage from './components/KnowledgeBase/KnowledgeBasePage';
import AiModels from './components/AiModels/AiModels';
import ChatHistory from './components/ChatHistory/ChatHistory';
import ConversationDetail from './components/ChatHistory/ConversationDetail';
import LiveChat from './components/LiveChat/LiveChat';
import LeadsContacts from './components/Leads&Contacts/Leads&Contacts';
import Integrations from './components/Integrations/Integrations';
import Webhooks from './components/Webhooks/Webhooks';
import Settings from './components/Settings/Settings';
import AdminDashboard from './components/admin/Dashboard';
import TenantManagement from './components/admin/TenantManagement';
import TestChatPage from './components/TestChat/TestChatPage';
import OAuthCallback from './components/OAuthCallback/OAuthCallback';
import PublicChat from './components/PublicChat/PublicChat';
import ManageChatbots from './components/ManageChatbots/ManageChatbots';
import ConfigureModels from './components/ConfigureModels/ConfigureModels';
import HowToUse from './components/HowToUse/HowToUse';

function App() {
  return (
    <AuthProvider>
    <Router>
      <Routes>
              {/* Root redirect to /home */}
        <Route exact path="/" element={<Navigate to="/home" replace />} />
        
              {/* Public routes - No WebSocket needed */}
        <Route exact path="/home" element={<Home />} />
        <Route exact path="/login" element={<Login />} />
        <Route exact path="/signup" element={<Create />} />
        <Route exact path="/forget_password" element={<ForgotPassword />} />
        <Route exact path="/verify_code" element={<VerifyCode />} />
        <Route exact path="/set_password" element={<SetPassword />} />
            <Route exact path="/confirm-email" element={<EmailConfirmation />} />
            <Route exact path="/oauth-callback" element={<OAuthCallback />} />
            <Route exact path="/public/chat/:chatbotId" element={<PublicChat />} />
            
            {/* App routes - With WebSocket */}
            <Route path="/*" element={
              <WebSocketProvider>
                <Routes>
            
              {/* Protected routes */}
              <Route exact path="/chatbot" element={
                <ProtectedRoute>
                  <Mychatbot />
                </ProtectedRoute>
              } />
              
              <Route exact path="/my-chatbots" element={
                <ProtectedRoute>
                  <Mychatbot />
                </ProtectedRoute>
              } />
              
              <Route exact path="/overview" element={
                <ProtectedRoute>
                  <Overview />
                </ProtectedRoute>
              } />
              
              <Route exact path="/analytics-kpis" element={
                <ProtectedRoute requiredPermissions={['view_analytics']}>
                  <Analytics />
                </ProtectedRoute>
              } />
              
              <Route exact path="/how-to-use" element={
                <ProtectedRoute>
                  <HowToUse />
                </ProtectedRoute>
              } />
              
              <Route exact path="/create-chatbot" element={
                <ProtectedRoute requiredPermissions={['manage_chatbots']} fallbackPath="/chatbot">
                  <CreateBot />
                </ProtectedRoute>
              } />
              
              <Route exact path="/configuration-design" element={
                <ProtectedRoute requiredPermissions={['manage_chatbots']} fallbackPath="/chatbot">
                  <ConfigDesign />
                </ProtectedRoute>
              } />
              
              <Route exact path="/data-sources" element={
                <ProtectedRoute requiredPermissions={['manage_chatbots']} fallbackPath="/chatbot">
                  <DataSource />
                </ProtectedRoute>
              } />
              
              <Route exact path="/knowledge-base" element={
                <ProtectedRoute requiredPermissions={['manage_chatbots']} fallbackPath="/chatbot">
                  <KnowledgeBasePage />
                </ProtectedRoute>
              } />
              
              <Route exact path="/ai-models" element={
                <ProtectedRoute requiredPermissions={['manage_chatbots']} fallbackPath="/chatbot">
                  <AiModels />
                </ProtectedRoute>
              } />
              
              <Route exact path="/chat-history" element={
                <ProtectedRoute>
                  <ChatHistory />
                </ProtectedRoute>
              } />
              <Route exact path="/chat-history/conversation/:conversationId" element={
                <ProtectedRoute>
                  <ConversationDetail />
                </ProtectedRoute>
              } />
              
              <Route exact path="/live-chat-agents" element={
                <ProtectedRoute>
                  <LiveChat />
                </ProtectedRoute>
              } />
              
              <Route exact path="/leads-contacts" element={
                <ProtectedRoute requiredPermissions={['manage_leads']}>
                  <LeadsContacts />
                </ProtectedRoute>
              } />
              
              <Route exact path="/integrations" element={
                <ProtectedRoute>
                  <Integrations />
                </ProtectedRoute>
              } />
              
              <Route exact path="/api-webhooks" element={
                <ProtectedRoute requireTenantAdmin>
                  <Webhooks />
                </ProtectedRoute>
              } />
              
              <Route exact path="/settings" element={
                <ProtectedRoute>
                  <Settings />
                </ProtectedRoute>
              } />
              
              {/* Super Admin Routes */}
              <Route exact path="/manage-chatbots" element={
                <ProtectedRoute requireSuperAdmin>
                  <ManageChatbots />
                </ProtectedRoute>
              } />
              
              {/* Admin Routes */}
              <Route exact path="/admin/dashboard" element={
                <ProtectedRoute requireSuperAdmin>
                  <AdminDashboard />
                </ProtectedRoute>
              } />
              
              <Route exact path="/admin/tenants" element={
                <ProtectedRoute requireSuperAdmin>
                  <TenantManagement />
                </ProtectedRoute>
              } />

              <Route exact path="/admin/models" element={
                <ProtectedRoute requireSuperAdmin>
                  <ConfigureModels />
                </ProtectedRoute>
              } />

              {/* Chatbot Testing Route */}
              <Route exact path="/chatbot/:id/test" element={
                <ProtectedRoute>
                  <TestChatPage />
                </ProtectedRoute>
              } />
                </Routes>
              </WebSocketProvider>
            } />
      </Routes>
      {/* General AI Assistant Widget - standalone chat using OpenAI GPT-4o
          Only shows on internal pages, not on public embed pages */}
      <ConditionalGeneralWidget />
    </Router>
    </AuthProvider>
  );
}

// Wrapper component to conditionally show GeneralChatWidget
function ConditionalGeneralWidget() {
  const location = useLocation();
  
  // Don't show on public embed chat pages
  const isPublicEmbedPage = location.pathname.startsWith('/public/chat/');
  
  // Only show on internal dashboard/app pages
  if (isPublicEmbedPage) {
    return null;
  }
  
  return <GeneralChatWidget />;
}

export default App;
