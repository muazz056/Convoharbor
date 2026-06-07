import "./Forgot_password.css";
import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import Navbar from "../navbar/navbar";
import { validateEmail } from "../../utils/validation";

const ForgotPassword = () => {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [status, setStatus] = useState("form");
  const [submittedEmail, setSubmittedEmail] = useState("");
  const navigate = useNavigate();

  const apiUrl = process.env.REACT_APP_API_URL || "http://localhost:5001/api/v1";

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setFieldError("");

    const emailError = validateEmail(email);
    if (emailError) {
      setFieldError(emailError);
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${apiUrl}/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      });

      const data = await response.json().catch(() => ({}));

      if (response.ok && data.user_exists) {
        setSubmittedEmail(email.trim().toLowerCase());
        setStatus("sent");
      } else if (response.status === 404 || data.user_exists === false) {
        setSubmittedEmail(email.trim().toLowerCase());
        setStatus("notFound");
      } else {
        setError(data.error || "Failed to send reset code. Please try again.");
      }
    } catch (err) {
      console.error("Forgot password error:", err);
      setError("Network error. Please check your connection and try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleContinue = () => {
    navigate("/verify_code", { state: { email: submittedEmail } });
  };

  const handleTryDifferent = () => {
    setStatus("form");
    setError("");
    setFieldError("");
  };

  return (
    <div className="auth-page">
      <Navbar />
      <div className="auth-container">
        <div className="auth-card">
          <div className="auth-back-link">
            <Link to="/login">
              <i className="fas fa-angle-left"></i> Back to Login
            </Link>
          </div>

          {status === "form" && (
            <>
              <div className="auth-header">
                <div className="auth-icon-circle">
                  <i className="fas fa-key"></i>
                </div>
                <h1 className="auth-title">Forgot Password?</h1>
                <p className="auth-subtitle">
                  Enter your email and we'll send you a 6-digit verification code to reset your password.
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
                  <label htmlFor="email">Email Address</label>
                  <div className={`auth-input-wrapper ${fieldError ? "has-error" : ""}`}>
                    <i className="fas fa-envelope"></i>
                    <input
                      type="email"
                      id="email"
                      name="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="name@example.com"
                      className="auth-input"
                      autoComplete="email"
                      autoFocus
                    />
                  </div>
                  {fieldError && <span className="auth-error">{fieldError}</span>}
                </div>

                <button
                  type="submit"
                  className="auth-submit-btn"
                  disabled={loading}
                >
                  {loading ? (
                    <>
                      <i className="fas fa-spinner fa-spin"></i> Sending Code...
                    </>
                  ) : (
                    <>Send Reset Code</>
                  )}
                </button>
              </form>
            </>
          )}

          {status === "sent" && (
            <>
              <div className="auth-header">
                <div className="auth-icon-circle success">
                  <i className="fas fa-envelope-open-text"></i>
                </div>
                <h1 className="auth-title">Check Your Email</h1>
                <p className="auth-subtitle">
                  We've sent a 6-digit verification code to
                  <br />
                  <strong>{submittedEmail}</strong>
                </p>
              </div>

              <div className="auth-alert-success">
                <i className="fas fa-check-circle"></i>
                A verification code has been sent to your inbox. The code expires in 15 minutes.
              </div>

              <button
                type="button"
                className="auth-submit-btn"
                onClick={handleContinue}
              >
                Enter Verification Code <i className="fas fa-arrow-right"></i>
              </button>

              <div className="auth-footer-text">
                Didn't receive the code?{" "}
                <button
                  type="button"
                  className="auth-link-btn"
                  onClick={handleTryDifferent}
                >
                  Try a different email
                </button>
              </div>
            </>
          )}

          {status === "notFound" && (
            <>
              <div className="auth-header">
                <div className="auth-icon-circle error">
                  <i className="fas fa-user-slash"></i>
                </div>
                <h1 className="auth-title">No Account Found</h1>
                <p className="auth-subtitle">
                  We couldn't find an account associated with
                  <br />
                  <strong>{submittedEmail}</strong>
                </p>
              </div>

              <div className="auth-alert auth-alert-error">
                <i className="fas fa-exclamation-circle"></i>
                No account exists with this email address. Please check the email or create a new account.
              </div>

              <button
                type="button"
                className="auth-submit-btn"
                onClick={() => navigate("/signup")}
              >
                Create New Account <i className="fas fa-user-plus"></i>
              </button>

              <div className="auth-footer-text">
                Already have an account?{" "}
                <Link to="/login" className="auth-link-btn">
                  Sign In
                </Link>
              </div>

              <div className="auth-footer-text" style={{ marginTop: "8px" }}>
                <button
                  type="button"
                  className="auth-link-btn"
                  onClick={handleTryDifferent}
                >
                  Try a different email
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default ForgotPassword;
