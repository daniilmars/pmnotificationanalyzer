"""
Security Audit Logging Service for PM Notification Analyzer.

Provides comprehensive audit logging for security-relevant events
including authentication, authorization, data access, and administrative actions.
"""

import os
import logging
import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import sqlite3
from pathlib import Path
import hashlib
import threading
from queue import Queue

from flask import Flask, request, g

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of security audit events."""
    # Authentication events
    AUTH_LOGIN_SUCCESS = 'auth.login.success'
    AUTH_LOGIN_FAILURE = 'auth.login.failure'
    AUTH_LOGOUT = 'auth.logout'
    AUTH_TOKEN_REFRESH = 'auth.token.refresh'
    AUTH_TOKEN_REVOKE = 'auth.token.revoke'
    AUTH_MFA_SUCCESS = 'auth.mfa.success'
    AUTH_MFA_FAILURE = 'auth.mfa.failure'

    # Authorization events
    AUTHZ_ACCESS_GRANTED = 'authz.access.granted'
    AUTHZ_ACCESS_DENIED = 'authz.access.denied'
    AUTHZ_ROLE_CHANGE = 'authz.role.change'
    AUTHZ_PERMISSION_CHANGE = 'authz.permission.change'

    # API Key events
    API_KEY_CREATE = 'apikey.create'
    API_KEY_REVOKE = 'apikey.revoke'
    API_KEY_DELETE = 'apikey.delete'
    API_KEY_USE = 'apikey.use'

    # Data access events
    DATA_READ = 'data.read'
    DATA_CREATE = 'data.create'
    DATA_UPDATE = 'data.update'
    DATA_DELETE = 'data.delete'
    DATA_EXPORT = 'data.export'

    # Administrative events
    ADMIN_CONFIG_CHANGE = 'admin.config.change'
    ADMIN_USER_CREATE = 'admin.user.create'
    ADMIN_USER_UPDATE = 'admin.user.update'
    ADMIN_USER_DELETE = 'admin.user.delete'
    ADMIN_IP_WHITELIST_CHANGE = 'admin.ip.whitelist.change'

    # Security events
    SECURITY_RATE_LIMIT = 'security.rate.limit'
    SECURITY_IP_BLOCKED = 'security.ip.blocked'
    SECURITY_SUSPICIOUS_ACTIVITY = 'security.suspicious'
    SECURITY_BRUTE_FORCE = 'security.brute.force'

    # System events
    SYSTEM_STARTUP = 'system.startup'
    SYSTEM_SHUTDOWN = 'system.shutdown'
    SYSTEM_ERROR = 'system.error'


class AuditSeverity(Enum):
    """Severity levels for audit events."""
    DEBUG = 'debug'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'


@dataclass
class AuditEvent:
    """Represents a security audit event."""
    event_id: str
    event_type: AuditEventType
    severity: AuditSeverity
    timestamp: datetime
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    action: Optional[str] = None
    status: str = 'success'
    details: Dict[str, Any] = field(default_factory=dict)
    request_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['event_type'] = self.event_type.value
        result['severity'] = self.severity.value
        result['timestamp'] = self.timestamp.isoformat()
        return result


@dataclass
class AuditConfig:
    """Configuration for audit logging."""
    enabled: bool = True
    log_to_file: bool = True
    log_to_database: bool = True
    log_level: AuditSeverity = AuditSeverity.INFO

    # What to log
    log_auth_events: bool = True
    log_data_access: bool = True
    log_admin_events: bool = True
    log_security_events: bool = True

    # Sensitive data handling
    mask_sensitive_data: bool = True
    sensitive_fields: List[str] = field(default_factory=lambda: [
        'password', 'token', 'api_key', 'secret', 'authorization',
        'credit_card', 'ssn', 'private_key'
    ])

    # Retention
    retention_days: int = 90
    archive_enabled: bool = False

    # Async logging
    async_logging: bool = True
    queue_size: int = 1000


class AuditStorage:
    """
    Storage backend for audit logs.
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            data_dir = Path(__file__).parent.parent.parent / 'data'
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / 'security_audit.db')

        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    user_id TEXT,
                    user_email TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    endpoint TEXT,
                    method TEXT,
                    resource_type TEXT,
                    resource_id TEXT,
                    action TEXT,
                    status TEXT,
                    details TEXT,
                    request_id TEXT
                )
            ''')

            # Create indexes for common queries
            conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_events(user_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events(event_type)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_ip ON audit_events(ip_address)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_events(severity)')

            conn.commit()

    def save(self, event: AuditEvent) -> bool:
        """Save an audit event."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO audit_events
                    (event_id, event_type, severity, timestamp, user_id, user_email,
                     ip_address, user_agent, endpoint, method, resource_type, resource_id,
                     action, status, details, request_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    event.event_id,
                    event.event_type.value,
                    event.severity.value,
                    event.timestamp.isoformat(),
                    event.user_id,
                    event.user_email,
                    event.ip_address,
                    event.user_agent,
                    event.endpoint,
                    event.method,
                    event.resource_type,
                    event.resource_id,
                    event.action,
                    event.status,
                    json.dumps(event.details),
                    event.request_id
                ))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save audit event: {e}")
            return False

    def query(
        self,
        event_type: str = None,
        user_id: str = None,
        ip_address: str = None,
        severity: str = None,
        from_date: datetime = None,
        to_date: datetime = None,
        status: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditEvent]:
        """Query audit events with filters."""
        try:
            conditions = []
            params = []

            if event_type:
                conditions.append('event_type = ?')
                params.append(event_type)
            if user_id:
                conditions.append('user_id = ?')
                params.append(user_id)
            if ip_address:
                conditions.append('ip_address = ?')
                params.append(ip_address)
            if severity:
                conditions.append('severity = ?')
                params.append(severity)
            if from_date:
                conditions.append('timestamp >= ?')
                params.append(from_date.isoformat())
            if to_date:
                conditions.append('timestamp <= ?')
                params.append(to_date.isoformat())
            if status:
                conditions.append('status = ?')
                params.append(status)

            query = 'SELECT * FROM audit_events'
            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)
            query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(query, params)
                events = []
                for row in cursor.fetchall():
                    events.append(AuditEvent(
                        event_id=row[0],
                        event_type=AuditEventType(row[1]),
                        severity=AuditSeverity(row[2]),
                        timestamp=datetime.fromisoformat(row[3]),
                        user_id=row[4],
                        user_email=row[5],
                        ip_address=row[6],
                        user_agent=row[7],
                        endpoint=row[8],
                        method=row[9],
                        resource_type=row[10],
                        resource_id=row[11],
                        action=row[12],
                        status=row[13],
                        details=json.loads(row[14]) if row[14] else {},
                        request_id=row[15]
                    ))
                return events
        except Exception as e:
            logger.error(f"Failed to query audit events: {e}")
            return []

    def get_summary(
        self,
        from_date: datetime = None,
        to_date: datetime = None
    ) -> Dict[str, Any]:
        """Get summary statistics for audit events."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conditions = []
                params = []

                if from_date:
                    conditions.append('timestamp >= ?')
                    params.append(from_date.isoformat())
                if to_date:
                    conditions.append('timestamp <= ?')
                    params.append(to_date.isoformat())

                where_clause = ' WHERE ' + ' AND '.join(conditions) if conditions else ''

                # Total count
                cursor = conn.execute(
                    f'SELECT COUNT(*) FROM audit_events{where_clause}',
                    params
                )
                total_count = cursor.fetchone()[0]

                # Count by event type
                cursor = conn.execute(
                    f'SELECT event_type, COUNT(*) FROM audit_events{where_clause} GROUP BY event_type',
                    params
                )
                by_type = dict(cursor.fetchall())

                # Count by severity
                cursor = conn.execute(
                    f'SELECT severity, COUNT(*) FROM audit_events{where_clause} GROUP BY severity',
                    params
                )
                by_severity = dict(cursor.fetchall())

                # Count by status
                cursor = conn.execute(
                    f'SELECT status, COUNT(*) FROM audit_events{where_clause} GROUP BY status',
                    params
                )
                by_status = dict(cursor.fetchall())

                # Top users
                cursor = conn.execute(
                    f'SELECT user_id, COUNT(*) as cnt FROM audit_events{where_clause} '
                    'WHERE user_id IS NOT NULL GROUP BY user_id ORDER BY cnt DESC LIMIT 10',
                    params
                )
                top_users = dict(cursor.fetchall())

                # Top IPs
                cursor = conn.execute(
                    f'SELECT ip_address, COUNT(*) as cnt FROM audit_events{where_clause} '
                    'WHERE ip_address IS NOT NULL GROUP BY ip_address ORDER BY cnt DESC LIMIT 10',
                    params
                )
                top_ips = dict(cursor.fetchall())

                return {
                    'total_events': total_count,
                    'by_event_type': by_type,
                    'by_severity': by_severity,
                    'by_status': by_status,
                    'top_users': top_users,
                    'top_ips': top_ips,
                    'period': {
                        'from': from_date.isoformat() if from_date else None,
                        'to': to_date.isoformat() if to_date else None
                    }
                }
        except Exception as e:
            logger.error(f"Failed to get audit summary: {e}")
            return {}

    def cleanup_old_events(self, retention_days: int) -> int:
        """Remove events older than retention period."""
        try:
            cutoff = datetime.utcnow() - timedelta(days=retention_days)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'DELETE FROM audit_events WHERE timestamp < ?',
                    (cutoff.isoformat(),)
                )
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Failed to cleanup old events: {e}")
            return 0


class SecurityAuditLogger:
    """
    Main audit logger with async support.
    """

    def __init__(self, config: Optional[AuditConfig] = None, storage: Optional[AuditStorage] = None):
        self.config = config or self._load_config()
        self.storage = storage or AuditStorage()
        self._queue: Optional[Queue] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False

        if self.config.async_logging:
            self._start_async_worker()

    def _load_config(self) -> AuditConfig:
        """Load configuration from environment variables."""
        return AuditConfig(
            enabled=os.environ.get('AUDIT_LOG_ENABLED', 'true').lower() == 'true',
            log_to_file=os.environ.get('AUDIT_LOG_TO_FILE', 'true').lower() == 'true',
            log_to_database=os.environ.get('AUDIT_LOG_TO_DATABASE', 'true').lower() == 'true',
            retention_days=int(os.environ.get('AUDIT_LOG_RETENTION_DAYS', '90')),
            async_logging=os.environ.get('AUDIT_LOG_ASYNC', 'true').lower() == 'true'
        )

    def _start_async_worker(self):
        """Start the async logging worker thread."""
        self._queue = Queue(maxsize=self.config.queue_size)
        self._running = True

        def worker():
            while self._running:
                try:
                    event = self._queue.get(timeout=1)
                    self._persist_event(event)
                    self._queue.task_done()
                except Exception:
                    pass  # Queue timeout or shutdown

        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()
        logger.debug("Audit logger async worker started")

    def _stop_async_worker(self):
        """Stop the async logging worker."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)

    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
        random_part = hashlib.sha256(os.urandom(32)).hexdigest()[:8]
        return f"evt_{timestamp}_{random_part}"

    def _mask_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask sensitive fields in data."""
        if not self.config.mask_sensitive_data:
            return data

        masked = {}
        for key, value in data.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in self.config.sensitive_fields):
                if isinstance(value, str) and len(value) > 4:
                    masked[key] = value[:2] + '*' * (len(value) - 4) + value[-2:]
                else:
                    masked[key] = '***MASKED***'
            elif isinstance(value, dict):
                masked[key] = self._mask_sensitive_data(value)
            else:
                masked[key] = value
        return masked

    def _get_request_context(self) -> Dict[str, Any]:
        """Extract context from the current request."""
        context = {}

        if request:
            context['ip_address'] = request.headers.get('X-Forwarded-For', request.remote_addr)
            context['user_agent'] = request.headers.get('User-Agent')
            context['endpoint'] = request.path
            context['method'] = request.method
            context['request_id'] = request.headers.get('X-Request-ID')

        try:
            if hasattr(g, 'current_user') and g.current_user:
                context['user_id'] = g.current_user.get('user_id')
                context['user_email'] = g.current_user.get('email')
        except RuntimeError:
            pass  # Outside request context (e.g., during startup)

        return context

    def _persist_event(self, event: AuditEvent):
        """Persist an audit event to storage."""
        # Log to database
        if self.config.log_to_database:
            self.storage.save(event)

        # Log to file/standard logging
        if self.config.log_to_file:
            log_level = {
                AuditSeverity.DEBUG: logging.DEBUG,
                AuditSeverity.INFO: logging.INFO,
                AuditSeverity.WARNING: logging.WARNING,
                AuditSeverity.ERROR: logging.ERROR,
                AuditSeverity.CRITICAL: logging.CRITICAL
            }.get(event.severity, logging.INFO)

            logger.log(
                log_level,
                f"AUDIT: {event.event_type.value} | "
                f"user={event.user_id} | "
                f"ip={event.ip_address} | "
                f"status={event.status} | "
                f"resource={event.resource_type}:{event.resource_id}"
            )

    def log(
        self,
        event_type: AuditEventType,
        severity: AuditSeverity = AuditSeverity.INFO,
        resource_type: str = None,
        resource_id: str = None,
        action: str = None,
        status: str = 'success',
        details: Dict[str, Any] = None,
        **kwargs
    ):
        """Log an audit event."""
        if not self.config.enabled:
            return

        # Get request context
        context = self._get_request_context()

        # Create event
        event = AuditEvent(
            event_id=self._generate_event_id(),
            event_type=event_type,
            severity=severity,
            timestamp=datetime.utcnow(),
            user_id=kwargs.get('user_id') or context.get('user_id'),
            user_email=kwargs.get('user_email') or context.get('user_email'),
            ip_address=kwargs.get('ip_address') or context.get('ip_address'),
            user_agent=context.get('user_agent'),
            endpoint=context.get('endpoint'),
            method=context.get('method'),
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            status=status,
            details=self._mask_sensitive_data(details or {}),
            request_id=context.get('request_id')
        )

        # Log asynchronously or synchronously
        if self.config.async_logging and self._queue:
            try:
                self._queue.put_nowait(event)
            except Exception:
                # Queue full, log synchronously
                self._persist_event(event)
        else:
            self._persist_event(event)

    # Convenience methods for common event types
    def log_auth_success(self, user_id: str, user_email: str = None, details: Dict = None):
        """Log successful authentication."""
        self.log(
            AuditEventType.AUTH_LOGIN_SUCCESS,
            AuditSeverity.INFO,
            resource_type='user',
            resource_id=user_id,
            action='login',
            user_id=user_id,
            user_email=user_email,
            details=details
        )

    def log_auth_failure(self, user_id: str = None, reason: str = None, details: Dict = None):
        """Log failed authentication."""
        self.log(
            AuditEventType.AUTH_LOGIN_FAILURE,
            AuditSeverity.WARNING,
            resource_type='user',
            resource_id=user_id,
            action='login',
            status='failure',
            details={'reason': reason, **(details or {})}
        )

    def log_access_denied(self, resource_type: str, resource_id: str, required_permission: str = None):
        """Log access denial."""
        self.log(
            AuditEventType.AUTHZ_ACCESS_DENIED,
            AuditSeverity.WARNING,
            resource_type=resource_type,
            resource_id=resource_id,
            action='access',
            status='denied',
            details={'required_permission': required_permission}
        )

    def log_data_access(self, resource_type: str, resource_id: str, action: str = 'read'):
        """Log data access."""
        self.log(
            AuditEventType.DATA_READ if action == 'read' else AuditEventType.DATA_UPDATE,
            AuditSeverity.INFO,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action
        )

    def log_security_event(self, event_type: AuditEventType, details: Dict = None):
        """Log a security-related event."""
        self.log(
            event_type,
            AuditSeverity.WARNING,
            details=details
        )

    def log_admin_action(self, action: str, resource_type: str, resource_id: str, details: Dict = None):
        """Log an administrative action."""
        self.log(
            AuditEventType.ADMIN_CONFIG_CHANGE,
            AuditSeverity.WARNING,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            details=details
        )

    def query_events(self, **kwargs) -> List[AuditEvent]:
        """Query audit events."""
        return self.storage.query(**kwargs)

    def get_summary(self, from_date: datetime = None, to_date: datetime = None) -> Dict[str, Any]:
        """Get audit summary statistics."""
        return self.storage.get_summary(from_date, to_date)


# Global audit logger instance
_audit_logger: Optional[SecurityAuditLogger] = None


def get_audit_logger() -> SecurityAuditLogger:
    """Get or create the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = SecurityAuditLogger()
    return _audit_logger


def register_audit_logger(app: Flask) -> bool:
    """
    Register audit logging middleware.

    Returns True if audit logging is enabled.
    """
    audit_logger = get_audit_logger()

    if not audit_logger.config.enabled:
        logger.info("Security audit logging is DISABLED")
        return False

    @app.after_request
    def log_request(response):
        # Skip logging for health checks and static files
        if request.path in ['/health', '/favicon.ico']:
            return response
        if request.path.startswith('/static'):
            return response

        # Determine event type based on response status
        if response.status_code >= 400:
            if response.status_code == 401:
                audit_logger.log(
                    AuditEventType.AUTH_LOGIN_FAILURE,
                    AuditSeverity.WARNING,
                    status='failure',
                    details={'status_code': response.status_code}
                )
            elif response.status_code == 403:
                audit_logger.log(
                    AuditEventType.AUTHZ_ACCESS_DENIED,
                    AuditSeverity.WARNING,
                    status='denied',
                    details={'status_code': response.status_code}
                )
            elif response.status_code == 429:
                audit_logger.log(
                    AuditEventType.SECURITY_RATE_LIMIT,
                    AuditSeverity.WARNING,
                    status='rate_limited',
                    details={'status_code': response.status_code}
                )

        return response

    # Log system startup
    audit_logger.log(
        AuditEventType.SYSTEM_STARTUP,
        AuditSeverity.INFO,
        details={'application': 'PM Notification Analyzer'}
    )

    logger.info("Security audit logging enabled")
    return True
