"""
IP Whitelisting Middleware for PM Notification Analyzer.

Provides IP-based access control with support for:
- CIDR notation (e.g., 192.168.1.0/24)
- Individual IPs
- Dynamic whitelist management
- Endpoint-specific restrictions
"""

import os
import logging
import ipaddress
from typing import List, Optional, Set, Dict
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
import json
import sqlite3
from pathlib import Path

from flask import Flask, request, jsonify, g

logger = logging.getLogger(__name__)


@dataclass
class IPWhitelistConfig:
    """Configuration for IP whitelisting."""
    enabled: bool = False  # Disabled by default (opt-in security)
    mode: str = 'allowlist'  # 'allowlist' or 'blocklist'

    # Default allowed IPs (localhost, private networks)
    default_allowed: List[str] = field(default_factory=lambda: [
        '127.0.0.1',
        '::1',
        '10.0.0.0/8',
        '172.16.0.0/12',
        '192.168.0.0/16'
    ])

    # Always allow health checks regardless of IP
    allow_health_checks: bool = True

    # Log blocked attempts
    log_blocked: bool = True

    # Block duration for repeated violations (seconds)
    auto_block_threshold: int = 100  # Violations before auto-block
    auto_block_duration: int = 3600  # 1 hour

    # Admin-only endpoints (more restrictive)
    admin_endpoints: List[str] = field(default_factory=lambda: [
        '/api/configuration',
        '/api/sap/connect',
        '/api/sap/disconnect',
        '/api/sap/sync',
        '/api/alerts/config'
    ])

    # IPs allowed for admin endpoints
    admin_allowed_ips: List[str] = field(default_factory=list)


@dataclass
class IPEntry:
    """Represents an IP whitelist/blocklist entry."""
    ip_or_cidr: str
    description: str = ''
    added_at: datetime = field(default_factory=datetime.utcnow)
    added_by: str = ''
    expires_at: Optional[datetime] = None
    is_admin_only: bool = False


