import React, { useState, useEffect } from 'react';
import './Settings.css';
import InnerNavbar from '../navbar/InnerNavbar'
import Sidebar from '../Sidebar/Sidebar';
import { useAuth } from '../../contexts/AuthContext';
import AOS from 'aos';
import 'aos/dist/aos.css';

const SettingsPage = () => {
  const { user, updateUser } = useAuth();
  
  // Profile form state
  const [profileData, setProfileData] = useState({
    first_name: '',
    last_name: '',
    email: '',
    current_password: '',
    new_password: '',
    confirm_password: ''
  });
  
  // UI state
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('profile');
  
  // Settings state
  const [language, setLanguage] = useState('English');
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [soundNotifications, setSoundNotifications] = useState(false);
  const [developerMode, setDeveloperMode] = useState(false);
  
  // Security state
  const [twoFactorEnabled, setTwoFactorEnabled] = useState(false);
  const [activeSessions, setActiveSessions] = useState([]);
  const [showSessions, setShowSessions] = useState(false);
  const [apiKeys, setApiKeys] = useState([]);
  const [showApiKeys, setShowApiKeys] = useState(false);
  const [showNewApiKeyForm, setShowNewApiKeyForm] = useState(false);
  const [newApiKeyName, setNewApiKeyName] = useState('');
  
  // Preferences loading state
  const [preferencesLoading, setPreferencesLoading] = useState(false);

  useEffect(() => {
    AOS.init({
      duration: 800,
      easing: 'ease-in-out',
      once: true,
    });

    // Fetch fresh profile data from API
    const fetchProfileData = async () => {
      try {
        const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
        const token = localStorage.getItem('authToken');
        
        if (!token) {
          console.log('🔍 Settings: No auth token found');
          return;
        }

        console.log('🔍 Settings: Fetching fresh profile data from API...');
        const response = await fetch(`${baseURL}/users/profile`, {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        if (response.ok) {
          const profileData = await response.json();
          console.log('🔍 Settings: Fresh profile data from API:', profileData);
          
          setProfileData(prev => ({
            ...prev,
            first_name: profileData.first_name || '',
            last_name: profileData.last_name || '',
            email: profileData.email || ''
          }));
        } else {
          console.error('🔍 Settings: Failed to fetch profile data:', response.status);
        }
      } catch (error) {
        console.error('🔍 Settings: Error fetching profile data:', error);
      }
    };

    // Initialize form with user data from context
    if (user) {
      console.log('🔍 Settings: User data received from context:', user);
      console.log('🔍 Settings: User object keys:', Object.keys(user));
      console.log('🔍 Settings: first_name:', user.first_name);
      console.log('🔍 Settings: last_name:', user.last_name);
      console.log('🔍 Settings: firstName:', user.firstName);
      console.log('🔍 Settings: lastName:', user.lastName);
      console.log('🔍 Settings: email:', user.email);
      
      // Also check localStorage directly
      const storedUserData = localStorage.getItem('userData');
      if (storedUserData) {
        try {
          const parsedData = JSON.parse(storedUserData);
          console.log('🔍 Settings: localStorage userData:', parsedData);
          console.log('🔍 Settings: localStorage keys:', Object.keys(parsedData));
        } catch (e) {
          console.error('🔍 Settings: Error parsing localStorage userData:', e);
        }
      }
      
      setProfileData(prev => ({
        ...prev,
        // Handle both camelCase (from login) and snake_case (from profile update) formats
        first_name: user.first_name || user.firstName || '',
        last_name: user.last_name || user.lastName || '',
        email: user.email || ''
      }));

      // Also fetch fresh data from API to ensure we have the latest
      fetchProfileData();
    }

    // Load user preferences from localStorage
    loadUserPreferences();
    loadSecuritySettings();
  }, [user]);

  const loadUserPreferences = () => {
    try {
      const savedPrefs = localStorage.getItem('userPreferences');
      if (savedPrefs) {
        const prefs = JSON.parse(savedPrefs);
        setLanguage(prefs.language || 'English');
        setEmailNotifications(prefs.emailNotifications !== false);
        setSoundNotifications(prefs.soundNotifications || false);
        setDeveloperMode(prefs.developerMode || false);
      }
    } catch (error) {
      console.error('Error loading preferences:', error);
    }
  };

  const saveUserPreferences = async () => {
    setPreferencesLoading(true);
    try {
      const preferences = {
        language,
        emailNotifications,
        soundNotifications,
        developerMode,
        updatedAt: new Date().toISOString()
      };
      
      localStorage.setItem('userPreferences', JSON.stringify(preferences));
      setSuccess('Preferences saved successfully!');
      setTimeout(() => setSuccess(''), 3000);
    } catch (error) {
      setError('Failed to save preferences');
      setTimeout(() => setError(''), 3000);
    } finally {
      setPreferencesLoading(false);
    }
  };

  const loadSecuritySettings = async () => {
    try {
      // Load mock security data (in real app, this would come from API)
      const mockSessions = [
        {
          id: 1,
          device: 'Chrome on Windows',
          location: 'New York, NY',
          lastActive: new Date().toISOString(),
          current: true
        },
        {
          id: 2,
          device: 'Firefox on MacOS',
          location: 'San Francisco, CA',
          lastActive: new Date(Date.now() - 86400000).toISOString(),
          current: false
        }
      ];
      
      const mockApiKeys = [
        {
          id: 1,
          name: 'Production API',
          key: 'sk-...4f2a',
          created: new Date(Date.now() - 7 * 86400000).toISOString(),
          lastUsed: new Date().toISOString()
        }
      ];
      
      setActiveSessions(mockSessions);
      setApiKeys(mockApiKeys);
      setTwoFactorEnabled(false); // Mock data
    } catch (error) {
      console.error('Error loading security settings:', error);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setProfileData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleProfileSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    // Validate passwords if changing password
    if (profileData.new_password) {
      if (profileData.new_password !== profileData.confirm_password) {
        setError('New passwords do not match');
        setLoading(false);
        return;
      }
      if (profileData.new_password.length < 6) {
        setError('New password must be at least 6 characters long');
        setLoading(false);
        return;
      }
      if (!profileData.current_password) {
        setError('Current password is required to change password');
        setLoading(false);
        return;
      }
    }

    try {
      const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
      const token = localStorage.getItem('authToken');
      
      const updateData = {
        first_name: profileData.first_name,
        last_name: profileData.last_name
      };

      // Add password fields if changing password
      if (profileData.new_password) {
        updateData.current_password = profileData.current_password;
        updateData.new_password = profileData.new_password;
      }

      const response = await fetch(`${baseURL}/users/profile`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(updateData)
      });

      const result = await response.json();

      if (response.ok) {
        setSuccess('Profile updated successfully!');
        // Update user context with the response data
        if (updateUser && result.user) {
          updateUser(result.user);
        }
        // Clear password fields
        setProfileData(prev => ({
          ...prev,
          current_password: '',
          new_password: '',
          confirm_password: ''
        }));
      } else {
        setError(result.error || result.message || 'Failed to update profile');
      }
    } catch (err) {
      setError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleToggle2FA = async () => {
    try {
      setLoading(true);
      // Mock 2FA toggle (in real app, this would call API)
      await new Promise(resolve => setTimeout(resolve, 1000));
      setTwoFactorEnabled(!twoFactorEnabled);
      setSuccess(`Two-factor authentication ${!twoFactorEnabled ? 'enabled' : 'disabled'} successfully!`);
      setTimeout(() => setSuccess(''), 3000);
    } catch (error) {
      setError('Failed to update two-factor authentication');
      setTimeout(() => setError(''), 3000);
    } finally {
      setLoading(false);
    }
  };

  const handleRevokeSession = async (sessionId) => {
    try {
      if (window.confirm('Are you sure you want to revoke this session?')) {
        setActiveSessions(prev => prev.filter(session => session.id !== sessionId));
        setSuccess('Session revoked successfully!');
        setTimeout(() => setSuccess(''), 3000);
      }
    } catch (error) {
      setError('Failed to revoke session');
      setTimeout(() => setError(''), 3000);
    }
  };

  const handleCreateApiKey = async () => {
    try {
      if (!newApiKeyName.trim()) {
        setError('API key name is required');
        setTimeout(() => setError(''), 3000);
        return;
      }

      const newKey = {
        id: Date.now(),
        name: newApiKeyName,
        key: `sk-${Math.random().toString(36).substr(2, 9)}...${Math.random().toString(36).substr(2, 4)}`,
        created: new Date().toISOString(),
        lastUsed: null
      };

      setApiKeys(prev => [...prev, newKey]);
      setNewApiKeyName('');
      setShowNewApiKeyForm(false);
      setSuccess('API key created successfully!');
      setTimeout(() => setSuccess(''), 3000);
    } catch (error) {
      setError('Failed to create API key');
      setTimeout(() => setError(''), 3000);
    }
  };

  const handleDeleteApiKey = async (keyId) => {
    try {
      if (window.confirm('Are you sure you want to delete this API key? This action cannot be undone.')) {
        setApiKeys(prev => prev.filter(key => key.id !== keyId));
        setSuccess('API key deleted successfully!');
        setTimeout(() => setSuccess(''), 3000);
      }
    } catch (error) {
      setError('Failed to delete API key');
      setTimeout(() => setError(''), 3000);
    }
  };

  return (
      <>
        <div className="layout-container">
          <Sidebar />
          
          <div className="main-content">
            <InnerNavbar />
    <div className="page" id="settings">
      <div className="page-header">
              <h1 className="page-title">⚙️ Account Settings</h1>
              <p className="page-subtitle">Manage your profile and account preferences</p>
            </div>

            {/* Tab Navigation */}
            <div className="settings-tabs" data-aos="fade-up">
              <button 
                className={`tab-button ${activeTab === 'profile' ? 'active' : ''}`}
                onClick={() => setActiveTab('profile')}
              >
                👤 Profile
              </button>
              <button 
                className={`tab-button ${activeTab === 'preferences' ? 'active' : ''}`}
                onClick={() => setActiveTab('preferences')}
              >
                🎛️ Preferences
              </button>
              <button 
                className={`tab-button ${activeTab === 'security' ? 'active' : ''}`}
                onClick={() => setActiveTab('security')}
              >
                🔒 Security
              </button>
            </div>

            {/* Profile Tab */}
            {activeTab === 'profile' && (
              <div className="settings-section" data-aos="fade-up" data-aos-delay="200">
                <div className="section-header">
                  <h2 className="settings-title">Profile Information</h2>
                  <p className="settings-description">Update your personal information and account details</p>
                </div>

                {/* Success/Error Messages */}
                {success && (
                  <div className="alert alert-success">
                    <span className="alert-icon">✅</span>
                    {success}
                  </div>
                )}
                {error && (
                  <div className="alert alert-error">
                    <span className="alert-icon">❌</span>
                    {error}
                  </div>
                )}

                <form onSubmit={handleProfileSubmit} className="profile-form">
                  <div className="form-grid">
                    <div className="form-group">
                      <label htmlFor="first_name" className="form-label">
                        First Name
                      </label>
                      <input
                        type="text"
                        id="first_name"
                        name="first_name"
                        value={profileData.first_name}
                        onChange={handleInputChange}
                        className="form-input"
                        placeholder="Enter your first name"
                      />
                    </div>

                    <div className="form-group">
                      <label htmlFor="last_name" className="form-label">
                        Last Name
                      </label>
                      <input
                        type="text"
                        id="last_name"
                        name="last_name"
                        value={profileData.last_name}
                        onChange={handleInputChange}
                        className="form-input"
                        placeholder="Enter your last name"
                      />
                    </div>

                    <div className="form-group full-width">
                      <label htmlFor="email" className="form-label">
                        Email Address
                      </label>
                      <input
                        type="email"
                        id="email"
                        name="email"
                        value={profileData.email}
                        className="form-input"
                        disabled
                        title="Email cannot be changed"
                      />
                      <small className="form-hint">Email address cannot be changed</small>
                    </div>
                  </div>

                  <div className="form-divider">
                    <span>Change Password (Optional)</span>
                  </div>

                  <div className="form-grid">
                    <div className="form-group">
                      <label htmlFor="current_password" className="form-label">
                        Current Password
                      </label>
                      <input
                        type="password"
                        id="current_password"
                        name="current_password"
                        value={profileData.current_password}
                        onChange={handleInputChange}
                        className="form-input"
                        placeholder="Enter current password"
                      />
                    </div>

                    <div className="form-group">
                      <label htmlFor="new_password" className="form-label">
                        New Password
                      </label>
                      <input
                        type="password"
                        id="new_password"
                        name="new_password"
                        value={profileData.new_password}
                        onChange={handleInputChange}
                        className="form-input"
                        placeholder="Enter new password"
                      />
                    </div>

                    <div className="form-group">
                      <label htmlFor="confirm_password" className="form-label">
                        Confirm New Password
                      </label>
                      <input
                        type="password"
                        id="confirm_password"
                        name="confirm_password"
                        value={profileData.confirm_password}
                        onChange={handleInputChange}
                        className="form-input"
                        placeholder="Confirm new password"
                      />
                    </div>
      </div>

                  <div className="form-actions">
                    <button 
                      type="submit" 
                      className="btn btn-primary"
                      disabled={loading}
                    >
                      {loading ? (
                        <>
                          <span className="spinner"></span>
                          Updating...
                        </>
                      ) : (
                        <>
                          💾 Save Changes
                        </>
                      )}
                    </button>
                  </div>
                </form>
              </div>
            )}

            {/* Preferences Tab */}
            {activeTab === 'preferences' && (
      <div className="settings-section" data-aos="fade-up" data-aos-delay="200">
                <div className="section-header">
                  <h2 className="settings-title">Application Preferences</h2>
                  <p className="settings-description">Customize your application experience</p>
                </div>

                {/* Success/Error Messages */}
                {success && (
                  <div className="alert alert-success">
                    <span className="alert-icon">✅</span>
                    {success}
                  </div>
                )}
                {error && (
                  <div className="alert alert-error">
                    <span className="alert-icon">❌</span>
                    {error}
                  </div>
                )}

        <div className="settings-item">
          <div className="settings-info">
            <div className="settings-label">Interface Language</div>
            <div className="settings-description">Choose the application language</div>
          </div>
          <select
                    className="form-select"
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
          >
                    <option value="English">English</option>
                    <option value="French">French</option>
                    <option value="Spanish">Spanish</option>
                    <option value="German">German</option>
                    <option value="Italian">Italian</option>
          </select>
        </div>

        <ToggleSetting
          label="Email Notifications"
          description="Receive important notifications via email"
          active={emailNotifications}
          onToggle={() => setEmailNotifications((prev) => !prev)}
        />

        <ToggleSetting
          label="Notification Sound"
          description="Play a sound when receiving messages"
          active={soundNotifications}
          onToggle={() => setSoundNotifications((prev) => !prev)}
        />

        <ToggleSetting
          label="Developer Mode"
          description="Show advanced options and logs"
          active={developerMode}
          onToggle={() => setDeveloperMode((prev) => !prev)}
        />

                <div className="form-actions">
                  <button 
                    onClick={saveUserPreferences}
                    className="btn btn-primary"
                    disabled={preferencesLoading}
                  >
                    {preferencesLoading ? (
                      <>
                        <span className="spinner"></span>
                        Saving...
                      </>
                    ) : (
                      <>
                        💾 Save Preferences
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* Security Tab */}
            {activeTab === 'security' && (
              <div className="settings-section" data-aos="fade-up" data-aos-delay="200">
                <div className="section-header">
                  <h2 className="settings-title">Security & Privacy</h2>
                  <p className="settings-description">Manage your account security settings</p>
      </div>

                {/* Success/Error Messages */}
                {success && (
                  <div className="alert alert-success">
                    <span className="alert-icon">✅</span>
                    {success}
                  </div>
                )}
                {error && (
                  <div className="alert alert-error">
                    <span className="alert-icon">❌</span>
                    {error}
                  </div>
                )}

                {/* Two-Factor Authentication */}
                <div className="settings-item">
                  <div className="settings-info">
                    <div className="settings-label">Two-Factor Authentication</div>
                    <div className="settings-description">
                      {twoFactorEnabled 
                        ? "Two-factor authentication is enabled for your account" 
                        : "Add an extra layer of security to your account"
                      }
                    </div>
                  </div>
                  <button 
                    className={`btn ${twoFactorEnabled ? 'btn-secondary' : 'btn-primary'}`}
                    onClick={handleToggle2FA}
                    disabled={loading}
                  >
                    {loading ? (
                      <>
                        <span className="spinner"></span>
                        {twoFactorEnabled ? 'Disabling...' : 'Enabling...'}
                      </>
                    ) : (
                      twoFactorEnabled ? '🔓 Disable 2FA' : '🔒 Enable 2FA'
                    )}
                  </button>
                </div>

                {/* Active Sessions */}
                <div className="settings-item">
                  <div className="settings-info">
                    <div className="settings-label">Active Sessions</div>
                    <div className="settings-description">Manage your active login sessions across devices</div>
                  </div>
                  <button 
                    className="btn btn-secondary"
                    onClick={() => setShowSessions(!showSessions)}
                  >
                    {showSessions ? '👁️ Hide Sessions' : '👀 View Sessions'}
                  </button>
      </div>

                {/* Sessions List */}
                {showSessions && (
                  <div className="security-subsection">
                    <h4>Active Sessions ({activeSessions.length})</h4>
                    <div className="sessions-list">
                      {activeSessions.map((session) => (
                        <div key={session.id} className="session-item">
                          <div className="session-info">
                            <div className="session-device">
                              {session.device} {session.current && <span className="current-badge">Current</span>}
                            </div>
                            <div className="session-details">
                              📍 {session.location} • Last active: {new Date(session.lastActive).toLocaleDateString()}
                            </div>
                          </div>
                          {!session.current && (
                            <button 
                              className="btn btn-danger btn-sm"
                              onClick={() => handleRevokeSession(session.id)}
                            >
                              Revoke
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* API Keys */}
                <div className="settings-item">
                  <div className="settings-info">
                    <div className="settings-label">API Keys</div>
                    <div className="settings-description">Manage your API access keys for integrations</div>
                  </div>
                  <button 
                    className="btn btn-secondary"
                    onClick={() => setShowApiKeys(!showApiKeys)}
                  >
                    {showApiKeys ? '👁️ Hide Keys' : '🔑 Manage Keys'}
                  </button>
                </div>

                {/* API Keys List */}
                {showApiKeys && (
                  <div className="security-subsection">
                    <div className="subsection-header">
                      <h4>API Keys ({apiKeys.length})</h4>
                      <button 
                        className="btn btn-primary btn-sm"
                        onClick={() => setShowNewApiKeyForm(!showNewApiKeyForm)}
                      >
                        ➕ Create New Key
                      </button>
                    </div>

                    {/* New API Key Form */}
                    {showNewApiKeyForm && (
                      <div className="new-api-key-form">
                        <div className="form-group">
                          <label className="form-label">Key Name</label>
                          <input
                            type="text"
                            className="form-input"
                            placeholder="e.g., Production API, Development Key"
                            value={newApiKeyName}
                            onChange={(e) => setNewApiKeyName(e.target.value)}
        />
      </div>
                        <div className="form-actions">
                          <button 
                            className="btn btn-primary btn-sm"
                            onClick={handleCreateApiKey}
                          >
                            Create Key
                          </button>
                          <button 
                            className="btn btn-secondary btn-sm"
                            onClick={() => {
                              setShowNewApiKeyForm(false);
                              setNewApiKeyName('');
                            }}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    )}

                    <div className="api-keys-list">
                      {apiKeys.map((key) => (
                        <div key={key.id} className="api-key-item">
                          <div className="api-key-info">
                            <div className="api-key-name">{key.name}</div>
                            <div className="api-key-details">
                              🔑 {key.key} • Created: {new Date(key.created).toLocaleDateString()}
                              {key.lastUsed && ` • Last used: ${new Date(key.lastUsed).toLocaleDateString()}`}
                            </div>
                          </div>
                          <button 
                            className="btn btn-danger btn-sm"
                            onClick={() => handleDeleteApiKey(key.id)}
                          >
                            🗑️ Delete
                          </button>
                        </div>
                      ))}
                      {apiKeys.length === 0 && (
                        <div className="empty-state">
                          <p>No API keys created yet. Create your first API key to get started.</p>
                        </div>
                      )}
    </div>
          </div>
                )}

                <div className="security-info">
                  <div className="info-card">
                    <div className="info-icon">🛡️</div>
                    <div className="info-content">
                      <h4>Account Security</h4>
                      <p>Your account is protected with industry-standard security measures. We recommend enabling two-factor authentication for additional security.</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
        </div>
      </>
  );
};

const ToggleSetting = ({ label, description, active, onToggle }) => (
  <div className="settings-item">
    <div className="settings-info">
      <div className="settings-label">{label}</div>
      <div className="settings-description">{description}</div>
    </div>
    <div
      className={`toggle-switch ${active ? 'active' : ''}`}
      onClick={onToggle}
    />
  </div>
);

const ButtonSetting = ({ label, description, buttonText, type = 'btn-secondary' }) => (
  <div className="settings-item">
    <div className="settings-info">
      <div className="settings-label">{label}</div>
      <div className="settings-description">{description}</div>
    </div>
    <button className={`btn ${type}`}>{buttonText}</button>
  </div>
);

export default SettingsPage;
