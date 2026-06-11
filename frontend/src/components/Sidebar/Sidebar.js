import './Sidebar.css';
import React, { useState, useEffect } from 'react';
import { NavLink, Link } from 'react-router-dom';
import { MdMenu, MdClose, MdDashboard, MdAnalytics, MdChat, MdCreate, MdSettings, MdIntegrationInstructions, MdDataUsage, MdOutlineLibraryBooks, MdOutlineModelTraining, MdSupervisorAccount, MdHelpOutline, MdStar } from 'react-icons/md';

const Sidebar = () => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [user, setUser] = useState(null);

  const toggleSidebar = () => {
    setIsCollapsed(!isCollapsed);
  };

  const toggleMobile = () => {
    setIsMobileOpen(!isMobileOpen);
  };

  useEffect(() => {
    const userData = localStorage.getItem('userData');
    if (userData) {
      setUser(JSON.parse(userData));
    }
  }, []);

  const getNavItems = () => {
    const baseItems = [
      {
        title: 'Dashboard',
        items: [
          { name: 'Overview', icon: <MdDashboard /> },
          { name: 'Analytics & KPIs', icon: <MdAnalytics /> },
          { name: 'Feedback', icon: <MdStar />, path: '/feedback' },
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
          // { name: 'Live Chat Agents', icon: <MdOutlineSupportAgent /> },
          // { name: 'Leads & Contacts', icon: <MdPeople /> },
        ],
      },
      {
        title: 'System',
        items: [
          { name: 'Integrations', icon: <MdIntegrationInstructions /> },
          { name: 'Settings', icon: <MdSettings /> },
        ],
      },
    ];

    if (user && user.role === 'super_admin') {
      const chatbotManagementSection = baseItems.find(section => section.title === 'Chatbot Management');
      if (chatbotManagementSection) {
        chatbotManagementSection.items.unshift({ name: 'Manage Chatbots', icon: <MdSupervisorAccount />, path: '/manage-chatbots' });
      }
      const aiTrainingSection = baseItems.find(section => section.title === 'AI Training');
      if (aiTrainingSection) {
        aiTrainingSection.items.push({ name: 'Configure Models', icon: <MdOutlineModelTraining />, path: '/admin/models' });
      }
    }

    return baseItems;
  };

  const navItems = getNavItems();
  const sidebarClasses = `sidebar ${isCollapsed ? 'collapsed' : ''} ${isMobileOpen ? 'open' : ''}`;

  return (
    <>
      <div className={sidebarClasses}>
        <div className="sidebar-header">
          <Link to="/home" className="sidebar-logo">
            {!isCollapsed && <span>{process.env.REACT_APP_APP_NAME || 'Convoharbor'}</span>}
          </Link>
          <button className="sidebar-toggle" onClick={isMobileOpen ? toggleMobile : toggleSidebar}>
            {isMobileOpen ? <MdClose /> : <MdMenu />}
          </button>
        </div>

        <div className="sidebar-scroll">
          {navItems.map((section, index) => (
            <div className="sidebar-section" key={index}>
              {!isCollapsed && <div className="sidebar-section-title">{section.title}</div>}
              <ul className="sidebar-nav">
                {section.items.map((item) => (
                  <li className="sidebar-nav-item" key={item.name}>
                    <NavLink
                      to={item.path || `/${item.name.toLowerCase().replace(/ & | /g, '-')}`}
                      className={({ isActive }) => `sidebar-nav-link ${isActive ? 'active' : ''}`}
                    >
                      <span className="nav-icon">{item.icon}</span>
                      <span className="nav-text">{item.name}</span>
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {!isCollapsed && user && (
          <div className="sidebar-footer">
            <div className="sidebar-footer-avatar">
              {user.first_name?.[0] || user.email?.[0] || 'U'}
            </div>
            <div className="sidebar-footer-info">
              <div className="sidebar-footer-name">
                {user.first_name ? `${user.first_name} ${user.last_name || ''}` : user.email}
              </div>
              <div className="sidebar-footer-role">
                {user.role === 'super_admin' ? 'Super Admin' : user.role === 'admin' ? 'Admin' : 'User'}
              </div>
            </div>
          </div>
        )}
      </div>

      {isMobileOpen && <div className="sidebar-overlay" onClick={toggleMobile} />}
    </>
  );
};

export default Sidebar;
