"""
Clerk Authentication Integration for PM Notification Analyzer

Provides authentication and user management via Clerk.dev service.

Setup:
1. Create account at https://clerk.dev
2. Create an application
3. Get your API keys from the Clerk Dashboard
4. Set environment variables:
   - CLERK_SECRET_KEY
   - CLERK_PUBLISHABLE_KEY
   - CLERK_JWT_VERIFICATION_KEY (optional, for local JWT verification)

Features:
- JWT token verification
- User session management
- Role-based access control
- User metadata sync
"""

import os
import json
import logging
from functools import wraps
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime

import requests
from flask import request, g, jsonify, current_app
from jose import jwt, JWTError

logger = logging.getLogger(__name__)


# ============================================
# Configuration
# ============================================

@dataclass
class ClerkConfig:
    """Clerk configuration from environment"""
    secret_key: str = ""
    publishable_key: str = ""
    api_url: str = "https://api.clerk.dev/v1"
    jwt_verification_key: str = ""
    enabled: bool = False

    # Role configuration
    admin_roles: List[str] = field(default_factory=lambda: ["admin", "org:admin"])
    editor_roles: List[str] = field(default_factory=lambda: ["editor", "org:editor"])
    auditor_roles: List[str] = field(default_factory=lambda: ["auditor", "org:auditor"])
    viewer_roles: List[str] = field(default_factory=lambda: ["viewer", "org:viewer", "org:member"])

    @classmethod
    def from_env(cls) -> 'ClerkConfig':
        """Load configuration from environment variables"""
        secret_key = os.environ.get('CLERK_SECRET_KEY', '')

        return cls(
            secret_key=secret_key,
            publishable_key=os.environ.get('CLERK_PUBLISHABLE_KEY', ''),
            jwt_verification_key=os.environ.get('CLERK_JWT_VERIFICATION_KEY', ''),
            enabled=bool(secret_key) and os.environ.get('CLERK_ENABLED', 'true').lower() == 'true'
        )


# Global config instance
_clerk_config: Optional[ClerkConfig] = None


def get_clerk_config() -> ClerkConfig:
    """Get or create Clerk configuration"""
    global _clerk_config
    if _clerk_config is None:
        _clerk_config = ClerkConfig.from_env()
    return _clerk_config


# ============================================
# User Data Models
# ============================================

@dataclass
class ClerkUser:
    """Represents a Clerk user"""
    id: str
    email: str
    first_name: str = ""
    last_name: str = ""
    username: str = ""
    image_url: str = ""
    roles: List[str] = field(default_factory=list)
    org_id: Optional[str] = None
    org_role: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    last_sign_in: Optional[datetime] = None

    @property
    def full_name(self) -> str:
        """Get user's full name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username or self.email.split('@')[0]

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role"""
        config = get_clerk_config()
        return any(role in config.admin_roles for role in self.roles)

    @property
    def is_editor(self) -> bool:
        """Check if user has editor role"""
        config = get_clerk_config()
        return self.is_admin or any(role in config.editor_roles for role in self.roles)

    @property
    def is_auditor(self) -> bool:
        """Check if user has auditor role"""
        config = get_clerk_config()
        return self.is_admin or any(role in config.auditor_roles for role in self.roles)

    def has_role(self, role: str) -> bool:
        """Check if user has specific role"""
        return role in self.roles or self.is_admin

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'username': self.username,
            'image_url': self.image_url,
            'roles': self.roles,
            'org_id': self.org_id,
            'org_role': self.org_role,
            'is_admin': self.is_admin,
            'is_editor': self.is_editor,
            'is_auditor': self.is_auditor
        }


# ============================================
# JWT Token Verification
# ============================================

