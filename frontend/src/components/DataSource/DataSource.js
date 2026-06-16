import "./DataSource.css";
import SimpleLoader from '../common/SimpleLoader';
import AOS from 'aos';
import 'aos/dist/aos.css';
import { useEffect, useState, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { dataSourceService } from '../../services/datasource.service';
import { chatbotService } from '../../services/chatbot.service';
import { useAuth } from '../../contexts/AuthContext';
import { useWebSocket } from '../../contexts/WebSocketContext';

  const DataSource = () => {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const { hasPermission } = useAuth();
    const { socket, isConnected } = useWebSocket();
    
    const [dataSources, setDataSources] = useState([]);
    const [chatbots, setChatbots] = useState([]);
    const [selectedChatbot, setSelectedChatbot] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState({});
    const [showUrlInput, setShowUrlInput] = useState(false);
    const [crawlTab, setCrawlTab] = useState('specific'); // 'specific' | 'full'
    const [specificUrls, setSpecificUrls] = useState([{ url: '', depth: 'single' }]);
    const [fullUrl, setFullUrl] = useState('');
    const [crawling, setCrawling] = useState(false);
    const [crawlQueueIndex, setCrawlQueueIndex] = useState(-1);
    const [crawlQueueTotal, setCrawlQueueTotal] = useState(0);
    const [pageCountError, setPageCountError] = useState('');
    const [estimatingPageCount, setEstimatingPageCount] = useState(false);
    const [pollingSources, setPollingSources] = useState(new Set());
    const [crawlProgress, setCrawlProgress] = useState({}); // Track progress by data_source_id
    const [embeddingProgress, setEmbeddingProgress] = useState({}); // Rate-limit-aware progress by data_source_id
    const [countdowns, setCountdowns] = useState({}); // Countdown timers (seconds remaining) by data_source_id
    const [crawlLogs, setCrawlLogs] = useState({}); // Real-time logs by data_source_id

    const fileInputRef = useRef(null);

      useEffect(() => {
        AOS.init({
          duration: 800, // animation duration in ms
          easing: 'ease-in-out', // animation easing
          once: true, // animate only once
        });
      
      // Load chatbots and data sources
      loadChatbots();
      loadDataSources();
      
      // Check if specific chatbot is selected from URL
      const chatbotId = searchParams.get('chatbot_id');
      if (chatbotId) {
        setSelectedChatbot(parseInt(chatbotId));
      }
    }, [searchParams]);

    // Poll for processing status updates
    useEffect(() => {
      if (pollingSources.size === 0) return;

      const interval = setInterval(async () => {
        for (const sourceId of pollingSources) {
          try {
            const status = await dataSourceService.getDataSourceStatus(sourceId);
            if (status.status === 'completed') {
              setPollingSources(prev => {
                const newSet = new Set(prev);
                newSet.delete(sourceId);
                return newSet;
              });
              // Full load (with loading indicator) on completion
              await loadDataSources();
              setTimeout(() => navigate('/knowledge-base'), 1500);
              return;
            } else if (status.status === 'failed') {
              setPollingSources(prev => {
                const newSet = new Set(prev);
                newSet.delete(sourceId);
                return newSet;
              });
              await loadDataSources();
              return;
            }
          } catch (error) {
            console.error(`Error polling source ${sourceId}:`, error);
            // Remove stale source (e.g. 404 — deleted) so polling stops
            setPollingSources(prev => {
              const newSet = new Set(prev);
              newSet.delete(sourceId);
              return newSet;
            });
          }
        }
        // Silent refresh for meta_data updates (progress_message, etc.)
        await refreshDataSources();
      }, 3000);

      return () => clearInterval(interval);
    }, [pollingSources, navigate]);

    // WebSocket listeners for crawl updates
    useEffect(() => {
      if (!socket) return;

      console.log('🔌 DataSource: registering WebSocket listeners');

      // Listen for crawl progress updates
      const handleCrawlProgress = (data) => {
        console.log('📊 Crawl progress:', data);
        setCrawlProgress(prev => ({
          ...prev,
          [data.data_source_id]: {
            pages_crawled: data.pages_crawled,
            total_pages: data.total_pages,
            progress_percent: data.progress_percent,
            pages_failed: data.pages_failed
          }
        }));
      };

      // Listen for crawl completion
      const handleCrawlCompleted = (data) => {
        console.log('✅ Crawl completed:', data);
        setCrawlProgress(prev => {
          const newProgress = { ...prev };
          delete newProgress[data.data_source_id];
          return newProgress;
        });
        setCrawlLogs(prev => {
          const newLogs = { ...prev };
          delete newLogs[data.data_source_id];
          return newLogs;
        });
        loadDataSources();
        // Auto-redirect to knowledge base after short delay
        setTimeout(() => navigate('/knowledge-base'), 1500);
      };

      // Listen for crawl failure
      const handleCrawlFailed = (data) => {
        console.log('❌ Crawl failed:', data);
        setError(data.message || 'Web crawl failed');
        setCrawlProgress(prev => {
          const newProgress = { ...prev };
          delete newProgress[data.data_source_id];
          return newProgress;
        });
        setCrawlLogs(prev => {
          const newLogs = { ...prev };
          delete newLogs[data.data_source_id];
          return newLogs;
        });
        loadDataSources();
      };

      // Listen for embedding / data-source stage progress (rate-limit
      // aware). Emitted by the backend's _run_ai_processing thread on
      // every batch boundary and whenever the rate limiter has to wait.
      const handleDatasourceProgress = (data) => {
        const sid = data.data_source_id;
        if (sid == null) return;
        setEmbeddingProgress(prev => ({
          ...prev,
          [sid]: {
            stage: data.stage,
            total_chunks: data.total_chunks,
            chunks_embedded: data.chunks_embedded,
            total_batches: data.total_batches,
            current_batch: data.current_batch,
            provider: data.provider,
            rate_limit_per_minute: data.rate_limit_per_minute,
            rate_used: data.rate_used,
            rate_capacity: data.rate_capacity,
            wait_seconds: data.wait_seconds,
            error: data.error,
            updated_at: data.updated_at,
          },
        }));
        if (data.stage === 'completed' || data.stage === 'failed') {
          setCountdowns(prev => {
            const next = { ...prev };
            delete next[sid];
            return next;
          });
          if (data.stage === 'completed') {
            loadDataSources();
          } else if (data.stage === 'failed') {
            loadDataSources();
          }
        } else if (data.wait_seconds && data.wait_seconds > 0) {
          setCountdowns(prev => ({
            ...prev,
            [sid]: Math.ceil(data.wait_seconds),
          }));
        }
      };

      // Listen for crawl log events (real-time step-by-step logs)
      const handleCrawlLog = (data) => {
        const sid = data.data_source_id;
        if (sid == null) return;
        console.log('📝 Crawl log:', data);
        setCrawlLogs(prev => ({
          ...prev,
          [sid]: [
            ...(prev[sid] || []),
            {
              message: data.message,
              level: data.level,
              timestamp: data.timestamp
            }
          ]
        }));
      };

      socket.on('crawl_progress', handleCrawlProgress);
      socket.on('crawl_completed', handleCrawlCompleted);
      socket.on('crawl_failed', handleCrawlFailed);
      socket.on('datasource_progress', handleDatasourceProgress);
      socket.on('crawl_log', handleCrawlLog);

      return () => {
        socket.off('crawl_progress', handleCrawlProgress);
        socket.off('crawl_completed', handleCrawlCompleted);
        socket.off('crawl_failed', handleCrawlFailed);
        socket.off('datasource_progress', handleDatasourceProgress);
        socket.off('crawl_log', handleCrawlLog);
      };
    }, [socket, isConnected]);

    // Tick down the rate-limit countdown every second so the user sees
    // a live "resets in 32s" message while the embedding thread is
    // blocked waiting for a Gemini quota slot.
    useEffect(() => {
      const activeIds = Object.keys(countdowns).filter(id => (countdowns[id] || 0) > 0);
      if (activeIds.length === 0) return undefined;
      const tick = setInterval(() => {
        setCountdowns(prev => {
          const next = { ...prev };
          let changed = false;
          for (const id of activeIds) {
            const v = (prev[id] || 0) - 1;
            if (v <= 0) {
              delete next[id];
            } else {
              next[id] = v;
            }
            changed = true;
          }
          return changed ? next : prev;
        });
      }, 1000);
      return () => clearInterval(tick);
    }, [countdowns]);

    const loadChatbots = async () => {
      try {
        const response = await chatbotService.getChatbots({ per_page: 100 });
        setChatbots(response.chatbots || []);
      } catch (err) {
        console.error('Error loading chatbots:', err);
      }
    };

    const loadDataSources = async () => {
      try {
        setLoading(true);
        setError(null);
        
        const filters = { per_page: 500 };
        if (selectedChatbot) filters.chatbot_id = selectedChatbot;
        
        const response = await dataSourceService.getDataSources(filters);
        const allSources = response.data_sources || [];
        setDataSources(allSources.filter(s =>
          ['pending', 'processing', 'uploading', 'crawling', 'failed'].includes(s.status)
        ));
      } catch (err) {
        if (err.message === 'Authentication required') {
          window.location.href = '/login';
          return;
        }
        setError(err.message);
        console.error('Error loading data sources:', err);
      } finally {
        setLoading(false);
      }
    };

    // Silent refresh — does NOT set loading=true, avoids UI flicker
    const refreshDataSources = async () => {
      try {
        const filters = { per_page: 500 };
        if (selectedChatbot) filters.chatbot_id = selectedChatbot;
        const response = await dataSourceService.getDataSources(filters);
        const allSources = response.data_sources || [];
        setDataSources(allSources.filter(s =>
          ['pending', 'processing', 'uploading', 'crawling', 'failed'].includes(s.status)
        ));
      } catch (err) {
        // Silently ignore polling errors
      }
    };

    const handleFileSelect = async (event) => {
      const files = Array.from(event.target.files);
      if (files.length === 0) return;

      // Check if chatbot is selected
      if (!selectedChatbot) {
        setError('Please select a chatbot first before uploading documents');
        alert('⚠️ Please select a chatbot first\n\nYou must choose which chatbot should use these documents before uploading.');
        // Clear file input
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        return;
      }

      try {
        setUploading(true);
        setUploadProgress({});

        const onProgress = (fileIndex, percent, fileName) => {
          setUploadProgress(prev => ({
            ...prev,
            [fileIndex]: { fileName, percent }
          }));
        };

        const uploadOptions = {
          chatbot_id: selectedChatbot,
          description: `Training data for ${chatbots.find(c => c.id === selectedChatbot)?.name || 'chatbot'}`
        };
        
        const result = await dataSourceService.uploadFiles(files, uploadOptions, onProgress);
        
        // Refresh data sources list
        await refreshDataSources();
        
        // Clear file input
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        
        // Show message and start polling
        alert(`✅ Files uploaded! Processing started. You'll be redirected to Knowledge Base when done.`);
      } catch (err) {
        setError(err.message);
        console.error('Error uploading files:', err);
      } finally {
        setUploading(false);
        setUploadProgress({});
      }
    };

    const handleUrlCrawl = async () => {
      if (crawlTab === 'specific') {
        const validEntries = specificUrls.filter(u => u.url.trim());
        if (validEntries.length === 0) return;
        await crawlSpecificUrls(validEntries);
      } else {
        if (!fullUrl.trim()) return;
        await crawlFullSite(fullUrl.trim());
      }
    };

    const crawlSpecificUrls = async (entries) => {
      if (!selectedChatbot) {
        setError('Please select a chatbot first before crawling a website');
        alert('⚠️ Please select a chatbot first\n\nYou must choose which chatbot should use this content before crawling.');
        return;
      }

      try {
        setCrawling(true);
        setError(null);
        setCrawlQueueTotal(entries.length);
        setCrawlQueueIndex(0);

        for (let i = 0; i < entries.length; i++) {
          const { url, depth } = entries[i];
          setCrawlQueueIndex(i + 1);

          const crawlOptions = {
            chatbot_id: selectedChatbot,
            crawl_type: 'specific',
            depth: depth,
            description: `Web content for ${chatbots.find(c => c.id === selectedChatbot)?.name || 'chatbot'}`,
          };

          const result = await dataSourceService.crawlWebsite(url, crawlOptions);

          // Refresh sources list (silent, no loading flash)
          await refreshDataSources();

          if (result && result.data_source_id) {
            setPollingSources(prev => new Set([...prev, result.data_source_id]));
          }
        }

        setSpecificUrls([{ url: '', depth: 'single' }]);
        setShowUrlInput(false);
        setCrawlQueueIndex(-1);
        setCrawlQueueTotal(0);
      } catch (err) {
        setError(err.message);
        console.error('Error starting web crawl:', err);
      } finally {
        setCrawling(false);
      }
    };

    const crawlFullSite = async (url) => {
      if (!selectedChatbot) {
        setError('Please select a chatbot first before crawling a website');
        alert('⚠️ Please select a chatbot first\n\nYou must choose which chatbot should use this content before crawling.');
        return;
      }

      try {
        setCrawling(true);
        setError(null);
        setPageCountError('');
        setEstimatingPageCount(true);

        const crawlOptions = {
          chatbot_id: selectedChatbot,
          crawl_type: 'full',
          description: `Web content for ${chatbots.find(c => c.id === selectedChatbot)?.name || 'chatbot'}`,
        };

        const result = await dataSourceService.crawlWebsite(url, crawlOptions);

        await refreshDataSources();

        setEstimatingPageCount(false);
        setFullUrl('');
        setShowUrlInput(false);

        if (result && result.data_source_id) {
          setPollingSources(prev => new Set([...prev, result.data_source_id]));
        }
      } catch (err) {
        setEstimatingPageCount(false);
        const msg = err.message || '';
        // Check if it's a page limit error
        if (msg.toLowerCase().includes('page limit') || msg.toLowerCase().includes('250')) {
          setPageCountError(msg);
          alert(`⚠️ ${msg}`);
        } else {
          setError(msg);
        }
        console.error('Error starting web crawl:', err);
      } finally {
        setCrawling(false);
        setEstimatingPageCount(false);
      }
    };

    const addSpecificUrl = () => {
      setSpecificUrls(prev => [...prev, { url: '', depth: 'single' }]);
    };

    const removeSpecificUrl = (index) => {
      if (specificUrls.length <= 1) return;
      setSpecificUrls(prev => prev.filter((_, i) => i !== index));
    };

    const updateSpecificUrl = (index, value) => {
      setSpecificUrls(prev => {
        const next = [...prev];
        next[index] = { ...next[index], url: value };
        return next;
      });
    };

    const updateSpecificDepth = (index, depth) => {
      setSpecificUrls(prev => {
        const next = [...prev];
        next[index] = { ...next[index], depth };
        return next;
      });
    };

    const isValidRootUrl = (url) => {
      try {
        const u = new URL(url);
        const path = u.pathname.replace(/\/$/, '');
        return !path || path === '';
      } catch {
        return false;
      }
    };

    const DEPTH_INFO = {
      single: 'Scrape only this single page. Best for specific articles or documentation pages.',
      depth1: 'Scrape this page plus all directly linked pages under the same path (up to 20 pages). Good for guides with multiple sub-pages.',
      depth2: 'Scrape this page plus linked pages and their sub-links under the same path (up to 50 pages). Most thorough option for section-level crawling.',
    };

    const isFormValid = () => {
      if (!selectedChatbot) return false;
      if (crawlTab === 'specific') {
        return specificUrls.some(e => e.url.trim());
      }
      return fullUrl.trim() && isValidRootUrl(fullUrl.trim());
    };

    const getSourceIcon = (sourceType) => {
      const icons = {
        upload: '📄',
        crawl: '🌐',
        api: '🔗'
      };
      return icons[sourceType] || '📄';
    };

    const getStatusBadge = (status) => {
      const statusConfig = {
        pending: { class: 'status-pending', label: 'Pending', icon: '⏳' },
        processing: { class: 'status-processing', label: 'Processing', icon: '⚙️' },
        completed: { class: 'status-completed', label: 'Completed', icon: '✅' },
        failed: { class: 'status-failed', label: 'Failed', icon: '❌' }
      };
      
      const config = statusConfig[status] || { class: 'status-pending', label: status, icon: '⚪' };
      return (
        <span className={`status-badge ${config.class}`}>
          {config.icon} {config.label}
        </span>
      );
    };

    const formatDate = (dateString) => {
      if (!dateString) return 'N/A';
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    };

    return (
      <>
            <div className="page" id="training" data-aos="fade-up" data-aos-delay="200">
            <div className="page-header">
                <div className="header-content">
                  <h1 className="page-title">Training Data</h1>
                  <p className="page-subtitle">Manage data sources for your AI chatbots</p>
                </div>
              </div>

              {/* Filters and Controls */}
              <div className="controls-section">
                <div className="filter-group">
                  <label>Chatbot: <span className="required-indicator">*</span></label>
                  <select 
                    value={selectedChatbot || ''} 
                    onChange={(e) => {
                      setSelectedChatbot(e.target.value ? parseInt(e.target.value) : null);
                      loadDataSources();
                      // Clear any existing error when chatbot is selected
                      if (e.target.value && error?.includes('select a chatbot')) {
                        setError(null);
                      }
                    }}
                    className={`filter-select ${!selectedChatbot ? 'required-field' : ''}`}
                  >
                    <option value="">⚠️ Select a chatbot (required for uploads/crawling)</option>
                    {chatbots.map(bot => (
                      <option key={bot.id} value={bot.id}>
                        {bot.name}
                      </option>
                    ))}
                  </select>
                </div>

                <button 
                  onClick={loadDataSources}
                  className="refresh-button"
                  disabled={loading}
                >
                  🔄 Refresh
                </button>
            </div>

              {/* Error Message */}
              {error && (
                <div className="error-message">
                  <span>⚠️ {error}</span>
                  <button onClick={() => setError(null)} className="close-button">×</button>
                </div>
              )}

              {/* File Upload Zone */}
              {hasPermission('manage_chatbots') && (
                <>
                  <div 
                    className={`upload-zone ${uploading ? 'uploading' : ''}`}
                    onClick={() => !uploading && fileInputRef.current?.click()}
                  >
                    <div className="upload-icon">📁</div>
                    <h3 className="upload-title">
                      {uploading ? 'Uploading Files...' : 'Drop your files here'}
                    </h3>
                    <p className="upload-subtitle">
                      {uploading 
                        ? `Processing ${Object.keys(uploadProgress).length} files`
                        : 'or click to browse (PDF, TXT, DOCX supported)'
                      }
                    </p>
                    {selectedChatbot && (
                      <p className="chatbot-info">
                        📤 Uploading to: <strong>{chatbots.find(c => c.id === selectedChatbot)?.name}</strong>
                      </p>
                    )}
                  
                    {/* Upload Progress */}
                    {uploading && Object.entries(uploadProgress).map(([index, progress]) => (
                      <div key={index} className="upload-progress">
                        <div className="progress-info">
                          <span className="file-name">{progress.fileName}</span>
                          <span className="progress-percent">{Math.round(progress.percent)}%</span>
                        </div>
                        <div className="progress-bar">
                          <div 
                            className="progress-fill"
                            style={{ width: `${progress.percent}%` }}
                          ></div>
                        </div>
                      </div>
                    ))}

                    <input
                      ref={fileInputRef}
                      type="file"
                      style={{ display: "none" }}
                      multiple
                      accept=".pdf,.txt,.docx,.doc"
                      onChange={handleFileSelect}
                      disabled={uploading}
                    />
                  </div>
                  
                  {/* Add Website Button - Placed just before URL input */}
                  <div className="url-input-trigger">
                    <button 
                      onClick={() => setShowUrlInput(!showUrlInput)}
                      className="website-button"
                      disabled={!hasPermission('manage_chatbots')}
                    >
                      <span className="button-icon">🌐</span>
                      <span className="button-text">{showUrlInput ? 'Hide Website Form' : 'Add Website Content'}</span>
                      <span className="button-arrow">{showUrlInput ? '▲' : '▼'}</span>
                    </button>
                    <p className="button-hint">Extract content from any website URL</p>
                  </div>

                  {/* URL Input Section - Appears after button click */}
                  {showUrlInput && (
                    <div className="url-input-section">
                      <h3>🌐 Add Website Content</h3>

                      {/* Tab Switcher */}
                      <div className="crawl-tabs">
                        <button
                          className={`crawl-tab ${crawlTab === 'specific' ? 'active' : ''}`}
                          onClick={() => setCrawlTab('specific')}
                          disabled={crawling}
                        >
                          Specific Pages
                        </button>
                        <button
                          className={`crawl-tab ${crawlTab === 'full' ? 'active' : ''}`}
                          onClick={() => setCrawlTab('full')}
                          disabled={crawling}
                        >
                          Full Crawl
                        </button>
                      </div>

                      {/* ── Specific Pages Tab ──────────────────────── */}
                      {crawlTab === 'specific' && (
                        <div className="crawl-tab-content">
                          <div className="url-input-form">
                            <div className="url-input-list">
                              {specificUrls.map((entry, index) => (
                                <div key={index} className="specific-url-block">
                                  <div className="url-input-row">
                                    <input
                                      type="url"
                                      value={entry.url}
                                      onChange={(e) => updateSpecificUrl(index, e.target.value)}
                                      placeholder={selectedChatbot ? "https://example.com/docs/guide" : "Select a chatbot to enable crawling"}
                                      className="url-input"
                                      disabled={crawling || !selectedChatbot}
                                    />
                                    {specificUrls.length > 1 && (
                                      <button
                                        type="button"
                                        className="url-remove-btn"
                                        onClick={() => removeSpecificUrl(index)}
                                        disabled={crawling}
                                        title="Remove this URL"
                                      >
                                        ✕
                                      </button>
                                    )}
                                  </div>
                                  {/* Depth radio group */}
                                  <div className="depth-radio-group">
                                    {['single', 'depth1', 'depth2'].map(d => (
                                      <label key={d} className="depth-radio-label">
                                        <input
                                          type="radio"
                                          name={`depth-${index}`}
                                          value={d}
                                          checked={entry.depth === d}
                                          onChange={() => updateSpecificDepth(index, d)}
                                          disabled={crawling || !selectedChatbot}
                                        />
                                        <span className="depth-radio-text">
                                          {d === 'single' ? 'Single page' : d === 'depth1' ? 'Depth 1' : 'Depth 2'}
                                        </span>
                                        <span
                                          className="depth-info-icon"
                                          title={DEPTH_INFO[d]}
                                        >ℹ️</span>
                                      </label>
                                    ))}
                                  </div>
                                </div>
                              ))}
                            </div>
                            <div className="url-input-actions">
                              <button
                                type="button"
                                onClick={addSpecificUrl}
                                disabled={crawling || !selectedChatbot}
                                className="add-url-button"
                              >
                                + Add Another URL
                              </button>
                              <button 
                                onClick={handleUrlCrawl}
                                disabled={crawling || !isFormValid() || !selectedChatbot}
                                className="crawl-button"
                              >
                                {crawling ? (
                                  <span>🕷️ Crawling {crawlQueueIndex}/{crawlQueueTotal}...</span>
                                ) : (
                                  <span>🕷️ Start Crawl</span>
                                )}
                              </button>
                            </div>
                            {crawlQueueTotal > 1 && crawling && (
                              <div className="crawl-queue-progress">
                                <div className="crawl-queue-bar">
                                  <div
                                    className="crawl-queue-fill"
                                    style={{ width: `${(crawlQueueIndex / crawlQueueTotal) * 100}%` }}
                                  />
                                </div>
                                <span className="crawl-queue-text">
                                  Processing URL {crawlQueueIndex} of {crawlQueueTotal}
                                </span>
                              </div>
                            )}
                          </div>
                          <p className="help-text">
                            Enter one or more specific page URLs. Choose the crawl depth for each URL.
                          </p>
                          {!selectedChatbot && (
                            <p className="help-text required-text">
                              Please select a chatbot from the dropdown above to enable website crawling.
                            </p>
                          )}
                        </div>
                      )}

                      {/* ── Full Crawl Tab ──────────────────────────── */}
                      {crawlTab === 'full' && (
                        <div className="crawl-tab-content">
                          <div className="url-input-form">
                            <div className="url-input-row">
                              <input
                                type="url"
                                value={fullUrl}
                                onChange={(e) => {
                                  setFullUrl(e.target.value);
                                  setPageCountError('');
                                }}
                                placeholder={selectedChatbot ? "https://example.com" : "Select a chatbot to enable crawling"}
                                className={`url-input ${pageCountError ? 'input-error' : ''}`}
                                disabled={crawling || !selectedChatbot}
                              />
                            </div>
                            {estimatingPageCount && (
                              <div className="page-count-estimating">
                                🔍 Checking website page count...
                              </div>
                            )}
                            {pageCountError && (
                              <div className="page-count-error">
                                ⚠️ {pageCountError}
                              </div>
                            )}
                            {fullUrl.trim() && !isValidRootUrl(fullUrl.trim()) && (
                              <div className="url-validation-warning">
                                ℹ️ Full crawl works best with a root URL (e.g. https://example.com).
                                For specific paths, use the "Specific Pages" tab.
                              </div>
                            )}
                            <div className="url-input-actions">
                              <button 
                                onClick={handleUrlCrawl}
                                disabled={crawling || !isFormValid() || !selectedChatbot}
                                className="crawl-button full-crawl-btn"
                              >
                                {crawling ? (
                                  <span>🕷️ Crawling...</span>
                                ) : (
                                  <span>🕷️ Start Full Crawl</span>
                                )}
                              </button>
                            </div>
                            <div className="full-crawl-info">
                              <p>📋 Full crawl will scan the entire website and extract all pages (max 250 pages).</p>
                              <p>⏱️ This may take a few minutes depending on the website size.</p>
                            </div>
                          </div>
                          {!selectedChatbot && (
                            <p className="help-text required-text">
                              Please select a chatbot from the dropdown above to enable website crawling.
                            </p>
                          )}
                        </div>
                      )}

                    </div>
                  )}
                </>
              )}

              {/* Data Sources List */}
              {loading ? (
                <SimpleLoader message="Loading data sources..." />
              ) : dataSources.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-icon">📂</div>
                  <h3>No Data Sources Yet</h3>
                  <p>Upload files or add websites to start training your chatbots!</p>
                </div>
              ) : (
                <div className="source-list">
                  <div className="source-header">
                    <div className="source-count">
                      {dataSources.length} data source{dataSources.length !== 1 ? 's' : ''}
                      {selectedChatbot && ` for ${chatbots.find(c => c.id === selectedChatbot)?.name}`}
                </div>
                </div>

                  {dataSources.map(source => (
                    <div key={source.id} className="source-item">
                <div className="source-info">
                        <div className="source-icon">
                          {getSourceIcon(source.source_type)}
                        </div>
                    <div className="source-details">
                          <h4>{source.source_name}</h4>
                          <p className="source-meta">
                            ID: {source.id} • {source.source_type === 'upload' ? 'File Upload' : 'Web Crawl'} • 
                            Created {formatDate(source.created_at)}
                            {source.chatbot_id && chatbots.find(c => c.id === source.chatbot_id) && (
                              <> • For <strong>{chatbots.find(c => c.id === source.chatbot_id)?.name}</strong></>
                            )}
                          </p>
                          <div className="source-status-row">
                            {getStatusBadge(source.status)}
                            {source.metadata?.description && (
                              <span className="source-description">
                                {source.metadata.description}
                              </span>
                            )}
                            {pollingSources.has(source.id) && (
                              <span className="polling-indicator">🔄 Updating...</span>
                            )}
                          </div>
                          {source.status === 'failed' && source.metadata?.error && (
                            <div className="error-details">
                              ❌ Error: {source.metadata.error}
                            </div>
                          )}

                          {/* === RATE-LIMIT-AWARE EMBEDDING PROGRESS ===
                              Shown whenever the backend is actively processing
                              this source and we have a progress block (either
                              from the initial status response or a live
                              WebSocket update). Covers waiting-for-quota,
                              in-flight batches, and completion. */}
                          {(() => {
                            const live = embeddingProgress[source.id];
                            const meta = source.metadata || {};
                            const progress = source.progress || live || null;
                            const stage = (live && live.stage) || meta.progress_stage;
                            const isActive = ['pending', 'processing', 'uploading'].includes(source.status);
                            if (!isActive && !progress) return null;
                            if (!stage) return null;
                            if (['completed', 'failed'].includes(stage) && !isActive) return null;

                            const total = (live && live.total_chunks) ?? progress?.total_chunks ?? meta.total_chunks;
                            const done = (live && live.chunks_embedded) ?? progress?.chunks_embedded ?? meta.chunks_embedded;
                            const totalBatches = (live && live.total_batches) ?? progress?.total_batches ?? meta.total_batches;
                            const currentBatch = (live && live.current_batch) ?? progress?.current_batch ?? meta.current_batch;
                            const provider = (live && live.provider) ?? progress?.provider ?? meta.provider ?? meta.embed_provider;
                            const rateUsed = (live && live.rate_used) ?? progress?.rate_used ?? meta.rate_used;
                            const rateCap = (live && live.rate_capacity) ?? progress?.rate_capacity ?? meta.rate_capacity;
                            const rateLimit = (live && live.rate_limit_per_minute) ?? progress?.rate_limit_per_minute ?? meta.rate_limit_per_minute;
                            const remaining = (countdowns[source.id] || 0);

                            const percent = total && done != null ? Math.min(100, Math.round((done / total) * 100)) : null;
                            const isRateLimited = stage === 'embedding' && remaining > 0;
                            const stageLabel = {
                              extracting: 'Extracting text',
                              chunking: 'Chunking content',
                              embedding: isRateLimited ? 'Waiting for rate limit' : 'Generating embeddings',
                              storing: 'Storing vectors',
                              completed: 'Completed',
                              failed: 'Failed',
                            }[stage] || stage;

                            return (
                              <div className={`embedding-progress ${isRateLimited ? 'is-waiting' : ''} stage-${stage}`}>
                                <div className="embedding-progress-header">
                                  <span className="embedding-stage">
                                    {isRateLimited ? '⏳' : '⚙️'} {stageLabel}
                                    {totalBatches > 1 && currentBatch != null && (
                                      <> &middot; batch {Math.min(currentBatch + (isRateLimited ? 0 : 1), totalBatches)}/{totalBatches}</>
                                    )}
                                    {provider && (
                                      <span className="embedding-provider"> via {provider}</span>
                                    )}
                                  </span>
                                  {isRateLimited && (
                                    <span className="embedding-countdown">
                                      resets in <strong>{remaining}s</strong>
                                    </span>
                                  )}
                                </div>

                                {total != null && done != null && (
                                  <div className="embedding-bar-wrap">
                                    <div className="embedding-bar">
                                      <div
                                        className="embedding-bar-fill"
                                        style={{ width: `${percent}%` }}
                                      />
                                    </div>
                                    <div className="embedding-bar-meta">
                                      <span>{done}/{total} chunks</span>
                                      {percent != null && <span>{percent}%</span>}
                                    </div>
                                  </div>
                                )}

                                {rateLimit && (
                                  <div className="embedding-quota">
                                    Gemini rate limit:&nbsp;
                                    <strong>
                                      {rateUsed != null && rateCap != null
                                        ? `${rateUsed}/${rateCap}`
                                        : `0/${rateLimit}`}
                                    </strong>
                                    &nbsp;requests in the current 60s window
                                    {totalBatches > 1 && (
                                      <> &middot; max {Math.min(totalBatches * 100, total || 0)}/min sustained</>
                                    )}
                                  </div>
                                )}

                                {isRateLimited && totalBatches > 1 && (
                                  <div className="embedding-hint">
                                    ⏸ Paused &mdash; free tier is capped at {rateLimit || 100} requests/min.
                                    Resuming automatically as soon as the quota window resets.
                                  </div>
                                )}
                              </div>
                            );
                          })()}
                          {source.status === 'completed' && source.metadata?.processed_chunks && (
                            <div className="processing-stats">
                              ✅ Processed: {source.metadata.processed_chunks} chunks
                            </div>
                          )}
                          {/* Crawl progress bar */}
                          {crawlProgress[source.id] && (
                            <div className="crawl-progress-container">
                              <div className="crawl-progress-bar">
                                <div 
                                  className="crawl-progress-fill" 
                                  style={{ width: `${crawlProgress[source.id].progress_percent}%` }}
                                />
                              </div>
                              <div className="crawl-progress-text">
                                🕷️ Crawling: {crawlProgress[source.id].pages_crawled}/{crawlProgress[source.id].total_pages} pages ({crawlProgress[source.id].progress_percent}%)
                                {crawlProgress[source.id].pages_failed > 0 && (
                                  <span className="crawl-failed-count"> • {crawlProgress[source.id].pages_failed} failed</span>
                                )}
                              </div>
                            </div>
                          )}
                          {/* Real-time crawl log panel */}
                          {crawlLogs[source.id] && crawlLogs[source.id].length > 0 && source.status !== 'completed' && source.status !== 'failed' && (
                            <div className="crawl-log-panel">
                              {crawlLogs[source.id].slice(-8).map((log, idx) => (
                                <div key={idx} className={`crawl-log-entry crawl-log-${log.level}`}>
                                  <span className="crawl-log-time">
                                    {new Date(log.timestamp).toLocaleTimeString()}
                                  </span>
                                  <span className="crawl-log-msg">{log.message}</span>
                                </div>
                              ))}
                            </div>
                          )}
                          {/* Fallback: show progress_message from meta_data when no live logs */}
                          {(!crawlLogs[source.id] || crawlLogs[source.id].length === 0) && 
                            source.metadata?.progress_message && 
                            source.status !== 'completed' && source.status !== 'failed' && (
                            <div className="progress-message-bar">
                              ⚙️ {source.metadata.progress_message}
                            </div>
                          )}
                    </div>
                </div>
                <div className="source-actions">
                        {source.source_type === 'crawl' && (
                          <button 
                            className="action-button"
                            onClick={() => window.open(source.source_url, '_blank')}
                            title="View original website"
                          >
                            🌐 View
                          </button>
                        )}
                        {source.status === 'processing' && (
                          <button 
                            className="action-button"
                            onClick={() => {
                              dataSourceService.getDataSourceStatus(source.id)
                                .then(() => loadDataSources())
                                .catch(console.error);
                            }}
                            title="Check status"
                          >
                            🔄 Status
                          </button>
                        )}
                        {hasPermission('manage_chatbots') && (
                          <button 
                            className="action-button danger"
                            onClick={async () => {
                              const isProcessing = source.status === 'processing' || source.status === 'crawling';
                              const msg = isProcessing
                                ? `Cancel and delete "${source.source_name}"?\n\nThis data source is still processing. Deleting will stop processing and remove all content.`
                                : `Delete "${source.source_name}"?\n\nThis will remove all processed content and cannot be undone.`;
                              if (window.confirm(msg)) {
                                try {
                                  await dataSourceService.deleteDataSource(source.id);
        await refreshDataSources();
                                  alert('Data source deleted successfully!');
                                } catch (err) {
                                  setError(`Failed to delete: ${err.message}`);
                                  console.error('Error deleting data source:', err);
                                }
                              }
                            }}
                            title="Delete data source"
                          >
                            🗑️ Delete
                          </button>
                        )}
                </div>
                </div>
                  ))}
                    </div>
              )}
            </div>
      </>
    );
  };

export default DataSource;