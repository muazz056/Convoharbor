import "./FAQs.css";
import { Collapse, initMDB } from 'mdb-ui-kit';
import React, { useEffect } from 'react';
import AOS from 'aos';
import 'aos/dist/aos.css';

const FAQs = () => {
    useEffect(() => {
        initMDB({ Collapse });
        AOS.init({ duration: 800, easing: 'ease-in-out', once: true });
    }, []);

    const faqs = [
        {
            q: `What is ${process.env.REACT_APP_APP_NAME || 'Convoharbor'}?`,
            a: `${process.env.REACT_APP_APP_NAME || 'Convoharbor'} is an AI-powered chatbot builder that lets you create intelligent chatbots trained on your own business data. Upload documents, FAQs, or website content, and the chatbot learns to answer customer questions accurately — 24/7.`
        },
        {
            q: `How does ${process.env.REACT_APP_APP_NAME || 'Convoharbor'} learn about my business?`,
            a: `You upload your business data — PDFs, text files, website URLs, or documents. ${process.env.REACT_APP_APP_NAME || 'Convoharbor'} processes and indexes your content using vector embeddings (Gemini AI), so the chatbot can retrieve and deliver accurate answers from your knowledge base.`
        },
        {
            q: `What AI models does ${process.env.REACT_APP_APP_NAME || 'Convoharbor'} use?`,
            a: `${process.env.REACT_APP_APP_NAME || 'Convoharbor'} uses Google Gemini for generating embeddings and responses, with optional OpenAI support. You can configure your own API keys and choose which model powers your chatbot.`
        },
        {
            q: `Can I integrate ${process.env.REACT_APP_APP_NAME || 'Convoharbor'} with my website?`,
            a: `Yes. ${process.env.REACT_APP_APP_NAME || 'Convoharbor'} provides a public chat widget you can embed on any website using a simple script tag. You can customize the widget's appearance, position, and behavior to match your brand.`
        },
        {
            q: `Is my customer data safe with ${process.env.REACT_APP_APP_NAME || 'Convoharbor'}?`,
            a: `Yes. Your data is stored securely in your own database. API keys are kept in environment variables. ${process.env.REACT_APP_APP_NAME || 'Convoharbor'} does not share your data with third parties — it's used solely to power your chatbot's responses.`
        },
        {
            q: `Do I need coding knowledge to set it up?`,
            a: `No. The entire setup is no-code. Upload your files, configure your chatbot settings through the dashboard, and deploy the widget with a single script tag. The platform handles embedding, vector search, and response generation automatically.`
        }
    ];

    return (
        <>
            <div className="accordion accordion-flush" id="accordionFlushExample">
                {faqs.map((faq, i) => (
                    <div key={i} data-aos="fade-up" data-aos-delay={i * 60} className="mt-3 accordion-item">
                        <h2 className="accordion-header" id={`flush-heading${i}`}>
                            <button
                                data-mdb-collapse-init
                                className="accordion-button collapsed"
                                type="button"
                                data-mdb-target={`#flush-collapse${i}`}
                                aria-expanded="false"
                                aria-controls={`flush-collapse${i}`}
                            >
                                <span className="accordion-heading">{faq.q}</span>
                            </button>
                        </h2>
                        <div
                            id={`flush-collapse${i}`}
                            className="accordion-collapse collapse"
                            aria-labelledby={`flush-heading${i}`}
                            data-mdb-parent="#accordionFlushExample"
                        >
                            <div className="accordion-body">{faq.a}</div>
                        </div>
                    </div>
                ))}
            </div>
        </>
    );
};

export default FAQs;
