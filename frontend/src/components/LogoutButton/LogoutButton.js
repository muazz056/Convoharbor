import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import './LogoutButton.css';

const LogoutButton = () => {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      const result = await logout();
      if (result.success) {
        navigate('/login');
      }
    } catch (error) {
      console.error('Error during logout:', error);
      // Still navigate to login page even if there's an error
      navigate('/login');
    }
  };

  return (
    <button 
      className="logout-button" 
      onClick={handleLogout}
      aria-label="Logout"
    >
      <i className="fas fa-sign-out-alt"></i>
      <span>Logout</span>
    </button>
  );
};

export default LogoutButton;
