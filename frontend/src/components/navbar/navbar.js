import "./navbar.css";
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import LogoutButton from '../LogoutButton/LogoutButton';

const Navbar = () => {
  const { isAuthenticated, user } = useAuth();

  const scrollToSection = (e, sectionId) => {
    e.preventDefault();
    const element = document.querySelector(sectionId);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <nav className="site-navbar">
      <div className="site-navbar-brand">
        <Link to="/home" className="site-brand">
          {process.env.REACT_APP_APP_NAME || 'Convoharbor'}
        </Link>
      </div>

      <div className="site-navbar-links">
        <Link to="/home" className="site-nav-link">Home</Link>
        <Link to="/overview" className="site-nav-link">Chatbot</Link>
        <a href="#features" className="site-nav-link" onClick={(e) => scrollToSection(e, '#features')}>Features</a>
        <a href="#pricing" className="site-nav-link" onClick={(e) => scrollToSection(e, '#pricing')}>Pricing</a>
        <a href="#testimonials" className="site-nav-link" onClick={(e) => scrollToSection(e, '#testimonials')}>Testimonials</a>
        <Link to="/how-to-use" className="site-nav-link">About</Link>
        <Link to="/contact" className="site-nav-link">Contact</Link>
      </div>

      <div className="site-navbar-actions">
        {isAuthenticated ? (
          <>
            <span className="site-welcome-text">
              {user?.first_name || user?.firstName || user?.email?.split('@')[0] || 'User'}
            </span>
            <LogoutButton />
          </>
        ) : (
          <>
            <Link to="/login" className="site-login-btn">Login</Link>
            <Link to="/signup" className="site-signup-btn">Sign Up</Link>
          </>
        )}
      </div>
    </nav>
  );
};

export default Navbar;
