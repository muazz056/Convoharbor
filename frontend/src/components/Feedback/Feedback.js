import "./Feedback.css";
import SimpleLoader from '../common/SimpleLoader';
import React, { useEffect, useState } from 'react';
import AOS from 'aos';
import 'aos/dist/aos.css';

const Feedback = () => {
  const [loading, setLoading] = useState(true);
  const [feedbacks, setFeedbacks] = useState([]);
  const [stats, setStats] = useState(null);
  const [chatbots, setChatbots] = useState([]);
  const [selectedChatbot, setSelectedChatbot] = useState('');
  const [selectedRating, setSelectedRating] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState(null);

  const getAuthHeaders = () => {
    const token = localStorage.getItem('authToken');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  };

  useEffect(() => {
    AOS.init({ duration: 800, easing: 'ease-in-out', once: true });
    loadChatbots();
  }, []);

  useEffect(() => {
    loadFeedback();
    loadStats();
  }, [selectedChatbot, selectedRating, page]);

  const loadChatbots = async () => {
    try {
      const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
      const res = await fetch(`${baseURL}/chatbots?page=1&per_page=100`, {
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setChatbots(data.chatbots || []);
      }
    } catch (e) {
      console.error('Failed to load chatbots:', e);
    }
  };

  const loadFeedback = async () => {
    try {
      setLoading(true);
      setError(null);
      const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
      let url = `${baseURL}/conversations/feedback?page=${page}&per_page=12`;
      if (selectedChatbot) url += `&chatbot_id=${selectedChatbot}`;
      if (selectedRating) {
        url += `&min_rating=${selectedRating}&max_rating=${selectedRating}`;
      }

      const res = await fetch(url, { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        setFeedbacks(data.data.feedbacks || []);
        setTotalPages(data.data.pages || 1);
        setTotal(data.data.total || 0);
      } else {
        setError('Failed to load feedback');
      }
    } catch (e) {
      console.error('Failed to load feedback:', e);
      setError('Failed to load feedback');
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
      let url = `${baseURL}/conversations/feedback/stats`;
      if (selectedChatbot) url += `&chatbot_id=${selectedChatbot}`;

      const res = await fetch(url, { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        setStats(data.data);
      }
    } catch (e) {
      console.error('Failed to load stats:', e);
    }
  };

  const renderStars = (rating, size = 'normal') => {
    return (
      <div className={`feedback-stars ${size}`}>
        {[1, 2, 3, 4, 5].map(star => (
          <span key={star} className={`feedback-star ${star <= rating ? 'filled' : ''}`}>
            ★
          </span>
        ))}
      </div>
    );
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getRatingLabel = (rating) => {
    const labels = { 1: 'Poor', 2: 'Fair', 3: 'Good', 4: 'Great', 5: 'Excellent' };
    return labels[rating] || '';
  };

  const getRatingColor = (rating) => {
    const colors = { 5: '#10b981', 4: '#22c55e', 3: '#fbbf24', 2: '#f97316', 1: '#ef4444' };
    return colors[rating] || '#94a3b8';
  };

  const maxDistribution = stats ? Math.max(...Object.values(stats.rating_distribution || {}), 1) : 1;

  return (
    <div className="page" id="feedback" data-aos="fade-up" data-aos-delay="200">
      <div className="page-header">
        <h1 className="page-title">Customer Feedback</h1>
        <p className="page-subtitle">View all ratings and feedback from your users</p>
      </div>

      {loading && <SimpleLoader message="Loading feedback..." />}

      {!loading && error && (
        <div className="analytics-error">
          <p>⚠️ {error}</p>
          <button onClick={loadFeedback}>Retry</button>
        </div>
      )}

      {!loading && !error && (
        <>
          {/* Filters at top */}
          <div className="feedback-filters" data-aos="fade-up" data-aos-delay="100">
            <select
              className="feedback-filter-select"
              value={selectedChatbot}
              onChange={(e) => { setSelectedChatbot(e.target.value); setPage(1); }}
            >
              <option value="">All Chatbots</option>
              {chatbots.map(bot => (
                <option key={bot.id} value={bot.id}>{bot.name}</option>
              ))}
            </select>
            <select
              className="feedback-filter-select"
              value={selectedRating}
              onChange={(e) => { setSelectedRating(e.target.value); setPage(1); }}
            >
              <option value="">All Ratings</option>
              <option value="5">5 Stars</option>
              <option value="4">4 Stars</option>
              <option value="3">3 Stars</option>
              <option value="2">2 Stars</option>
              <option value="1">1 Star</option>
            </select>
            <div className="feedback-total-count">
              {total} rating{total !== 1 ? 's' : ''}
            </div>
          </div>

          {/* Stats Cards */}
          {stats && (
            <div className="feedback-stats-row" data-aos="fade-up" data-aos-delay="100">
              <div className="feedback-stat-card">
                <div className="feedback-stat-icon">⭐</div>
                <div className="feedback-stat-value">{stats.total_ratings}</div>
                <div className="feedback-stat-label">Total Ratings</div>
              </div>
              <div className="feedback-stat-card">
                <div className="feedback-stat-icon">📊</div>
                <div className="feedback-stat-value">{stats.avg_rating.toFixed(1)}</div>
                <div className="feedback-stat-label">Average Rating</div>
              </div>
              <div className="feedback-stat-card">
                <div className="feedback-stat-icon">💬</div>
                <div className="feedback-stat-value">{stats.total_feedbacks}</div>
                <div className="feedback-stat-label">Written Feedbacks</div>
              </div>
              <div className="feedback-stat-card">
                <div className="feedback-stat-icon">📈</div>
                <div className="feedback-stat-value">{stats.satisfaction_rate}%</div>
                <div className="feedback-stat-label">Satisfaction Rate</div>
              </div>
            </div>
          )}

          {/* Rating Distribution */}
          {stats && stats.rating_distribution && (
            <div className="feedback-distribution-card" data-aos="fade-up" data-aos-delay="150">
              <h3 className="distribution-title">Rating Distribution</h3>
              <div className="distribution-bars">
                {[5, 4, 3, 2, 1].map(star => {
                  const count = stats.rating_distribution[String(star)] || 0;
                  const percentage = total > 0 ? (count / total * 100) : 0;
                  const barWidth = total > 0 ? Math.max((count / maxDistribution) * 100, 3) : 3;
                  return (
                    <div key={star} className="distribution-row">
                      <span className="distribution-label">{star} ★</span>
                      <div className="distribution-bar-track">
                        <div
                          className="distribution-bar-fill"
                          style={{
                            width: `${barWidth}%`,
                            background: `linear-gradient(90deg, ${getRatingColor(star)}, ${getRatingColor(star)}dd)`
                          }}
                        />
                      </div>
                      <span className="distribution-count">{count}</span>
                      <span className="distribution-percent">{percentage.toFixed(0)}%</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Feedback List */}
          <div className="feedback-list" data-aos="fade-up" data-aos-delay="250">
            {feedbacks.length === 0 ? (
              <div className="feedback-empty">
                <div className="feedback-empty-icon">📭</div>
                <h3>No feedback yet</h3>
                <p>Ratings will appear here once users start rating conversations.</p>
              </div>
            ) : (
              feedbacks.map(fb => (
                <div key={fb.id} className="feedback-card">
                  <div className="feedback-card-header">
                    <div className="feedback-card-rating">
                      {renderStars(fb.rating)}
                      <span className="feedback-card-rating-label">{getRatingLabel(fb.rating)}</span>
                    </div>
                    <div className="feedback-card-meta">
                      <span className="feedback-card-platform">{fb.source_platform || 'web'}</span>
                      <span className="feedback-card-date">{formatDate(fb.created_at)}</span>
                    </div>
                  </div>
                  {fb.feedback_text && (
                    <div className="feedback-card-text">{fb.feedback_text}</div>
                  )}
                  <div className="feedback-card-footer">
                    {fb.chatbot && (
                      <span className="feedback-card-chatbot">🤖 {fb.chatbot.name}</span>
                    )}
                    <span className="feedback-card-lang">🌐 {fb.language || 'en'}</span>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="feedback-pagination">
              <button
                className="feedback-page-btn"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                ← Previous
              </button>
              <span className="feedback-page-info">Page {page} of {totalPages}</span>
              <button
                className="feedback-page-btn"
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default Feedback;
