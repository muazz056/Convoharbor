import "./Analytics.css";
import SimpleLoader from '../common/SimpleLoader';
import React, { useEffect, useRef, useState } from 'react';
import Chart from 'chart.js/auto';
import AOS from 'aos';
import 'aos/dist/aos.css';
import analyticsService from '../../services/analytics.service';

const Analytics = () => {
  const [loading, setLoading] = useState(true);
  const [analyticsData, setAnalyticsData] = useState(null);
  const [timeseriesData, setTimeseriesData] = useState(null);
  const [performanceData, setPerformanceData] = useState(null);
  const [selectedDays, setSelectedDays] = useState(7);
  const [error, setError] = useState(null);

  const dailyRef = useRef(null);
  const satisfactionRef = useRef(null);
  const responseRef = useRef(null);
  const topicsRef = useRef(null);

  // Chart instances to track for cleanup
  const chartRefs = useRef({});

  useEffect(() => {
    AOS.init({
      duration: 800,
      easing: 'ease-in-out',
      once: true,
    });
  }, []);

  // Load analytics data
  useEffect(() => {
    const loadAnalyticsData = async () => {
      try {
        setLoading(true);
        setError(null);

        const [overview, timeseries, performance] = await Promise.all([
          analyticsService.getOverview({ days: selectedDays }),
          analyticsService.getTimeseries({ days: selectedDays, granularity: 'day' }),
          analyticsService.getPerformance({ days: selectedDays })
        ]);

        console.log('📊 Analytics: Overview data received:', overview.data);
        console.log('📊 Analytics: Timeseries data:', timeseries.data);
        console.log('📊 Analytics: Response times:', timeseries.data?.response_times);
        
        setAnalyticsData(overview.data);
        setTimeseriesData(timeseries.data);
        setPerformanceData(performance.data);
      } catch (error) {
        console.error('Error loading analytics:', error);
        setError('Failed to load analytics data');
      } finally {
        setLoading(false);
      }
    };

    loadAnalyticsData();
  }, [selectedDays]);

  // Create charts when data is loaded
  useEffect(() => {
    if (!analyticsData || !timeseriesData || !performanceData || loading) {
      return;
    }

    // Cleanup existing charts
    Object.values(chartRefs.current).forEach(chart => {
      if (chart) chart.destroy();
    });
    chartRefs.current = {};

    // Conversations over time chart
    if (dailyRef.current) {
      const conversationsChart = analyticsService.formatTimeseriesForChart(
        timeseriesData.conversations, 
        'Conversations'
      );
      
      chartRefs.current.daily = new Chart(dailyRef.current, {
        type: 'line',
        data: conversationsChart,
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: {
              beginAtZero: true,
              title: {
                display: true,
                text: 'Number of Conversations'
              }
            }
          }
        }
      });
    }

    // Satisfaction rate by chatbot
    if (satisfactionRef.current && analyticsData.top_chatbots.length > 0) {
      const satisfactionChart = analyticsService.formatBarChartData(
        analyticsData.top_chatbots.map(bot => ({
          name: bot.name,
          satisfaction: bot.satisfaction_rate || 0
        })),
        'name',
        'satisfaction',
        'Satisfaction %'
      );

      chartRefs.current.satisfaction = new Chart(satisfactionRef.current, {
        type: 'bar',
        data: satisfactionChart,
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: {
              beginAtZero: true,
              max: 100,
              title: {
                display: true,
                text: 'Satisfaction Rate (%)'
              }
            }
          }
        }
      });
    }

    // Response times over time
    if (responseRef.current) {
      const responseChart = analyticsService.formatTimeseriesForChart(
        timeseriesData.response_times || [],
        'Avg Response (s)'
      );

      chartRefs.current.response = new Chart(responseRef.current, {
        type: 'line',
        data: {
          ...responseChart,
          datasets: [{
            ...responseChart.datasets[0],
            borderColor: '#f43f5e',
            backgroundColor: 'rgba(244, 63, 94, 0.1)',
            fill: true,
            tension: 0.4,
            pointRadius: 4,
            pointHoverRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: {
              beginAtZero: true,
              title: {
                display: true,
                text: 'Response Time (seconds)'
              }
            },
            x: {
              title: {
                display: true,
                text: 'Date'
              }
            }
          },
          plugins: {
            tooltip: {
              callbacks: {
                label: (context) => {
                  return `Response Time: ${context.parsed.y.toFixed(2)}s`;
                }
              }
            }
          }
        }
      });
    }

    // Platform distribution pie chart
    if (topicsRef.current && analyticsData.platforms.length > 0) {
      const platformChart = analyticsService.formatPieChartData(
        analyticsData.platforms,
        'platform',
        'count'
      );

      chartRefs.current.topics = new Chart(topicsRef.current, {
        type: 'pie',
        data: platformChart,
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'right'
            }
          }
        }
      });
    }

    // Cleanup function
    return () => {
      Object.values(chartRefs.current).forEach(chart => {
        if (chart) chart.destroy();
      });
    };
  }, [analyticsData, timeseriesData, performanceData, loading]);


  return (
    <>
        <div className="page" id="analytics" data-aos="fade-up" data-aos-delay="200">
          <div className="page-header">
              <h1 className="page-title">Analytics</h1>
              <p className="page-subtitle">Analyze your chatbots performance</p>
              
              {/* Time period selector */}
              <div className="analytics-controls">
                <div className="time-selector">
                  <button 
                    className={`time-btn ${selectedDays === 7 ? 'active' : ''}`}
                    onClick={() => setSelectedDays(7)}
                  >
                    7 days
                  </button>
                  <button 
                    className={`time-btn ${selectedDays === 30 ? 'active' : ''}`}
                    onClick={() => setSelectedDays(30)}
                  >
                    30 days
                  </button>
                  <button 
                    className={`time-btn ${selectedDays === 90 ? 'active' : ''}`}
                    onClick={() => setSelectedDays(90)}
                  >
                    90 days
                  </button>
                </div>
              </div>
          </div>

          {/* Loading state */}
          {loading && (
            <SimpleLoader message="Loading analytics data..." />
          )}

          {/* Error state */}
          {error && (
            <div className="analytics-error">
              <p>⚠️ {error}</p>
              <button onClick={() => window.location.reload()}>Retry</button>
            </div>
          )}

          {/* Charts */}
          {!loading && !error && (
            <div className="analytics-grid">
              <div className="anly-chart-container">
                <div className="chart-header">
                  <h3 className="chart-title">Conversations per day</h3>
                  <p className="chart-subtitle">Last {selectedDays} days</p>
                </div>
                <div className="chart-wrapper">
                  <canvas ref={dailyRef}></canvas>
                </div>
              </div>

              <div className="anly-chart-container">
                <div className="chart-header">
                  <h3 className="chart-title">Satisfaction rate</h3>
                  <p className="chart-subtitle">By chatbot</p>
                </div>
                <div className="chart-wrapper">
                  <canvas ref={satisfactionRef}></canvas>
                </div>
              </div>

              <div className="anly-chart-container">
                <div className="chart-header">
                  <h3 className="chart-title">Average response time</h3>
                  <p className="chart-subtitle">In seconds</p>
                </div>
                <div className="chart-wrapper">
                  <canvas ref={responseRef}></canvas>
                </div>
              </div>

              <div className="anly-chart-container">
                <div className="chart-header">
                  <h3 className="chart-title">Platform distribution</h3>
                  <p className="chart-subtitle">Conversation sources</p>
                </div>
                <div className="chart-wrapper d-flex justify-content-center">
                  <canvas ref={topicsRef}></canvas>
                </div>
              </div>
            </div>
          )}

          {/* Analytics Summary Cards */}
          {!loading && !error && analyticsData && (
            <div className="analytics-summary" data-aos="fade-up" data-aos-delay="400">
              <h2>Summary</h2>
              <div className="summary-grid">
                <div className="summary-card">
                  <h3>Total Conversations</h3>
                  <div className="metric-value">{analyticsData.conversations.total}</div>
                  <div className="metric-detail">
                    {analyticsData.conversations.active} active, {analyticsData.conversations.inactive} inactive
                  </div>
                </div>
                
                <div className="summary-card">
                  <h3>Total Messages</h3>
                  <div className="metric-value">{analyticsData.messages.total}</div>
                  <div className="metric-detail">
                    {analyticsData.messages.avg_per_conversation} avg per conversation
                  </div>
                </div>
                
                <div className="summary-card">
                  <h3>Avg Response Time</h3>
                  <div className="metric-value">{analyticsData.performance.avg_response_time}s</div>
                  <div className="metric-detail">
                    Satisfaction: {Math.round(analyticsData.performance.satisfaction_rate || 0)}%
                  </div>
                </div>
                
                <div className="summary-card">
                  <h3>Top Chatbot</h3>
                  <div className="metric-value">
                    {analyticsData.top_chatbots[0]?.name || 'N/A'}
                  </div>
                  <div className="metric-detail">
                    {analyticsData.top_chatbots[0]?.message_count || 0} messages
                  </div>
                </div>
              </div>
            </div>
          )}
          </div>
    </>
  );
};

export default Analytics;