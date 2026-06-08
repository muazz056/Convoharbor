import InnerNavbar from '../navbar/InnerNavbar'
import "./Integeration.css";
import Sidebar from '../Sidebar/Sidebar';
import AOS from 'aos';
import 'aos/dist/aos.css';
import { useEffect } from 'react';


const Integeration = () => {
                  useEffect(() => {
                    AOS.init({
                      duration: 800, // animation duration in ms
                      easing: 'ease-in-out', // animation easing
                      once: true, // animate only once
                    });
                  }, []);

  const integrations = [
    {
      icon: '🛒',
      name: 'WooCommerce',
      description: 'Connect your WooCommerce store to automate customer support',
      status: 'connected',
      statusText: 'Connected',
      buttonText: 'Configure',
      colorClass: 'purple-theme'
    },
    {
      icon: '🛍️',
      name: 'Shopify',
      description: 'Integrate your Shopify store for intelligent customer support',
      status: 'disconnected',
      statusText: 'Not connected',
      buttonText: 'Connect',
      colorClass: 'green-theme'
    },
    {
      icon: '🔗',
      name: 'API Actions',
      description: 'Create custom actions via REST API',
      status: 'connected',
      statusText: '2 actions actives',
      buttonText: 'Manage',
      colorClass: 'blue-theme'
    },
    {
      icon: '📧',
      name: 'Email Marketing',
      description: 'Synchronize with your ORM and Emailing tools',
      status: 'disconnected',
      statusText: 'Non connected',
      buttonText: 'Connect',
      colorClass: 'orange-theme'
    },
    {
      icon: '💳',
      name: 'Stripe',
      description: 'Manage payment and subscriptions directly',
      status: 'disconnected',
      statusText: 'Non connecté',
      buttonText: 'Connect',
      colorClass: 'pink-theme'
    },
    {
      icon: '📱',
      name: 'WhatsApp Business',
      description: 'Deploy your chatbots on WhatsApp',
      status: 'disconnected',
      statusText: 'Non connecté',
      buttonText: 'Connect',
      colorClass: 'cyan-theme'
    }
  ];

  return (
    <div className="layout-container">
      <Sidebar />
      <div className="main-content">
        <InnerNavbar />
        <div className="page" id="integrations" data-aos="fade-up" data-aos-delay="200">
          <div className="page-header">
            <h1 className="integeration-page-title">Integrations</h1>
            <p className="page-subtitle">Connect {process.env.REACT_APP_APP_NAME || 'Convoharbor'} to your favorite tools</p>
          </div>

          <div className="integration-grid">
            {integrations.map((integration, index) => (
              <div className={`integration-card ${integration.colorClass}`} key={index}>
                <div className="integration-icon">{integration.icon}</div>
                <h3 className="integration-name">{integration.name}</h3>
                <p className="integration-description">{integration.description}</p>
                <div className={`integration-status ${integration.status}`}>
                  <span className="status-dot" />
                  {integration.statusText}
                </div>
                <button className="integeration-primary-button">
                  {integration.buttonText}
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Integeration;