def verify_clerk_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a Clerk JWT token.

    Clerk tokens can be verified:
    1. Using the JWKS endpoint (recommended)
    2. Using a local verification key
    3. Via Clerk API (fallback)
    """
    config = get_clerk_config()

    if not config.enabled:
        logger.warning("Clerk authentication is disabled")
        return None

    try:
        # Try local JWT verification first (faster)
        if config.jwt_verification_key:
            return _verify_token_local(token, config.jwt_verification_key)

        # Fall back to JWKS verification
        return _verify_token_jwks(token)

    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        return None
    except Exception as e:
        logger.exception(f"Token verification error: {e}")
        return None


def _verify_token_local(token: str, verification_key: str) -> Optional[Dict[str, Any]]:
    """Verify token using local key"""
    try:
        # Clerk uses RS256 by default
        payload = jwt.decode(
            token,
            verification_key,
            algorithms=['RS256'],
            options={'verify_aud': False}  # Clerk doesn't always set audience
        )
        return payload
    except JWTError:
        raise


def _verify_token_jwks(token: str) -> Optional[Dict[str, Any]]:
    """Verify token using Clerk's JWKS endpoint"""
    config = get_clerk_config()

    # Get the key ID from token header
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get('kid')

    if not kid:
        logger.warning("Token missing key ID (kid)")
        return None

    # Fetch JWKS from Clerk
    # The JWKS URL is derived from the frontend API URL in publishable key
    # Format: pk_test_xxx or pk_live_xxx
    if config.publishable_key.startswith('pk_test_'):
        jwks_url = "https://clerk.clerk.dev/.well-known/jwks.json"
    else:
        # Extract the frontend API from publishable key
        # This is a simplified approach - in production, use the actual frontend API
        jwks_url = f"{config.api_url.replace('api.', '')}/.well-known/jwks.json"

    try:
        response = requests.get(jwks_url, timeout=10)
        response.raise_for_status()
        jwks = response.json()

        # Find the matching key
        rsa_key = None
        for key in jwks.get('keys', []):
            if key.get('kid') == kid:
                rsa_key = key
                break

        if not rsa_key:
            logger.warning(f"No matching key found for kid: {kid}")
            return None

        # Verify the token
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=['RS256'],
            options={'verify_aud': False}
        )
        return payload

    except requests.RequestException as e:
        logger.error(f"Failed to fetch JWKS: {e}")
        return None


# ============================================
# Clerk API Client
# ============================================

class ClerkClient:
    """Client for Clerk Backend API"""

    def __init__(self, config: Optional[ClerkConfig] = None):
        self.config = config or get_clerk_config()
        self._session = requests.Session()
        self._session.headers.update({
            'Authorization': f'Bearer {self.config.secret_key}',
            'Content-Type': 'application/json'
        })

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make API request to Clerk"""
        url = f"{self.config.api_url}{endpoint}"

        try:
            response = self._session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            logger.error(f"Clerk API error: {e.response.status_code} - {e.response.text}")
            raise
        except requests.RequestException as e:
            logger.error(f"Clerk API request failed: {e}")
            raise

    def get_user(self, user_id: str) -> Optional[ClerkUser]:
        """Get user by ID"""
        try:
            data = self._request('GET', f'/users/{user_id}')
            return self._parse_user(data)
        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {e}")
            return None

    def get_user_by_email(self, email: str) -> Optional[ClerkUser]:
        """Get user by email"""
        try:
            data = self._request('GET', '/users', params={'email_address': email})
            users = data.get('data', [])
            if users:
                return self._parse_user(users[0])
            return None
        except Exception as e:
            logger.error(f"Failed to get user by email {email}: {e}")
            return None

    def list_users(self, limit: int = 100, offset: int = 0) -> List[ClerkUser]:
        """List all users"""
        try:
            data = self._request('GET', '/users', params={
                'limit': limit,
                'offset': offset
            })
            return [self._parse_user(u) for u in data.get('data', [])]
        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            return []

    def update_user_metadata(self, user_id: str, public_metadata: Dict = None,
                            private_metadata: Dict = None) -> bool:
        """Update user metadata"""
        try:
            payload = {}
            if public_metadata:
                payload['public_metadata'] = public_metadata
            if private_metadata:
                payload['private_metadata'] = private_metadata

            self._request('PATCH', f'/users/{user_id}', json=payload)
            return True
        except Exception as e:
            logger.error(f"Failed to update user metadata: {e}")
            return False

    def set_user_roles(self, user_id: str, roles: List[str]) -> bool:
        """Set user roles in metadata"""
        return self.update_user_metadata(user_id, public_metadata={'roles': roles})

    def verify_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Verify a session"""
        try:
            return self._request('GET', f'/sessions/{session_id}')
        except Exception:
            return None

    def _parse_user(self, data: Dict[str, Any]) -> ClerkUser:
        """Parse Clerk API response into ClerkUser"""
        # Get primary email
        email_addresses = data.get('email_addresses', [])
        primary_email = next(
            (e['email_address'] for e in email_addresses
             if e.get('id') == data.get('primary_email_address_id')),
            email_addresses[0]['email_address'] if email_addresses else ''
        )

        # Get roles from public metadata
        public_metadata = data.get('public_metadata', {})
        roles = public_metadata.get('roles', [])

        # Parse timestamps
        created_at = None
        if data.get('created_at'):
            created_at = datetime.fromtimestamp(data['created_at'] / 1000)

        last_sign_in = None
        if data.get('last_sign_in_at'):
            last_sign_in = datetime.fromtimestamp(data['last_sign_in_at'] / 1000)

        return ClerkUser(
            id=data['id'],
            email=primary_email,
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            username=data.get('username', ''),
            image_url=data.get('image_url', ''),
            roles=roles if isinstance(roles, list) else [roles] if roles else [],
            metadata=public_metadata,
            created_at=created_at,
            last_sign_in=last_sign_in
        )


