# backend/app/services/redis_service.py
# Redis Service for caching, rate limiting, session management, and pub/sub
# Initialized on server startup in create_app()

import redis
import json
import time
import pickle
from typing import Optional, Any, List
from flask import current_app


class RedisService:
    """Central Redis service for ConvoPilot.
    
    Provides:
    - Caching (get/set/invalidate with TTL)
    - Rate limiting (sliding window counter)
    - Session management (set/get/delete)
    - Pub/Sub for real-time WebSocket communication
    - Distributed locking
    """

    def __init__(self, redis_url=None, socket_timeout=None, cache_ttl=None, rate_limit=None, app=None):
        self.client = None
        self._redis_url = redis_url
        self._socket_timeout = socket_timeout
        self._cache_ttl = cache_ttl
        self._rate_limit = rate_limit
        self._app = app
        self._init_client()

    def _log(self, level, msg):
        if self._app:
            getattr(self._app.logger, level)(msg)
        else:
            print(f"[Redis] {level.upper()}: {msg}")

    def _init_client(self):
        """Initialize Redis client from config. Fails fast if Redis is unavailable."""
        redis_url = self._redis_url or current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
        socket_timeout = self._socket_timeout or current_app.config.get('REDIS_SOCKET_TIMEOUT', 5)

        try:
            self.client = redis.from_url(
                redis_url,
                socket_timeout=socket_timeout,
                socket_connect_timeout=socket_timeout,
                decode_responses=True,
                health_check_interval=30
            )
            # Verify connection immediately - fail fast
            self.client.ping()
            self._log('info', "Redis initialized and connected successfully")
        except redis.ConnectionError as e:
            self._log('error', f"Redis connection failed: {e}")
            raise RuntimeError(
                f"Redis is required but connection failed at {redis_url}. "
                "Please ensure Redis is running and accessible."
            )
        except Exception as e:
            self._log('error', f"Unexpected Redis initialization error: {e}")
            raise RuntimeError(f"Redis initialization failed: {e}")

    # ============================================================
    # CACHING
    # ============================================================

    def get_cache(self, key: str) -> Optional[Any]:
        """Retrieve a cached value by key. Returns None if not found."""
        try:
            data = self.client.get(f"cache:{key}")
            return json.loads(data) if data else None
        except Exception as e:
            current_app.logger.warning(f"Redis cache get error for '{key}': {e}")
            return None

    def set_cache(self, key: str, value: Any, ttl: int = None) -> bool:
        """Store a value in cache with optional TTL (seconds).
        
        If ttl is None, uses config's REDIS_CACHE_TTL.
        """
        if ttl is None:
            ttl = self._cache_ttl or current_app.config.get('REDIS_CACHE_TTL', 300)
        try:
            self.client.setex(f"cache:{key}", ttl, json.dumps(value))
            return True
        except Exception as e:
            current_app.logger.warning(f"Redis cache set error for '{key}': {e}")
            return False

    def invalidate_cache(self, pattern: str) -> int:
        """Invalidate all cache keys matching a pattern (e.g., 'chatbot:*')."""
        try:
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = self.client.scan(cursor, f"cache:{pattern}", count=100)
                if keys:
                    self.client.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break
            if deleted > 0:
                current_app.logger.info(f"🗑️ Invalidated {deleted} cache keys matching '{pattern}'")
            return deleted
        except Exception as e:
            current_app.logger.warning(f"Redis cache invalidation error for '{pattern}': {e}")
            return 0

    # ============================================================
    # RATE LIMITING
    # ============================================================

    def check_rate_limit(self, key: str, max_requests: int = None, window: int = 60) -> tuple:
        """Check if a request should be rate limited.
        
        Args:
            key: Unique identifier (e.g., IP address, user ID)
            max_requests: Max requests allowed in the window (default from config)
            window: Time window in seconds (default: 60)
            
        Returns:
            Tuple of (allowed: bool, remaining: int, reset_at: float)
                - allowed: True if request is permitted
                - remaining: Number of requests remaining in this window
                - reset_at: Unix timestamp when the window resets
        """
        if max_requests is None:
            max_requests = self._rate_limit or current_app.config.get('REDIS_RATE_LIMIT', 120)

        try:
            now = int(time.time())
            window_start = now - (now % window)
            window_key = f"ratelimit:{key}:{window_start}"

            pipe = self.client.pipeline()
            pipe.incr(window_key)
            pipe.expire(window_key, window + 1)
            count, _ = pipe.execute()

            allowed = count <= max_requests
            remaining = max(0, max_requests - count)
            reset_at = window_start + window

            return allowed, remaining, reset_at
        except Exception as e:
            current_app.logger.warning(f"Redis rate limit check error for '{key}': {e}")
            # Fail open - allow request if Redis is down
            return True, 1, time.time() + window

    def get_rate_limit_headers(self, key: str, max_requests: int = None, window: int = 60) -> dict:
        """Get rate limit headers for API responses."""
        _, remaining, reset_at = self.check_rate_limit(key, max_requests, window)
        return {
            'X-RateLimit-Limit': str(max_requests or current_app.config.get('REDIS_RATE_LIMIT', 120)),
            'X-RateLimit-Remaining': str(remaining),
            'X-RateLimit-Reset': str(reset_at)
        }

    # ============================================================
    # SESSION MANAGEMENT
    # ============================================================

    def set_session(self, session_id: str, data: dict, ttl: int = 86400) -> bool:
        """Store session data with TTL (default: 24 hours)."""
        try:
            self.client.setex(f"session:{session_id}", ttl, json.dumps(data))
            return True
        except Exception as e:
            current_app.logger.warning(f"Redis session set error for '{session_id}': {e}")
            return False

    def get_session(self, session_id: str) -> Optional[dict]:
        """Retrieve session data by session ID."""
        try:
            data = self.client.get(f"session:{session_id}")
            return json.loads(data) if data else None
        except Exception as e:
            current_app.logger.warning(f"Redis session get error for '{session_id}': {e}")
            return None

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        try:
            self.client.delete(f"session:{session_id}")
            return True
        except Exception as e:
            current_app.logger.warning(f"Redis session delete error for '{session_id}': {e}")
            return False

    # ============================================================
    # PUB/SUB (for WebSocket real-time communication)
    # ============================================================

    def publish(self, channel: str, message: dict) -> bool:
        """Publish a message to a Redis channel for real-time updates."""
        try:
            self.client.publish(channel, json.dumps(message))
            return True
        except Exception as e:
            current_app.logger.warning(f"Redis publish error on channel '{channel}': {e}")
            return False

    def get_pubsub_listener(self) -> Optional[redis.client.PubSub]:
        """Get a PubSub listener instance for subscribing to channels."""
        try:
            return self.client.pubsub()
        except Exception as e:
            current_app.logger.warning(f"Redis PubSub listener creation error: {e}")
            return None

    # ============================================================
    # DISTRIBUTED LOCKING
    # ============================================================

    def acquire_lock(self, lock_name: str, timeout: int = 10) -> bool:
        """Acquire a distributed lock with automatic release via TTL.
        
        Args:
            lock_name: Name of the lock
            timeout: Lock TTL in seconds (lock auto-releases after this)
            
        Returns:
            True if lock was acquired, False if already held
        """
        try:
            acquired = self.client.setnx(f"lock:{lock_name}", "locked")
            if acquired:
                self.client.expire(f"lock:{lock_name}", timeout)
                return True
            return False
        except Exception as e:
            current_app.logger.warning(f"Redis lock acquire error for '{lock_name}': {e}")
            return False

    def release_lock(self, lock_name: str) -> bool:
        """Release a distributed lock."""
        try:
            self.client.delete(f"lock:{lock_name}")
            return True
        except Exception as e:
            current_app.logger.warning(f"Redis lock release error for '{lock_name}': {e}")
            return False

    # ============================================================
    # HEALTH CHECK
    # ============================================================

    def is_healthy(self) -> bool:
        """Check if Redis connection is healthy."""
        try:
            return self.client.ping() if self.client else False
        except Exception:
            return False

    def get_info(self) -> dict:
        """Get Redis server info for monitoring."""
        try:
            info = self.client.info()
            return {
                'connected': True,
                'version': info.get('redis_version', 'unknown'),
                'uptime_days': info.get('uptime_in_days', 0),
                'used_memory_human': info.get('used_memory_human', 'unknown'),
                'connected_clients': info.get('connected_clients', 0),
                'total_commands_processed': info.get('total_commands_processed', 0),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
            }
        except Exception as e:
            return {
                'connected': False,
                'error': str(e)
            }