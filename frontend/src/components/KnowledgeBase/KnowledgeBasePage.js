import React, { useState, useEffect } from 'react';
import './KnowledgeBasePage.css';
import { dataSourceService } from '../../services/datasource.service';
import { chatbotService } from '../../services/chatbot.service'; // Import chatbot service
import Sidebar from '../Sidebar/Sidebar'; // Import Sidebar
import InnerNavbar from '../navbar/InnerNavbar'; // Import InnerNavbar
import AOS from 'aos';
import 'aos/dist/aos.css';

const KnowledgeBasePage = () => {
  const [chatbots, setChatbots] = useState([]);
  const [dataSources, setDataSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeChatbotId, setActiveChatbotId] = useState(null); // To control accordion
  
  // State for the chunk viewer (repurposed from modal)
  const [selectedDataSource, setSelectedDataSource] = useState(null);
  const [chunks, setChunks] = useState([]);
  const [chunksLoading, setChunksLoading] = useState(false);
  const [chunksError, setChunksError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedChunks, setExpandedChunks] = useState(new Set());

  useEffect(() => {
    AOS.init({
      duration: 800,
      easing: 'ease-in-out',
      once: true,
    });
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [chatbotsRes, dataSourcesRes] = await Promise.all([
        chatbotService.getChatbots({ per_page: 100 }),
        dataSourceService.getDataSources({ per_page: 500 }) // Fetch more sources
      ]);
      setChatbots(chatbotsRes.chatbots || []);
      setDataSources(dataSourcesRes.data_sources || []);
    } catch (err) {
      setError(err.message);
      console.error("Failed to fetch data:", err);
    } finally {
      setLoading(false);
    }
  };
  
  const handleDataSourceClick = async (dataSource) => {
    if (selectedDataSource && selectedDataSource.id === dataSource.id) {
        // If the same source is clicked again, close the viewer
        setSelectedDataSource(null);
        setChunks([]);
        return;
    }

    setSelectedDataSource(dataSource);
    setChunksLoading(true);
    setChunksError(null);
    setSearchTerm('');
    try {
      const result = await dataSourceService.getDataSourceChunks(dataSource.id);
      setChunks(result.chunks || []);
    } catch (err) {
      setChunksError(err.message);
      console.error('Error loading chunks:', err);
    } finally {
      setChunksLoading(false);
    }
  };

  // Group data sources by chatbot
  const sourcesByChatbot = dataSources.reduce((acc, source) => {
    const chatbotId = source.chatbot_id || 'unassigned';
    if (!acc[chatbotId]) {
      acc[chatbotId] = [];
    }
    acc[chatbotId].push(source);
    return acc;
  }, {});

  // Helper functions for chunk viewer
  const toggleChunkExpansion = (index) => {
    const newExpanded = new Set(expandedChunks);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedChunks(newExpanded);
  };

  const filteredChunks = chunks.filter(chunk =>
    chunk.content.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const truncateText = (text, maxLength = 200) => {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  };
  
  const formatMetadata = (metadata) => {
    const displayMetadata = { ...metadata };
    // Remove internal fields that are not useful for the user
    delete displayMetadata.doc_id;
    delete displayMetadata.chunk_id;
    delete displayMetadata.embedding_provider;
    
    return Object.entries(displayMetadata).filter(([key, value]) => value !== null && value !== undefined && value !== '');
  };

  const getSourceIcon = (sourceType) => {
    const icons = {
      upload: '📄',
      crawl: '🌐',
      api: '🔗'
    };
    return icons[sourceType] || '📄';
  };

  // Main render
  return (
    <>
      <div className="layout-container">
        <Sidebar />
        <div className="main-content">
          <InnerNavbar />
          <div className="page" id="knowledge-base-overview" data-aos="fade-up">
            <div className="page-header">
              <h1 className="page-title">Knowledge Base Overview</h1>
              <p className="page-subtitle">View and manage the knowledge for all your chatbots.</p>
            </div>

            {loading && (
              <div className="loading-state">
                <div className="spinner"></div>
                <p>Loading knowledge bases...</p>
              </div>
            )}
            
            {error && <div className="error-message">⚠️ {error}</div>}

            {!loading && !error && (
              <div className="kb-content">
                <div className="chatbot-list-column">
                  <h3>Chatbots</h3>
                  <div className="chatbot-accordion">
                    {/* Unassigned Data Sources Section */}
                    {sourcesByChatbot['unassigned'] && sourcesByChatbot['unassigned'].length > 0 && (
                      <div className="chatbot-section active">
                        <button className="accordion-header" disabled>
                          <span className='chatbot-name'>Unassigned Sources</span>
                          <span className='data-source-count'>
                            {sourcesByChatbot['unassigned'].length} sources
                          </span>
                        </button>
                        <div className="accordion-content">
                          {sourcesByChatbot['unassigned'].map(source => (
                            <div 
                              key={source.id} 
                              className={`data-source-item ${selectedDataSource?.id === source.id ? 'active' : ''}`}
                              onClick={() => handleDataSourceClick(source)}
                            >
                              <span className="source-icon">{getSourceIcon(source.source_type)}</span>
                              <span className="source-name">{source.source_name}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {chatbots.map(chatbot => (
                      <div key={chatbot.id} className={`chatbot-section ${activeChatbotId === chatbot.id ? 'active' : ''}`}>
                        <button 
                          className="accordion-header"
                          onClick={() => setActiveChatbotId(activeChatbotId === chatbot.id ? null : chatbot.id)}
                        >
                          <span className='chatbot-name'>{chatbot.name}</span>
                          <span className='data-source-count'>
                            {sourcesByChatbot[chatbot.id]?.length || 0} sources
                          </span>
                        </button>
                        {activeChatbotId === chatbot.id && (
                          <div className="accordion-content">
                            {sourcesByChatbot[chatbot.id] && sourcesByChatbot[chatbot.id].length > 0 ? (
                              sourcesByChatbot[chatbot.id].map(source => (
                                <div 
                                  key={source.id} 
                                  className={`data-source-item ${selectedDataSource?.id === source.id ? 'active' : ''}`}
                                  onClick={() => handleDataSourceClick(source)}
                                >
                                  <span className="source-icon">{getSourceIcon(source.source_type)}</span>
                                  <span className="source-name">{source.source_name}</span>
                                </div>
                              ))
                            ) : (
                              <div className="no-sources">No data sources for this chatbot.</div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="chunk-viewer-column">
                  {selectedDataSource ? (
                    <div className="chunk-viewer">
                      <div className="viewer-header">
                        <h3>Processed Content for: <strong>{selectedDataSource.source_name}</strong></h3>
                      </div>
                      
                      {chunksLoading ? (
                        <div className="loading-state"><div className="spinner"></div><p>Loading chunks...</p></div>
                      ) : chunksError ? (
                        <div className="error-message">⚠️ {chunksError}</div>
                      ) : (
                        <>
                          <div className="knowledge-controls">
                            <div className="search-box">
                              <span className="search-icon">🔍</span>
                              <input
                                type="text"
                                placeholder="Search chunks..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                className="search-input"
                              />
                            </div>
                            <div className="knowledge-stats">
                              <span>{filteredChunks.length} of {chunks.length} chunks</span>
                            </div>
                          </div>
                          
                          <div className="chunks-list">
                            {filteredChunks.length > 0 ? filteredChunks.map((chunk, index) => {
                                const isExpanded = expandedChunks.has(index);
                                const metadata = formatMetadata(chunk.metadata); // Use the helper
                                return (
                                  <div key={index} className="chunk-card">
                                    <div className="chunk-header" onClick={() => toggleChunkExpansion(index)}>
                                      <div className="chunk-info">
                                        <span className="chunk-number">Chunk #{index + 1}</span>
                                        {chunk.embedding_stats?.has_embedding && (
                                            <span className="embedding-badge">🧠 Embedded</span>
                                        )}
                                      </div>
                                      <button className="expand-button">{isExpanded ? '▼' : '▶'}</button>
                                    </div>
                                    
                                    <div className="chunk-content">
                                      <div className="content-text">
                                        {isExpanded ? chunk.content : truncateText(chunk.content, 250)}
                                      </div>
                                      {!isExpanded && chunk.content.length > 250 && (
                                        <button 
                                          className="read-more-button" 
                                          onClick={() => toggleChunkExpansion(index)}
                                        >
                                          Read more...
                                        </button>
                                      )}
                                    </div>

                                    {isExpanded && metadata.length > 0 && (
                                      <div className="chunk-metadata">
                                        <h4>📋 Metadata</h4>
                                        <div className="metadata-grid">
                                          {metadata.map(([key, value]) => (
                                            <div key={key} className="metadata-item">
                                              <span className="metadata-key">{key}:</span>
                                              <span className="metadata-value">
                                                {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                                              </span>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    )}

                                  </div>
                                );
                            }) : (
                                <div className="empty-state">No chunks found for this data source.</div>
                            )}
                          </div>
                        </>
                      )}
                    </div>
                  ) : (
                    <div className="empty-viewer">
                      <div className="empty-icon">👈</div>
                      <h3>Select a Data Source</h3>
                      <p>Click on a data source from the list on the left to view its processed knowledge chunks.</p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
};

export default KnowledgeBasePage;