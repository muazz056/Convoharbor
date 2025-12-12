import InnerNavbar from '../navbar/InnerNavbar'
import "./LiveChat.css";
import Sidebar from '../Sidebar/Sidebar';
// import ChatWindow from '../ChatWindow/ChatWindow'
import AOS from 'aos';
import 'aos/dist/aos.css';
import { useEffect } from 'react';


  const LiveChat = () => {

                useEffect(() => {
                  AOS.init({
                    duration: 800, // animation duration in ms
                    easing: 'ease-in-out', // animation easing
                    once: true, // animate only once
                  });
                }, []);

    return (
      <>
        <div className="layout-container">
          <Sidebar />
          
          <div className="main-content">
            <InnerNavbar />
            <div className="page" id="chatbots" data-aos="fade-up" data-aos-delay="200">
              <div className="page-header">
                <h1 className="page-title">Live Chat</h1>
                <p className="page-subtitle">Take control of real-time conversations</p>
              </div>
              <div className="section-card">
                <p style={{ textAlign: "center", padding: "60px 0", color: "var(--text-secondary)" }}>
                  Live chat interface to implement...
                </p>
              </div>
            </div>
          </div>

        </div>
      </>
    );
  };

export default LiveChat;