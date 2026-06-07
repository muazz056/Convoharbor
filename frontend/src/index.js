import React from 'react';
import ReactDOM from 'react-dom/client';
import 'bootstrap/dist/css/bootstrap.min.css';
import 'aos/dist/aos.css';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// Initialize AOS animation library once on every page load so that
// `data-aos` attributes work on all routes (not just pages that
// explicitly call AOS.init). Without this, elements that have
// `data-aos` stay at opacity: 0 until the library processes them,
// which made Login/Signup forms appear blank when accessed directly.
import('aos').then((AOS) => {
  AOS.init({
    duration: 800,
    easing: 'ease-in-out',
    once: true,
    startEvent: 'DOMContentLoaded',
  });
});

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
