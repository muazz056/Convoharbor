import "./Footer.css";
import { Link } from 'react-router-dom';

const Footer = () => {
  return (
    <footer className="site-footer">
      <div className="footer-container">
        <div className="footer-grid">
          {/* Brand Column */}
          <div className="footer-brand-col">
            <h3 className="footer-brand">
              {process.env.REACT_APP_APP_NAME || 'Convoharbor'}
            </h3>
            <p className="footer-desc">
              AI-powered customer service chatbot for your website. Available 24/7.
            </p>
            <div className="footer-social">
              <a href="https://facebook.com" className="social-link" aria-label="Facebook"><i className="fab fa-facebook-f"></i></a>
              <a href="https://twitter.com" className="social-link" aria-label="Twitter"><i className="fab fa-twitter"></i></a>
              <a href="https://linkedin.com" className="social-link" aria-label="LinkedIn"><i className="fab fa-linkedin-in"></i></a>
              <a href="https://github.com" className="social-link" aria-label="GitHub"><i className="fab fa-github"></i></a>
            </div>
          </div>

          {/* Product */}
          <div className="footer-col">
            <h4 className="footer-heading">Product</h4>
            <ul className="footer-links">
              <li><Link to="/overview">Chatbot</Link></li>
              <li><a href="#features">Features</a></li>
              <li><a href="#pricing">Pricing</a></li>
              <li><Link to="/how-to-use">About</Link></li>
            </ul>
          </div>

          {/* Resources */}
          <div className="footer-col">
            <h4 className="footer-heading">Resources</h4>
            <ul className="footer-links">
              <li><a href="#!">Documentation</a></li>
              <li><a href="#!">API Reference</a></li>
              <li><a href="#!">Blog</a></li>
              <li><a href="#!">Support</a></li>
            </ul>
          </div>

          {/* Company */}
          <div className="footer-col">
            <h4 className="footer-heading">Company</h4>
            <ul className="footer-links">
              <li><Link to="/how-to-use">About Us</Link></li>
              <li><a href="#!">Careers</a></li>
              <li><a href="#!">Privacy Policy</a></li>
              <li><a href="#!">Terms of Service</a></li>
            </ul>
          </div>

          {/* Newsletter */}
          <div className="footer-col">
            <h4 className="footer-heading">Stay Updated</h4>
            <p className="footer-desc">Get the latest news and updates.</p>
            <div className="footer-newsletter">
              <input type="email" placeholder="Your email" className="footer-input" />
              <button className="footer-subscribe-btn">Subscribe</button>
            </div>
          </div>
        </div>

        <div className="footer-bottom">
          <p>&copy; {new Date().getFullYear()} {process.env.REACT_APP_APP_NAME || 'Convoharbor'}. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
