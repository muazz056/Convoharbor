import "./DataSource.css";
import SimpleLoader from '../common/SimpleLoader';
import AOS from 'aos';
import 'aos/dist/aos.css';
import { useEffect, useState, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { dataSourceService } from '../../services/datasource.service';
import { chatbotService } from '../../services/chatbot.service';
import { useAuth } from '../../contexts/AuthContext';

  const DataSource = () => {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const { hasPermission } = useAuth();
    
    const [dataSources, setDataSources] = useState([]);
    const [chatbots, setChatbots] = useState([]);
    const [selectedChatbot, setSelectedChatbot] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState({});
    const [showUrlInput, setShowUrlInput] = useState(false);
    const [crawlUrl, setCrawlUrl] = useState('');
    const [crawling, setCrawling] = useState(false);
    const [pollingSources, setPollingSources] = useState(new Set());
    const [crawlProgress, setCrawlProgress] = useState({}); // Track progress by data_source_id
    const [embeddingProgress, setEmbeddingProgress] = useState({}); // Rate-limit-aware progress by data_source_id
    const [countdowns, setCountdowns] = useState({}); // Countdown timers (seconds remaining) by data_source_id

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
        try {
          for (const sourceId of pollingSources) {
            const status = await dataSourceService.getDataSourceStatus(sourceId);
            if (status.status === 'completed') {
              setPollingSources(prev => {
                const newSet = new Set(prev);
                newSet.delete(sourceId);
                return newSet;
              });
              // Refresh list and redirect to knowledge base
              await loadDataSources();
              alert('✅ Processing completed! Redirecting to Knowledge Base...');
              navigate('/knowledge-base');
              return;
            } else if (status.status === 'failed') {
              setPollingSources(prev => {
                const newSet = new Set(prev);
                newSet.delete(sourceId);
                return newSet;
              });
              await loadDataSources();
            }
          }
        } catch (error) {
          console.error('Error polling status:', error);
        }
      }, 3000);

      return () => clearInterval(interval);
    }, [pollingSources, navigate]);

    // WebSocket listeners for crawl updates
    useEffect(() => {
      const { socket } = window;
      if (!socket) return;

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
        loadDataSources();
        alert('✅ Web crawl completed! Redirecting to Knowledge Base...');
        navigate('/knowledge-base');
      };

      // Listen for crawl failure
      const handleCrawlFailed = (data) => {
        console.log('❌ Crawl failed:', data);
        alert(`❌ Web crawl failed!\n\n${data.message}`);
        setCrawlProgress(prev => {
          const newProgress = { ...prev };
          delete newProgress[data.data_source_id];
          return newProgress;
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
          // Refresh the list so the row leaves the active list, and
          // clear the countdown for this source.
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
          // Seed a fresh countdown from the backend's estimate.
          setCountdowns(prev => ({
            ...prev,
            [sid]: Math.ceil(data.wait_seconds),
          }));
        }
      };

      socket.on('crawl_progress', handleCrawlProgress);
      socket.on('crawl_completed', handleCrawlCompleted);
      socket.on('crawl_failed', handleCrawlFailed);
      socket.on('datasource_progress', handleDatasourceProgress);

      return () => {
        socket.off('crawl_progress', handleCrawlProgress);
        socket.off('crawl_completed', handleCrawlCompleted);
        socket.off('crawl_failed', handleCrawlFailed);
        socket.off('datasource_progress', handleDatasourceProgress);
      };
    }, []);

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
        
        // Only show pending/processing/failed sources (completed ones are in Knowledge Base)
        const activeSources = allSources.filter(s => 
          s.status === 'pending' || s.status === 'processing' || s.status === 'uploading' || s.status === 'failed'
        );
        setDataSources(activeSources);
        
        // Start polling for processing sources
        const processingSources = activeSources
          .filter(source => source.status === 'processing' || source.status === 'pending' || source.status === 'uploading')
          .map(source => source.id);
        
        if (processingSources.length > 0) {
          setPollingSources(new Set(processingSources));
        }
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
        await loadDataSources();
        
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
      if (!crawlUrl.trim()) return;

      // Check if chatbot is selected
      if (!selectedChatbot) {
        setError('Please select a chatbot first before crawling a website');
        alert('⚠️ Please select a chatbot first\n\nYou must choose which chatbot should use this content before crawling.');
        return;
      }

      try {
        setCrawling(true);
        setError(null);

        const crawlOptions = {};
        if (selectedChatbot) {
          crawlOptions.chatbot_id = selectedChatbot;
          crawlOptions.description = `Web content for ${chatbots.find(c => c.id === selectedChatbot)?.name || 'chatbot'}`;
        }
        
        const result = await dataSourceService.crawlWebsite(crawlUrl.trim(), crawlOptions);
        
        // Refresh data sources list
        await loadDataSources();
        
        setCrawlUrl('');
        setShowUrlInput(false);
        alert(`🌐 Web crawling started! You'll be redirected to Knowledge Base when done.`);
      } catch (err) {
        setError(err.message);
        console.error('Error starting web crawl:', err);
      } finally {
        setCrawling(false);
      }
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
                      <div className="url-input-form">
                        <input
                          type="url"
                          value={crawlUrl}
                          onChange={(e) => setCrawlUrl(e.target.value)}
                          placeholder={selectedChatbot ? "https://example.com/docs" : "Select a chatbot to enable crawling"}
                          className="url-input"
                          disabled={crawling || !selectedChatbot}
                        />
                        <button 
                          onClick={handleUrlCrawl}
                          disabled={crawling || !crawlUrl.trim() || !selectedChatbot}
                          className="crawl-button"
                        >
                          {crawling ? 'Crawling...' : 'Start Crawl'}
                        </button>
                      </div>
                      {!selectedChatbot && (
                        <p className="help-text required-text">
                          Please select a chatbot from the dropdown above to enable website crawling.
                        </p>
                      )}
                      <p className="help-text">
                        Enter a website URL to extract and process its content for your chatbot training.
                      </p>
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
                              if (window.confirm(`Delete "${source.source_name}"?\n\nThis will remove all processed content and cannot be undone.`)) {
                                try {
                                  await dataSourceService.deleteDataSource(source.id);
                                  await loadDataSources();
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