import "./SetPassword.css";
import React, { useState, useEffect } from "react";
import { useNavigate, Link, useLocation } from "react-router-dom";
import Navbar from "../navbar/navbar";

const PASSWORD_REGEX = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*(),.?":{}|<>_-])[A-Za-z\d!@#$%^&*(),.?":{}|<>_-]{8,}$/;

const checkPasswordStrength = (password) => {
  const checks = {
    length: password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    digit: /\d/.test(password),
    special: /[!@#$%^&*(),.?":{}|<>_-]/.test(password),
  };
  const passed = Object.values(checks).filter(Boolean).length;
  let strength = "weak";
  if (passed === 5) strength = "strong";
  else if (passed >= 3) strength = "medium";
  return { checks, strength };
};

const SetPassword = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { email, reset_token } = location.state || {};

  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState({
    newPassword: "",
    confirmPassword: "",
  });
  const [fieldErrors, setFieldErrors] = useState({
    newPassword: "",
    confirmPassword: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const apiUrl = process.env.REACT_APP_API_URL || "http://localhost:5001/api/v1";

  useEffect(() => {
    if (!email || !reset_token) {
      navigate("/forget_password", { replace: true });
    }
  }, [email, reset_token, navigate]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    setFieldErrors((prev) => ({ ...prev, [name]: "" }));
    setError("");
  };

  const validateForm = () => {
    const errors = { newPassword: "", confirmPassword: "" };

    if (!formData.newPassword) {
      errors.newPassword = "New password is required";
    } else if (!PASSWORD_REGEX.test(formData.newPassword)) {
      errors.newPassword =
        "Must be 8+ characters with uppercase, lowercase, number, and special character";
    }

    if (!formData.confirmPassword) {
      errors.confirmPassword = "Please confirm your new password";
    } else if (formData.newPassword !== formData.confirmPassword) {
      errors.confirmPassword = "Passwords do not match";
    }

    setFieldErrors(errors);
    return !errors.newPassword && !errors.confirmPassword;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (!validateForm()) return;

    setLoading(true);

    try {
      const response = await fetch(`${apiUrl}/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          reset_token,
          new_password: formData.newPassword,
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (response.ok && data.success) {
        setSuccess(true);
        setTimeout(() => {
          navigate("/login", { replace: true });
        }, 2500);
      } else {
        setError(data.error || "Failed to reset password. Please try again.");
      }
    } catch (err) {
      console.error("Reset password error:", err);
      setError("Network error. Please check your connection and try again.");
    } finally {
      setLoading(false);
    }
  };

  const { checks, strength } = checkPasswordStrength(formData.newPassword);
  const strengthLabels = { weak: "Weak", medium: "Medium", strong: "Strong" };
  const strengthColors = { weak: "#ef4444", medium: "#f59e0b", strong: "#10b981" };

  return (
    <div className="auth-page">
      <Navbar />
      <div className="auth-container">
        <div className="auth-card">
          <div className="auth-back-link">
            <Link to="/verify_code" state={{ email }}>
              <i className="fas fa-angle-left"></i> Back
            </Link>
          </div>

          {!success ? (
            <>
              <div className="auth-header">
                <div className="auth-icon-circle">
                  <i className="fas fa-lock"></i>
                </div>
                <h1 className="auth-title">Set New Password</h1>
                <p className="auth-subtitle">
                  Create a strong password for your account
                </p>
              </div>

              {error && (
                <div className="auth-alert auth-alert-error">
                  <i className="fas fa-exclamation-circle"></i>
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} noValidate>
                <div className="auth-field">
                  <label htmlFor="newPassword">New Password</label>
                  <div
                    className={`auth-input-wrapper ${fieldErrors.newPassword ? "has-error" : ""}`}
                  >
                    <i className="fas fa-lock"></i>
                    <input
                      type={showPassword ? "text" : "password"}
                      id="newPassword"
                      name="newPassword"
                      value={formData.newPassword}
                      onChange={handleChange}
                      placeholder="Enter new password"
                      className="auth-input"
                      autoComplete="new-password"
                      autoFocus
                    />
                    <button
                      type="button"
                      className="auth-toggle-password"
                      onClick={() => setShowPassword(!showPassword)}
                      tabIndex={-1}
                    >
                      <i className={`fas ${showPassword ? "fa-eye-slash" : "fa-eye"}`}></i>
                    </button>
                  </div>
                  {formData.newPassword && (
                    <div className="password-strength">
                      <div className="strength-bar-container">
                        <div
                          className="strength-bar"
                          style={{
                            width:
                              strength === "strong"
                                ? "100%"
                                : strength === "medium"
                                ? "66%"
                                : "33%",
                            backgroundColor: strengthColors[strength],
                          }}
                        ></div>
                      </div>
                      <span
                        className="strength-label"
                        style={{ color: strengthColors[strength] }}
                      >
                        {strengthLabels[strength]}
                      </span>
                    </div>
                  )}
                  {fieldErrors.newPassword && (
                    <span className="auth-error">{fieldErrors.newPassword}</span>
                  )}
                  {!fieldErrors.newPassword && formData.newPassword && (
                    <div className="password-requirements">
                      <div className={checks.length ? "req met" : "req"}>
                        <i className={`fas ${checks.length ? "fa-check" : "fa-circle"}`}></i>
                        8+ characters
                      </div>
                      <div className={checks.uppercase ? "req met" : "req"}>
                        <i className={`fas ${checks.uppercase ? "fa-check" : "fa-circle"}`}></i>
                        Uppercase letter
                      </div>
                      <div className={checks.lowercase ? "req met" : "req"}>
                        <i className={`fas ${checks.lowercase ? "fa-check" : "fa-circle"}`}></i>
                        Lowercase letter
                      </div>
                      <div className={checks.digit ? "req met" : "req"}>
                        <i className={`fas ${checks.digit ? "fa-check" : "fa-circle"}`}></i>
                        Number
                      </div>
                      <div className={checks.special ? "req met" : "req"}>
                        <i className={`fas ${checks.special ? "fa-check" : "fa-circle"}`}></i>
                        Special character
                      </div>
                    </div>
                  )}
                </div>

                <div className="auth-field">
                  <label htmlFor="confirmPassword">Confirm New Password</label>
                  <div
                    className={`auth-input-wrapper ${fieldErrors.confirmPassword ? "has-error" : ""}`}
                  >
                    <i className="fas fa-lock"></i>
                    <input
                      type={showPassword ? "text" : "password"}
                      id="confirmPassword"
                      name="confirmPassword"
                      value={formData.confirmPassword}
                      onChange={handleChange}
                      placeholder="Re-enter new password"
                      className="auth-input"
                      autoComplete="new-password"
                    />
                  </div>
                  {fieldErrors.confirmPassword && (
                    <span className="auth-error">{fieldErrors.confirmPassword}</span>
                  )}
                </div>

                <button
                  type="submit"
                  className="auth-submit-btn"
                  disabled={loading}
                >
                  {loading ? (
                    <>
                      <i className="fas fa-spinner fa-spin"></i> Resetting Password...
                    </>
                  ) : (
                    <>Reset Password</>
                  )}
                </button>
              </form>
            </>
          ) : (
            <>
              <div className="auth-header">
                <div className="auth-icon-circle success">
                  <i className="fas fa-check"></i>
                </div>
                <h1 className="auth-title">Password Reset!</h1>
                <p className="auth-subtitle">
                  Your password has been successfully reset.
                  <br />
                  Redirecting you to login...
                </p>
              </div>
              <div className="auth-alert auth-alert-success">
                <i className="fas fa-check-circle"></i>
                You can now log in with your new password.
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default SetPassword;