# ============================================
# Flask Middleware & Decorators
# ============================================

def get_current_user() -> Optional[ClerkUser]:
    """Get the current authenticated user from Flask's g object"""
    return getattr(g, 'current_user', None)


def clerk_auth_middleware():
    """
    Flask middleware to authenticate requests using Clerk.

    Call this in your Flask app's before_request or use as decorator.
    Sets g.current_user if authentication is successful.
    """
    config = get_clerk_config()

    # Skip if Clerk is disabled
    if not config.enabled:
        return None

    # Get token from Authorization header
    auth_header = request.headers.get('Authorization', '')

    if not auth_header.startswith('Bearer '):
        return None

    token = auth_header[7:]  # Remove 'Bearer ' prefix

    # Verify token
    payload = verify_clerk_token(token)

    if not payload:
        return None

    # Extract user info from token
    user_id = payload.get('sub')

    if not user_id:
        return None

    # Get additional user data from token claims or fetch from API
    # Clerk includes some user data in the token
    session_claims = payload.get('session_claims', {})

    # Create user object from token
    g.current_user = ClerkUser(
        id=user_id,
        email=payload.get('email', ''),
        first_name=payload.get('first_name', ''),
        last_name=payload.get('last_name', ''),
        roles=payload.get('public_metadata', {}).get('roles', []),
        org_id=payload.get('org_id'),
        org_role=payload.get('org_role')
    )

    return None


def require_auth(f: Callable) -> Callable:
    """
    Decorator to require authentication for a route.

    Usage:
        @app.route('/api/protected')
        @require_auth
        def protected_route():
            user = get_current_user()
            return jsonify({'user': user.email})
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        config = get_clerk_config()

        # Skip auth check if disabled (development mode)
        if not config.enabled:
            return f(*args, **kwargs)

        # Run middleware if not already done
        if not hasattr(g, 'current_user') or g.current_user is None:
            clerk_auth_middleware()

        user = get_current_user()

        if not user:
            return jsonify({
                'error': {
                    'code': 'UNAUTHORIZED',
                    'message': 'Authentication required'
                }
            }), 401

        return f(*args, **kwargs)

    return decorated


def require_role(*roles: str) -> Callable:
    """
    Decorator to require specific roles for a route.

    Usage:
        @app.route('/api/admin')
        @require_role('admin')
        def admin_route():
            return jsonify({'admin': True})

        @app.route('/api/edit')
        @require_role('admin', 'editor')
        def edit_route():
            return jsonify({'can_edit': True})
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        @require_auth
        def decorated(*args, **kwargs):
            # Skip role check if auth is disabled (development mode)
            config = get_clerk_config()
            if not config.enabled:
                return f(*args, **kwargs)

            user = get_current_user()

            if not user:
                return jsonify({
                    'error': {
                        'code': 'UNAUTHORIZED',
                        'message': 'Authentication required'
                    }
                }), 401

            # Check if user has any of the required roles
            if not any(user.has_role(role) for role in roles):
                return jsonify({
                    'error': {
                        'code': 'FORBIDDEN',
                        'message': f'Required role: {" or ".join(roles)}'
                    }
                }), 403

            return f(*args, **kwargs)

        return decorated

    return decorator


def require_admin(f: Callable) -> Callable:
    """Decorator to require admin role"""
    return require_role('admin')(f)


def require_editor(f: Callable) -> Callable:
    """Decorator to require editor role (or admin)"""
    return require_role('admin', 'editor')(f)


def require_auditor(f: Callable) -> Callable:
    """Decorator to require auditor role (or admin)"""
    return require_role('admin', 'auditor')(f)


# ============================================
# Flask Blueprint for Auth Endpoints
# ============================================

from flask import Blueprint

clerk_bp = Blueprint('clerk', __name__)


@clerk_bp.route('/auth/status', methods=['GET'])
def auth_status():
    """Get authentication status and configuration"""
    config = get_clerk_config()

    return jsonify({
        'enabled': config.enabled,
        'publishable_key': config.publishable_key if config.enabled else None,
        'user': get_current_user().to_dict() if get_current_user() else None
    })


