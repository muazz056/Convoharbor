// components/Sidebar.js
import './Sidebar.css'; // Add your custom styles
import React, { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { MdMenu } from 'react-icons/md'; 
import logo from '../images/logo.png'
import {
  MdDashboard,
  MdAnalytics,
  MdChat,
  MdCreate,
  MdSettings,
  MdIntegrationInstructions,
  MdDataUsage,
  MdOutlineSupportAgent, // Commented out - not used
  MdWebhook, // Commented out - not used
  MdPeople, // Commented out - not used
  MdOutlineLibraryBooks,
  MdOutlineModelTraining,
  MdSupervisorAccount,
  MdHelpOutline,
} from 'react-icons/md';


const Sidebar = () => {

  const [isCollapsed, setIsCollapsed] = useState(false);
  const [user, setUser] = useState(null);
  
  const toggleSidebar = () => {
    setIsCollapsed(!isCollapsed);
  };

  useEffect(() => {
    // Load user data to check role
    const userData = localStorage.getItem('userData');
    if (userData) {
      const parsedUser = JSON.parse(userData);
      console.log('🔍 Sidebar: User data loaded:', parsedUser);
      console.log('🔍 Sidebar: User role:', parsedUser.role);
      setUser(parsedUser);
    } else {
      console.log('⚠️ Sidebar: No user data found in localStorage');
    }
  }, []);


  // Build navigation items based on user role
  const getNavItems = () => {
    const baseItems = [
      {
        title: 'Dashboard',
        items: [
          { name: 'Overview', icon: <MdDashboard /> },
          { name: 'Analytics & KPIs', icon: <MdAnalytics /> },
          { name: 'How to Use', icon: <MdHelpOutline /> },
        ],
      },
      {
        title: 'Chatbot Management',
        items: [
          { name: 'My Chatbots', icon: <MdChat /> },
          { name: 'Create Chatbot', icon: <MdCreate /> },
          { name: 'Configuration & Design', icon: <MdSettings /> },
        ],
      },
      {
        title: 'AI Training',
        items: [
          { name: 'Data Sources', icon: <MdDataUsage /> },
          { name: 'Knowledge Base', icon: <MdOutlineLibraryBooks /> },
          { name: 'AI Models', icon: <MdOutlineModelTraining /> },
        ],
      },
      {
        title: 'Customer Support',
        items: [
          { name: 'Chat History', icon: <MdChat /> },
          { name: 'Live Chat Agents', icon: <MdOutlineSupportAgent /> },
          { name: 'Leads & Contacts', icon: <MdPeople /> },
        ],
      },
      {
        title: 'System',
        items: [
          { name: 'Integrations', icon: <MdIntegrationInstructions /> },
          // { name: 'API & Webhooks', icon: <MdWebhook /> },
          { name: 'Settings', icon: <MdSettings /> },
        ],
      },
    ];

    // Add Manage Chatbots to Chatbot Management section if user is super admin
    if (user && user.role === 'super_admin') {
      console.log('✅ Sidebar: Adding Manage Chatbots to Chatbot Management for user:', user.email);
      // Find the Chatbot Management section and add Manage Chatbots at the beginning
      const chatbotManagementSection = baseItems.find(section => section.title === 'Chatbot Management');
      if (chatbotManagementSection) {
        chatbotManagementSection.items.unshift({ name: 'Manage Chatbots', icon: <MdSupervisorAccount /> });
      }
    } else {
      console.log('❌ Sidebar: Not adding Manage Chatbots menu. User:', user ? `${user.email} (${user.role})` : 'null');
    }

    return baseItems;
  };

  const navItems = getNavItems();

  return (
      <div className={`sidebar ${isCollapsed ? "collapsed" : ""}`}>
            <div className="top-bar">
              {!isCollapsed && <a href="/home"><img src={logo} alt="Logo" className="logo" /></a>}
              <button className="toggle-btn" onClick={toggleSidebar}>
                <MdMenu />
              </button>
            </div>

            {navItems.map((section, index) => (
              <div key={index}>
                {!isCollapsed && (
                  <div className="section-titles">{section.title.toUpperCase()}</div>
                )}
                <ul className="nav-links">
                  {section.items.map((item) => (
                    <li key={item.name}>
                      <NavLink
                        to={`/${item.name.toLowerCase().replace(/ & | /g, "-")}`}
                        className={({ isActive }) =>
                          `nav-items ${isActive ? "active" : ""}`
                        }
                      >
                        <span className="icon">{item.icon}</span>
                        {!isCollapsed && <span className="text">{item.name}</span>}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
      </div>
  );
};

export default Sidebar;
