import Navbar from '../navbar/navbar'
import Testimonials from '../testimonials/Testimonials';
import "./home.css";
import FAQs from '../FAQs/FAQs';
import Footer from '../Footer/Footer';
import AOS from 'aos';
import 'aos/dist/aos.css';
import { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

const features = [
  { icon: '🤖', title: 'AI-Powered Responses', desc: 'Smart chatbot that understands context and delivers accurate answers trained on your business data.' },
  { icon: '📊', title: 'Real-Time Analytics', desc: 'Track conversations, satisfaction rates, and performance metrics with an intuitive dashboard.' },
  { icon: '🔗', title: 'Easy Integration', desc: 'Connect with Slack, Shopify, Zendesk, and 50+ tools in just a few clicks.' },
  { icon: '🧠', title: 'Custom Knowledge Base', desc: 'Upload documents, FAQs, and manuals. Your chatbot learns from your unique business content.' },
  { icon: '⚡', title: 'Instant Setup', desc: 'Get your chatbot live in under 5 minutes. No coding required. Just point, train, and launch.' },
  { icon: '🔒', title: 'Enterprise Security', desc: 'SOC 2 compliant with end-to-end encryption. Your data stays private and secure.' },
];

const steps = [
  { num: '01', title: 'Create Your Chatbot', desc: 'Sign up and create your first chatbot in seconds. Choose a name and personality.' },
  { num: '02', title: 'Train on Your Data', desc: 'Upload documents, paste URLs, or connect APIs. Your chatbot learns everything about your business.' },
  { num: '03', title: 'Deploy Anywhere', desc: 'Embed on your website with one line of code. Deploy on Slack, WhatsApp, or any platform.' },
];

const pricingData = [
  {
    name: 'Starter',
    price: '29',
    description: 'Perfect for small businesses getting started.',
    features: ['1 chatbot', '500 queries/month', 'Basic analytics', 'Email support', 'Standard customization'],
    popular: false,
  },
  {
    name: 'Professional',
    price: '79',
    description: 'For growing teams that need more power.',
    features: ['5 chatbots', '5,000 queries/month', 'Advanced analytics', 'Priority support', 'Custom branding', 'API access'],
    popular: true,
  },
  {
    name: 'Enterprise',
    price: '199',
    description: 'For large organizations with custom needs.',
    features: ['Unlimited chatbots', 'Unlimited queries', 'Dedicated manager', 'Custom integration', 'SLA guarantee', 'White-label'],
    popular: false,
  },
];

const Home = () => {
  const { user, isAuthenticated, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    AOS.init({ duration: 800, easing: 'ease-in-out', once: true });
  }, []);

  const handleStartAction = (e) => {
    e.preventDefault();
    if (isAuthenticated && user) {
      navigate('/chatbot');
    } else {
      navigate('/login');
    }
  };

  return (
    <div className="home-page">
      <Navbar />

      {/* Hero */}
      <section className="hero">
        <div className="hero-inner">
          <span className="hero-badge" data-aos="fade-down">Trusted by 10,000+ businesses</span>
          <h1 className="hero-title" data-aos="fade-up">
            Build an AI Chatbot<br />
            <span className="hero-gradient">That Actually Helps</span>
          </h1>
          <p className="hero-subtitle" data-aos="fade-up" data-aos-delay="80">
            Train a chatbot on your business data in minutes. It answers customer questions,
            resolves issues, and works 24/7 — so your team can focus on what matters.
          </p>
          <div className="hero-actions" data-aos="fade-up" data-aos-delay="160">
            <Link to="#" className="hero-btn-primary" onClick={handleStartAction}>Start Action</Link>
            <Link to="/how-to-use" className="hero-btn-secondary">See How It Works</Link>
          </div>
          <p className="hero-note" data-aos="fade-up" data-aos-delay="200">No credit card required. Setup in under 5 minutes.</p>
        </div>
      </section>

      {/* Trusted By */}
      <section className="trusted" data-aos="fade-up">
        <p className="trusted-label">Trusted by teams at</p>
        <div className="trusted-logos">
          <span className="trusted-logo">Stripe</span>
          <span className="trusted-logo">Shopify</span>
          <span className="trusted-logo">HubSpot</span>
          <span className="trusted-logo">Zendesk</span>
          <span className="trusted-logo">Slack</span>
        </div>
      </section>

      {/* How It Works */}
      <section className="how-it-works" id="how-it-works">
        <div className="container-sm">
          <h2 className="section-heading" data-aos="fade-up">How It Works</h2>
          <p className="section-subheading" data-aos="fade-up" data-aos-delay="60">Three simple steps to your own AI assistant</p>
          <div className="steps-grid">
            {steps.map((step, i) => (
              <div className="step-card" key={i} data-aos="fade-up" data-aos-delay={100 + i * 100}>
                <span className="step-num">{step.num}</span>
                <h3 className="step-title">{step.title}</h3>
                <p className="step-desc">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="features" id="features">
        <div className="container-sm">
          <h2 className="section-heading" data-aos="fade-up">Everything You Need</h2>
          <p className="section-subheading" data-aos="fade-up" data-aos-delay="60">Powerful features to deliver exceptional customer support</p>
          <div className="features-grid">
            {features.map((f, i) => (
              <div className="feature-card" key={i} data-aos="fade-up" data-aos-delay={80 + i * 60}>
                <span className="feature-icon">{f.icon}</span>
                <h3 className="feature-title">{f.title}</h3>
                <p className="feature-desc">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="pricing" id="pricing">
        <div className="container-sm">
          <h2 className="section-heading" data-aos="fade-up">Simple, Transparent Pricing</h2>
          <p className="section-subheading" data-aos="fade-up" data-aos-delay="60">No hidden fees. Upgrade or cancel anytime.</p>
          <div className="pricing-grid">
            {pricingData.map((plan, i) => (
              <div className={`pricing-card ${plan.popular ? 'pricing-popular' : ''}`} key={i} data-aos="fade-up" data-aos-delay={100 + i * 100}>
                {plan.popular && <span className="pricing-badge">Most Popular</span>}
                <h3 className="pricing-name">{plan.name}</h3>
                <p className="pricing-desc">{plan.description}</p>
                <div className="pricing-price">
                  <span className="pricing-currency">$</span>
                  <span className="pricing-amount">{plan.price}</span>
                  <span className="pricing-period">/mo</span>
                </div>
                <ul className="pricing-features">
                  {plan.features.map((f, j) => (
                    <li key={j} className="pricing-feature">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
                      {f}
                    </li>
                  ))}
                </ul>
                <Link to="#" onClick={handleStartAction} className={`pricing-cta ${plan.popular ? 'pricing-cta-primary' : 'pricing-cta-secondary'}`}>
                  {plan.name === 'Enterprise' ? 'Contact Sales' : 'Get Started'}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="testimonials-section" id="testimonials">
        <div className="container-sm">
          <Testimonials />
        </div>
      </section>

      {/* FAQ */}
      <section className="faq-section" id="faq">
        <div className="container-sm">
          <h2 className="section-heading" data-aos="fade-up">Frequently Asked Questions</h2>
          <FAQs />
        </div>
      </section>

      {/* CTA */}
      <section className="cta-section" data-aos="fade-up">
        <div className="container-sm">
          <h2 className="cta-title">Ready to Transform Your Customer Support?</h2>
          <p className="cta-subtitle">Join thousands of businesses using AI to deliver faster, smarter support.</p>
          <Link to="#" className="hero-btn-primary" onClick={handleStartAction}>Start Action</Link>
        </div>
      </section>

      <Footer />
    </div>
  );
};

export default Home;
