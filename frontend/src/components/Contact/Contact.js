import React from 'react';

const Contact = () => {
  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Contact Us</h1>
          <p className="page-subtitle">Get in touch with our team</p>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 20, color: 'var(--text-primary)' }}>
            Send us a message
          </h2>
          <form onSubmit={e => e.preventDefault()}>
            <div className="form-group">
              <label className="form-label">Name</label>
              <input className="form-input" placeholder="Your name" />
            </div>
            <div className="form-group">
              <label className="form-label">Email</label>
              <input className="form-input" type="email" placeholder="you@example.com" />
            </div>
            <div className="form-group">
              <label className="form-label">Message</label>
              <textarea className="form-textarea" rows={5} placeholder="How can we help?" />
            </div>
            <button className="btn btn-primary">Send Message</button>
          </form>
        </div>

        <div className="card">
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 20, color: 'var(--text-primary)' }}>
            Contact Info
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <div>
              <div style={{ fontSize: 13, color: 'var(--text-tertiary)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Email</div>
              <div style={{ fontSize: 14, color: 'var(--text-primary)' }}>support@convoharbor.com</div>
            </div>
            <div>
              <div style={{ fontSize: 13, color: 'var(--text-tertiary)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Documentation</div>
              <div style={{ fontSize: 14, color: 'var(--text-primary)' }}>docs.convoharbor.com</div>
            </div>
            <div>
              <div style={{ fontSize: 13, color: 'var(--text-tertiary)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Response Time</div>
              <div style={{ fontSize: 14, color: 'var(--text-primary)' }}>Typically within 24 hours</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Contact;
