import React from 'react';
import './SimpleLoader.css';

const SimpleLoader = ({ message = "Loading..." }) => {
  return (
    <div className="simple-loader-container">
      <div className="simple-loading-spinner"></div>
      <p className="simple-loader-message">{message}</p>
    </div>
  );
};

export default SimpleLoader;
