"""
Authentication and Authorization Service for Rule Manager.

Provides:
- User authentication with password hashing
- JWT token management
- Session management
- Electronic signature creation (FDA 21 CFR Part 11)
- Permission checking (RBAC)
- Access logging
"""
import os
import logging
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any, List
from functools import wraps
from flask import request, jsonify, g

logger = logging.getLogger(__name__)

# Configuration
AUTH_ENABLED = os.environ.get('AUTH_ENABLED', 'false').lower() == 'true'
AUTH_SECRET_KEY = os.environ.get('AUTH_SECRET_KEY', '')
TOKEN_EXPIRY_HOURS = int(os.environ.get('TOKEN_EXPIRY_HOURS', '8'))
SESSION_TIMEOUT_MINUTES = int(os.environ.get('SESSION_TIMEOUT_MINUTES', '30'))
MAX_FAILED_LOGINS = int(os.environ.get('MAX_FAILED_LOGINS', '5'))
LOCKOUT_DURATION_MINUTES = int(os.environ.get('LOCKOUT_DURATION_MINUTES', '30'))
PASSWORD_MIN_LENGTH = int(os.environ.get('PASSWORD_MIN_LENGTH', '12'))
PASSWORD_EXPIRY_DAYS = int(os.environ.get('PASSWORD_EXPIRY_DAYS', '90'))

# Only import jose if auth is enabled
if AUTH_ENABLED:
    try:
        from jose import jwt, JWTError
    except ImportError:
        logger.error("python-jose required when AUTH_ENABLED=true")
        raise ImportError("python-jose required for authentication")


# ============================================================================
# PASSWORD UTILITIES
# ============================================================================

def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with salt."""
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{password_hash}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against its stored hash."""
    try:
        salt, password_hash = stored_hash.split(':')
        computed_hash = hashlib.sha256((salt + password).encode()).hexdigest()
        return secrets.compare_digest(computed_hash, password_hash)
    except (ValueError, AttributeError):
        return False


def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate password meets complexity requirements.

    Requirements:
    - Minimum length (default 12)
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {PASSWORD_MIN_LENGTH} characters"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"
    if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
        return False, "Password must contain at least one special character"
    return True, None


# ============================================================================
# TOKEN MANAGEMENT
# ============================================================================

def create_access_token(user_id: str, username: str, role: str, permissions: List[str]) -> str:
    """Create a JWT access token."""
    if not AUTH_SECRET_KEY:
        raise ValueError("AUTH_SECRET_KEY must be set")

    payload = {
        'sub': user_id,
        'username': username,
        'role': role,
        'permissions': permissions,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS)
    }
    return jwt.encode(payload, AUTH_SECRET_KEY, algorithm='HS256')


def decode_token(token: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """Decode and validate a JWT token."""
    if not AUTH_SECRET_KEY:
        return False, None, "Server authentication misconfigured"

    try:
        payload = jwt.decode(token, AUTH_SECRET_KEY, algorithms=['HS256'])
        return True, payload, None
    except JWTError as e:
        logger.warning(f"Token decode failed: {e}")
        return False, None, "Invalid or expired token"


def get_token_hash(token: str) -> str:
    """Get a hash of a token for session storage."""
    return hashlib.sha256(token.encode()).hexdigest()


# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

def create_session(session, user_id: str, token: str, ip_address: str = None, user_agent: str = None):
    """Create a new user session."""
    from .database import UserSession

    # Invalidate any existing sessions for this user (single session per user)
    session.query(UserSession).filter_by(user_id=user_id, is_active=True).update({'is_active': False})

    new_session = UserSession(
        user_id=user_id,
        token_hash=get_token_hash(token),
        ip_address=ip_address,
        device_info=user_agent,
        expires_at=datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS)
    )
    session.add(new_session)
    return new_session


def validate_session(session, user_id: str, token: str) -> Tuple[bool, Optional[str]]:
    """Validate a user's session is active and not expired."""
    from .database import UserSession

    token_hash = get_token_hash(token)
    user_session = session.query(UserSession).filter_by(
        user_id=user_id,
        token_hash=token_hash,
        is_active=True
    ).first()

    if not user_session:
        return False, "Session not found or expired"

    # Check session expiry
    if user_session.expires_at < datetime.utcnow():
        user_session.is_active = False
        session.commit()
        return False, "Session expired"

    # Check session timeout (inactivity)
    timeout_threshold = datetime.utcnow() - timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    if user_session.last_activity < timeout_threshold:
        user_session.is_active = False
        session.commit()
        return False, "Session timed out due to inactivity"

    # Update last activity
    user_session.last_activity = datetime.utcnow()
    session.commit()

    return True, None


