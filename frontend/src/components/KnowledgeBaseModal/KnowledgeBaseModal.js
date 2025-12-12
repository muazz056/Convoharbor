import React, { useState, useEffect } from 'react';
import './KnowledgeBaseModal.css';
import SimpleLoader from '../common/SimpleLoader';
import { dataSourceService } from '../../services/datasource.service';

const KnowledgeBaseModal = ({ dataSource, onClose }) => {
  const [chunks, setChunks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedChunks, setExpandedChunks] = useState(new Set());

  useEffect(() => {
    if (dataSource && dataSource.id) {
      loadChunks();
    } else {
      setError('Invalid data source provided');
      setLoading(false);
    }
  }, [dataSource?.id]);

  const loadChunks = async () => {
    if (!dataSource || !dataSource.id) {
      setError('Invalid data source provided');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const result = await dataSourceService.getDataSourceChunks(dataSource.id);
      setChunks(result.chunks || []);
    } catch (err) {
      setError(err.message);
      console.error('Error loading chunks:', err);
    } finally {
      setLoading(false);
    }
  };

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
    // Remove internal fields
    delete displayMetadata.doc_id;
    delete displayMetadata.chunk_id;
    delete displayMetadata.embedding_provider;
    
    return Object.entries(displayMetadata).filter(([key, value]) => value !== null && value !== undefined);
  };

  if (!dataSource) {
    return null;
  }

  return (
    <div className="knowledge-base-modal">
      <div className="modal-overlay" onClick={onClose}></div>
      <div className="modal-content">
        <div className="modal-header">
          <div className="header-content">
            <h2>📚 Knowledge Base</h2>
            <p className="modal-subtitle">
              Processed content from <strong>{dataSource?.source_name || 'Unknown Source'}</strong>
            </p>
          </div>
          <button className="close-button" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          {loading ? (
            <SimpleLoader message="Loading knowledge base..." />
          ) : error ? (
            <div className="error-state">
              <div className="error-icon">❌</div>
              <h3>Failed to Load Knowledge Base</h3>
              <p>{error}</p>
              <button className="retry-button" onClick={loadChunks}>
                🔄 Try Again
              </button>
            </div>
          ) : (
            <>
              {/* Search and Stats */}
              <div className="knowledge-controls">
                <div className="search-box">
                  <input
                    type="text"
                    placeholder="🔍 Search knowledge base..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="search-input"
                  />
                </div>
                <div className="knowledge-stats">
                  <span className="stat">
                    📄 {filteredChunks.length} of {chunks.length} chunks
                  </span>
                  {searchTerm && (
                    <button 
                      className="clear-search"
                      onClick={() => setSearchTerm('')}
                    >
                      Clear
                    </button>
                  )}
                </div>
              </div>

              {/* Chunks List */}
              {filteredChunks.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-icon">📭</div>
                  <h3>No Content Found</h3>
                  <p>
                    {searchTerm 
                      ? `No chunks match "${searchTerm}"`
                      : 'This document has no processed content yet.'
                    }
                  </p>
                </div>
              ) : (
                <div className="chunks-list">
                  {filteredChunks.map((chunk, index) => {
                    const isExpanded = expandedChunks.has(index);
                    const metadata = formatMetadata(chunk.metadata);
                    
                    return (
                      <div key={index} className="chunk-card">
                        <div className="chunk-header">
                          <div className="chunk-info">
                            <span className="chunk-number">#{index + 1}</span>
                            {chunk.embedding_stats?.has_embedding && (
                              <span className="embedding-badge" title="Has vector embedding">
                                🧠 Embedded
                              </span>
                            )}
                          </div>
                          <button
                            className="expand-button"
                            onClick={() => toggleChunkExpansion(index)}
                            title={isExpanded ? 'Collapse' : 'Expand'}
                          >
                            {isExpanded ? '▼' : '▶'}
                          </button>
                        </div>

                        <div className="chunk-content">
                          <div className="content-text">
                            {isExpanded ? chunk.content : truncateText(chunk.content)}
                          </div>
                          
                          {!isExpanded && chunk.content.length > 200 && (
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

                        {isExpanded && chunk.embedding_stats && (
                          <div className="embedding-info">
                            <h4>🧠 Embedding Info</h4>
                            <div className="embedding-details">
                              <span>Provider: {chunk.embedding_stats.provider}</span>
                              <span>Vector Length: {chunk.embedding_stats.vector_length}</span>
                              <span>Status: {chunk.embedding_stats.has_embedding ? '✅ Ready' : '❌ Missing'}</span>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default KnowledgeBaseModal;
