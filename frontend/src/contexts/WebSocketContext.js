import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import io from 'socket.io-client';
import { useAuth } from './AuthContext';

const WebSocketContext = createContext({
  socket: null,
  isConnected: false,
  connectSocket: () => {},
  disconnectSocket: () => {}
});

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  return context;
};

export const WebSocketProvider = ({ children }) => {
  const [socket, setSocket] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const { user } = useAuth();

  const connectSocket = useCallback(() => {
    if (socket) return;
    const baseURL = process.env.REACT_APP_API_URL?.replace('/api/v1','') || 'http://localhost:5001';
    const hasToken = !!user?.token || !!localStorage.getItem('authToken');
    const namespace = hasToken ? '/' : '/public';
    const auth = hasToken ? { token: user?.token || localStorage.getItem('authToken') } : {};
    const newSocket = io(baseURL + namespace, {
      transports: ['polling', 'websocket'],
      upgrade: true,
      reconnectionAttempts: 20,
      reconnectionDelay: 2000,
      reconnectionDelayMax: 30000,
      timeout: 20000,
      forceNew: true,
      auth
    });
    newSocket.on('connect', () => {
      console.log('WebSocket connected successfully');
      setIsConnected(true);
      // Make socket available globally for components that need it
      window.socket = newSocket;
    });
    newSocket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      setIsConnected(false);
      // Clear global socket reference
      window.socket = null;
    });
    newSocket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
      setIsConnected(false);
    });
    setSocket(newSocket);
  }, [socket, user]);

  const disconnectSocket = useCallback(() => {
    if (socket) {
      socket.disconnect();
      setSocket(null);
      setIsConnected(false);
    }
  }, [socket]);

  useEffect(() => {
    connectSocket();
    return () => disconnectSocket();
  }, [connectSocket, disconnectSocket]);

  return (
    <WebSocketContext.Provider value={{ socket, isConnected }}>
      {children}
    </WebSocketContext.Provider>
  );
};
