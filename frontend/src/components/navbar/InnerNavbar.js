import "./InnerNavbar.css";
import { FaMoon, FaSun, FaUser } from "react-icons/fa";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";

const InnerNavbar = () => {
  const [isDark, setIsDark] = useState(() => {
    const storedTheme = localStorage.getItem("theme");
    return storedTheme === "dark";
  });
  const navigate = useNavigate();
  const { user } = useAuth();

  // Get user initials for avatar
  const getUserInitials = () => {
    if (!user) return "U";
    
    const firstName = user.first_name || user.firstName || "";
    const lastName = user.last_name || user.lastName || "";
    
    if (firstName && lastName) {
      return `${firstName[0]}${lastName[0]}`.toUpperCase();
    } else if (firstName) {
      return firstName.substring(0, 2).toUpperCase();
    } else if (user.email) {
      return user.email.substring(0, 2).toUpperCase();
    }
    
    return "U";
  };

  useEffect(() => {
    const theme = isDark ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [isDark]);

  return (
    <nav className="navbar p-0 m-0">
      <div className="container-fluid">
        <form className="d-flex" role="search">
          <button
            type="submit"
            style={{
              border: "0",
              backgroundColor: "transparent",
              width: "40px",
              height: "40px",
              color: isDark ? "#fff" : "rgb(199, 199, 199)",
              transition: "all 0.3s ease",
            }}
          >
            <i className="fas fa-magnifying-glass"></i>
          </button>
          <input
            style={{
              border: "2px solid rgb(224, 224, 224)",
              backgroundColor: "transparent",
              color: isDark ? "#fff" : "rgb(199, 199, 199)",
              transition: "all 0.3s ease",
            }}
            className="form-control"
            id="nav-searchbar"
            type="search"
            placeholder="Search here"
            aria-label="Search"
          />
        </form>

        {/* Right Buttons */}
        <div className="d-flex justify-content-end gap-3 mt-3 mt-lg-0 align-items-center">
          <button
            style={{
              backgroundColor: "transparent",
              border: "2px solid rgb(199, 199, 199)",
              borderRadius: "20%",
              width: "40px",
              height: "40px",
              color: isDark ? "#fff" : "rgb(199, 199, 199)",
              transition: "all 0.3s ease",
            }}
          >
            <i className="fas fa-bell"></i>
          </button>

          {/* Theme Toggle */}
          <button
            className="btn btn-outline-light d-flex align-items-center justify-content-center"
            onClick={() => setIsDark(!isDark)}
            style={{
              backgroundColor: "transparent",
              border: "2px solid rgb(199, 199, 199)",
              borderRadius: "20%",
              width: "40px",
              height: "40px",
              color: isDark ? "#fff" : "rgb(199, 199, 199)",
              transition: "all 0.3s ease",
            }}
          >
            {isDark ? <FaSun /> : <FaMoon />}
          </button>

          {/* User Profile Button */}
          <button
            onClick={() => navigate('/settings')}
            style={{
              background: "linear-gradient(113deg, #468AF0, #B45693)",
              border: "0",
              borderRadius: "50%",
              width: "40px",
              height: "40px",
              color: "#fff",
              transition: "all 0.3s ease",
              fontWeight: "600",
              fontSize: "14px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
            title={user ? user.email : "Profile"}
          >
            {getUserInitials()}
          </button>
        </div>
      </div>
    </nav>
  );
};

export default InnerNavbar;
