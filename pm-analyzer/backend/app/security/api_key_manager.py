"""
API Key Management Service for PM Notification Analyzer.

Provides secure API key generation, validation, and management
for service-to-service authentication.
"""

import os
import secrets
import hashlib
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
import json
import sqlite3
from pathlib import Path

from flask import Flask, request, jsonify, g

logger = logging.getLogger(__name__)


@dataclass
class APIKey:
    """Represents an API key with metadata."""
    key_id: str
    name: str
    key_hash: str  # SHA-256 hash of the actual key
    key_prefix: str  # First 8 chars for identification
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    is_active: bool = True
    scopes: List[str] = field(default_factory=list)
    rate_limit_override: Optional[int] = None  # Custom requests/minute
    ip_whitelist: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_by: Optional[str] = None


@dataclass
class APIKeyConfig:
    """Configuration for API key management."""
    enabled: bool = True
    key_length: int = 32  # Length in bytes (results in 64 char hex string)
    prefix: str = "pmna_"  # Prefix for easy identification
    default_expiry_days: int = 365
    max_keys_per_user: int = 10
    require_ip_whitelist: bool = False


class APIKeyStorage:
    """
    SQLite-based storage for API keys.

    For production, consider using a more robust database.
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            data_dir = Path(__file__).parent.parent.parent / 'data'
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / 'api_keys.db')

        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS api_keys (
                    key_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    key_hash TEXT NOT NULL UNIQUE,
                    key_prefix TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    last_used_at TEXT,
                    is_active INTEGER DEFAULT 1,
                    scopes TEXT,
                    rate_limit_override INTEGER,
                    ip_whitelist TEXT,
                    metadata TEXT,
                    created_by TEXT
                )
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_key_hash ON api_keys(key_hash)
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_key_prefix ON api_keys(key_prefix)
            ''')

            # Create audit log table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS api_key_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    key_id TEXT,
                    action TEXT NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    details TEXT
                )
            ''')

            conn.commit()

    def _row_to_api_key(self, row: tuple) -> APIKey:
        """Convert a database row to an APIKey object."""
        return APIKey(
            key_id=row[0],
            name=row[1],
            key_hash=row[2],
            key_prefix=row[3],
            created_at=datetime.fromisoformat(row[4]),
            expires_at=datetime.fromisoformat(row[5]) if row[5] else None,
            last_used_at=datetime.fromisoformat(row[6]) if row[6] else None,
            is_active=bool(row[7]),
            scopes=json.loads(row[8]) if row[8] else [],
            rate_limit_override=row[9],
            ip_whitelist=json.loads(row[10]) if row[10] else None,
            metadata=json.loads(row[11]) if row[11] else {},
            created_by=row[12]
        )

    def save(self, api_key: APIKey) -> bool:
        """Save or update an API key."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO api_keys
                    (key_id, name, key_hash, key_prefix, created_at, expires_at,
                     last_used_at, is_active, scopes, rate_limit_override,
                     ip_whitelist, metadata, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    api_key.key_id,
                    api_key.name,
                    api_key.key_hash,
                    api_key.key_prefix,
                    api_key.created_at.isoformat(),
                    api_key.expires_at.isoformat() if api_key.expires_at else None,
                    api_key.last_used_at.isoformat() if api_key.last_used_at else None,
                    1 if api_key.is_active else 0,
                    json.dumps(api_key.scopes),
                    api_key.rate_limit_override,
                    json.dumps(api_key.ip_whitelist) if api_key.ip_whitelist else None,
                    json.dumps(api_key.metadata),
                    api_key.created_by
                ))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save API key: {e}")
            return False

    def get_by_hash(self, key_hash: str) -> Optional[APIKey]:
        """Get an API key by its hash."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT * FROM api_keys WHERE key_hash = ?',
                    (key_hash,)
                )
                row = cursor.fetchone()
                if row:
                    return self._row_to_api_key(row)
        except Exception as e:
            logger.error(f"Failed to get API key: {e}")
        return None

    def get_by_prefix(self, prefix: str) -> Optional[APIKey]:
        """Get an API key by its prefix."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT * FROM api_keys WHERE key_prefix = ?',
                    (prefix,)
                )
                row = cursor.fetchone()
                if row:
                    return self._row_to_api_key(row)
        except Exception as e:
            logger.error(f"Failed to get API key by prefix: {e}")
        return None

    def get_by_id(self, key_id: str) -> Optional[APIKey]:
        """Get an API key by its ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT * FROM api_keys WHERE key_id = ?',
                    (key_id,)
                )
                row = cursor.fetchone()
                if row:
                    return self._row_to_api_key(row)
        except Exception as e:
            logger.error(f"Failed to get API key by ID: {e}")
        return None

    def list_all(self, include_inactive: bool = False) -> List[APIKey]:
        """List all API keys."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if include_inactive:
                    cursor = conn.execute('SELECT * FROM api_keys ORDER BY created_at DESC')
                else:
                    cursor = conn.execute('SELECT * FROM api_keys WHERE is_active = 1 ORDER BY created_at DESC')
                return [self._row_to_api_key(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to list API keys: {e}")
            return []

    def list_by_user(self, user_id: str) -> List[APIKey]:
        """List API keys created by a specific user."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT * FROM api_keys WHERE created_by = ? ORDER BY created_at DESC',
                    (user_id,)
                )
                return [self._row_to_api_key(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to list API keys for user: {e}")
            return []

    def delete(self, key_id: str) -> bool:
        """Delete an API key."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('DELETE FROM api_keys WHERE key_id = ?', (key_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete API key: {e}")
            return False

    def update_last_used(self, key_id: str):
        """Update the last_used_at timestamp."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    'UPDATE api_keys SET last_used_at = ? WHERE key_id = ?',
                    (datetime.utcnow().isoformat(), key_id)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to update last used: {e}")

    def log_audit(self, key_id: Optional[str], action: str, details: str = None):
        """Log an audit entry for API key operations."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO api_key_audit (timestamp, key_id, action, ip_address, user_agent, details)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    datetime.utcnow().isoformat(),
                    key_id,
                    action,
                    request.remote_addr if request else None,
                    request.headers.get('User-Agent') if request else None,
                    details
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log audit: {e}")


class APIKeyManager:
    """
    Manager for API key operations.
    """

    def __init__(self, config: Optional[APIKeyConfig] = None, storage: Optional[APIKeyStorage] = None):
        self.config = config or self._load_config()
        self.storage = storage or APIKeyStorage()

    def _load_config(self) -> APIKeyConfig:
        """Load configuration from environment variables."""
        return APIKeyConfig(
            enabled=os.environ.get('API_KEY_ENABLED', 'true').lower() == 'true',
            key_length=int(os.environ.get('API_KEY_LENGTH', '32')),
            prefix=os.environ.get('API_KEY_PREFIX', 'pmna_'),
            default_expiry_days=int(os.environ.get('API_KEY_EXPIRY_DAYS', '365')),
            max_keys_per_user=int(os.environ.get('API_KEY_MAX_PER_USER', '10')),
            require_ip_whitelist=os.environ.get('API_KEY_REQUIRE_IP_WHITELIST', 'false').lower() == 'true'
        )

    def generate_key(
        self,
        name: str,
        created_by: str,
        scopes: List[str] = None,
        expires_in_days: int = None,
        ip_whitelist: List[str] = None,
        rate_limit_override: int = None,
        metadata: Dict[str, Any] = None
    ) -> tuple[str, APIKey]:
        """
        Generate a new API key.

        Returns: (raw_key, api_key_object)
        The raw key is returned only once and cannot be recovered.
        """
        # Check user's key limit
        user_keys = self.storage.list_by_user(created_by)
        if len(user_keys) >= self.config.max_keys_per_user:
            raise ValueError(f"Maximum number of API keys ({self.config.max_keys_per_user}) reached")

        # Generate secure random key
        raw_key_bytes = secrets.token_bytes(self.config.key_length)
        raw_key_hex = raw_key_bytes.hex()
        raw_key = f"{self.config.prefix}{raw_key_hex}"

        # Hash the key for storage
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        # Create key prefix for identification
        key_prefix = raw_key[:8 + len(self.config.prefix)]

        # Calculate expiry
        expires_at = None
        if expires_in_days is not None:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        elif self.config.default_expiry_days > 0:
            expires_at = datetime.utcnow() + timedelta(days=self.config.default_expiry_days)

        # Generate unique key ID
        key_id = f"key_{secrets.token_hex(8)}"

        api_key = APIKey(
            key_id=key_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            scopes=scopes or ['read'],
            ip_whitelist=ip_whitelist,
            rate_limit_override=rate_limit_override,
            metadata=metadata or {},
            created_by=created_by
        )

        # Save to storage
        if not self.storage.save(api_key):
            raise RuntimeError("Failed to save API key")

        # Log the creation
        self.storage.log_audit(key_id, 'create', f"Key created by {created_by}")

        logger.info(f"API key created: {key_id} by {created_by}")

        return raw_key, api_key

    def validate_key(self, raw_key: str) -> Optional[APIKey]:
        """
        Validate an API key and return the key object if valid.

        Returns None if the key is invalid, expired, or revoked.
        """
        if not raw_key:
            return None

        # Check prefix
        if not raw_key.startswith(self.config.prefix):
            return None

        # Hash the key
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        # Look up in storage
        api_key = self.storage.get_by_hash(key_hash)

        if not api_key:
            self.storage.log_audit(None, 'validate_failed', 'Key not found')
            return None

        # Check if active
        if not api_key.is_active:
            self.storage.log_audit(api_key.key_id, 'validate_failed', 'Key is inactive')
            return None

        # Check expiry
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            self.storage.log_audit(api_key.key_id, 'validate_failed', 'Key expired')
            return None

        # Check IP whitelist
        if api_key.ip_whitelist:
            client_ip = request.remote_addr if request else None
            if client_ip and client_ip not in api_key.ip_whitelist:
                self.storage.log_audit(api_key.key_id, 'validate_failed', f'IP {client_ip} not whitelisted')
                return None

        # Update last used
        self.storage.update_last_used(api_key.key_id)

        return api_key

    def revoke_key(self, key_id: str, revoked_by: str) -> bool:
        """Revoke (deactivate) an API key."""
        api_key = self.storage.get_by_id(key_id)
        if not api_key:
            return False

        api_key.is_active = False
        if self.storage.save(api_key):
            self.storage.log_audit(key_id, 'revoke', f"Revoked by {revoked_by}")
            logger.info(f"API key revoked: {key_id} by {revoked_by}")
            return True
        return False

    def delete_key(self, key_id: str, deleted_by: str) -> bool:
        """Permanently delete an API key."""
        if self.storage.delete(key_id):
            self.storage.log_audit(key_id, 'delete', f"Deleted by {deleted_by}")
            logger.info(f"API key deleted: {key_id} by {deleted_by}")
            return True
        return False

    def list_keys(self, user_id: str = None, include_inactive: bool = False) -> List[APIKey]:
        """List API keys, optionally filtered by user."""
        if user_id:
            return self.storage.list_by_user(user_id)
        return self.storage.list_all(include_inactive)

    def has_scope(self, api_key: APIKey, required_scope: str) -> bool:
        """Check if an API key has a required scope."""
        if 'admin' in api_key.scopes:
            return True
        if '*' in api_key.scopes:
            return True
        return required_scope in api_key.scopes


# Global API key manager instance
_api_key_manager: Optional[APIKeyManager] = None


def get_api_key_manager() -> APIKeyManager:
    """Get or create the global API key manager instance."""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


def register_api_key_auth(app: Flask) -> bool:
    """
    Register API key authentication middleware.

    Returns True if API key auth is enabled.
    """
    manager = get_api_key_manager()

    if not manager.config.enabled:
        logger.info("API key authentication is DISABLED")
        return False

    @app.before_request
    def check_api_key():
        # Skip for health checks
        if request.path in ['/health', '/favicon.ico']:
            return None

        # Check for API key in header
        api_key_header = request.headers.get('X-API-Key')

        if api_key_header:
            api_key = manager.validate_key(api_key_header)
            if api_key:
                # Store key info in request context
                g.api_key = api_key
                g.auth_method = 'api_key'

                # Create a pseudo-user for compatibility with existing auth
                g.current_user = {
                    'user_id': f"apikey:{api_key.key_id}",
                    'email': api_key.metadata.get('email', f"{api_key.key_id}@api"),
                    'roles': api_key.scopes,
                    'is_api_key': True
                }

    logger.info("API key authentication enabled")
    return True


def require_api_key(scope: str = None):
    """
    Decorator to require API key authentication with optional scope.

    Usage:
        @app.route('/api/service-endpoint')
        @require_api_key(scope='write')
        def service_endpoint():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            manager = get_api_key_manager()

            if not manager.config.enabled:
                return f(*args, **kwargs)

            # Check for API key
            if not hasattr(g, 'api_key') or not g.api_key:
                return jsonify({
                    'error': {
                        'code': 'API_KEY_REQUIRED',
                        'message': 'API key is required for this endpoint'
                    }
                }), 401

            # Check scope if required
            if scope and not manager.has_scope(g.api_key, scope):
                return jsonify({
                    'error': {
                        'code': 'INSUFFICIENT_SCOPE',
                        'message': f'API key does not have required scope: {scope}'
                    }
                }), 403

            return f(*args, **kwargs)
        return decorated
    return decorator
