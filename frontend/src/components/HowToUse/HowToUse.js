import React, { useState } from 'react';
import './HowToUse.css';

const APP_NAME = process.env.REACT_APP_APP_NAME || 'Convoharbor';

const HowToUse = () => {
  const [activeStep, setActiveStep] = useState(1);

  const steps = [
    {
      id: 1,
      title: "Create Your Chatbot",
      icon: "🤖",
      description: "Set up a new AI assistant",
      content: {
        overview: `Go to <b>Create Chatbot</b> in the sidebar to build your AI assistant. Choose a name, AI provider (OpenAI / Gemini), model, and optional theme colors.`,
        steps: [
          `Click <b>Create Chatbot</b> in the sidebar under Chatbot Management`,
          "Enter a name and description for your bot",
          `Choose AI Provider (OpenAI / Google Gemini) and a model`,
          "Set the mode: <b>Strict</b> (answers only from your data) or <b>Permissive</b> (falls back to general knowledge)",
          "Adjust Temperature (0.1–0.7 recommended)",
          `Optionally pick theme colors and a greeting message`,
          "Click <b>Create Chatbot</b> — you'll be taken to Data Sources automatically"
        ],
        tips: [
          "Use Strict mode for customer support bots that must stay on-brand",
          "Start with GPT-4o Mini / Gemini 2.5 Flash for cost efficiency",
          "You can change all settings later in Configuration & Design"
        ]
      }
    },
    {
      id: 2,
      title: "Add Data Sources",
      icon: "📚",
      description: "Upload documents and web pages to train your bot",
      content: {
        overview: `After creating your chatbot, the <b>Data Sources</b> page opens automatically. Upload PDFs, paste text, or add website URLs. The system scrapes and chunks them for vector search.`,
        steps: [
          `From the Data Sources page, click <b>Upload Files</b> or <b>Add URL</b>`,
          "Upload PDF documents (text-based, not scanned images)",
          "Add website URLs — the scraper will fetch and index the content",
          "Paste raw text directly if needed",
          "Wait for processing — files go through chunking → embedding → vector DB",
          `Review uploaded sources in the list — status shows <b>Processing</b>, <b>Ready</b>, or <b>Failed</b>`
        ],
        tips: [
          "PDFs must be text-based (not scanned) for the system to read them",
          "Keep documents focused on the topics your chatbot should answer",
          "You can add more sources anytime — changes take effect after re-processing"
        ]
      }
    },
    {
      id: 3,
      title: "Knowledge Base",
      icon: "🧠",
      description: "Review indexed content and test your knowledge",
      content: {
        overview: `The <b>Knowledge Base</b> page shows every chunk the system extracted from your data sources. You can inspect, search, and delete individual chunks.`,
        steps: [
          `Navigate to <b>Knowledge Base</b> in the sidebar under AI Training`,
          "Browse the list of text chunks extracted from your sources",
          `Use the search bar to find specific topics`,
          "Delete irrelevant or low-quality chunks",
          "If chunks are missing, re-process the source from Data Sources",
          "Use <b>Test Query</b> to preview how your chatbot will answer a question"
        ],
        tips: [
          "Review chunks after uploading — remove garbage or irrelevant fragments",
          "If the scraper got bad content, delete those chunks and re-scrape the URL",
          "The vector search uses cosine similarity — well-written chunks give better answers"
        ]
      }
    },
    {
      id: 4,
      title: "Configure & Design",
      icon: "🎨",
      description: "Customize the look, feel, and behavior",
      content: {
        overview: `Use <b>Configuration & Design</b> to fine-tune your chatbot's AI settings, prompts, and widget appearance — all without recreating it.`,
        steps: [
          `Go to <b>Configuration & Design</b> in the sidebar`,
          "Select your chatbot from the dropdown",
          "Change AI model, provider, temperature, or mode anytime",
          `Set custom <b>Greeting</b> and <b>Farewell</b> prompts`,
          "Adjust the widget's primary color, button style, and position",
          "Preview changes live in the right panel",
          "Click <b>Save</b> to apply"
        ],
        tips: [
          "Match the widget colors to your brand for a seamless look",
          "Custom greeting and farewell prompts make the bot feel more personal",
          "Changing the AI model does NOT affect your existing data sources"
        ]
      }
    },
    {
      id: 5,
      title: "Test Your Chatbot",
      icon: "🧪",
      description: "Verify responses before going live",
      content: {
        overview: `From <b>My Chatbots</b>, click <b>Test Chat</b> on any bot to open a private test widget. This does NOT save conversations to the database.`,
        steps: [
          `Go to <b>My Chatbots</b> in the sidebar`,
          "Find your chatbot and click <b>Test Chat</b>",
          "Type questions your users will ask",
          "Verify answers come from your knowledge base (not hallucinated)",
          "Test edge cases: greetings, out-of-scope questions, farewells",
          `Check that the rating prompt appears when you say goodbye`
        ],
        tips: [
          "Test with real user questions, not just obvious ones",
          "If the bot doesn't know something, add more data sources",
          "Test chat messages are stored in localStorage only — no database clutter"
        ]
      }
    },
    {
      id: 6,
      title: "Integrations & Deploy",
      icon: "🔗",
      description: "Embed your chatbot on any website",
      content: {
        overview: `The <b>Integrations</b> page gives you ready-to-use embed scripts for HTML, Next.js, Vue 3, React, WooCommerce, Shopify, and BaseLinker. The chatbot ID and frontend URL are baked directly into each script — no .env setup required.`,
        steps: [
          `Go to <b>Integrations</b> in the sidebar`,
          "Find your chatbot and click <b>Embed</b>",
          "Choose your platform tab (HTML / Next.js / Vue / React / etc.)",
          "Copy the script and paste it into your site",
          "The iframe is fixed 400×620px and positioned at your configured corner"
        ],
        tips: [
          "For HTML sites: paste the script before closing </body>",
          "For Next.js: create components/ConvoharborWidget.tsx, render in layout.tsx",
          "Test on a staging site before production",
          "Keep your chatbot Active for the widget to appear"
        ]
      }
    },
    {
      id: 7,
      title: "Monitor & Optimize",
      icon: "📊",
      description: "Track usage and improve over time",
      content: {
        overview: `Use <b>Analytics & KPIs</b> and <b>Chat History</b> to see how users interact with your chatbot. Identify knowledge gaps and iterate.`,
        steps: [
          `Visit <b>Analytics & KPIs</b> to view total conversations, ratings, and trends`,
          "Check <b>Chat History</b> to read real user conversations",
          "Look for repeated questions your bot couldn't answer",
          "Add more data sources to fill knowledge gaps",
          "Adjust AI settings (temperature, mode) based on feedback",
          "Iterate: update content → re-process → test → deploy"
        ],
        tips: [
          "Low ratings are a signal to improve your knowledge base",
          "Chat History shows exactly what users are asking — use it to refine content",
          "Set up regular reviews of analytics to catch issues early"
        ]
      }
    }
  ];

  const currentStep = steps.find(step => step.id === activeStep);

  return (
    <>
      <div className="page" id="how-to-use">
        <div className="page-header">
          <h1 className="page-title">📖 How to Use {APP_NAME}</h1>
          <p className="page-subtitle">
            Complete guide — from creating your chatbot to deploying it live
          </p>
        </div>

        <div className="guide-container">
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
                <p dangerouslySetInnerHTML={{ __html: currentStep.content.overview }} />
              </div>

              <div className="steps-section">
                <h3>🔢 Step-by-Step Instructions</h3>
                <ol className="instruction-list">
                  {currentStep.content.steps.map((instruction, index) => (
                    <li key={index} className="instruction-item" dangerouslySetInnerHTML={{ __html: instruction }} />
                  ))}
                </ol>
              </div>

              <div className="tips-section">
                <h3>💡 Pro Tips</h3>
                <ul className="tips-list">
                  {currentStep.content.tips.map((tip, index) => (
                    <li key={index} className="tip-item">{tip}</li>
                  ))}
                </ul>
              </div>
            </div>

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

        <div className="quick-links-section">
          <h3>🔗 Quick Links</h3>
          <div className="quick-links-grid">
            <a href="/create-chatbot" className="quick-link-card">
              <span className="quick-link-icon">🤖</span>
              <div>
                <h4>Create Chatbot</h4>
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

            <a href="/data-sources" className="quick-link-card">
              <span className="quick-link-icon">📚</span>
              <div>
                <h4>Data Sources</h4>
                <p>Upload documents and URLs</p>
              </div>
            </a>

            <a href="/knowledge-base" className="quick-link-card">
              <span className="quick-link-icon">🧠</span>
              <div>
                <h4>Knowledge Base</h4>
                <p>Review indexed chunks</p>
              </div>
            </a>

            <a href="/configuration-design" className="quick-link-card">
              <span className="quick-link-icon">🎨</span>
              <div>
                <h4>Configure & Design</h4>
                <p>Customize appearance and AI settings</p>
              </div>
            </a>
            
            <a href="/integrations" className="quick-link-card">
              <span className="quick-link-icon">🔗</span>
              <div>
                <h4>Integrations</h4>
                <p>Get embed scripts</p>
              </div>
            </a>
            
            <a href="/analytics-kpis" className="quick-link-card">
              <span className="quick-link-icon">📊</span>
              <div>
                <h4>Analytics</h4>
                <p>Monitor performance</p>
              </div>
            </a>
          </div>
        </div>
      </div>
    </>
  );
};

export default HowToUse;
