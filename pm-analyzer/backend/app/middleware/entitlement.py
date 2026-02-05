"""
Entitlement Enforcement Middleware for SAP BTP SaaS.

Enforces subscription plan limits and tracks usage metrics on every API request:
- Feature entitlement checks (is the tenant allowed to use this endpoint?)
- Usage quota enforcement (has the tenant exceeded notification/user limits?)
- Automatic usage metering (counts API calls, analyses, exports)

Endpoints are mapped to features via ENDPOINT_FEATURE_MAP. Requests to
unprotected endpoints (health, tenant callbacks) pass through without checks.
"""

import os
import re
import logging
from functools import wraps
from typing import Optional, Dict

from flask import Flask, request, jsonify, g

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Endpoint-to-feature mapping
# ---------------------------------------------------------------------------

ENDPOINT_FEATURE_MAP: Dict[str, str] = {
    # Analysis endpoints
    '/api/analyze': 'analysis',
    '/api/chat': 'analysis',

    # Quality endpoints
    '/api/quality': 'quality_scoring',

    # Reliability endpoints
    '/api/reliability': 'reliability',

    # Report endpoints
    '/api/reports': 'reporting',

    # Alert endpoints
    '/api/alerts': 'alerts',
    '/api/alert-rules': 'alerts',

    # Audit/compliance endpoints
    '/api/audit': 'fda_compliance',
    '/api/status': 'fda_compliance',
    '/api/confirmations': 'fda_compliance',

    # QMS endpoints
    '/api/qms': 'qms_integration',

    # Governance endpoints
    '/api/governance': 'analysis',
}

# Endpoints that count toward usage metering
METERED_ENDPOINTS: Dict[str, str] = {
    '/api/analyze': 'notifications_analyzed',
    '/api/chat': 'chat_requests',
    '/api/reports': 'reports_generated',
    '/api/quality/export': 'exports',
    '/api/reliability/export': 'exports',
    '/api/audit/export': 'exports',
}

# Endpoints that bypass entitlement checks entirely
BYPASS_PREFIXES = [
    '/health',
    '/api/tenant/',
    '/api/docs',
    '/api/redoc',
    '/api/openapi',
    '/api/configuration',
    '/api/notifications',  # Basic read access for all plans
    '/api/tenants',        # Admin endpoints have their own auth
]


