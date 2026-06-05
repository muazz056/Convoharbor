import "./VerifyCode.css";
import React, { useState, useEffect, useRef } from "react";
import { useNavigate, Link, useLocation } from "react-router-dom";
import Navbar from "../navbar/navbar";

const VerifyCode = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const email = location.state?.email || "";

  const [code, setCode] = useState(["", "", "", "", "", ""]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [resending, setResending] = useState(false);
  const [resendMessage, setResendMessage] = useState("");
  const [countdown, setCountdown] = useState(0);
  const inputRefs = useRef([]);

  const apiUrl = process.env.REACT_APP_API_URL || "http://localhost:5001/api/v1";

  useEffect(() => {
    if (!email) {
      navigate("/forget_password", { replace: true });
    }
  }, [email, navigate]);

  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  useEffect(() => {
    inputRefs.current[0]?.focus();
  }, []);

  const handleChange = (index, value) => {
    if (!/^\d*$/.test(value)) return;

    const newCode = [...code];
    newCode[index] = value.slice(-1);
    setCode(newCode);
    setError("");

    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }

    if (newCode.every((digit) => digit !== "") && index === 5) {
      handleSubmit(newCode.join(""));
    }
  };

  const handleKeyDown = (index, e) => {
    if (e.key === "Backspace" && !code[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
    if (e.key === "ArrowLeft" && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
    if (e.key === "ArrowRight" && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handlePaste = (e) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (pastedData.length === 6) {
      const newCode = pastedData.split("");
      setCode(newCode);
      setError("");
      inputRefs.current[5]?.focus();
      handleSubmit(pastedData);
    }
  };

  const handleSubmit = async (codeString) => {
    const codeToSend = codeString || code.join("");
    if (codeToSend.length !== 6) {
      setError("Please enter the complete 6-digit code");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${apiUrl}/auth/verify-reset-code`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          code: codeToSend,
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (response.ok && data.success) {
        navigate("/set_password", {
          state: {
            email: email.trim().toLowerCase(),
            reset_token: data.reset_token,
          },
        });
      } else {
        setError(data.error || "Invalid or expired code");
        setCode(["", "", "", "", "", ""]);
        inputRefs.current[0]?.focus();
      }
    } catch (err) {
      console.error("Verify code error:", err);
      setError("Network error. Please check your connection and try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (countdown > 0 || resending) return;

    setResending(true);
    setResendMessage("");
    setError("");

    try {
      const response = await fetch(`${apiUrl}/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      });

      if (response.ok) {
        setResendMessage("A new code has been sent to your email.");
        setCountdown(60);
        setCode(["", "", "", "", "", ""]);
        inputRefs.current[0]?.focus();
      } else {
        setError("Failed to resend code. Please try again.");
      }
    } catch (err) {
      setError("Network error. Please try again.");
    } finally {
      setResending(false);
    }
  };

  return (
    <div className="auth-page">
      <Navbar />
      <div className="auth-container">
        <div className="auth-card" data-aos="fade-up">
          <div className="auth-back-link">
            <Link to="/forget_password">
              <i className="fas fa-angle-left"></i> Back
            </Link>
          </div>

          <div className="auth-header">
            <div className="auth-icon-circle">
              <i className="fas fa-shield-halved"></i>
            </div>
            <h1 className="auth-title">Verify Code</h1>
            <p className="auth-subtitle">
              We've sent a 6-digit verification code to
              <br />
              <strong>{email}</strong>
            </p>
          </div>

          {error && (
            <div className="auth-alert auth-alert-error">
              <i className="fas fa-exclamation-circle"></i>
              {error}
            </div>
          )}

          {resendMessage && (
            <div className="auth-alert auth-alert-success">
              <i className="fas fa-check-circle"></i>
              {resendMessage}
            </div>
          )}

          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSubmit();
            }}
            noValidate
          >
            <div className="auth-field">
              <label>Enter Verification Code</label>
              <div className="code-input-group" onPaste={handlePaste}>
                {code.map((digit, index) => (
                  <input
                    key={index}
                    ref={(el) => (inputRefs.current[index] = el)}
                    type="text"
                    inputMode="numeric"
                    maxLength="1"
                    value={digit}
                    onChange={(e) => handleChange(index, e.target.value)}
                    onKeyDown={(e) => handleKeyDown(index, e)}
                    className="code-input"
                    disabled={loading}
                    autoComplete="one-time-code"
                  />
                ))}
              </div>
            </div>

            <button
              type="submit"
              className="auth-submit-btn"
              disabled={loading || code.some((d) => !d)}
            >
              {loading ? (
                <>
                  <i className="fas fa-spinner fa-spin"></i> Verifying...
                </>
              ) : (
                <>Verify Code <i className="fas fa-arrow-right"></i></>
              )}
            </button>

            <div className="auth-footer-text">
              Didn't receive the code?{" "}
              {countdown > 0 ? (
                <span className="auth-countdown">
                  Resend in {countdown}s
                </span>
              ) : (
                <button
                  type="button"
                  className="auth-link-btn"
                  onClick={handleResend}
                  disabled={resending}
                >
                  {resending ? "Sending..." : "Resend Code"}
                </button>
              )}
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default VerifyCode;
