import AOS from 'aos';
import 'aos/dist/aos.css';
import './Testimonials.css';
import { useEffect } from 'react';
import user1 from '../images/user1.png';
import user2 from '../images/user2.png';
import user3 from '../images/user3.png';
import user4 from '../images/user4.png';

const cards = [
  { id: 1, img: user1, name: 'David R.', role: 'Tech Startup CTO' },
  { id: 2, img: user2, name: 'David R.', role: 'Tech Startup CTO' },
  { id: 3, img: user3, name: 'David R.', role: 'Tech Startup CTO' },
  { id: 4, img: user4, name: 'David R.', role: 'Tech Startup CTO' },
];

const Testimonials = () => {

      useEffect(() => {
        AOS.init({
          duration: 800, // animation duration in ms
          easing: 'ease-in-out', // animation easing
          once: true, // animate only once
        });
      }, []);
      
  return (
  <section className="testimonial-wrapper py-5">
    {/* Section heading */}
    <h2 className="section-title my-4" data-aos="fade-up" data-aos-delay="200">
      <span className="gradient">Voices of Our Happy Clients</span>
    </h2>

    {/* Card grid */}
    <div className="container mt-5" data-aos="fade-up" data-aos-delay="200">
      <div className="row g-4 justify-content-center mt-5">
        {cards.map(({ id, img, name, role }) => (
          <div key={id} className="col-12 col-md-6 col-lg-3 my-4">
            <div className="t-card position-relative text-center p-4 mt-5">

              {/* Circle avatar */}
              <img src={img} alt={name} className="avatar rounded-circle"/>

              {/* Stars */}
              <div className="stars mt-5">
                {'★★★★★'.split('').map((s, i) => (
                  <span key={i}>★</span>
                ))}
              </div>

              {/* Name & Role */}
              <h6 className="fw-bold mb-1">{name}</h6>
              <p className="small fst-italic mb-3">{role}</p>

              {/* Body copy */}
              <p className="t-text small m-0">
                <i>
                    The integration was seamless. We trained it on our product docs and now it handles
                every technical question faster than our support staff. Truly impressive.
                </i>
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  </section>
)};

export default Testimonials;
