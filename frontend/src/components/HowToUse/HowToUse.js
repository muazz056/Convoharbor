import React, { useState } from 'react';
import './HowToUse.css';


const HowToUse = () => {
  const [activeStep, setActiveStep] = useState(1);

  const steps = [
    {
      id: 1,
      title: "Create Your Chatbot",
      icon: "🤖",
      description: "Set up your AI assistant with custom configuration",
      content: {
        overview: "Start by creating a new chatbot with your desired settings and AI model.",
        steps: [
          "Navigate to 'My Chatbots' in the sidebar",
          "Click the '+ New Chatbot' button",
          "Fill in basic information (name, description, type)",
          "Choose your AI provider (OpenAI or Google Gemini)",
          "Select the AI model (GPT-4o, Gemini 2.5 Flash, etc.)",
          "Configure temperature and response settings",
          "Set conversation mode (Strict or Permissive)",
          "Customize theme colors and welcome message",
          "Click 'Create Chatbot' to proceed to data sources"
        ],
        tips: [
          "Choose a descriptive name that reflects your chatbot's purpose",
          "Start with GPT-4o Mini for cost-effective performance",
          "Use 'Strict' mode for knowledge-base focused responses",
          "Keep temperature between 0.1-0.7 for balanced responses"
        ]
      }
    },
    {
      id: 2,
      title: "Add Data Sources",
      icon: "📚",
      description: "Upload documents and add knowledge to your chatbot",
      content: {
        overview: "After creating your chatbot, you'll be redirected to add data sources that will form your chatbot's knowledge base.",
        steps: [
          "Upload PDF documents using the file uploader",
          "Add website URLs for web scraping",
          "Paste text content directly",
          "Configure document processing settings",
          "Review uploaded files in the data sources list",
          "Wait for processing to complete",
          "Verify that documents are successfully indexed"
        ],
        tips: [
          "Upload high-quality, relevant documents for better responses",
          "Ensure PDFs are text-based, not scanned images",
          "Add multiple sources for comprehensive knowledge",
          "Keep documents organized and up-to-date"
        ]
      }
    },
    {
      id: 3,
      title: "Configure & Design",
      icon: "🎨",
      description: "Customize your chatbot's appearance and behavior",
      content: {
        overview: "Fine-tune your chatbot's configuration, design, and conversation flow.",
        steps: [
          "Go to 'Configuration & Design' from the sidebar",
          "Select your chatbot from the list",
          "Update AI model and provider if needed",
          "Adjust temperature and response parameters",
          "Customize conversation mode and behavior",
          "Design the chat widget appearance",
          "Set primary colors and theme",
          "Configure welcome message and prompts",
          "Preview your changes in real-time",
          "Save your configuration"
        ],
        tips: [
          "Test different temperature settings to find the right balance",
          "Choose colors that match your brand identity",
          "Write a welcoming and informative greeting message",
          "Preview changes before saving"
        ]
      }
    },
    {
      id: 4,
      title: "Test Your Chatbot",
      icon: "🧪",
      description: "Verify your chatbot works correctly before deployment",
      content: {
        overview: "Test your chatbot's responses and behavior in a controlled environment.",
        steps: [
          "Navigate to your chatbot in 'My Chatbots'",
          "Click the 'Test Chat' button",
          "Ask various questions to test knowledge base",
          "Verify responses are accurate and helpful",
          "Test both knowledge-based and general questions",
          "Check conversation flow and user experience",
          "Test different conversation scenarios",
          "Ensure the chatbot handles edge cases properly"
        ],
        tips: [
          "Test with questions your users are likely to ask",
          "Verify the chatbot stays within its knowledge domain",
          "Check response quality and relevance",
          "Test conversation ending and rating functionality"
        ]
      }
    },
    {
      id: 5,
      title: "Get Embed Code",
      icon: "🔗",
      description: "Generate the embed script for your website",
      content: {
        overview: "Generate and customize the embed code to add your chatbot to any website.",
        steps: [
          "Go to 'Integrations' from the sidebar",
          "Find your chatbot in the list",
          "Click the 'Embed' button",
          "Copy the generated embed script",
          "Customize embed settings if needed",
          "Choose widget position and appearance",
          "Test the embed code in a development environment"
        ],
        tips: [
          "Test the embed code on a staging site first",
          "Ensure your chatbot is 'Active' before embedding",
          "Keep the embed script secure and up-to-date",
          "Monitor chatbot performance after deployment"
        ]
      }
    },
    {
      id: 6,
      title: "Deploy to Website",
      icon: "🚀",
      description: "Add your chatbot to your website or application",
      content: {
        overview: "Implement your chatbot on your website using various integration methods.",
        steps: [
          "Choose your integration method based on your platform:",
          "• HTML: Paste script before closing </body> tag",
          "• React/Next.js: Use useEffect hook or Script component",
          "• Vue.js: Use mounted lifecycle or composables",
          "• WordPress: Add to theme files or use plugin",
          "Configure environment variables for different domains",
          "Test the chatbot on your live website",
          "Monitor conversations and user interactions"
        ],
        tips: [
          "Always test on staging before production deployment",
          "Configure CORS settings if needed",
          "Monitor chatbot performance and user feedback",
          "Keep your API endpoints secure"
        ]
      }
    },
    {
      id: 7,
      title: "Monitor & Optimize",
      icon: "📊",
      description: "Track performance and improve your chatbot",
      content: {
        overview: "Monitor your chatbot's performance and continuously improve its responses.",
        steps: [
          "Visit 'Analytics & KPIs' to view performance metrics",
          "Check conversation volume and user satisfaction",
          "Review chat history for common questions",
          "Identify knowledge gaps and add more content",
          "Update your chatbot's knowledge base regularly",
          "Adjust AI model settings based on performance",
          "Collect user feedback and ratings",
          "Iterate on your chatbot's configuration"
        ],
        tips: [
          "Regular monitoring leads to better user experience",
          "Update knowledge base with new information",
          "Pay attention to user satisfaction ratings",
          "Continuously refine your chatbot's responses"
        ]
      }
    }
  ];

  const currentStep = steps.find(step => step.id === activeStep);

  return (
    <>
          <div className="page" id="how-to-use">
            <div className="page-header">
              <h1 className="page-title">📖 How to Use {process.env.REACT_APP_APP_NAME || 'Convoharbor'}</h1>
              <p className="page-subtitle">
                Complete guide from creating your chatbot to embedding it on your website
              </p>
            </div>

            <div className="guide-container">
              {/* Step Navigation */}
              <div className="steps-navigation">
                <h3>Quick Navigation</h3>
                <div className="steps-list">
                  {steps.map((step) => (
                    <button
                      key={step.id}
                      className={`step-nav-item ${activeStep === step.id ? 'active' : ''}`}
                      onClick={() => setActiveStep(step.id)}
                    >
                      <span className="step-icon">{step.icon}</span>
                      <div className="step-info">
                        <span className="step-number">Step {step.id}</span>
                        <span className="step-title">{step.title}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Step Content */}
              <div className="step-content">
                <div className="step-header">
                  <div className="step-badge">
                    <span className="step-icon-large">{currentStep.icon}</span>
                    <div>
                      <span className="step-number">Step {currentStep.id} of {steps.length}</span>
                      <h2 className="step-title">{currentStep.title}</h2>
                    </div>
                  </div>
                  <p className="step-description">{currentStep.description}</p>
                </div>

                <div className="step-body">
                  <div className="overview-section">
                    <h3>📋 Overview</h3>
                    <p>{currentStep.content.overview}</p>
                  </div>

                  <div className="steps-section">
                    <h3>🔢 Step-by-Step Instructions</h3>
                    <ol className="instruction-list">
                      {currentStep.content.steps.map((instruction, index) => (
                        <li key={index} className="instruction-item">
                          {instruction}
                        </li>
                      ))}
                    </ol>
                  </div>

                  <div className="tips-section">
                    <h3>💡 Pro Tips</h3>
                    <ul className="tips-list">
                      {currentStep.content.tips.map((tip, index) => (
                        <li key={index} className="tip-item">
                          {tip}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

                {/* Navigation Buttons */}
                <div className="step-navigation">
                  <button
                    className="nav-button prev"
                    onClick={() => setActiveStep(Math.max(1, activeStep - 1))}
                    disabled={activeStep === 1}
                  >
                    ← Previous Step
                  </button>
                  
                  <span className="step-indicator">
                    {activeStep} of {steps.length}
                  </span>
                  
                  <button
                    className="nav-button next"
                    onClick={() => setActiveStep(Math.min(steps.length, activeStep + 1))}
                    disabled={activeStep === steps.length}
                  >
                    Next Step →
                  </button>
                </div>
              </div>
            </div>

            {/* Quick Links Section */}
            <div className="quick-links-section">
              <h3>🔗 Quick Links</h3>
              <div className="quick-links-grid">
                <a href="/create-chatbot" className="quick-link-card">
                  <span className="quick-link-icon">🤖</span>
                  <div>
                    <h4>Create New Chatbot</h4>
                    <p>Start building your AI assistant</p>
                  </div>
                </a>
                
                <a href="/my-chatbots" className="quick-link-card">
                  <span className="quick-link-icon">📱</span>
                  <div>
                    <h4>My Chatbots</h4>
                    <p>Manage existing chatbots</p>
                  </div>
                </a>
                
                <a href="/integrations" className="quick-link-card">
                  <span className="quick-link-icon">🔗</span>
                  <div>
                    <h4>Get Embed Code</h4>
                    <p>Generate integration scripts</p>
                  </div>
                </a>
                
                <a href="/analytics-kpis" className="quick-link-card">
                  <span className="quick-link-icon">📊</span>
                  <div>
                    <h4>View Analytics</h4>
                    <p>Monitor performance metrics</p>
                  </div>
                </a>
              </div>
            </div>
          </div>
    </>
  );
};

export default HowToUse;
