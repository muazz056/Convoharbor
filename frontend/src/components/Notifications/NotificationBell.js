// frontend/src/components/Notifications/NotificationBell.js

import React, { useState, useEffect, useRef } from 'react';
import notificationService from '../../services/notification.service';
import './NotificationBell.css';

const NotificationBell = () => {
    const [notifications, setNotifications] = useState([]);
    const [unreadCount, setUnreadCount] = useState(0);
    const [isOpen, setIsOpen] = useState(false);
    const [loading, setLoading] = useState(false);
    const dropdownRef = useRef(null);

    // Load notifications on component mount
    useEffect(() => {
        loadNotifications();
        
        // Set up polling for new notifications every 30 seconds
        const interval = setInterval(loadNotifications, 30000);
        
        return () => clearInterval(interval);
    }, []);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const loadNotifications = async () => {
        try {
            setLoading(true);
            const response = await notificationService.getNotifications({ limit: 20 });
            setNotifications(response.notifications || []);
            setUnreadCount(response.unread_count || 0);
        } catch (error) {
            console.error('Failed to load notifications:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleNotificationClick = async (notification) => {
        if (!notification.read_at) {
            try {
                await notificationService.markAsRead(notification.id);
                // Update local state
                setNotifications(prev => 
                    prev.map(n => 
                        n.id === notification.id 
                            ? { ...n, read_at: new Date().toISOString(), status: 'read' }
                            : n
                    )
                );
                setUnreadCount(prev => Math.max(0, prev - 1));
            } catch (error) {
                console.error('Failed to mark notification as read:', error);
            }
        }
    };

    const handleMarkAllRead = async () => {
        try {
            await notificationService.markAllAsRead();
            setNotifications(prev => 
                prev.map(n => ({ 
                    ...n, 
                    read_at: n.read_at || new Date().toISOString(),
                    status: 'read'
                }))
            );
            setUnreadCount(0);
        } catch (error) {
            console.error('Failed to mark all notifications as read:', error);
        }
    };

    const formatTimeAgo = (dateString) => {
        return notificationService.getTimeAgo(dateString);
    };

    const getPriorityClass = (priority) => {
        switch (priority) {
            case 'urgent': return 'priority-urgent';
            case 'high': return 'priority-high';
            case 'normal': return 'priority-normal';
            case 'low': return 'priority-low';
            default: return 'priority-normal';
        }
    };

    const getCategoryIcon = (category) => {
        return notificationService.getCategoryIcon(category);
    };

    return (
        <div className="notification-bell" ref={dropdownRef}>
            <button 
                className="notification-bell-button"
                onClick={() => setIsOpen(!isOpen)}
                aria-label={`Notifications (${unreadCount} unread)`}
            >
                <span className="bell-icon">🔔</span>
                {unreadCount > 0 && (
                    <span className="notification-badge">
                        {unreadCount > 99 ? '99+' : unreadCount}
                    </span>
                )}
            </button>

            {isOpen && (
                <div className="notification-dropdown">
                    <div className="notification-header">
                        <h3>Notifications</h3>
                        {unreadCount > 0 && (
                            <button 
                                className="mark-all-read-btn"
                                onClick={handleMarkAllRead}
                            >
                                Mark all read
                            </button>
                        )}
                    </div>

                    <div className="notification-list">
                        {loading ? (
                            <div className="notification-loading">
                                <div className="loading-spinner"></div>
                                <span>Loading notifications...</span>
                            </div>
                        ) : notifications.length === 0 ? (
                            <div className="no-notifications">
                                <span className="no-notifications-icon">📭</span>
                                <p>No notifications yet</p>
                            </div>
                        ) : (
                            notifications.map((notification) => (
                                <div
                                    key={notification.id}
                                    className={`notification-item ${!notification.read_at ? 'unread' : ''} ${getPriorityClass(notification.priority)}`}
                                    onClick={() => handleNotificationClick(notification)}
                                >
                                    <div className="notification-icon">
                                        {getCategoryIcon(notification.category)}
                                    </div>
                                    <div className="notification-content">
                                        <div className="notification-title">
                                            {notification.title}
                                        </div>
                                        <div className="notification-message">
                                            {notification.message}
                                        </div>
                                        <div className="notification-time">
                                            {formatTimeAgo(notification.created_at)}
                                        </div>
                                    </div>
                                    {!notification.read_at && (
                                        <div className="unread-indicator"></div>
                                    )}
                                </div>
                            ))
                        )}
                    </div>

                    {notifications.length > 0 && (
                        <div className="notification-footer">
                            <button 
                                className="view-all-btn"
                                onClick={() => {
                                    setIsOpen(false);
                                    // Navigate to full notifications page
                                    window.location.href = '/notifications';
                                }}
                            >
                                View all notifications
                            </button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default NotificationBell;
