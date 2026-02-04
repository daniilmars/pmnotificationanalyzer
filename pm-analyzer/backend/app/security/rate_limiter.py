"""
Rate Limiting Middleware for PM Notification Analyzer.

Provides configurable rate limiting to prevent API abuse.
Supports per-user, per-IP, and per-endpoint limits.
"""

import os
import time
import logging
from typing import Dict, Optional, Tuple, Callable
from functools import wraps
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import threading
import hashlib

from flask import Flask, request, jsonify, g

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    enabled: bool = True

    # Default limits (requests per window)
    default_requests_per_minute: int = 60
    default_requests_per_hour: int = 1000
    default_requests_per_day: int = 10000

    # Endpoint-specific limits (more restrictive for expensive operations)
    analysis_requests_per_minute: int = 10
    report_requests_per_minute: int = 5
    sap_sync_requests_per_hour: int = 10

    # Authentication endpoint limits (prevent brute force)
    auth_requests_per_minute: int = 10
    auth_requests_per_hour: int = 100

    # Burst allowance (temporary spike handling)
    burst_multiplier: float = 1.5

    # Cleanup interval for expired entries
    cleanup_interval_seconds: int = 300

    # Response headers
    include_headers: bool = True

    # Whitelist (bypass rate limiting)
    whitelisted_ips: list = field(default_factory=list)
    whitelisted_api_keys: list = field(default_factory=list)


@dataclass
class RateLimitEntry:
    """Tracks rate limit state for a single key."""
    request_count: int = 0
    window_start: float = 0.0
    blocked_until: Optional[float] = None


class RateLimitStorage:
    """
    In-memory storage for rate limit tracking.

    For production, consider using Redis for distributed rate limiting.
    """

    def __init__(self):
        self._data: Dict[str, Dict[str, RateLimitEntry]] = defaultdict(dict)
        self._lock = threading.Lock()
        self._last_cleanup = time.time()

    def get_entry(self, key: str, window: str) -> RateLimitEntry:
        """Get or create a rate limit entry."""
        with self._lock:
            if window not in self._data[key]:
                self._data[key][window] = RateLimitEntry(
                    request_count=0,
                    window_start=time.time()
                )
            return self._data[key][window]

    def increment(self, key: str, window: str, window_seconds: int) -> Tuple[int, float]:
        """
        Increment request count and return (count, remaining_time).

        Implements sliding window algorithm.
        """
        with self._lock:
            now = time.time()

            if window not in self._data[key]:
                self._data[key][window] = RateLimitEntry(
                    request_count=1,
                    window_start=now
                )
                return 1, window_seconds

            entry = self._data[key][window]

            # Check if window has expired
            elapsed = now - entry.window_start
            if elapsed >= window_seconds:
                # Reset window
                entry.request_count = 1
                entry.window_start = now
                return 1, window_seconds

            # Increment count
            entry.request_count += 1
            remaining = window_seconds - elapsed

            return entry.request_count, remaining

    def is_blocked(self, key: str) -> Tuple[bool, float]:
        """Check if a key is currently blocked."""
        with self._lock:
            for window_data in self._data.get(key, {}).values():
                if window_data.blocked_until and window_data.blocked_until > time.time():
                    return True, window_data.blocked_until - time.time()
            return False, 0

    def block(self, key: str, duration_seconds: int):
        """Block a key for a specified duration."""
        with self._lock:
            if 'block' not in self._data[key]:
                self._data[key]['block'] = RateLimitEntry()
            self._data[key]['block'].blocked_until = time.time() + duration_seconds

    def cleanup(self, max_age_seconds: int = 3600):
        """Remove expired entries to prevent memory growth."""
        with self._lock:
            now = time.time()
            keys_to_remove = []

            for key, windows in self._data.items():
                windows_to_remove = []
                for window, entry in windows.items():
                    # Remove if window is old and not blocked
                    if (now - entry.window_start > max_age_seconds and
                        (not entry.blocked_until or entry.blocked_until < now)):
                        windows_to_remove.append(window)

                for window in windows_to_remove:
                    del windows[window]

                if not windows:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._data[key]

            if keys_to_remove:
                logger.debug(f"Rate limiter cleanup: removed {len(keys_to_remove)} expired keys")


