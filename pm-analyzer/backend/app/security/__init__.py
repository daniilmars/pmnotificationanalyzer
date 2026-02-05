"""
Security Module for PM Notification Analyzer.

Provides comprehensive security features including:
- Rate limiting
- API key management
- IP whitelisting
- Security audit logging
- Session management
"""

from app.security.rate_limiter import (
    get_rate_limiter,
    register_rate_limiter,
    rate_limit,
    RateLimiter,
    RateLimitConfig
)

from app.security.api_key_manager import (
    get_api_key_manager,
    register_api_key_auth,
    require_api_key,
    APIKeyManager,
    APIKeyConfig,
    APIKey
)

from app.security.ip_whitelist import (
    get_ip_whitelist,
    register_ip_whitelist,
    require_whitelisted_ip,
    IPWhitelist,
    IPWhitelistConfig
)

from app.security.audit_logger import (
    get_audit_logger,
    register_audit_logger,
    SecurityAuditLogger,
    AuditConfig,
    AuditEventType,
    AuditSeverity
)

from app.security.session_manager import (
    get_session_manager,
    register_session_manager,
    SessionManager,
    SessionConfig,
    Session
)

__all__ = [
    # Rate limiter
    'get_rate_limiter',
    'register_rate_limiter',
    'rate_limit',
    'RateLimiter',
    'RateLimitConfig',

    # API key manager
    'get_api_key_manager',
    'register_api_key_auth',
    'require_api_key',
    'APIKeyManager',
    'APIKeyConfig',
    'APIKey',

    # IP whitelist
    'get_ip_whitelist',
    'register_ip_whitelist',
    'require_whitelisted_ip',
    'IPWhitelist',
    'IPWhitelistConfig',

    # Audit logger
    'get_audit_logger',
    'register_audit_logger',
    'SecurityAuditLogger',
    'AuditConfig',
    'AuditEventType',
    'AuditSeverity',

    # Session manager
    'get_session_manager',
    'register_session_manager',
    'SessionManager',
    'SessionConfig',
    'Session'
]
