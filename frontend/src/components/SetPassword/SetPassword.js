import "./SetPassword.css";
import logo from "../images/logo.png";
import React, { useState } from "react";
import { Link } from "react-router-dom";

const CreateAccount = () => {
    const [showPassword, setShowPassword] = useState(false);
  return (
    <>
        <a href="/home">
          <img
          src={logo}
          alt="LOGO"
          style={{
            position: "absolute",
            top: "1rem",
            left: "1rem",
            height: "40px", // adjust size as needed
            zIndex: 2,
          }}
        />
        </a>
    <div className="right-pane" style={{position: "absolute", left: "30%",top: "20%"}}>
        <form className="form-box needs-validation" novalidate>
        
        <div className="mb-4">
            <i className="fas fa-angle-left pe-2"></i>
            <Link to="/login" className="white-text">Back to login</Link>
        </div>

          <h2 className="fw-bold mb-3">Set Password</h2>
          <p className="mb-4">Please set a new password</p>

          <div className="mb-3 position-relative">
            <input
              type={showPassword ? "text" : "password"}
              className="form-control"
              id="exampleFormControlInput1"
              placeholder="password"
            />
            <span
              onClick={() => setShowPassword(!showPassword)}
              className="position-absolute top-50 end-0 translate-middle-y me-3"
              style={{ cursor: "pointer" }}
            >
              <i
                className={`fa ${
                  showPassword ? "fa-eye-slash" : "fa-eye"
                } text-secondary`}
              ></i>
            </span>
          </div>
            <div className="mb-3 position-relative">
            <input
              type={showPassword ? "text" : "password"}
              className="form-control"
              id="exampleFormControlInput2"
              placeholder="confirm password"
            />
            <span
              onClick={() => setShowPassword(!showPassword)}
              className="position-absolute top-50 end-0 translate-middle-y me-3"
              style={{ cursor: "pointer" }}
            >
              <i
                className={`fa ${
                  showPassword ? "fa-eye-slash" : "fa-eye"
                } text-secondary`}
              ></i>
            </span>
          </div>

          <button className="btn w-100 mb-3" type="submit" id="login_button">
            Submit
          </button>
        </form>

        
      </div>
    </>
  );
};

export default CreateAccount;