def _get_tenant_id() -> Optional[str]:
    """
    Extract tenant ID from the current request.

    Resolution order:
    1. X-Tenant-ID header (set by approuter or test clients)
    2. JWT token subdomain claim (BTP XSUAA)
    3. TENANT_ID environment variable (single-tenant dev mode)
    """
    # Explicit header
    tenant_id = request.headers.get('X-Tenant-ID')
    if tenant_id:
        return tenant_id

    # From JWT token (BTP XSUAA sets zid claim for tenant zone)
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        try:
            import json
            import base64
            token = auth_header.split(' ')[1]
            payload_b64 = token.split('.')[1]
            # Add padding
            payload_b64 += '=' * (4 - len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            zid = payload.get('zid')
            if zid:
                return zid
        except (IndexError, ValueError, Exception):
            pass

    # Dev mode fallback
    return os.environ.get('TENANT_ID')


def _match_endpoint_feature(path: str) -> Optional[str]:
    """Find the feature required for the given request path."""
    for prefix, feature in ENDPOINT_FEATURE_MAP.items():
        if path.startswith(prefix):
            return feature
    return None


def _match_metered_endpoint(path: str) -> Optional[str]:
    """Find the usage metric for the given request path."""
    for prefix, metric in METERED_ENDPOINTS.items():
        if path.startswith(prefix):
            return metric
    return None


def _should_bypass(path: str) -> bool:
    """Check if the path should bypass entitlement checks."""
    for prefix in BYPASS_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


# ---------------------------------------------------------------------------
# Middleware registration
# ---------------------------------------------------------------------------

def register_entitlement_middleware(app: Flask) -> bool:
    """
    Register entitlement enforcement middleware with Flask.

    Returns True if middleware was activated, False if skipped.
    """
    enabled = os.environ.get('ENTITLEMENT_ENFORCEMENT', 'true').lower() == 'true'

    if not enabled:
        logger.info("Entitlement enforcement is DISABLED")
        return False

    @app.before_request
    def enforce_entitlements():
        path = request.path

        # Skip non-API and bypass paths
        if not path.startswith('/api') or _should_bypass(path):
            return None

        tenant_id = _get_tenant_id()

        # Store for downstream usage
        g.tenant_id = tenant_id

        # If no tenant ID, skip enforcement (local dev or unauthenticated)
        if not tenant_id:
            return None

        try:
            from app.services.tenant_service import get_tenant_service
            tenant_service = get_tenant_service()

            # Check tenant exists and is active
            tenant = tenant_service.get_tenant(tenant_id)
            if not tenant:
                # Unknown tenant - allow in dev, block in production
                if os.environ.get('FLASK_ENV') == 'production':
                    return jsonify({
                        'error': {
                            'code': 'TENANT_NOT_FOUND',
                            'message': 'Subscription not found. Please subscribe to the application.'
                        }
                    }), 403
                return None

            if tenant.status != 'active':
                return jsonify({
                    'error': {
                        'code': 'TENANT_SUSPENDED',
                        'message': f'Subscription is {tenant.status}. Please contact support.'
                    }
                }), 403

            g.tenant = tenant

            # Check feature entitlement
            feature = _match_endpoint_feature(path)
            if feature and not tenant_service.check_entitlement(tenant_id, feature):
                return jsonify({
                    'error': {
                        'code': 'FEATURE_NOT_AVAILABLE',
                        'message': f'Feature "{feature}" is not available on your {tenant.plan} plan. '
                                   f'Please upgrade to access this functionality.',
                        'current_plan': tenant.plan,
                        'required_feature': feature
                    }
                }), 403

            # Check usage limits for metered endpoints (POST/PUT only to avoid counting reads)
            if request.method in ('POST', 'PUT'):
                metric = _match_metered_endpoint(path)
                if metric:
                    limit_check = tenant_service.check_usage_limit(tenant_id, metric)
                    if not limit_check.get('allowed', True):
                        return jsonify({
                            'error': {
                                'code': 'USAGE_LIMIT_EXCEEDED',
                                'message': f'Usage limit exceeded for {metric}.',
                                'used': limit_check.get('used'),
                                'limit': limit_check.get('limit'),
                                'current_plan': tenant.plan
                            }
                        }), 429

        except ImportError:
            logger.debug("Tenant service not available, skipping entitlement check")
        except Exception as e:
            logger.warning(f"Entitlement check error: {e}")
            # Fail open - don't block requests due to internal errors
            pass

        return None

    @app.after_request
    def meter_usage(response):
        """Record usage metrics after successful requests."""
        if response.status_code < 400:
            tenant_id = getattr(g, 'tenant_id', None)
            if tenant_id and request.method in ('POST', 'PUT'):
                metric = _match_metered_endpoint(request.path)
                if metric:
                    try:
                        from app.services.tenant_service import get_tenant_service
                        get_tenant_service().record_usage(tenant_id, metric)
                    except Exception:
                        pass  # Don't fail the response over metering errors
        return response

    logger.info("Entitlement enforcement middleware registered")
    return True


# ---------------------------------------------------------------------------
# Decorator for explicit feature checks
# ---------------------------------------------------------------------------

def require_feature(feature: str):
    """
    Decorator to enforce feature entitlement on a specific endpoint.

    Usage:
        @app.route('/api/advanced')
        @require_feature('advanced_analytics')
        def advanced_endpoint():
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            tenant_id = getattr(g, 'tenant_id', None)
            if not tenant_id:
                return f(*args, **kwargs)

            try:
                from app.services.tenant_service import get_tenant_service
                if not get_tenant_service().check_entitlement(tenant_id, feature):
                    tenant = getattr(g, 'tenant', None)
                    plan = tenant.plan if tenant else 'unknown'
                    return jsonify({
                        'error': {
                            'code': 'FEATURE_NOT_AVAILABLE',
                            'message': f'Feature "{feature}" requires a plan upgrade.',
                            'current_plan': plan,
                            'required_feature': feature
                        }
                    }), 403
            except Exception:
                pass

            return f(*args, **kwargs)
        return wrapper
    return decorator
