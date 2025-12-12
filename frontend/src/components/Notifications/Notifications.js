// frontend/src/components/Notifications/Notifications.js

import React, { useState, useEffect } from 'react';
import { notificationService } from '../../services/notification.service';
import './Notifications.css';

const Notifications = () => {
    const [notifications, setNotifications] = useState([]);
    const [preferences, setPreferences] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [activeTab, setActiveTab] = useState('notifications');

    useEffect(() => {
        loadNotifications();
        loadPreferences();
    }, []);

    const loadNotifications = async () => {
        try {
            setLoading(true);
            const data = await notificationService.getNotifications();
            setNotifications(data.notifications || []);
        } catch (err) {
            setError('Failed to load notifications');
            console.error('Error loading notifications:', err);
        } finally {
            setLoading(false);
        }
    };

    const loadPreferences = async () => {
        try {
            const data = await notificationService.getPreferences();
            setPreferences(data.preferences || {});
        } catch (err) {
            console.error('Error loading preferences:', err);
        }
    };

    const handleMarkAsRead = async (notificationId) => {
        try {
            await notificationService.markAsRead(notificationId);
            setNotifications(prev => 
                prev.map(n => 
                    n.id === notificationId 
                        ? { ...n, read_at: new Date().toISOString() }
                        : n
                )
            );
        } catch (err) {
            console.error('Error marking notification as read:', err);
        }
    };

    const handleUpdatePreferences = async (newPreferences) => {
        try {
            await notificationService.updatePreferences(newPreferences);
            setPreferences(newPreferences);
        } catch (err) {
            console.error('Error updating preferences:', err);
        }
    };

    const handleSendTestNotification = async () => {
        try {
            await notificationService.sendTestNotification();
            loadNotifications(); // Reload to show the test notification
        } catch (err) {
            console.error('Error sending test notification:', err);
        }
    };

    const formatNotification = (notification) => {
        return notificationService.formatNotification(notification);
    };

    if (loading) {
        return (
            <div className="notifications-container">
                <div className="loading">Loading notifications...</div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="notifications-container">
                <div className="error">{error}</div>
            </div>
        );
    }

    return (
        <div className="notifications-container">
            <div className="notifications-header">
                <h2>Notifications</h2>
                <div className="notifications-tabs">
                    <button 
                        className={`tab ${activeTab === 'notifications' ? 'active' : ''}`}
                        onClick={() => setActiveTab('notifications')}
                    >
                        Notifications ({notifications.filter(n => !n.read_at).length})
                    </button>
                    <button 
                        className={`tab ${activeTab === 'preferences' ? 'active' : ''}`}
                        onClick={() => setActiveTab('preferences')}
                    >
                        Preferences
                    </button>
                </div>
            </div>

            {activeTab === 'notifications' && (
                <div className="notifications-list">
                    {notifications.length === 0 ? (
                        <div className="no-notifications">
                            <p>No notifications yet</p>
                            <button 
                                className="test-notification-btn"
                                onClick={handleSendTestNotification}
                            >
                                Send Test Notification
                            </button>
                        </div>
                    ) : (
                        notifications.map(notification => {
                            const formatted = formatNotification(notification);
                            return (
                                <div 
                                    key={notification.id}
                                    className={`notification-item ${formatted.isUnread ? 'unread' : 'read'}`}
                                    onClick={() => handleMarkAsRead(notification.id)}
                                >
                                    <div className="notification-icon">
                                        {formatted.categoryIcon}
                                    </div>
                                    <div className="notification-content">
                                        <div className="notification-title">
                                            {notification.title}
                                        </div>
                                        <div className="notification-message">
                                            {notification.message}
                                        </div>
                                        <div className="notification-meta">
                                            <span className="notification-time">
                                                {formatted.timeAgo}
                                            </span>
                                            <span 
                                                className="notification-priority"
                                                style={{ color: formatted.priorityColor }}
                                            >
                                                {notification.priority}
                                            </span>
                                        </div>
                                    </div>
                                    {formatted.isUnread && (
                                        <div className="unread-indicator"></div>
                                    )}
                                </div>
                            );
                        })
                    )}
                </div>
            )}

            {activeTab === 'preferences' && preferences && (
                <div className="notification-preferences">
                    <h3>Notification Preferences</h3>
                    <div className="preference-group">
                        <label>
                            <input
                                type="checkbox"
                                checked={preferences.conversation_started || false}
                                onChange={(e) => handleUpdatePreferences({
                                    ...preferences,
                                    conversation_started: e.target.checked
                                })}
                            />
                            New conversations started
                        </label>
                    </div>
                    <div className="preference-group">
                        <label>
                            <input
                                type="checkbox"
                                checked={preferences.feedback_received || false}
                                onChange={(e) => handleUpdatePreferences({
                                    ...preferences,
                                    feedback_received: e.target.checked
                                })}
                            />
                            Feedback received
                        </label>
                    </div>
                    <div className="preference-group">
                        <label>
                            <input
                                type="checkbox"
                                checked={preferences.usage_alerts || false}
                                onChange={(e) => handleUpdatePreferences({
                                    ...preferences,
                                    usage_alerts: e.target.checked
                                })}
                            />
                            Usage alerts
                        </label>
                    </div>
                    <div className="preference-group">
                        <label>
                            <input
                                type="checkbox"
                                checked={preferences.weekly_reports || false}
                                onChange={(e) => handleUpdatePreferences({
                                    ...preferences,
                                    weekly_reports: e.target.checked
                                })}
                            />
                            Weekly reports
                        </label>
                    </div>
                    <button 
                        className="test-notification-btn"
                        onClick={handleSendTestNotification}
                    >
                        Send Test Notification
                    </button>
                </div>
            )}
        </div>
    );
};

export default Notifications;
