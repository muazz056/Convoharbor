import "./navbar.css";
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import LogoutButton from '../LogoutButton/LogoutButton';
import logo from '../images/logo.png';

const Navbar = () => {
  const { isAuthenticated, user } = useAuth();

  return (
    <nav className="navbar navbar-expand-lg navbar-light py-3">
      <div className="container-fluid">
        {/* Logo */}
        <Link className="navbar-brand d-flex align-items-center" to="/home">
          <img src={logo} alt="Logo" width="160" className="me-2" />
        </Link>

        {/* Hamburger Toggle */}
        <button
          className="navbar-toggler"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#navbarResponsive"
          aria-controls="navbarResponsive"
          aria-expanded="false"
          aria-label="Toggle navigation"
        >
          <span className="navbar-toggler-icon"></span>
        </button>

        {/* Collapsible Content */}
        <div className="collapse navbar-collapse" id="navbarResponsive">
          <div className="w-100 d-lg-flex justify-content-between align-items-center">

            {/* Center Nav Links */}
            <ul className="navbar-nav mx-auto mb-2 mb-lg-0 nav-center-custom">
              <li className="nav-item">
                <Link className="nav-link" to="/chatbot">ChatBot</Link>
              </li>
              <li className="nav-item">
                <a 
                  className="nav-link" 
                  href="#testimonials" 
                  onClick={(e) => {
                    e.preventDefault();
                    const element = document.querySelector('#testimonials');
                    if (element) {
                      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    } else {
                      window.location.href = '/home#testimonials';
                    }
                  }}
                >
                  Testimonials
                </a>
              </li>
              <li className="nav-item">
                <a 
                  className="nav-link" 
                  href="#pricing" 
                  onClick={(e) => {
                    e.preventDefault();
                    const element = document.querySelector('#pricing');
                    if (element) {
                      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    } else {
                      window.location.href = '/home#pricing';
                    }
                  }}
                >
                  Pricing
                </a>
              </li>
              <li className="nav-item">
                <a 
                  className="nav-link" 
                  href="#features" 
                  onClick={(e) => {
                    e.preventDefault();
                    const element = document.querySelector('#features');
                    if (element) {
                      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    } else {
                      window.location.href = '/home#features';
                    }
                  }}
                >
                  Features
                </a>
              </li>
              <li className="nav-item">
                <a 
                  className="nav-link" 
                  href="#contact" 
                  onClick={(e) => {
                    e.preventDefault();
                    const element = document.querySelector('#contact');
                    if (element) {
                      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    } else {
                      window.location.href = '/home#contact';
                    }
                  }}
                >
                  Contact
                </a>
              </li>
            </ul>

            {/* Right Buttons */}
            <div className="d-flex justify-content-end gap-3 mt-3 mt-lg-0 align-items-center">
              {isAuthenticated ? (
                <>
                  <span className="welcome-text">Welcome, {user?.first_name || user?.firstName || user?.email?.split('@')[0] || 'User'}</span>
                  <LogoutButton />
                </>
              ) : (
                <>
                  <Link to="/login" className="login-btn px-3 py-3">Login</Link>
                  <Link to="/signup" className="signup-btn px-3 py-3">SignUp</Link>
                </>
              )}
            </div>

          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
