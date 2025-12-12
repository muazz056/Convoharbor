import "./Footer.css";


  const Footer = () => {
    return (
        <>
            <footer className="text-center text-lg-start text-light">
            <section className="d-flex justify-content-center justify-content-lg-between p-4 border-bottom">
            
            </section>
            <section className="">
                <div className="container text-center text-md-start mt-5">
                <div className="row mt-3">

                    <div className="col-md-2 col-lg-2 col-xl-2 mx-auto mb-4">
                    <h6 className="text-uppercase fw-bold mb-4">
                        Info
                    </h6>
                    <p>
                        <a href="#!" className="text-reset">Formats</a>
                    </p>
                    <p>
                        <a href="#!" className="text-reset">Compression</a>
                    </p>
                    <p>
                        <a href="#!" className="text-reset">Pricing</a>
                    </p>
                    <p>
                        <a href="#!" className="text-reset">Status</a>
                    </p>
                    </div>
                    <div className="col-md-2 col-lg-2 col-xl-2 mx-auto mb-4">
                    <h6 className="text-uppercase fw-bold mb-4">
                        Resources
                    </h6>
                    <p>
                        <a href="#!" className="text-reset">Developer API</a>
                    </p>
                    <p>
                        <a href="#!" className="text-reset">Tools</a>
                    </p>
                    <p>
                        <a href="#!" className="text-reset">Blogs</a>
                    </p>
                    </div>

                    <div className="col-md-3 col-lg-2 col-xl-2 mx-auto mb-4">
                    <h6 className="text-uppercase fw-bold mb-4">
                        Company
                    </h6>
                    <p>
                        <a href="#!" className="text-reset">About Us</a>
                    </p>
                    <p>
                        <a href="#!" className="text-reset">Sustainability</a>
                    </p>
                    <p>
                        <a href="#!" className="text-reset">Blogs</a>
                    </p>
                    </div>

                    <div className="col-md-4 col-lg-3 col-xl-3 mx-auto mb-md-0 mb-4">
                        <h6 className="text-uppercase fw-bold mb-4">Subscribe to our newsletter</h6>
                        <div className="input-group mb-3">
                            <input type="text" className="form-control" placeholder="Your email..." aria-label="Your email..." aria-describedby="button-addon2" />
                            <button className="btn btn-outline-secondary gradient-hover-btn" type="button" id="button-addon2">
                                Subscribe
                            </button>
                        </div>
                    <div className="mt-4">
                        <h6 className="text-uppercase fw-bold mb-4">
                            Follow us
                        </h6>
                        <a href="/" className="me-4 text-reset">
                            <i className="fab fa-facebook-f"></i>
                        </a>
                        <a href="/" className="me-4 text-reset">
                            <i className="fab fa-twitter"></i>
                        </a>
                        <a href="/" className="me-4 text-reset">
                            <i className="fab fa-google"></i>
                        </a>
                        <a href="/" className="me-4 text-reset">
                            <i className="fab fa-instagram"></i>
                        </a>
                        <a href="/" className="me-4 text-reset">
                            <i className="fab fa-linkedin"></i>
                        </a>
                        <a href="/" className="me-4 text-reset">
                            <i className="fab fa-github"></i>
                        </a>
                        </div>
                    </div>
                </div>
                </div>
            </section>
            </footer>
        </>
    );
  };

export default Footer;