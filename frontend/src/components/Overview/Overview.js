import "./Overview.css";
import SimpleLoader from '../common/SimpleLoader';
import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import Chart from 'chart.js/auto';

import AOS from 'aos';
import 'aos/dist/aos.css';
import analyticsService from '../../services/analytics.service';
import { chatbotService } from '../../services/chatbot.service';

const Overview = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [overviewData, setOverviewData] = useState(null);
  const [chatbots, setChatbots] = useState([]);
  const [error, setError] = useState(null);
  useEffect(() => {
    AOS.init({
      duration: 800, // animation duration in ms
      easing: 'ease-in-out', // animation easing
      once: true, // animate only once
    });
  }, []);

  // Load overview data
  useEffect(() => {
    const loadOverviewData = async () => {
      try {
        setLoading(true);
        setError(null);

        const [analytics, chatbotsData] = await Promise.all([
          analyticsService.getOverview({ days: 7, _t: Date.now() }),
          chatbotService.getChatbots()
        ]);

        console.log('📊 Analytics data received:', analytics.data);
        console.log('📊 Satisfaction rate from API:', analytics.data?.performance?.satisfaction_rate);
        console.log('📊 Performance object:', analytics.data?.performance);
        console.log('📊 Feedback object:', analytics.data?.feedback);
        console.log('📊 Top chatbots:', analytics.data?.top_chatbots);
        
        setOverviewData(analytics.data);
        setChatbots(chatbotsData.chatbots || []);
      } catch (error) {
        console.error('Error loading overview:', error);
        setError('Failed to load dashboard data');
      } finally {
        setLoading(false);
      }
    };

    loadOverviewData();
  }, []);

  // Chart reference for cleanup
  const chartRef = React.useRef(null);
  const resizeObserverRef = React.useRef(null);

  // Create chart when data is available
  useEffect(() => {
    if (loading) return;
    
    const initializeChart = async () => {
      console.log('🔍 DEBUG: Chart initialization started at zoom level:', window.devicePixelRatio);
      const canvas = document.getElementById('conversationsChart');
      if (!canvas) {
        console.warn('📊 Chart canvas not found');
        return;
      }
      console.log('🔍 DEBUG: Canvas found:', canvas);
      
      const container = canvas.parentElement;
      if (!container || container.offsetWidth === 0 || container.offsetHeight === 0) {
        console.warn('📊 Chart container has no dimensions, retrying...');
        setTimeout(initializeChart, 100);
        return;
      }
      
      console.log('📊 Container dimensions:', container.offsetWidth, 'x', container.offsetHeight);
      
      const ctx = canvas.getContext('2d');

      // Destroy existing chart if it exists
      if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
      }

      try {
    // Get timeseries data for chart
        console.log('📊 Fetching timeseries data...');
        const timeseries = await analyticsService.getTimeseries({ days: 7, granularity: 'day' });
        console.log('📊 Timeseries data received:', timeseries);
        
        let chartData;
        
        if (!timeseries || !timeseries.data || !timeseries.data.conversations || timeseries.data.conversations.length === 0) {
          console.warn('No timeseries data available, creating sample data');
          // Create chart with sample data to show the chart is working
          chartData = {
            labels: ['Day 1', 'Day 2', 'Day 3', 'Day 4', 'Day 5', 'Day 6', 'Day 7'],
            datasets: [{
              label: 'Conversations',
              data: [0, 1, 0, 2, 1, 0, 1],
              borderColor: '#7c3aed',
              backgroundColor: 'rgba(124, 58, 237, 0.1)',
              fill: true,
              tension: 0.4
            }]
          };
        } else {
          chartData = analyticsService.formatTimeseriesForChart(
          timeseries.data.conversations,
          'Conversations'
        );

          console.log('📊 Formatted chart data:', chartData);
          
          // Ensure we have valid data structure
          if (!chartData || !chartData.datasets || chartData.datasets.length === 0) {
            console.warn('Invalid chart data structure, using fallback');
            chartData = {
              labels: ['No Data'],
            datasets: [{
                label: 'Conversations',
                data: [0],
              borderColor: '#7c3aed',
              backgroundColor: 'rgba(124, 58, 237, 0.1)',
              fill: true
            }]
            };
          } else {
            // Ensure proper styling for existing data
            chartData.datasets[0] = {
              ...chartData.datasets[0],
              borderColor: '#7c3aed',
              backgroundColor: 'rgba(124, 58, 237, 0.1)',
              fill: true,
              tension: 0.4
            };
          }
        }

        // Create the chart with improved responsive options
        chartRef.current = new Chart(ctx, {
          type: 'line',
          data: chartData,
          options: {
            responsive: true,
            maintainAspectRatio: false,
            resizeDelay: 0,
            animation: {
              duration: 750,
              easing: 'easeInOutQuart'
            },
            layout: {
              padding: {
                top: 10,
                bottom: 10,
                left: 10,
                right: 10
              }
            },
            plugins: {
              legend: {
                display: true,
                position: 'top'
              }
            },
            scales: {
              y: {
                beginAtZero: true,
                grid: {
                  color: 'rgba(0, 0, 0, 0.1)'
                },
                ticks: {
                  precision: 0
                }
              },
              x: {
                grid: {
                  color: 'rgba(0, 0, 0, 0.1)'
                }
              }
            },
            interaction: {
              intersect: false,
              mode: 'index'
            },
            onResize: (chart, size) => {
              console.log('📊 Chart resized to:', size.width, 'x', size.height);
            }
          }
        });
        
        console.log('📊 Chart created successfully');
        
        // Set up ResizeObserver to handle container size changes
        if (window.ResizeObserver && container) {
          resizeObserverRef.current = new ResizeObserver((entries) => {
            for (const entry of entries) {
              if (chartRef.current && entry.contentRect.width > 0 && entry.contentRect.height > 0) {
                console.log('📊 Container resized, updating chart...');
                // Use requestAnimationFrame to ensure smooth resizing
                requestAnimationFrame(() => {
                  if (chartRef.current) {
                    chartRef.current.resize();
                  }
                });
              }
            }
          });
          resizeObserverRef.current.observe(container);
        }
        
        // Also listen for window resize as fallback
        const handleWindowResize = () => {
          if (chartRef.current) {
            requestAnimationFrame(() => {
              if (chartRef.current) {
                chartRef.current.resize();
              }
            });
          }
        };
        
        window.addEventListener('resize', handleWindowResize);
        
        // Store the cleanup function for window listener
        chartRef.current._windowResizeCleanup = () => {
          window.removeEventListener('resize', handleWindowResize);
        };
        
      } catch (error) {
        console.error('📊 Error loading chart data:', error);
        // Create error state chart
        const errorData = {
          labels: ['Error'],
          datasets: [{
            label: 'Failed to load data',
            data: [0],
            borderColor: '#ef4444',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            fill: true
          }]
        };
        
        chartRef.current = new Chart(ctx, {
          type: 'line',
          data: errorData,
          options: {
            responsive: true,
            maintainAspectRatio: false
          }
        });
      }
    };
    
    // Start the initialization process with a longer delay to ensure layout is ready
    const timeoutId = setTimeout(initializeChart, 500);

    // Cleanup function
    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      if (resizeObserverRef.current) {
        resizeObserverRef.current.disconnect();
        resizeObserverRef.current = null;
      }
      if (chartRef.current) {
        // Clean up window resize listener if it exists
        if (chartRef.current._windowResizeCleanup) {
          chartRef.current._windowResizeCleanup();
        }
        chartRef.current.destroy();
        chartRef.current = null;
      }
    };
  }, [loading, overviewData]); // Reinitialize when data loads

    return (
        <div className="container mt-5">
                  <div className="page-header">
            <h1 className="overview-page-title">Dashboard</h1>
            <p className="page-subtitle">Welcome! Here's an overview of your chatbots today</p>
        </div>

        {/* Loading state */}
        {loading && (
          <SimpleLoader message="Loading dashboard..." />
        )}

        {/* Error state (temporarily disabled) */}
        {/* Debug info (temporarily disabled) */}

        {/* Metrics Cards */}
        {!loading && !error && overviewData && (
          <div className="row g-4 px-1" data-aos="fade-up" data-aos-delay="200">
            <div className="col-md-6 col-xl-3">
              <div className="overview-metric-card">
                <div className="metric-header">
                  <div className="metric-info">
                    <div className="overview-metric-title">Active Chatbots</div>
                    <div className="overview-metric-value">{chatbots.length || 0}</div>
                    <div className="metric-change positive">
                      <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                        <path d="M8 4l4 4H4l4-4z" />
                      </svg>
                      <span>↑</span>
                    </div>
                  </div>
                  <div className="metric-icon primary">🤖</div>
                </div>
              </div>
            </div>

            <div className="col-md-6 col-xl-3">
              <div className="overview-metric-card">
                <div className="metric-header">
                  <div className="metric-info">
                    <div className="overview-metric-title">Conversations</div>
                    <div className="overview-metric-value">{overviewData?.conversations?.total?.toLocaleString() || '0'}</div>
                    <div className="metric-change positive">
                      <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                        <path d="M8 4l4 4H4l4-4z" />
                      </svg>
                      <span>↑</span>
                    </div>
                  </div>
                  <div className="metric-icon success">💬</div>
                </div>
              </div>
            </div>

            <div className="col-md-6 col-xl-3">
              <div className="overview-metric-card">
                <div className="metric-header">
                  <div className="metric-info">
                    <div className="overview-metric-title">Total Messages</div>
                    <div className="overview-metric-value">{overviewData?.messages?.total?.toLocaleString() || '0'}</div>
                    <div className="metric-change positive">
                      <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                        <path d="M8 4l4 4H4l4-4z" />
                      </svg>
                      <span>↑</span>
                    </div>
                  </div>
                  <div className="metric-icon warning">💬</div>
                </div>
              </div>
            </div>

            <div className="col-md-6 col-xl-3">
              <div className="overview-metric-card">
                <div className="metric-header">
                  <div className="metric-info">
                    <div className="overview-metric-title">Satisfaction Rate</div>
                    <div className="overview-metric-value">
                      {Math.round(overviewData?.performance?.satisfaction_rate ?? overviewData?.feedback?.satisfaction_rate ?? 0)}%
                    </div>
                    <div className="metric-change positive">
                      <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                        <path d="M8 4l4 4H4l4-4z" />
                      </svg>
                      <span>↑</span>
                    </div>
                  </div>
                  <div className="metric-icon success">⭐</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Chart Section - Always render when not loading/error */}
        {!loading && !error && (
          <div className="chart-container mx-3" data-aos="fade-up" data-aos-delay="200">
            <div className="chart-header">
              <h2 className="chart-title">Conversation Activity</h2>
              <div className="chart-actions">
                <button className="chart-tab active">7 days</button>
                <button className="chart-tab">30 days</button>
                <button className="chart-tab">90 days</button>
              </div>
            </div>
            <div className="chart-wrapper">
              <canvas 
                id="conversationsChart" 
                width="400" 
                height="300"
                style={{ display: 'block', width: '100%', height: '300px' }}
              ></canvas>
              {!overviewData && (
                <div style={{ 
                  position: 'absolute', 
                  top: '50%', 
                  left: '50%', 
                  transform: 'translate(-50%, -50%)',
                  color: '#666',
                  fontSize: '14px'
                }}>
                  Loading chart data...
                </div>
              )}
            </div>
          </div>
        )}

        <div className="section-spacer"></div>
        {!loading && !error && (
          <div className="overview-section-card mx-3" data-aos="fade-up" data-aos-delay="250">
            <div className="section-header">
              <h2 className="section-title">Your Chatbots</h2>
              
              <button 
                className="overview-primary-button" 
                onClick={() => navigate('/create-chatbot')}
              >
                <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" />
                </svg>
                <span>New Chatbot</span>
              </button>
            </div>
            
            <div className="chatbot-grid">
              {chatbots.length > 0 ? (
                chatbots.slice(0, 6).map((bot, index) => {
                  // Find stats for this bot from analytics
                  const botStats = overviewData?.top_chatbots?.find(b => b.id === bot.id);
                  const conversationCount = botStats?.message_count || 0;
                  const satisfaction = Math.round(botStats?.satisfaction_rate || 0); // Real satisfaction data, rounded
                  
                  return (
                    <div className="chatbot-card" key={bot.id}>
                      <div className="chatbot-status"></div>
                      <div className="chatbot-avatar">🤖</div>
                      <h3 className="chatbot-name">{bot.name}</h3>
                      <p className="chatbot-description">{bot.description || 'AI Assistant'}</p>
                      <div className="chatbot-stats">
                        <div className="chatbot-stat">
                          <span className="chatbot-stat-value">{conversationCount}</span>
                          <span className="chatbot-stat-label">Messages</span>
                        </div>
                        <div className="chatbot-stat">
                          <span className="chatbot-stat-value">{satisfaction}%</span>
                          <span className="chatbot-stat-label">Satisfaction</span>
                        </div>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="no-chatbots">
                  <p>No chatbots found. Create your first chatbot to get started!</p>
                </div>
              )}
            </div>
          </div>
        )}

          {/* End Overview content */}
        </div>
    );
  };

export default Overview;