def invalidate_session(session, user_id: str, token: str = None):
    """Invalidate a user's session (logout)."""
    from .database import UserSession

    if token:
        token_hash = get_token_hash(token)
        session.query(UserSession).filter_by(
            user_id=user_id,
            token_hash=token_hash
        ).update({'is_active': False})
    else:
        # Invalidate all sessions for user
        session.query(UserSession).filter_by(user_id=user_id).update({'is_active': False})

    session.commit()


# ============================================================================
# ACCESS LOGGING
# ============================================================================

def log_access(session, username: str, user_id: str, action: str, success: bool,
               failure_reason: str = None, ip_address: str = None, user_agent: str = None):
    """Log an access attempt."""
    from .database import AccessLog

    log_entry = AccessLog(
        username=username,
        user_id=user_id,
        action=action,
        success=success,
        failure_reason=failure_reason,
        ip_address=ip_address,
        user_agent=user_agent
    )
    session.add(log_entry)
    session.commit()


# ============================================================================
# ELECTRONIC SIGNATURES (FDA 21 CFR Part 11)
# ============================================================================

def create_electronic_signature(
    session,
    user_id: str,
    password: str,
    entity_type: str,
    entity_id: str,
    meaning: str,
    reason: str = None,
    entity_version: int = None,
    ip_address: str = None,
    user_agent: str = None
) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    Create an electronic signature with re-authentication.

    FDA 21 CFR Part 11 requires:
    - Re-authentication at time of signing
    - Signature meaning declaration
    - Link to signed record
    - Timestamp
    """
    from .database import User, ElectronicSignature, SignatureMeaning

    # Validate signature meaning
    valid_meanings = [m.value for m in SignatureMeaning]
    if meaning not in valid_meanings:
        return False, None, f"Invalid signature meaning. Must be one of: {valid_meanings}"

    # Re-authenticate user
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        return False, None, "User not found"

    if not verify_password(password, user.password_hash):
        log_access(session, user.username, user_id, "signature_failed", False,
                  "Invalid password", ip_address, user_agent)
        return False, None, "Authentication failed - invalid password"

    # Check user is active
    if user.status != "Active":
        return False, None, "User account is not active"

    # Create signature
    signature = ElectronicSignature(
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_version=entity_version,
        meaning=meaning,
        reason=reason,
        auth_method="password",
        ip_address=ip_address,
        user_agent=user_agent
    )
    session.add(signature)

    # Log the signature creation
    log_access(session, user.username, user_id, "signature_created", True,
              None, ip_address, user_agent)

    session.commit()

    return True, signature.to_dict(), None


def get_signatures_for_entity(session, entity_type: str, entity_id: str) -> List[Dict]:
    """Get all electronic signatures for an entity."""
    from .database import ElectronicSignature

    signatures = session.query(ElectronicSignature).filter_by(
        entity_type=entity_type,
        entity_id=entity_id
    ).order_by(ElectronicSignature.timestamp.desc()).all()

    return [sig.to_dict() for sig in signatures]


# ============================================================================
# AUTHENTICATION DECORATORS
# ============================================================================

def require_auth(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not AUTH_ENABLED:
            g.current_user = {
                'user_id': 'anonymous',
                'username': 'Anonymous',
                'role': 'Admin',
                'permissions': ['*']
            }
            return f(*args, **kwargs)

        from .database import Session

        # Extract token
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401

        token = auth_header[7:]

        # Decode token
        is_valid, payload, error = decode_token(token)
        if not is_valid:
            return jsonify({'error': error}), 401

        # Validate session
        db_session = Session()
        try:
            session_valid, session_error = validate_session(db_session, payload['sub'], token)
            if not session_valid:
                return jsonify({'error': session_error}), 401

            g.current_user = {
                'user_id': payload['sub'],
                'username': payload['username'],
                'role': payload['role'],
                'permissions': payload['permissions']
            }
            g.token = token

            return f(*args, **kwargs)
        finally:
            db_session.close()

    return decorated


def require_permission(resource: str, action: str):
    """Decorator to require a specific permission."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not AUTH_ENABLED:
                return f(*args, **kwargs)

            current_user = getattr(g, 'current_user', None)
            if not current_user:
                return jsonify({'error': 'Authentication required'}), 401

            # Check for wildcard permission (Admin)
            if '*' in current_user['permissions']:
                return f(*args, **kwargs)

            # Check specific permission
            required_perm = f"{resource}:{action}"
            if required_perm not in current_user['permissions']:
                logger.warning(f"Permission denied: {current_user['username']} lacks {required_perm}")
                return jsonify({'error': f'Permission denied: requires {required_perm}'}), 403

            return f(*args, **kwargs)

        return decorated
    return decorator


