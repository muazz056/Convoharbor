import "./Forgot_password.css";
import logo from "../images/logo.png";

const CreateAccount = () => {

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
            <a href="/login" className="back-to-login-btn">Back to login</a>
        </div>

          <h2 className="fw-bold mb-3">Forgot Your Password?</h2>
          <p className="mb-4">Enter your email to recover your password</p>

          <div className="mb-3 d-flex">
            <input
              type="email"
              className="form-control"
              id="exampleFormControlInput1"
              placeholder="email@.com"
            />
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
