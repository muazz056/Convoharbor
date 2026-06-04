import "./navbar.css";
import { FaSignOutAlt } from "react-icons/fa";
import { useState, useEffect } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";

const InnerNavbar = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const [localUser, setLocalUser] = useState(null);

  useEffect(() => {
    const userData = localStorage.getItem('userData');
    if (userData) {
      setLocalUser(JSON.parse(userData));
    }
  }, []);

  const activeUser = user || localUser;

  const getUserInitials = () => {
    if (!activeUser) return "U";
    const n = `${activeUser.first_name || activeUser.firstName || ""} ${activeUser.last_name || activeUser.lastName || ""}`.trim();
    if (n.length >= 2) return n.split(" ").map(s => s[0]).join("").toUpperCase().slice(0, 2);
    if (activeUser.email) return activeUser.email.slice(0, 2).toUpperCase();
    return "U";
  };

  const getFullName = () => {
    if (!activeUser) return "User";
    const n = `${activeUser.first_name || activeUser.firstName || ""} ${activeUser.last_name || activeUser.lastName || ""}`.trim();
    if (n) return n;
    if (activeUser.email) return activeUser.email.split("@")[0];
    return "User";
  };

  const handleLogout = () => {
    if (logout) logout();
    localStorage.removeItem('authToken');
    localStorage.removeItem('userData');
    navigate("/login");
  };

  const scrollToSection = (e, sectionId) => {
    e.preventDefault();
    navigate('/home');
    setTimeout(() => {
      const el = document.querySelector(sectionId);
      if (el) el.scrollIntoView({ behavior: 'smooth' });
    }, 100);
  };

  const isActive = (path) => location.pathname === path;

  return (
    <nav className="site-navbar site-navbar-inner">
      <div className="site-navbar-links">
        <Link to="/home" className="site-nav-link">Home</Link>
        <Link to="/overview" className={`site-nav-link ${isActive('/overview') ? 'active' : ''}`}>Chatbot</Link>
        <a href="#features" className="site-nav-link" onClick={(e) => scrollToSection(e, '#features')}>Features</a>
        <a href="#pricing" className="site-nav-link" onClick={(e) => scrollToSection(e, '#pricing')}>Pricing</a>
        <a href="#testimonials" className="site-nav-link" onClick={(e) => scrollToSection(e, '#testimonials')}>Testimonials</a>
        <Link to="/how-to-use" className={`site-nav-link ${isActive('/how-to-use') ? 'active' : ''}`}>About</Link>
        <Link to="/contact" className={`site-nav-link ${isActive('/contact') ? 'active' : ''}`}>Contact</Link>
      </div>

      <div className="site-navbar-actions">
        {activeUser && (
          <>
            <div className="site-user-badge">
              <div className="site-user-avatar">{getUserInitials()}</div>
              <span className="site-user-name">{getFullName()}</span>
            </div>
            <button className="site-logout-btn" onClick={handleLogout}>
              <FaSignOutAlt />
              <span>Log Out</span>
            </button>
          </>
        )}
      </div>
    </nav>
  );
};

export default InnerNavbar;
