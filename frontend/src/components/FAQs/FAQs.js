import "./FAQs.css";
import { Collapse, initMDB } from 'mdb-ui-kit';
import React, { useEffect } from 'react';
import AOS from 'aos';
import 'aos/dist/aos.css';

  const FAQs = () => {
    useEffect(() => {
        // Init MDB Collapse
        initMDB({ Collapse });

        // Init AOS
        AOS.init({
        duration: 800,
        easing: 'ease-in-out',
        once: true,
        });
    }, []);
    return (
      <>
        <div className="container mt-5">
        <h2 className="section-title my-4" data-aos="fade-up" data-aos-delay="200">
            <span className="plain-text">Frequently Asked </span><span className="gradient">Questions</span>
        </h2>

        <div className="accordion accordion-flush py-5 mt-5 px-5" id="accordionFlushExample">

        <div data-aos="fade-up" data-aos-delay="200" className="mt-4 accordion-item">
            <h2 className="accordion-header" id="flush-headingOne">
            <button
                data-mdb-collapse-init
                className="accordion-button collapsed"
                type="button"
                data-mdb-target="#flush-collapseOne"
                aria-expanded="false"
                aria-controls="flush-collapseOne"
            >
                <span className="accordion-heading">What is ConvoPilot?</span>
            </button>
            </h2>
            <div
            id="flush-collapseOne"
            className="accordion-collapse collapse"
            aria-labelledby="flush-headingOne"
            data-mdb-parent="#accordionFlushExample"
            >
            <div className="accordion-body">
                Anim pariatur cliche reprehenderit, enim eiusmod high life accusamus terry
                richardson ad squid. 3 wolf moon officia aute, non cupidatat skateboard dolor
                brunch. Food truck quinoa nesciunt laborum eiusmod. Brunch 3 wolf moon tempor,
                sunt aliqua put a bird on it squid single-origin coffee nulla assumenda shoreditch
                et. Nihil anim keffiyeh helvetica, craft beer labore wes anderson cred nesciunt
                sapiente ea proident. Ad vegan excepteur butcher vice lomo. Leggings occaecat
                craft beer farm-to-table, raw denim aesthetic synth nesciunt you probably haven't
                heard of them accusamus labore sustainable VHS.
            </div>
            </div>
        </div>

        <div data-aos="fade-up" data-aos-delay="200" className="mt-4 accordion-item">
            <h2 className="accordion-header" id="flush-headingTwo">
            <button
                data-mdb-collapse-init
                className="accordion-button collapsed"
                type="button"
                data-mdb-target="#flush-collapseTwo"
                aria-expanded="false"
                aria-controls="flush-collapseTwo"
            >
                <span className="accordion-heading">How does ConvoPilot learn about my business?</span>
            </button>
            </h2>
            <div
            id="flush-collapseTwo"
            className="accordion-collapse collapse"
            aria-labelledby="flush-headingTwo"
            data-mdb-parent="#accordionFlushExample"
            >
            <div className="accordion-body">
                Anim pariatur cliche reprehenderit, enim eiusmod high life accusamus terry
                richardson ad squid. 3 wolf moon officia aute, non cupidatat skateboard dolor
                brunch. Food truck quinoa nesciunt laborum eiusmod. Brunch 3 wolf moon tempor,
                sunt aliqua put a bird on it squid single-origin coffee nulla assumenda shoreditch
                et. Nihil anim keffiyeh helvetica, craft beer labore wes anderson cred nesciunt
                sapiente ea proident. Ad vegan excepteur butcher vice lomo. Leggings occaecat
                craft beer farm-to-table, raw denim aesthetic synth nesciunt you probably haven't
                heard of them accusamus labore sustainable VHS.
            </div>
            </div>
        </div>

        <div data-aos="fade-up" data-aos-delay="200" className="mt-4 accordion-item">
            <h2 className="accordion-header" id="flush-headingThree">
            <button
                data-mdb-collapse-init
                className="accordion-button collapsed"
                type="button"
                data-mdb-target="#flush-collapseThree"
                aria-expanded="false"
                aria-controls="flush-collapseThree"
            >
                <span className="accordion-heading">Can I integrate ConvoPilot with my existing systems?</span>
            </button>
            </h2>
            <div
            id="flush-collapseThree"
            className="accordion-collapse collapse"
            aria-labelledby="flush-headingThree"
            data-mdb-parent="#accordionFlushExample"
            >
            <div className="accordion-body">
                Anim pariatur cliche reprehenderit, enim eiusmod high life accusamus terry
                richardson ad squid. 3 wolf moon officia aute, non cupidatat skateboard dolor
                brunch. Food truck quinoa nesciunt laborum eiusmod. Brunch 3 wolf moon tempor,
                sunt aliqua put a bird on it squid single-origin coffee nulla assumenda shoreditch
                et. Nihil anim keffiyeh helvetica, craft beer labore wes anderson cred nesciunt
                sapiente ea proident. Ad vegan excepteur butcher vice lomo. Leggings occaecat
                craft beer farm-to-table, raw denim aesthetic synth nesciunt you probably haven't
                heard of them accusamus labore sustainable VHS.
            </div>
            </div>
        </div>

        <div data-aos="fade-up" data-aos-delay="200" className="mt-4 accordion-item">
            <h2 className="accordion-header" id="flush-headingFour">
            <button
                data-mdb-collapse-init
                className="accordion-button collapsed"
                type="button"
                data-mdb-target="#flush-collapseThree"
                aria-expanded="false"
                aria-controls="flush-collapseThree"
            >
                <span className="accordion-heading">Is my customer data safe with ConvoPilot?</span>
            </button>
            </h2>
            <div
            id="flush-collapseThree"
            className="accordion-collapse collapse"
            aria-labelledby="flush-headingThree"
            data-mdb-parent="#accordionFlushExample"
            >
            <div className="accordion-body">
                Anim pariatur cliche reprehenderit, enim eiusmod high life accusamus terry
                richardson ad squid. 3 wolf moon officia aute, non cupidatat skateboard dolor
                brunch. Food truck quinoa nesciunt laborum eiusmod. Brunch 3 wolf moon tempor,
                sunt aliqua put a bird on it squid single-origin coffee nulla assumenda shoreditch
                et. Nihil anim keffiyeh helvetica, craft beer labore wes anderson cred nesciunt
                sapiente ea proident. Ad vegan excepteur butcher vice lomo. Leggings occaecat
                craft beer farm-to-table, raw denim aesthetic synth nesciunt you probably haven't
                heard of them accusamus labore sustainable VHS.
            </div>
            </div>
        </div>

        <div data-aos="fade-up" data-aos-delay="200" className="mt-4 accordion-item">
            <h2 className="accordion-header" id="flush-headingFive">
            <button
                data-mdb-collapse-init
                className="accordion-button collapsed"
                type="button"
                data-mdb-target="#flush-collapseThree"
                aria-expanded="false"
                aria-controls="flush-collapseThree"
            >
                <span className="accordion-heading">Does ConvoPilot work on mobile devices?</span>
            </button>
            </h2>
            <div
            id="flush-collapseThree"
            className="accordion-collapse collapse"
            aria-labelledby="flush-headingThree"
            data-mdb-parent="#accordionFlushExample"
            >
            <div className="accordion-body">
                Anim pariatur cliche reprehenderit, enim eiusmod high life accusamus terry
                richardson ad squid. 3 wolf moon officia aute, non cupidatat skateboard dolor
                brunch. Food truck quinoa nesciunt laborum eiusmod. Brunch 3 wolf moon tempor,
                sunt aliqua put a bird on it squid single-origin coffee nulla assumenda shoreditch
                et. Nihil anim keffiyeh helvetica, craft beer labore wes anderson cred nesciunt
                sapiente ea proident. Ad vegan excepteur butcher vice lomo. Leggings occaecat
                craft beer farm-to-table, raw denim aesthetic synth nesciunt you probably haven't
                heard of them accusamus labore sustainable VHS.
            </div>
            </div>
        </div>

        <div data-aos="fade-up" data-aos-delay="200" className="mt-4 accordion-item">
            <h2 className="accordion-header" id="flush-headingSix">
            <button
                data-mdb-collapse-init
                className="accordion-button collapsed"
                type="button"
                data-mdb-target="#flush-collapseThree"
                aria-expanded="false"
                aria-controls="flush-collapseThree"
            >
                <span className="accordion-heading">Do I need coding knowledge to set it up?</span>
            </button>
            </h2>
            <div
            id="flush-collapseThree"
            className="accordion-collapse collapse"
            aria-labelledby="flush-headingThree"
            data-mdb-parent="#accordionFlushExample"
            >
            <div className="accordion-body">
                Anim pariatur cliche reprehenderit, enim eiusmod high life accusamus terry
                richardson ad squid. 3 wolf moon officia aute, non cupidatat skateboard dolor
                brunch. Food truck quinoa nesciunt laborum eiusmod. Brunch 3 wolf moon tempor,
                sunt aliqua put a bird on it squid single-origin coffee nulla assumenda shoreditch
                et. Nihil anim keffiyeh helvetica, craft beer labore wes anderson cred nesciunt
                sapiente ea proident. Ad vegan excepteur butcher vice lomo. Leggings occaecat
                craft beer farm-to-table, raw denim aesthetic synth nesciunt you probably haven't
                heard of them accusamus labore sustainable VHS.
            </div>
            </div>
        </div>

        </div>

        </div>
      </>
    );
  };

export default FAQs;