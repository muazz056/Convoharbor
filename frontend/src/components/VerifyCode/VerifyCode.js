import "./VerifyCode.css";
import logo from "../images/logo.png";
import { Link } from "react-router-dom";

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
            <Link to="/login" className="white-text">Back to login</Link>
        </div>

          <h2 className="fw-bold mb-3">Verify Code</h2>
          <p className="mb-4">Authentication code has been sent to your email</p>

          <div className="mb-3 d-flex">
            <input
              type="number"
              className="form-control"
              id="exampleFormControlInput1"
              placeholder="code"
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