class IPWhitelistStorage:
    """
    SQLite-based storage for IP whitelist entries.
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            data_dir = Path(__file__).parent.parent.parent / 'data'
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / 'ip_whitelist.db')

        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS ip_whitelist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip_or_cidr TEXT NOT NULL UNIQUE,
                    description TEXT,
                    added_at TEXT NOT NULL,
                    added_by TEXT,
                    expires_at TEXT,
                    is_admin_only INTEGER DEFAULT 0,
                    list_type TEXT DEFAULT 'allow'
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS ip_violations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip_address TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    endpoint TEXT,
                    user_agent TEXT,
                    blocked_until TEXT
                )
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_ip_violations_ip ON ip_violations(ip_address)
            ''')

            conn.commit()

    def add_entry(self, entry: IPEntry, list_type: str = 'allow') -> bool:
        """Add an IP to the whitelist or blocklist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO ip_whitelist
                    (ip_or_cidr, description, added_at, added_by, expires_at, is_admin_only, list_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    entry.ip_or_cidr,
                    entry.description,
                    entry.added_at.isoformat(),
                    entry.added_by,
                    entry.expires_at.isoformat() if entry.expires_at else None,
                    1 if entry.is_admin_only else 0,
                    list_type
                ))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to add IP entry: {e}")
            return False

    def remove_entry(self, ip_or_cidr: str) -> bool:
        """Remove an IP from the list."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('DELETE FROM ip_whitelist WHERE ip_or_cidr = ?', (ip_or_cidr,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to remove IP entry: {e}")
            return False

    def get_all_entries(self, list_type: str = 'allow') -> List[IPEntry]:
        """Get all entries of a specific type."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT ip_or_cidr, description, added_at, added_by, expires_at, is_admin_only '
                    'FROM ip_whitelist WHERE list_type = ?',
                    (list_type,)
                )
                entries = []
                for row in cursor.fetchall():
                    entries.append(IPEntry(
                        ip_or_cidr=row[0],
                        description=row[1] or '',
                        added_at=datetime.fromisoformat(row[2]),
                        added_by=row[3] or '',
                        expires_at=datetime.fromisoformat(row[4]) if row[4] else None,
                        is_admin_only=bool(row[5])
                    ))
                return entries
        except Exception as e:
            logger.error(f"Failed to get IP entries: {e}")
            return []

    def log_violation(self, ip_address: str, endpoint: str):
        """Log an access violation."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO ip_violations (ip_address, timestamp, endpoint, user_agent)
                    VALUES (?, ?, ?, ?)
                ''', (
                    ip_address,
                    datetime.utcnow().isoformat(),
                    endpoint,
                    request.headers.get('User-Agent') if request else None
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log violation: {e}")

    def get_violation_count(self, ip_address: str, within_seconds: int = 3600) -> int:
        """Get the number of violations for an IP within a time window."""
        try:
            cutoff = datetime.utcnow().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT COUNT(*) FROM ip_violations WHERE ip_address = ? AND timestamp > ?',
                    (ip_address, cutoff)
                )
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Failed to get violation count: {e}")
            return 0

    def is_auto_blocked(self, ip_address: str) -> bool:
        """Check if an IP is auto-blocked due to violations."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT blocked_until FROM ip_violations '
                    'WHERE ip_address = ? AND blocked_until IS NOT NULL '
                    'ORDER BY blocked_until DESC LIMIT 1',
                    (ip_address,)
                )
                row = cursor.fetchone()
                if row and row[0]:
                    blocked_until = datetime.fromisoformat(row[0])
                    return blocked_until > datetime.utcnow()
        except Exception as e:
            logger.error(f"Failed to check auto-block: {e}")
        return False

    def set_auto_block(self, ip_address: str, duration_seconds: int):
        """Set auto-block for an IP."""
        try:
            blocked_until = datetime.utcnow()
            blocked_until = blocked_until.replace(
                second=blocked_until.second + duration_seconds
            )
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO ip_violations (ip_address, timestamp, endpoint, blocked_until)
                    VALUES (?, ?, 'auto_block', ?)
                ''', (ip_address, datetime.utcnow().isoformat(), blocked_until.isoformat()))
                conn.commit()
            logger.warning(f"IP {ip_address} auto-blocked until {blocked_until}")
        except Exception as e:
            logger.error(f"Failed to set auto-block: {e}")


class IPWhitelist:
    """
    IP whitelist manager with CIDR support.
    """

    def __init__(self, config: Optional[IPWhitelistConfig] = None, storage: Optional[IPWhitelistStorage] = None):
        self.config = config or self._load_config()
        self.storage = storage or IPWhitelistStorage()
        self._compiled_networks: Set[ipaddress.IPv4Network | ipaddress.IPv6Network] = set()
        self._compiled_admin_networks: Set[ipaddress.IPv4Network | ipaddress.IPv6Network] = set()
        self._blocked_ips: Set[str] = set()
        self._reload_rules()

    def _load_config(self) -> IPWhitelistConfig:
        """Load configuration from environment variables."""
        config = IPWhitelistConfig(
            enabled=os.environ.get('IP_WHITELIST_ENABLED', 'false').lower() == 'true',
            mode=os.environ.get('IP_WHITELIST_MODE', 'allowlist'),
            log_blocked=os.environ.get('IP_WHITELIST_LOG_BLOCKED', 'true').lower() == 'true',
            auto_block_threshold=int(os.environ.get('IP_WHITELIST_AUTO_BLOCK_THRESHOLD', '100')),
            auto_block_duration=int(os.environ.get('IP_WHITELIST_AUTO_BLOCK_DURATION', '3600'))
        )

        # Load allowed IPs from environment
        allowed_ips = os.environ.get('IP_WHITELIST_ALLOWED', '')
        if allowed_ips:
            config.default_allowed.extend(allowed_ips.split(','))

        # Load admin IPs from environment
        admin_ips = os.environ.get('IP_WHITELIST_ADMIN_ALLOWED', '')
        if admin_ips:
            config.admin_allowed_ips = admin_ips.split(',')

        return config

    def _reload_rules(self):
        """Reload and compile IP rules."""
        self._compiled_networks.clear()
        self._compiled_admin_networks.clear()
        self._blocked_ips.clear()

        # Add default allowed
        for ip_str in self.config.default_allowed:
            try:
                network = ipaddress.ip_network(ip_str.strip(), strict=False)
                self._compiled_networks.add(network)
            except ValueError as e:
                logger.warning(f"Invalid IP/CIDR in default allowed: {ip_str} - {e}")

        # Add admin allowed
        for ip_str in self.config.admin_allowed_ips:
            try:
                network = ipaddress.ip_network(ip_str.strip(), strict=False)
                self._compiled_admin_networks.add(network)
            except ValueError as e:
                logger.warning(f"Invalid IP/CIDR in admin allowed: {ip_str} - {e}")

        # Load from storage
        for entry in self.storage.get_all_entries('allow'):
            # Skip expired entries
            if entry.expires_at and entry.expires_at < datetime.utcnow():
                continue

            try:
                network = ipaddress.ip_network(entry.ip_or_cidr.strip(), strict=False)
                if entry.is_admin_only:
                    self._compiled_admin_networks.add(network)
                else:
                    self._compiled_networks.add(network)
            except ValueError as e:
                logger.warning(f"Invalid IP/CIDR in storage: {entry.ip_or_cidr} - {e}")

        # Load blocklist
        for entry in self.storage.get_all_entries('block'):
            if entry.expires_at and entry.expires_at < datetime.utcnow():
                continue
            self._blocked_ips.add(entry.ip_or_cidr)

        logger.debug(f"Loaded {len(self._compiled_networks)} allowed networks, "
                     f"{len(self._compiled_admin_networks)} admin networks, "
                     f"{len(self._blocked_ips)} blocked IPs")

    def _get_client_ip(self) -> str:
        """Get the client's IP address, handling proxies."""
        # Check X-Forwarded-For header (from reverse proxy)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            # Take the first IP (original client)
            return forwarded_for.split(',')[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip.strip()

        return request.remote_addr or 'unknown'

    def _is_ip_allowed(self, ip_str: str, networks: Set) -> bool:
        """Check if an IP is in any of the allowed networks."""
        try:
            ip = ipaddress.ip_address(ip_str)
            for network in networks:
                if ip in network:
                    return True
        except ValueError:
            logger.warning(f"Invalid IP address: {ip_str}")
        return False

    def is_allowed(self, endpoint: str = None) -> tuple[bool, str]:
        """
        Check if the current request's IP is allowed.

        Returns: (allowed, reason)
        """
        if not self.config.enabled:
            return True, 'IP whitelist disabled'

        client_ip = self._get_client_ip()

        # Check if auto-blocked
        if self.storage.is_auto_blocked(client_ip):
            return False, 'IP is temporarily blocked due to repeated violations'

        # Check explicit blocklist
        if client_ip in self._blocked_ips:
            return False, 'IP is blocked'

        # Check for CIDR match in blocklist
        for blocked in self._blocked_ips:
            try:
                if '/' in blocked:
                    network = ipaddress.ip_network(blocked, strict=False)
                    if ipaddress.ip_address(client_ip) in network:
                        return False, 'IP is in blocked range'
            except ValueError:
                pass

        # Check if admin endpoint
        is_admin_endpoint = any(
            endpoint and endpoint.startswith(admin_path)
            for admin_path in self.config.admin_endpoints
        )

        if is_admin_endpoint:
            # Must be in admin whitelist
            if self._compiled_admin_networks:
                if not self._is_ip_allowed(client_ip, self._compiled_admin_networks):
                    return False, 'IP not allowed for admin endpoints'
            # If no admin whitelist configured, fall through to regular check

        # Check regular whitelist
        if self.config.mode == 'allowlist':
            if not self._is_ip_allowed(client_ip, self._compiled_networks):
                return False, 'IP not in whitelist'

        return True, 'IP allowed'

    def add_allowed_ip(self, ip_or_cidr: str, description: str = '',
                       added_by: str = '', is_admin_only: bool = False,
                       expires_in_days: int = None) -> bool:
        """Add an IP to the whitelist."""
        # Validate IP/CIDR
        try:
            ipaddress.ip_network(ip_or_cidr, strict=False)
        except ValueError as e:
            logger.error(f"Invalid IP/CIDR: {ip_or_cidr} - {e}")
            return False

        entry = IPEntry(
            ip_or_cidr=ip_or_cidr,
            description=description,
            added_by=added_by,
            is_admin_only=is_admin_only,
            expires_at=datetime.utcnow().replace(
                day=datetime.utcnow().day + expires_in_days
            ) if expires_in_days else None
        )

        if self.storage.add_entry(entry, 'allow'):
            self._reload_rules()
            logger.info(f"Added IP to whitelist: {ip_or_cidr} by {added_by}")
            return True
        return False

    def add_blocked_ip(self, ip_or_cidr: str, description: str = '',
                       added_by: str = '', expires_in_days: int = None) -> bool:
        """Add an IP to the blocklist."""
        try:
            ipaddress.ip_network(ip_or_cidr, strict=False)
        except ValueError as e:
            logger.error(f"Invalid IP/CIDR: {ip_or_cidr} - {e}")
            return False

        entry = IPEntry(
            ip_or_cidr=ip_or_cidr,
            description=description,
            added_by=added_by,
            expires_at=datetime.utcnow().replace(
                day=datetime.utcnow().day + expires_in_days
            ) if expires_in_days else None
        )

        if self.storage.add_entry(entry, 'block'):
            self._reload_rules()
            logger.info(f"Added IP to blocklist: {ip_or_cidr} by {added_by}")
            return True
        return False

    def remove_ip(self, ip_or_cidr: str) -> bool:
        """Remove an IP from the whitelist or blocklist."""
        if self.storage.remove_entry(ip_or_cidr):
            self._reload_rules()
            return True
        return False

    def list_allowed(self) -> List[IPEntry]:
        """List all allowed IPs."""
        return self.storage.get_all_entries('allow')

    def list_blocked(self) -> List[IPEntry]:
        """List all blocked IPs."""
        return self.storage.get_all_entries('block')


# Global IP whitelist instance
_ip_whitelist: Optional[IPWhitelist] = None


def get_ip_whitelist() -> IPWhitelist:
    """Get or create the global IP whitelist instance."""
    global _ip_whitelist
    if _ip_whitelist is None:
        _ip_whitelist = IPWhitelist()
    return _ip_whitelist


def register_ip_whitelist(app: Flask) -> bool:
    """
    Register IP whitelisting middleware.

    Returns True if IP whitelisting is enabled.
    """
    whitelist = get_ip_whitelist()

    if not whitelist.config.enabled:
        logger.info("IP whitelisting is DISABLED")
        return False

    @app.before_request
    def check_ip_whitelist():
        # Always allow health checks if configured
        if whitelist.config.allow_health_checks and request.path == '/health':
            return None

        allowed, reason = whitelist.is_allowed(request.path)

        if not allowed:
            client_ip = whitelist._get_client_ip()

            if whitelist.config.log_blocked:
                logger.warning(f"Blocked request from {client_ip} to {request.path}: {reason}")
                whitelist.storage.log_violation(client_ip, request.path)

                # Check for auto-block threshold
                violations = whitelist.storage.get_violation_count(client_ip)
                if violations >= whitelist.config.auto_block_threshold:
                    whitelist.storage.set_auto_block(
                        client_ip,
                        whitelist.config.auto_block_duration
                    )

            return jsonify({
                'error': {
                    'code': 'IP_NOT_ALLOWED',
                    'message': 'Access denied from this IP address'
                }
            }), 403

    logger.info(f"IP whitelisting enabled in {whitelist.config.mode} mode")
    return True


def require_whitelisted_ip(admin_only: bool = False):
    """
    Decorator to require IP whitelisting for specific endpoints.

    Usage:
        @app.route('/api/sensitive')
        @require_whitelisted_ip(admin_only=True)
        def sensitive_endpoint():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            whitelist = get_ip_whitelist()

            if not whitelist.config.enabled:
                return f(*args, **kwargs)

            allowed, reason = whitelist.is_allowed(request.path)

            if not allowed:
                return jsonify({
                    'error': {
                        'code': 'IP_NOT_ALLOWED',
                        'message': 'Access denied from this IP address'
                    }
                }), 403

            # Additional admin check
            if admin_only:
                client_ip = whitelist._get_client_ip()
                if not whitelist._is_ip_allowed(client_ip, whitelist._compiled_admin_networks):
                    return jsonify({
                        'error': {
                            'code': 'IP_NOT_ALLOWED',
                            'message': 'Admin access denied from this IP address'
                        }
                    }), 403

            return f(*args, **kwargs)
        return decorated
    return decorator
