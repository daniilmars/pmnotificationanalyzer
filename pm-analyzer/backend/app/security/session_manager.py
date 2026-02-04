"""
Session Management Service for PM Notification Analyzer.

Provides enhanced session management including:
- Session tracking and limiting
- Forced logout/session invalidation
- Concurrent session control
- Session activity monitoring
"""

import os
import logging
import secrets
import hashlib
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import sqlite3
from pathlib import Path
import threading

from flask import Flask, request, jsonify, g

logger = logging.getLogger(__name__)


@dataclass
class SessionConfig:
    """Configuration for session management."""
    enabled: bool = True

    # Session limits
    max_concurrent_sessions: int = 5
    session_timeout_minutes: int = 60
    absolute_timeout_hours: int = 24

    # Security settings
    enforce_single_session: bool = False  # Allow only one active session
    invalidate_on_password_change: bool = True
    invalidate_on_role_change: bool = True

    # Tracking
    track_session_activity: bool = True
    activity_log_interval_seconds: int = 300  # Log activity every 5 minutes

    # Cleanup
    cleanup_interval_seconds: int = 3600


@dataclass
class Session:
    """Represents a user session."""
    session_id: str
    user_id: str
    user_email: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_info: Optional[str] = None
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class SessionStorage:
    """
    SQLite-based storage for session data.
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            data_dir = Path(__file__).parent.parent.parent / 'data'
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / 'sessions.db')

        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    user_email TEXT,
                    created_at TEXT NOT NULL,
                    last_activity TEXT NOT NULL,
                    expires_at TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    device_info TEXT,
                    is_active INTEGER DEFAULT 1,
                    metadata TEXT
                )
            ''')

            conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(is_active)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)')

            # Session activity log
            conn.execute('''
                CREATE TABLE IF NOT EXISTS session_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    endpoint TEXT,
                    ip_address TEXT,
                    details TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            ''')

            conn.execute('CREATE INDEX IF NOT EXISTS idx_activity_session ON session_activity(session_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON session_activity(timestamp)')

            conn.commit()

    def save(self, session: Session) -> bool:
        """Save or update a session."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO sessions
                    (session_id, user_id, user_email, created_at, last_activity, expires_at,
                     ip_address, user_agent, device_info, is_active, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    session.session_id,
                    session.user_id,
                    session.user_email,
                    session.created_at.isoformat(),
                    session.last_activity.isoformat(),
                    session.expires_at.isoformat() if session.expires_at else None,
                    session.ip_address,
                    session.user_agent,
                    session.device_info,
                    1 if session.is_active else 0,
                    json.dumps(session.metadata)
                ))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return False

    def get(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT * FROM sessions WHERE session_id = ?',
                    (session_id,)
                )
                row = cursor.fetchone()
                if row:
                    return Session(
                        session_id=row[0],
                        user_id=row[1],
                        user_email=row[2],
                        created_at=datetime.fromisoformat(row[3]),
                        last_activity=datetime.fromisoformat(row[4]),
                        expires_at=datetime.fromisoformat(row[5]) if row[5] else None,
                        ip_address=row[6],
                        user_agent=row[7],
                        device_info=row[8],
                        is_active=bool(row[9]),
                        metadata=json.loads(row[10]) if row[10] else {}
                    )
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
        return None

    def get_user_sessions(self, user_id: str, active_only: bool = True) -> List[Session]:
        """Get all sessions for a user."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if active_only:
                    cursor = conn.execute(
                        'SELECT * FROM sessions WHERE user_id = ? AND is_active = 1 ORDER BY last_activity DESC',
                        (user_id,)
                    )
                else:
                    cursor = conn.execute(
                        'SELECT * FROM sessions WHERE user_id = ? ORDER BY last_activity DESC',
                        (user_id,)
                    )

                sessions = []
                for row in cursor.fetchall():
                    sessions.append(Session(
                        session_id=row[0],
                        user_id=row[1],
                        user_email=row[2],
                        created_at=datetime.fromisoformat(row[3]),
                        last_activity=datetime.fromisoformat(row[4]),
                        expires_at=datetime.fromisoformat(row[5]) if row[5] else None,
                        ip_address=row[6],
                        user_agent=row[7],
                        device_info=row[8],
                        is_active=bool(row[9]),
                        metadata=json.loads(row[10]) if row[10] else {}
                    ))
                return sessions
        except Exception as e:
            logger.error(f"Failed to get user sessions: {e}")
            return []

    def count_active_sessions(self, user_id: str) -> int:
        """Count active sessions for a user."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT COUNT(*) FROM sessions WHERE user_id = ? AND is_active = 1',
                    (user_id,)
                )
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Failed to count sessions: {e}")
            return 0

    def invalidate(self, session_id: str) -> bool:
        """Invalidate a session."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    'UPDATE sessions SET is_active = 0 WHERE session_id = ?',
                    (session_id,)
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to invalidate session: {e}")
            return False

    def invalidate_user_sessions(self, user_id: str, except_session: str = None) -> int:
        """Invalidate all sessions for a user."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if except_session:
                    cursor = conn.execute(
                        'UPDATE sessions SET is_active = 0 WHERE user_id = ? AND session_id != ?',
                        (user_id, except_session)
                    )
                else:
                    cursor = conn.execute(
                        'UPDATE sessions SET is_active = 0 WHERE user_id = ?',
                        (user_id,)
                    )
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Failed to invalidate user sessions: {e}")
            return 0

    def update_activity(self, session_id: str) -> bool:
        """Update the last activity timestamp."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    'UPDATE sessions SET last_activity = ? WHERE session_id = ?',
                    (datetime.utcnow().isoformat(), session_id)
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update activity: {e}")
            return False

    def log_activity(self, session_id: str, action: str, endpoint: str = None, details: str = None):
        """Log session activity."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO session_activity (session_id, timestamp, action, endpoint, ip_address, details)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    session_id,
                    datetime.utcnow().isoformat(),
                    action,
                    endpoint,
                    request.remote_addr if request else None,
                    details
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log activity: {e}")

    def get_activity(self, session_id: str, limit: int = 100) -> List[Dict]:
        """Get activity log for a session."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT timestamp, action, endpoint, ip_address, details '
                    'FROM session_activity WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?',
                    (session_id, limit)
                )
                return [
                    {
                        'timestamp': row[0],
                        'action': row[1],
                        'endpoint': row[2],
                        'ip_address': row[3],
                        'details': row[4]
                    }
                    for row in cursor.fetchall()
                ]
        except Exception as e:
            logger.error(f"Failed to get activity: {e}")
            return []

    def cleanup_expired(self) -> int:
        """Remove expired sessions."""
        try:
            now = datetime.utcnow().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'UPDATE sessions SET is_active = 0 WHERE expires_at < ? AND is_active = 1',
                    (now,)
                )
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")
            return 0


class SessionManager:
    """
    Session manager with concurrent session control.
    """

    def __init__(self, config: Optional[SessionConfig] = None, storage: Optional[SessionStorage] = None):
        self.config = config or self._load_config()
        self.storage = storage or SessionStorage()
        self._cleanup_thread = None
        self._running = False
        self._last_activity_log: Dict[str, datetime] = {}

    def _load_config(self) -> SessionConfig:
        """Load configuration from environment variables."""
        return SessionConfig(
            enabled=os.environ.get('SESSION_MANAGEMENT_ENABLED', 'true').lower() == 'true',
            max_concurrent_sessions=int(os.environ.get('SESSION_MAX_CONCURRENT', '5')),
            session_timeout_minutes=int(os.environ.get('SESSION_TIMEOUT_MINUTES', '60')),
            absolute_timeout_hours=int(os.environ.get('SESSION_ABSOLUTE_TIMEOUT_HOURS', '24')),
            enforce_single_session=os.environ.get('SESSION_SINGLE_ONLY', 'false').lower() == 'true'
        )

    def _generate_session_id(self) -> str:
        """Generate a secure session ID."""
        return secrets.token_urlsafe(32)

    def _parse_user_agent(self, user_agent: str) -> str:
        """Parse user agent to extract device info."""
        if not user_agent:
            return 'Unknown'

        # Simple parsing - could be enhanced with a proper UA parser
        if 'Mobile' in user_agent or 'Android' in user_agent or 'iPhone' in user_agent:
            device_type = 'Mobile'
        elif 'Tablet' in user_agent or 'iPad' in user_agent:
            device_type = 'Tablet'
        else:
            device_type = 'Desktop'

        if 'Chrome' in user_agent:
            browser = 'Chrome'
        elif 'Firefox' in user_agent:
            browser = 'Firefox'
        elif 'Safari' in user_agent:
            browser = 'Safari'
        elif 'Edge' in user_agent:
            browser = 'Edge'
        else:
            browser = 'Other'

        return f"{device_type} - {browser}"

    def create_session(
        self,
        user_id: str,
        user_email: str = None,
        metadata: Dict = None
    ) -> Optional[Session]:
        """
        Create a new session for a user.

        Enforces concurrent session limits.
        """
        if not self.config.enabled:
            return None

        # Check concurrent session limit
        active_count = self.storage.count_active_sessions(user_id)

        if self.config.enforce_single_session and active_count > 0:
            # Invalidate existing sessions
            self.storage.invalidate_user_sessions(user_id)
            logger.info(f"Enforced single session for user {user_id}")

        elif active_count >= self.config.max_concurrent_sessions:
            # Invalidate oldest session
            user_sessions = self.storage.get_user_sessions(user_id)
            if user_sessions:
                oldest = user_sessions[-1]  # Sorted by last_activity DESC
                self.storage.invalidate(oldest.session_id)
                logger.info(f"Invalidated oldest session for user {user_id} (limit reached)")

        # Create new session
        session = Session(
            session_id=self._generate_session_id(),
            user_id=user_id,
            user_email=user_email,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=self.config.absolute_timeout_hours),
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get('User-Agent') if request else None,
            device_info=self._parse_user_agent(request.headers.get('User-Agent', '')) if request else None,
            metadata=metadata or {}
        )

        if self.storage.save(session):
            self.storage.log_activity(session.session_id, 'session_created')
            logger.info(f"Session created for user {user_id}: {session.session_id[:8]}...")
            return session

        return None

    def validate_session(self, session_id: str) -> Optional[Session]:
        """
        Validate a session and update activity.

        Returns the session if valid, None otherwise.
        """
        if not self.config.enabled:
            return None

        session = self.storage.get(session_id)

        if not session:
            return None

        if not session.is_active:
            return None

        # Check expiration
        now = datetime.utcnow()
        if session.expires_at and session.expires_at < now:
            self.storage.invalidate(session_id)
            return None

        # Check inactivity timeout
        inactivity_limit = session.last_activity + timedelta(minutes=self.config.session_timeout_minutes)
        if now > inactivity_limit:
            self.storage.invalidate(session_id)
            self.storage.log_activity(session_id, 'session_timeout')
            return None

        # Update activity
        self.storage.update_activity(session_id)

        # Log activity periodically
        if self.config.track_session_activity:
            last_log = self._last_activity_log.get(session_id)
            if not last_log or (now - last_log).seconds >= self.config.activity_log_interval_seconds:
                self.storage.log_activity(
                    session_id,
                    'activity',
                    request.path if request else None
                )
                self._last_activity_log[session_id] = now

        return session

    def invalidate_session(self, session_id: str, reason: str = 'logout') -> bool:
        """Invalidate a specific session."""
        if self.storage.invalidate(session_id):
            self.storage.log_activity(session_id, f'session_invalidated:{reason}')
            logger.info(f"Session invalidated: {session_id[:8]}... ({reason})")
            return True
        return False

    def invalidate_user_sessions(self, user_id: str, reason: str = 'forced_logout', except_current: str = None) -> int:
        """Invalidate all sessions for a user."""
        count = self.storage.invalidate_user_sessions(user_id, except_current)
        if count > 0:
            logger.info(f"Invalidated {count} sessions for user {user_id} ({reason})")
        return count

    def get_user_sessions(self, user_id: str) -> List[Session]:
        """Get all active sessions for a user."""
        return self.storage.get_user_sessions(user_id, active_only=True)

    def get_session_activity(self, session_id: str, limit: int = 100) -> List[Dict]:
        """Get activity log for a session."""
        return self.storage.get_activity(session_id, limit)

    def start_cleanup_thread(self):
        """Start background cleanup thread."""
        if self._running:
            return

        self._running = True

        def cleanup_loop():
            while self._running:
                threading.Event().wait(self.config.cleanup_interval_seconds)
                expired = self.storage.cleanup_expired()
                if expired > 0:
                    logger.info(f"Cleaned up {expired} expired sessions")

        self._cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self._cleanup_thread.start()
        logger.debug("Session cleanup thread started")

    def stop_cleanup_thread(self):
        """Stop the cleanup thread."""
        self._running = False


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get or create the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
        _session_manager.start_cleanup_thread()
    return _session_manager


def register_session_manager(app: Flask) -> bool:
    """
    Register session management middleware.

    Returns True if session management is enabled.
    """
    manager = get_session_manager()

    if not manager.config.enabled:
        logger.info("Session management is DISABLED")
        return False

    @app.before_request
    def check_session():
        # Skip for health checks and public endpoints
        if request.path in ['/health', '/favicon.ico', '/api/docs', '/api/redoc']:
            return None

        # Check for session token in header
        session_token = request.headers.get('X-Session-Token')

        if session_token:
            session = manager.validate_session(session_token)
            if session:
                g.session = session
                g.session_id = session.session_id
            else:
                # Invalid or expired session
                return jsonify({
                    'error': {
                        'code': 'SESSION_INVALID',
                        'message': 'Session is invalid or expired'
                    }
                }), 401

    logger.info(f"Session management enabled (max {manager.config.max_concurrent_sessions} concurrent)")
    return True
