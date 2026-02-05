"""
Authentication and Authorization module for PM Notification Analyzer.

This module provides JWT-based authentication that can be enabled/disabled
via the AUTH_ENABLED environment variable.

Usage:
    - Set AUTH_ENABLED=true to require authentication
    - Set AUTH_SECRET_KEY to a strong secret key for JWT signing
    - Use the @require_auth decorator on protected endpoints
"""
import os
import logging
from functools import wraps
from typing import Optional, Tuple, Dict, Any
from flask import request, jsonify, g
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Configuration
AUTH_ENABLED = os.environ.get('AUTH_ENABLED', 'false').lower() == 'true'
AUTH_SECRET_KEY = os.environ.get('AUTH_SECRET_KEY', '')
AUTH_TOKEN_EXPIRY_HOURS = int(os.environ.get('AUTH_TOKEN_EXPIRY_HOURS', '24'))

# Only import jose if auth is enabled to avoid unnecessary dependencies
if AUTH_ENABLED:
    try:
        from jose import jwt, JWTError
    except ImportError:
        logger.error("python-jose is required when AUTH_ENABLED=true. Install with: pip install python-jose[cryptography]")
        raise ImportError("python-jose is required for authentication")


def _get_token_from_header() -> Optional[str]:
    """Extract JWT token from Authorization header."""
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    return None


def _validate_token(token: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Validate JWT token and extract payload.
    Returns: (is_valid, payload, error_message)
    """
    if not AUTH_SECRET_KEY:
        return False, None, "Server authentication is misconfigured"

    try:
        payload = jwt.decode(token, AUTH_SECRET_KEY, algorithms=['HS256'])
        return True, payload, None
    except JWTError as e:
        logger.warning(f"Token validation failed: {e}")
        return False, None, "Invalid or expired token"


def create_token(user_id: str, username: str, roles: list = None) -> str:
    """
    Create a new JWT token for a user.

    Args:
        user_id: Unique user identifier
        username: User's display name
        roles: List of roles/permissions (optional)

    Returns:
        JWT token string
    """
    if not AUTH_SECRET_KEY:
        raise ValueError("AUTH_SECRET_KEY must be set to create tokens")

    payload = {
        'sub': user_id,
        'username': username,
        'roles': roles or [],
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(hours=AUTH_TOKEN_EXPIRY_HOURS)
    }
    return jwt.encode(payload, AUTH_SECRET_KEY, algorithm='HS256')


def require_auth(f):
    """
    Decorator to require authentication for an endpoint.

    When AUTH_ENABLED is false, this decorator does nothing.
    When AUTH_ENABLED is true, it validates the JWT token and sets g.current_user.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AUTH_ENABLED:
            # Auth disabled - allow all requests
            g.current_user = {'user_id': 'anonymous', 'username': 'Anonymous', 'roles': []}
            return f(*args, **kwargs)

        # Auth enabled - validate token
        token = _get_token_from_header()
        if not token:
            return jsonify({
                'error': {
                    'code': 'UNAUTHORIZED',
                    'message': 'Authentication required. Provide a valid Bearer token.'
                }
            }), 401

        is_valid, payload, error = _validate_token(token)
        if not is_valid:
            return jsonify({
                'error': {
                    'code': 'UNAUTHORIZED',
                    'message': error
                }
            }), 401

        # Set current user in Flask's g object
        g.current_user = {
            'user_id': payload.get('sub'),
            'username': payload.get('username'),
            'roles': payload.get('roles', [])
        }

        return f(*args, **kwargs)

    return decorated_function


def require_role(required_roles: list):
    """
    Decorator to require specific roles for an endpoint.
    Must be used after @require_auth.

    Args:
        required_roles: List of roles, user must have at least one

    Usage:
        @app.route('/admin')
        @require_auth
        @require_role(['admin', 'superuser'])
        def admin_endpoint():
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not AUTH_ENABLED:
                return f(*args, **kwargs)

            current_user = getattr(g, 'current_user', None)
            if not current_user:
                return jsonify({
                    'error': {
                        'code': 'UNAUTHORIZED',
                        'message': 'Authentication required'
                    }
                }), 401

            user_roles = current_user.get('roles', [])
            if not any(role in user_roles for role in required_roles):
                return jsonify({
                    'error': {
                        'code': 'FORBIDDEN',
                        'message': 'Insufficient permissions'
                    }
                }), 403

            return f(*args, **kwargs)

        return decorated_function
    return decorator


def get_current_user() -> Optional[Dict[str, Any]]:
    """Get the current authenticated user from Flask's g object."""
    return getattr(g, 'current_user', None)


def get_current_user_id() -> str:
    """Get the current user's ID, or 'anonymous' if not authenticated."""
    user = get_current_user()
    return user.get('user_id', 'anonymous') if user else 'anonymous'


# Log authentication status on module load
if AUTH_ENABLED:
    if not AUTH_SECRET_KEY:
        logger.warning("AUTH_ENABLED is true but AUTH_SECRET_KEY is not set!")
    else:
        logger.info("Authentication is ENABLED")
else:
    logger.info("Authentication is DISABLED - all endpoints are public")
