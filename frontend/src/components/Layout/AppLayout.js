import React from 'react';
import Sidebar from '../Sidebar/Sidebar';
import InnerNavbar from '../navbar/InnerNavbar';
import './AppLayout.css';

const AppLayout = ({ children }) => {
  return (
    <div className="app-layout">
      <Sidebar />
      <div className="app-main">
        <InnerNavbar />
        <div className="app-content">
          {children}
        </div>
      </div>
    </div>
  );
};

export default AppLayout;
