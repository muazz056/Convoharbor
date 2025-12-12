import Navbar from '../navbar/navbar'
import Testimonials from '../testimonials/Testimonials';
import "./home.css";
import hero_image from '../images/hero_image.png'
import chatgpt from '../images/artificial.png'
import star from '../images/Star.png'
import FAQs from '../FAQs/FAQs';
import Footer from '../Footer/Footer';
import f1 from '../images/feature_card_1.png';
import f2 from '../images/feature_card_2.png';
import f3 from '../images/feature_card_3.png';
import f4 from '../images/feature_card_4.png';
import f5 from '../images/feature_card_5.png';
import f6 from '../images/feature_card_6.png';
import AOS from 'aos';
import 'aos/dist/aos.css';
import { useEffect } from 'react';
import ChatWidget from '../ChatWidget/ChatWidget';


const cardData = [
  { img: f1, title: 'Actionable Insights Dashboard', text: 'Get real-time analytics on what customers are asking, response times, satisfaction levels, and more — helping you improve both your service and your strategy.' },
  { img: f2, title: 'Actionable Insights Dashboard', text: 'Get real-time analytics on what customers are asking, response times, satisfaction levels, and more — helping you improve both your service and your strategy.' },
  { img: f3, title: 'Actionable Insights Dashboard', text: 'Get real-time analytics on what customers are asking, response times, satisfaction levels, and more — helping you improve both your service and your strategy.' },
  { img: f4, title: 'Actionable Insights Dashboard', text: 'Get real-time analytics on what customers are asking, response times, satisfaction levels, and more — helping you improve both your service and your strategy.' },
  { img: f5, title: 'Actionable Insights Dashboard', text: 'Get real-time analytics on what customers are asking, response times, satisfaction levels, and more — helping you improve both your service and your strategy.' },
  { img: f6, title: 'Actionable Insights Dashboard', text: 'Get real-time analytics on what customers are asking, response times, satisfaction levels, and more — helping you improve both your service and your strategy.' },
];


  const Home = () => {

    useEffect(() => {
      AOS.init({
        duration: 800, // animation duration in ms
        easing: 'ease-in-out', // animation easing
        once: true, // animate only once
      });
    }, []);

    return (
      <>
      <div className='bg-home'>
        <Navbar />
        <div className="hero-wrapper text-center d-flex flex-column align-items-center justify-content-center px-3 py-3 mb-5">
      {/* Image */}
      <img src={hero_image} alt="AI Bot" className="img-fluid hero-img mb-4" />

      {/* Gradient Heading */}
      <h1 className="hero-heading mb-2">
        <span className="blue">AI-Powered</span>{' '}
        <span className="dark-blue">Customer</span>{' '}
        <span className="pink">Service ChatBot</span>
      </h1>

      {/* Description */}
      <p className="hero-desc mb-3">
        ConvoPilot is an AI-powered customer service chatbot designed for your website. It learns from your
        business data, integrates with your existing systems, and supports your clients by answering their questions and handling a wide range of customer interactions — all in real time.
      </p>

      {/* Sub Label */}
      <div className="small text-muted mb-4">
      <span className="powered-by">
        Powered by
        <img src={chatgpt} alt="ChatGPT" className="px-2 icon-img" style={{ width: '2.5rem' }} />
        ChatGPT
        </span>
        <span className="powered-by">
        <img src={star} alt="ChatGPT" className="px-2 icon-img" style={{ width: '2.5rem' }} />
        Gemini
        </span>
         
      </div>

      {/* Buttons */}
      <div className="d-flex gap-3 flex-wrap justify-content-center">
        {/* <a href="/chatbot"><button className="btn btn-dark px-4 py-2">Try For Free</button></a>
        <button className="btn btn-outline-dark px-4 py-2">Working</button> */}
        <a href="/Free_Trial" className="signup-btn px-4 py-2">Get a Free Trial</a>
        <a href="/Working" className="signup-btn px-4 py-2">Working</a>
      </div>
        </div>

        {/*Meet ConviPilot */}
        <div className=" meet-convo-container mb-5" id="meet-convopilot">

          <h3 className="intro-text" data-aos="fade-up" data-aos-delay="200">
            Meet <span className="convo-gradient">ConvoPilot</span> — Your 24/7 AI Support.
          </h3>

          <p className="main-text" data-aos="fade-up" data-aos-delay="200">
            Just ask, and it’s on it —<br />
            from answering customer questions<br />
            to booking appointments.<br />
            Trained on your data, and always learning.<br />
            Lightning-fast. Always accurate. Fully secure.
          </p>

          <p className="main-text" data-aos="fade-up" data-aos-delay="200">
            Give your customers instant support,<br />
            reduce response times, and free up<br />
            your human team for what matters most.<br />
            It’s not just a chatbot —<br />
            it’s your smartest team member.
          </p>
        </div>

        <div id="testimonials">
          <Testimonials />
        </div>
        
        <div id="pricing">
          <FAQs />
        </div>

        <div className='lower-portion'>
        <div id="features" className="feature-section mt-5 py-5">
        <h2 className="section-title my-4">
            <span className="plain-text-1">Our Primary Features</span>
        </h2>

        <div className="container py-5 mt-5 px-5">
          <div className="container">
                <div className="row">
                  {cardData.map((card, index) => (
                    <div className="col-12 col-sm-6 col-md-4 mb-4 d-flex justify-content-center" key={index}>
                      <div className="card border-0" style={{ width: '18rem' }}>
                        <img src={card.img} className="card-img-top card-img-custom" alt={card.title} />
                        <div className="card-body" id='card_text'>
                          <h5 className="card-title text-center">{card.title}</h5>
                          <p className="card-text text-center">{card.text}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
        </div>
        </div>

        <div id="contact">
          <Footer />
        </div>
        {/* Public embeddable widget on main landing. Use optional env for default chatbot. */}
        {(() => {
          const id = Number(process.env.REACT_APP_PUBLIC_CHATBOT_ID);
          return <ChatWidget publicMode={true} chatbotId={Number.isFinite(id) ? id : undefined} />
        })()}
        </div>            
      </div>
      </>
    );
  };

export default Home;