# ============================================================================
# USER AUTHENTICATION
# ============================================================================

def authenticate_user(session, username: str, password: str, ip_address: str = None,
                     user_agent: str = None) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    Authenticate a user and create a session.

    Returns: (success, token_data, error_message)
    """
    from .database import User

    user = session.query(User).filter_by(username=username).first()

    # Check if user exists
    if not user:
        log_access(session, username, None, "login", False, "User not found", ip_address, user_agent)
        return False, None, "Invalid username or password"

    # Check if account is locked
    if user.locked_until and user.locked_until > datetime.utcnow():
        remaining = (user.locked_until - datetime.utcnow()).seconds // 60
        log_access(session, username, user.id, "login", False, "Account locked", ip_address, user_agent)
        return False, None, f"Account locked. Try again in {remaining} minutes"

    # Check if account is active
    if user.status != "Active":
        log_access(session, username, user.id, "login", False, f"Account {user.status}", ip_address, user_agent)
        return False, None, f"Account is {user.status.lower()}"

    # Verify password
    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1

        # Lock account if too many failures
        if user.failed_login_attempts >= MAX_FAILED_LOGINS:
            user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            user.status = "Locked"
            log_access(session, username, user.id, "login", False, "Account locked due to failed attempts",
                      ip_address, user_agent)
            session.commit()
            return False, None, f"Account locked due to too many failed attempts"

        log_access(session, username, user.id, "login", False, "Invalid password", ip_address, user_agent)
        session.commit()
        return False, None, "Invalid username or password"

    # Check password expiry
    if user.password_expires_at and user.password_expires_at < datetime.utcnow():
        log_access(session, username, user.id, "login", False, "Password expired", ip_address, user_agent)
        return False, None, "Password has expired. Please contact administrator"

    # Successful login - reset failed attempts
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()

    # Get permissions from role
    permissions = [f"{p.resource}:{p.action}" for p in user.role.permissions]

    # Create token
    token = create_access_token(user.id, user.username, user.role.name, permissions)

    # Create session
    create_session(session, user.id, token, ip_address, user_agent)

    # Log successful login
    log_access(session, username, user.id, "login", True, None, ip_address, user_agent)

    session.commit()

    return True, {
        'token': token,
        'user_id': user.id,
        'username': user.username,
        'full_name': user.full_name,
        'role': user.role.name,
        'permissions': permissions,
        'must_change_password': user.must_change_password,
        'expires_in': TOKEN_EXPIRY_HOURS * 3600
    }, None


def logout_user(session, user_id: str, token: str, ip_address: str = None, user_agent: str = None):
    """Log out a user and invalidate their session."""
    from .database import User

    user = session.query(User).filter_by(id=user_id).first()
    username = user.username if user else "unknown"

    invalidate_session(session, user_id, token)
    log_access(session, username, user_id, "logout", True, None, ip_address, user_agent)


def change_password(session, user_id: str, old_password: str, new_password: str,
                   ip_address: str = None, user_agent: str = None) -> Tuple[bool, Optional[str]]:
    """Change a user's password."""
    from .database import User

    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        return False, "User not found"

    # Verify old password
    if not verify_password(old_password, user.password_hash):
        log_access(session, user.username, user_id, "password_change", False,
                  "Invalid old password", ip_address, user_agent)
        return False, "Current password is incorrect"

    # Validate new password
    is_valid, error = validate_password_strength(new_password)
    if not is_valid:
        return False, error

    # Check new password is different from old
    if verify_password(new_password, user.password_hash):
        return False, "New password must be different from current password"

    # Update password
    user.password_hash = hash_password(new_password)
    user.password_expires_at = datetime.utcnow() + timedelta(days=PASSWORD_EXPIRY_DAYS)
    user.must_change_password = False

    # Invalidate all sessions (force re-login)
    invalidate_session(session, user_id)

    log_access(session, user.username, user_id, "password_change", True, None, ip_address, user_agent)
    session.commit()

    return True, None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_request_info() -> Tuple[str, str]:
    """Get IP address and user agent from current request."""
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent', '')[:255]
    return ip_address, user_agent


def get_current_user_id() -> str:
    """Get the current authenticated user's ID."""
    current_user = getattr(g, 'current_user', None)
    return current_user['user_id'] if current_user else 'anonymous'


def get_current_username() -> str:
    """Get the current authenticated user's username."""
    current_user = getattr(g, 'current_user', None)
    return current_user['username'] if current_user else 'Anonymous'