class RateLimiter:
    """
    Rate limiter implementation with multiple window support.
    """

    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or self._load_config()
        self.storage = RateLimitStorage()
        self._cleanup_thread = None
        self._running = False

    def _load_config(self) -> RateLimitConfig:
        """Load configuration from environment variables."""
        return RateLimitConfig(
            enabled=os.environ.get('RATE_LIMIT_ENABLED', 'true').lower() == 'true',
            default_requests_per_minute=int(os.environ.get('RATE_LIMIT_PER_MINUTE', '60')),
            default_requests_per_hour=int(os.environ.get('RATE_LIMIT_PER_HOUR', '1000')),
            default_requests_per_day=int(os.environ.get('RATE_LIMIT_PER_DAY', '10000')),
            analysis_requests_per_minute=int(os.environ.get('RATE_LIMIT_ANALYSIS_PER_MINUTE', '10')),
            report_requests_per_minute=int(os.environ.get('RATE_LIMIT_REPORT_PER_MINUTE', '5')),
            whitelisted_ips=os.environ.get('RATE_LIMIT_WHITELIST_IPS', '').split(',') if os.environ.get('RATE_LIMIT_WHITELIST_IPS') else []
        )

    def _get_client_identifier(self) -> str:
        """
        Get a unique identifier for the client.

        Priority: authenticated user > API key > IP address
        """
        # Check for authenticated user
        if hasattr(g, 'current_user') and g.current_user:
            user_id = g.current_user.get('user_id') or g.current_user.get('email')
            if user_id:
                return f"user:{user_id}"

        # Check for API key
        api_key = request.headers.get('X-API-Key')
        if api_key:
            # Hash the API key for storage
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
            return f"apikey:{key_hash}"

        # Fall back to IP address
        # Handle proxies (X-Forwarded-For)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            # Take the first IP (client IP)
            client_ip = forwarded_for.split(',')[0].strip()
        else:
            client_ip = request.remote_addr or 'unknown'

        return f"ip:{client_ip}"

    def _is_whitelisted(self) -> bool:
        """Check if the current request is whitelisted."""
        # Check IP whitelist
        client_ip = request.remote_addr
        if client_ip in self.config.whitelisted_ips:
            return True

        # Check API key whitelist
        api_key = request.headers.get('X-API-Key')
        if api_key and api_key in self.config.whitelisted_api_keys:
            return True

        return False

    def _get_endpoint_limits(self, endpoint: str) -> Dict[str, Tuple[int, int]]:
        """
        Get rate limits for a specific endpoint.

        Returns: {window_name: (max_requests, window_seconds)}
        """
        # Analysis endpoints (expensive AI operations)
        if '/analyze' in endpoint or '/chat' in endpoint:
            return {
                'minute': (self.config.analysis_requests_per_minute, 60),
                'hour': (self.config.default_requests_per_hour // 2, 3600)
            }

        # Report generation (resource intensive)
        if '/reports/' in endpoint and '/pdf' in endpoint:
            return {
                'minute': (self.config.report_requests_per_minute, 60),
                'hour': (50, 3600)
            }

        # SAP sync (high impact)
        if '/sap/sync' in endpoint:
            return {
                'hour': (self.config.sap_sync_requests_per_hour, 3600),
                'day': (50, 86400)
            }

        # Authentication endpoints
        if '/auth' in endpoint or '/login' in endpoint:
            return {
                'minute': (self.config.auth_requests_per_minute, 60),
                'hour': (self.config.auth_requests_per_hour, 3600)
            }

        # Default limits
        return {
            'minute': (self.config.default_requests_per_minute, 60),
            'hour': (self.config.default_requests_per_hour, 3600),
            'day': (self.config.default_requests_per_day, 86400)
        }

    def check_rate_limit(self) -> Tuple[bool, Optional[Dict]]:
        """
        Check if the current request exceeds rate limits.

        Returns: (allowed, limit_info)
        """
        if not self.config.enabled:
            return True, None

        if self._is_whitelisted():
            return True, None

        client_id = self._get_client_identifier()
        endpoint = request.endpoint or request.path

        # Check if client is blocked
        is_blocked, block_remaining = self.storage.is_blocked(client_id)
        if is_blocked:
            return False, {
                'error': 'Too many requests - temporarily blocked',
                'retry_after': int(block_remaining),
                'blocked': True
            }

        limits = self._get_endpoint_limits(endpoint)

        for window_name, (max_requests, window_seconds) in limits.items():
            key = f"{client_id}:{endpoint}:{window_name}"
            count, remaining_time = self.storage.increment(key, window_name, window_seconds)

            # Allow burst
            effective_limit = int(max_requests * self.config.burst_multiplier)

            if count > effective_limit:
                # Block for escalating duration if repeatedly exceeding
                if count > effective_limit * 2:
                    self.storage.block(client_id, 300)  # 5 minute block
                    logger.warning(f"Rate limit exceeded significantly for {client_id}, blocking for 5 minutes")

                return False, {
                    'error': f'Rate limit exceeded ({window_name})',
                    'limit': max_requests,
                    'remaining': 0,
                    'reset': int(remaining_time),
                    'window': window_name
                }

        # Return current limit info for headers
        minute_key = f"{client_id}:{endpoint}:minute"
        minute_count, minute_remaining = self.storage.increment(minute_key, 'minute', 60)
        minute_limit = limits.get('minute', (self.config.default_requests_per_minute, 60))[0]

        return True, {
            'limit': minute_limit,
            'remaining': max(0, minute_limit - minute_count),
            'reset': int(minute_remaining)
        }

    def start_cleanup_thread(self):
        """Start background thread for cleaning up expired entries."""
        if self._running:
            return

        self._running = True

        def cleanup_loop():
            while self._running:
                time.sleep(self.config.cleanup_interval_seconds)
                self.storage.cleanup()

        self._cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self._cleanup_thread.start()
        logger.info("Rate limiter cleanup thread started")

    def stop_cleanup_thread(self):
        """Stop the cleanup thread."""
        self._running = False


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
        _rate_limiter.start_cleanup_thread()
    return _rate_limiter


def register_rate_limiter(app: Flask) -> bool:
    """
    Register rate limiting middleware with the Flask application.

    Returns True if rate limiting is enabled.
    """
    limiter = get_rate_limiter()

    if not limiter.config.enabled:
        logger.info("Rate limiting is DISABLED")
        return False

    @app.before_request
    def check_rate_limit():
        # Skip rate limiting for health checks and static files
        if request.path in ['/health', '/favicon.ico']:
            return None

        if request.path.startswith('/static'):
            return None

        allowed, limit_info = limiter.check_rate_limit()

        if not allowed:
            response = jsonify({
                'error': {
                    'code': 'RATE_LIMIT_EXCEEDED',
                    'message': limit_info.get('error', 'Rate limit exceeded'),
                    'retry_after': limit_info.get('reset', 60)
                }
            })
            response.status_code = 429

            if limiter.config.include_headers:
                response.headers['Retry-After'] = str(limit_info.get('reset', 60))
                response.headers['X-RateLimit-Limit'] = str(limit_info.get('limit', 0))
                response.headers['X-RateLimit-Remaining'] = '0'
                response.headers['X-RateLimit-Reset'] = str(limit_info.get('reset', 60))

            return response

        # Store limit info for response headers
        g.rate_limit_info = limit_info

    @app.after_request
    def add_rate_limit_headers(response):
        if limiter.config.include_headers and hasattr(g, 'rate_limit_info') and g.rate_limit_info:
            info = g.rate_limit_info
            response.headers['X-RateLimit-Limit'] = str(info.get('limit', 0))
            response.headers['X-RateLimit-Remaining'] = str(info.get('remaining', 0))
            response.headers['X-RateLimit-Reset'] = str(info.get('reset', 0))
        return response

    logger.info(f"Rate limiting enabled: {limiter.config.default_requests_per_minute}/min, {limiter.config.default_requests_per_hour}/hour")
    return True


def rate_limit(requests_per_minute: int = None, requests_per_hour: int = None):
    """
    Decorator for custom rate limits on specific endpoints.

    Usage:
        @app.route('/api/expensive')
        @rate_limit(requests_per_minute=5)
        def expensive_endpoint():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            limiter = get_rate_limiter()

            if not limiter.config.enabled:
                return f(*args, **kwargs)

            client_id = limiter._get_client_identifier()
            endpoint = f.__name__

            # Check custom minute limit
            if requests_per_minute:
                key = f"{client_id}:{endpoint}:custom_minute"
                count, remaining = limiter.storage.increment(key, 'minute', 60)
                if count > requests_per_minute:
                    return jsonify({
                        'error': {
                            'code': 'RATE_LIMIT_EXCEEDED',
                            'message': 'Rate limit exceeded for this endpoint',
                            'retry_after': int(remaining)
                        }
                    }), 429

            # Check custom hour limit
            if requests_per_hour:
                key = f"{client_id}:{endpoint}:custom_hour"
                count, remaining = limiter.storage.increment(key, 'hour', 3600)
                if count > requests_per_hour:
                    return jsonify({
                        'error': {
                            'code': 'RATE_LIMIT_EXCEEDED',
                            'message': 'Rate limit exceeded for this endpoint',
                            'retry_after': int(remaining)
                        }
                    }), 429

            return f(*args, **kwargs)
        return decorated
    return decorator