@clerk_bp.route('/auth/me', methods=['GET'])
@require_auth
def get_me():
    """Get current user information"""
    user = get_current_user()
    return jsonify(user.to_dict())


@clerk_bp.route('/auth/users', methods=['GET'])
@require_admin
def list_users():
    """List all users (admin only)"""
    client = ClerkClient()

    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)

    users = client.list_users(limit=limit, offset=offset)

    return jsonify({
        'users': [u.to_dict() for u in users],
        'count': len(users)
    })


@clerk_bp.route('/auth/users/<user_id>', methods=['GET'])
@require_admin
def get_user(user_id: str):
    """Get user by ID (admin only)"""
    client = ClerkClient()
    user = client.get_user(user_id)

    if not user:
        return jsonify({
            'error': {'code': 'NOT_FOUND', 'message': 'User not found'}
        }), 404

    return jsonify(user.to_dict())


@clerk_bp.route('/auth/users/<user_id>/roles', methods=['PUT'])
@require_admin
def set_user_roles(user_id: str):
    """Set user roles (admin only)"""
    data = request.get_json()
    roles = data.get('roles', [])

    if not isinstance(roles, list):
        return jsonify({
            'error': {'code': 'BAD_REQUEST', 'message': 'roles must be an array'}
        }), 400

    client = ClerkClient()
    success = client.set_user_roles(user_id, roles)

    if success:
        return jsonify({'status': 'ok', 'roles': roles})
    else:
        return jsonify({
            'error': {'code': 'UPDATE_FAILED', 'message': 'Failed to update roles'}
        }), 500


@clerk_bp.route('/auth/webhook', methods=['POST'])
def clerk_webhook():
    """
    Webhook endpoint for Clerk events.

    Configure this URL in your Clerk Dashboard under Webhooks.
    Events: user.created, user.updated, user.deleted,
            organization.created, organizationMembership.created, etc.
    """
    # Verify webhook signature (recommended for production)
    # webhook_secret = os.environ.get('CLERK_WEBHOOK_SECRET')
    # signature = request.headers.get('svix-signature')
    # TODO: Implement signature verification

    event = request.get_json()
    event_type = event.get('type')

    logger.info(f"Received Clerk webhook: {event_type}")

    if event_type == 'user.created':
        user_data = event.get('data', {})
        logger.info(f"New user created: {user_data.get('id')}")

    elif event_type == 'user.updated':
        user_data = event.get('data', {})
        logger.info(f"User updated: {user_data.get('id')}")

    elif event_type == 'user.deleted':
        user_data = event.get('data', {})
        logger.info(f"User deleted: {user_data.get('id')}")

    elif event_type == 'organizationMembership.created':
        # A user joined an organization (tenant)
        membership = event.get('data', {})
        org_id = membership.get('organization', {}).get('id', '')
        user_id = membership.get('public_user_data', {}).get('user_id', '')
        role = membership.get('role', '')
        logger.info(f"User {user_id} joined org {org_id} as {role}")

        # Record usage metric for active users
        if org_id:
            try:
                from app.services.tenant_service import get_tenant_service
                get_tenant_service().record_usage(org_id, 'active_users')
            except Exception:
                pass

    elif event_type == 'organizationMembership.deleted':
        membership = event.get('data', {})
        org_id = membership.get('organization', {}).get('id', '')
        user_id = membership.get('public_user_data', {}).get('user_id', '')
        logger.info(f"User {user_id} removed from org {org_id}")

    elif event_type == 'organization.deleted':
        # Clerk org deleted -> deprovision tenant
        org_data = event.get('data', {})
        org_id = org_data.get('id', '')
        logger.info(f"Organization deleted: {org_id}")

        if org_id:
            try:
                from app.services.tenant_service import get_tenant_service
                ts = get_tenant_service()
                tenant = ts.get_tenant(org_id)
                if tenant:
                    ts.on_unsubscription(org_id)
                    logger.info(f"Tenant {org_id} deprovisioned via org deletion")
            except Exception as e:
                logger.error(f"Error handling org deletion for {org_id}: {e}")

    return jsonify({'received': True})


def register_clerk_auth(app):
    """
    Register Clerk authentication with Flask app.

    Usage:
        from app.clerk_auth import register_clerk_auth
        register_clerk_auth(app)
    """
    config = get_clerk_config()

    if config.enabled:
        # Add middleware to run before each request
        app.before_request(clerk_auth_middleware)
        logger.info("Clerk authentication enabled")
    else:
        logger.warning("Clerk authentication is DISABLED")

    # Register blueprint
    app.register_blueprint(clerk_bp, url_prefix='/api')

    return config.enabled
