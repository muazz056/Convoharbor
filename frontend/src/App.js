import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Outlet, useLocation } from "react-router-dom";
import { AuthProvider } from './contexts/AuthContext';
import { WebSocketProvider } from './contexts/WebSocketContext';
import ProtectedRoute from './components/common/ProtectedRoute';
import AppLayout from './components/Layout/AppLayout';
import './App.css';

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
import Contact from './components/Contact/Contact';

// Layout wrapper for protected pages
const ProtectedLayout = () => (
  <ProtectedRoute>
    <AppLayout>
      <Outlet />
    </AppLayout>
  </ProtectedRoute>
);

function App() {
  return (
    <AuthProvider>
    <Router>
      <Routes>
        {/* Root redirect */}
        <Route exact path="/" element={<Navigate to="/home" replace />} />

        {/* Public routes */}
        <Route exact path="/home" element={<Home />} />
        <Route exact path="/login" element={<Login />} />
        <Route exact path="/signup" element={<Create />} />
        <Route exact path="/forget_password" element={<ForgotPassword />} />
        <Route exact path="/verify_code" element={<VerifyCode />} />
        <Route exact path="/set_password" element={<SetPassword />} />
        <Route exact path="/confirm-email" element={<EmailConfirmation />} />
        <Route exact path="/oauth-callback" element={<OAuthCallback />} />
        <Route exact path="/public/chat/:chatbotId" element={<PublicChat />} />

        {/* Protected routes with WebSocket + Layout */}
        <Route path="/*" element={
          <WebSocketProvider>
            <Routes>
              <Route element={<ProtectedLayout />}>
                <Route exact path="/overview" element={<Overview />} />
                <Route exact path="/my-chatbots" element={<Mychatbot />} />
                <Route exact path="/chatbot" element={<Mychatbot />} />
                <Route exact path="/analytics-kpis" element={
                  <ProtectedRoute requiredPermissions={['view_analytics']}>
                    <Analytics />
                  </ProtectedRoute>
                } />
                <Route exact path="/how-to-use" element={<HowToUse />} />
                <Route exact path="/contact" element={<Contact />} />
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
                <Route exact path="/chat-history" element={<ChatHistory />} />
                <Route exact path="/chat-history/conversation/:conversationId" element={<ConversationDetail />} />
                <Route exact path="/integrations" element={<Integrations />} />
                <Route exact path="/api-webhooks" element={
                  <ProtectedRoute requireTenantAdmin>
                    <Webhooks />
                  </ProtectedRoute>
                } />
                <Route exact path="/settings" element={<Settings />} />
                <Route exact path="/manage-chatbots" element={
                  <ProtectedRoute requireSuperAdmin>
                    <ManageChatbots />
                  </ProtectedRoute>
                } />
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
                <Route exact path="/chatbot/:id/test" element={<TestChatPage />} />
              </Route>
            </Routes>
          </WebSocketProvider>
        } />
      </Routes>
      <ConditionalGeneralWidget />
    </Router>
    </AuthProvider>
  );
}

function ConditionalGeneralWidget() {
  const location = useLocation();
  const isPublicEmbedPage = location.pathname.startsWith('/public/chat/');
  if (isPublicEmbedPage) return null;
  return <GeneralChatWidget />;
}

export default App;
