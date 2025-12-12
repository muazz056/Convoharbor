import InnerNavbar from '../navbar/InnerNavbar'
import "./DataSource.css";
import Sidebar from '../Sidebar/Sidebar';
import KnowledgeBaseModal from '../KnowledgeBaseModal/KnowledgeBaseModal';
import SimpleLoader from '../common/SimpleLoader';
import AOS from 'aos';
import 'aos/dist/aos.css';
import { useEffect, useState, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { dataSourceService } from '../../services/datasource.service';
import { chatbotService } from '../../services/chatbot.service';
import { useAuth } from '../../contexts/AuthContext';

  const DataSource = () => {
    const [searchParams] = useSearchParams();
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
    const [filterStatus, setFilterStatus] = useState('all');
    const [filterType, setFilterType] = useState('all');
    const [pollingSources, setPollingSources] = useState(new Set());
    const [selectedDataSourceId, setSelectedDataSourceId] = useState(null);
    const [crawlProgress, setCrawlProgress] = useState({}); // Track progress by data_source_id

    // Debug state changes
    useEffect(() => {
      console.log('selectedDataSourceId changed:', selectedDataSourceId);
    }, [selectedDataSourceId]);

    // Get the selected data source from the dataSources array
    const selectedDataSource = selectedDataSourceId 
      ? dataSources.find(source => source.id === selectedDataSourceId)
      : null;

    // Debug selected data source
    useEffect(() => {
      if (selectedDataSourceId) {
        console.log('Looking for data source with ID:', selectedDataSourceId);
        console.log('Available data sources:', dataSources.map(s => ({ id: s.id, name: s.source_name })));
        console.log('Found selected data source:', selectedDataSource);
      }
    }, [selectedDataSourceId, dataSources, selectedDataSource]);
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
            if (status.status === 'completed' || status.status === 'failed') {
              setPollingSources(prev => {
                const newSet = new Set(prev);
                newSet.delete(sourceId);
                return newSet;
              });
              // Refresh the list to show updated status
              loadDataSources();
            }
          }
        } catch (error) {
          console.error('Error polling status:', error);
        }
      }, 3000); // Poll every 3 seconds

      return () => clearInterval(interval);
    }, [pollingSources]);

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
        alert(`✅ Web crawl completed successfully!\n\n${data.message}`);
        setCrawlProgress(prev => {
          const newProgress = { ...prev };
          delete newProgress[data.data_source_id];
          return newProgress;
        });
        loadDataSources();
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

      socket.on('crawl_progress', handleCrawlProgress);
      socket.on('crawl_completed', handleCrawlCompleted);
      socket.on('crawl_failed', handleCrawlFailed);

      return () => {
        socket.off('crawl_progress', handleCrawlProgress);
        socket.off('crawl_completed', handleCrawlCompleted);
        socket.off('crawl_failed', handleCrawlFailed);
      };
    }, []);

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
        
        const filters = { per_page: 50 };
        if (selectedChatbot) filters.chatbot_id = selectedChatbot;
        if (filterStatus !== 'all') filters.status = filterStatus;
        if (filterType !== 'all') filters.source_type = filterType;
        
        const response = await dataSourceService.getDataSources(filters);
        const sources = response.data_sources || [];
        setDataSources(sources);
        
        // Start polling for processing sources
        const processingSources = sources
          .filter(source => source.status === 'processing' || source.status === 'pending')
          .map(source => source.id);
        
        if (processingSources.length > 0) {
          setPollingSources(new Set(processingSources));
        }
      } catch (err) {
        if (err.message === 'Authentication required') {
          // Redirect to login
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
        
        // Show appropriate message
        if (result.warning) {
          alert(`✅ ${result.warning}\n\nFiles uploaded: ${files.length}`);
        } else {
          alert(`✅ Successfully uploaded ${files.length} files!`);
        }
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
        alert(`Web crawling started for: ${crawlUrl}`);
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
        <div className="layout-container">
          <Sidebar />
          <div className="main-content">
            <InnerNavbar />

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

                <div className="filter-group">
                  <label>Status:</label>
                  <select 
                    value={filterStatus} 
                    onChange={(e) => {
                      setFilterStatus(e.target.value);
                      loadDataSources();
                    }}
                    className="filter-select"
                  >
                    <option value="all">All Status</option>
                    <option value="pending">Pending</option>
                    <option value="processing">Processing</option>
                    <option value="completed">Completed</option>
                    <option value="failed">Failed</option>
                  </select>
                </div>

                <div className="filter-group">
                  <label>Type:</label>
                  <select 
                    value={filterType} 
                    onChange={(e) => {
                      setFilterType(e.target.value);
                      loadDataSources();
                    }}
                    className="filter-select"
                  >
                    <option value="all">All Types</option>
                    <option value="upload">File Upload</option>
                    <option value="crawl">Web Crawl</option>
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
                              // Refresh this specific source
                              dataSourceService.getDataSourceStatus(source.id)
                                .then(() => loadDataSources())
                                .catch(console.error);
                            }}
                            title="Check status"
                          >
                            🔄 Status
                          </button>
                        )}
                        {source.status === 'completed' && (
                          <button 
                            className="action-button knowledge"
                            onClick={() => {
                              console.log('Selected data source:', source);
                              setSelectedDataSourceId(source.id);
                            }}
                            title="View processed knowledge base"
                          >
                            📚 Knowledge Base
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
                </div>
        </div>
        
        {/* Knowledge Base Modal */}
        {selectedDataSource && selectedDataSource.id && (
          <KnowledgeBaseModal
            dataSource={selectedDataSource}
            onClose={() => setSelectedDataSourceId(null)}
          />
        )}
      </>
    );
  };

export default DataSource;