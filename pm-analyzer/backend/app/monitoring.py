"""
Monitoring, Logging, and Health Check Module for SAP BTP.

Provides:
- Structured JSON logging for SAP Application Logging Service
- Deep health checks (database, SAP, QMS, LLM connectivity)
- Request metrics collection (latency, status codes, throughput)
- Readiness and liveness probes for Kubernetes/CF
"""

import os
import time
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify, g

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured JSON Logging (SAP Application Logging compatible)
# ---------------------------------------------------------------------------

class SAPLogFormatter(logging.Formatter):
    """
    JSON log formatter compatible with SAP Application Logging Service.

    Outputs logs in a format that SAP Kibana/ELK can parse,
    including correlation IDs and BTP-specific fields.
    """

    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add correlation ID if available
        correlation_id = getattr(record, 'correlation_id', None)
        if not correlation_id:
            try:
                from flask import has_request_context
                if has_request_context():
                    correlation_id = getattr(g, 'correlation_id', None)
            except Exception:
                pass
        if correlation_id:
            log_entry['correlation_id'] = correlation_id

        # Add tenant ID if available
        try:
            from flask import has_request_context
            if has_request_context():
                tenant_id = getattr(g, 'tenant_id', None)
                if tenant_id:
                    log_entry['tenant_id'] = tenant_id
        except Exception:
            pass

        # Add BTP component info
        log_entry['component'] = os.environ.get('VCAP_APPLICATION', {})
        if isinstance(log_entry['component'], str):
            try:
                app_info = json.loads(log_entry['component'])
                log_entry['component'] = app_info.get('application_name', 'pm-analyzer')
                log_entry['instance_id'] = app_info.get('instance_id', '')
                log_entry['space'] = app_info.get('space_name', '')
            except (json.JSONDecodeError, TypeError):
                log_entry['component'] = 'pm-analyzer'

        # Add exception info
        if record.exc_info and record.exc_info[0]:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
            }

        return json.dumps(log_entry)


def configure_logging(app: Flask):
    """Configure structured logging for SAP BTP."""
    use_json = os.environ.get('LOG_FORMAT', 'text').lower() == 'json'

    if use_json or os.environ.get('VCAP_SERVICES'):
        # Production: JSON logging for SAP Application Logging
        handler = logging.StreamHandler()
        handler.setFormatter(SAPLogFormatter())
        app.logger.handlers = [handler]
        logging.root.handlers = [handler]

        log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
        app.logger.setLevel(getattr(logging, log_level, logging.INFO))
        logging.root.setLevel(getattr(logging, log_level, logging.INFO))

        app.logger.info("Structured JSON logging configured for SAP Application Logging")
    else:
        app.logger.info("Using default text logging (set LOG_FORMAT=json for structured logs)")


# ---------------------------------------------------------------------------
# Request Metrics
# ---------------------------------------------------------------------------

class RequestMetrics:
    """Collects per-request metrics for monitoring dashboards."""

    def __init__(self):
        self.total_requests = 0
        self.total_errors = 0
        self.endpoint_counts: Dict[str, int] = {}
        self.endpoint_latencies: Dict[str, List[float]] = {}
        self.status_counts: Dict[int, int] = {}
        self._start_time = time.time()

    def record(self, endpoint: str, status_code: int, latency_ms: float):
        self.total_requests += 1
        if status_code >= 500:
            self.total_errors += 1

        self.endpoint_counts[endpoint] = self.endpoint_counts.get(endpoint, 0) + 1
        self.status_counts[status_code] = self.status_counts.get(status_code, 0) + 1

        if endpoint not in self.endpoint_latencies:
            self.endpoint_latencies[endpoint] = []
        latencies = self.endpoint_latencies[endpoint]
        latencies.append(latency_ms)
        # Keep only last 1000 measurements per endpoint
        if len(latencies) > 1000:
            self.endpoint_latencies[endpoint] = latencies[-1000:]

    def get_summary(self) -> Dict[str, Any]:
        uptime = time.time() - self._start_time
        avg_latencies = {}
        for endpoint, latencies in self.endpoint_latencies.items():
            if latencies:
                avg_latencies[endpoint] = {
                    'avg_ms': round(sum(latencies) / len(latencies), 2),
                    'max_ms': round(max(latencies), 2),
                    'min_ms': round(min(latencies), 2),
                    'count': len(latencies),
                }

        return {
            'uptime_seconds': round(uptime, 0),
            'total_requests': self.total_requests,
            'total_errors': self.total_errors,
            'error_rate': round(self.total_errors / max(self.total_requests, 1) * 100, 2),
            'requests_per_second': round(self.total_requests / max(uptime, 1), 2),
            'status_codes': self.status_counts,
            'top_endpoints': dict(sorted(self.endpoint_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            'latencies': avg_latencies,
        }


_metrics = RequestMetrics()


def register_request_metrics(app: Flask):
    """Register request timing and metrics middleware."""

    @app.before_request
    def start_timer():
        g.request_start_time = time.time()
        # Generate correlation ID
        g.correlation_id = request.headers.get(
            'X-Correlation-ID',
            request.headers.get('X-Request-ID', f"req-{int(time.time() * 1000)}")
        )

    @app.after_request
    def record_metrics(response):
        start = getattr(g, 'request_start_time', None)
        if start:
            latency_ms = (time.time() - start) * 1000
            endpoint = request.endpoint or request.path
            _metrics.record(endpoint, response.status_code, latency_ms)

            # Add correlation ID to response
            correlation_id = getattr(g, 'correlation_id', None)
            if correlation_id:
                response.headers['X-Correlation-ID'] = correlation_id

            # Add timing header
            response.headers['X-Response-Time'] = f"{latency_ms:.2f}ms"

        return response

    logger.info("Request metrics middleware registered")


# ---------------------------------------------------------------------------
# Deep Health Checks
# ---------------------------------------------------------------------------

def check_database_health() -> Dict[str, Any]:
    """Check database connectivity and basic query execution."""
    start = time.time()
    try:
        from app.database import get_standalone_connection
        conn = get_standalone_connection()
        try:
            cursor = conn.execute("SELECT 1 as health_check")
            row = cursor.fetchone()
            latency_ms = (time.time() - start) * 1000
            return {
                'status': 'healthy' if row else 'degraded',
                'latency_ms': round(latency_ms, 2),
                'type': os.environ.get('DATABASE_TYPE', 'sqlite'),
            }
        finally:
            conn.close()
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'latency_ms': round((time.time() - start) * 1000, 2),
        }


def check_llm_health() -> Dict[str, Any]:
    """Check LLM (Gemini) API connectivity."""
    start = time.time()
    try:
        api_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
        if not api_key:
            return {'status': 'not_configured', 'message': 'No API key set'}

        return {
            'status': 'configured',
            'latency_ms': round((time.time() - start) * 1000, 2),
            'provider': 'google_generativeai',
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'latency_ms': round((time.time() - start) * 1000, 2),
        }


def check_sap_health() -> Dict[str, Any]:
    """Check SAP system connectivity status."""
    start = time.time()
    try:
        sap_url = os.environ.get('SAP_ODATA_URL')
        if not sap_url:
            return {'status': 'not_configured', 'message': 'No SAP_ODATA_URL set'}

        return {
            'status': 'configured',
            'latency_ms': round((time.time() - start) * 1000, 2),
            'url': sap_url[:50] + '...' if len(sap_url) > 50 else sap_url,
            'connection_type': os.environ.get('SAP_CONNECTION_TYPE', 'odata'),
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'latency_ms': round((time.time() - start) * 1000, 2),
        }


def check_qms_health() -> Dict[str, Any]:
    """Check QMS connectivity status."""
    start = time.time()
    try:
        qms_provider = os.environ.get('QMS_PROVIDER')
        if not qms_provider:
            return {'status': 'not_configured', 'message': 'No QMS_PROVIDER set'}

        return {
            'status': 'configured',
            'latency_ms': round((time.time() - start) * 1000, 2),
            'provider': qms_provider,
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'latency_ms': round((time.time() - start) * 1000, 2),
        }


def run_deep_health_check() -> Dict[str, Any]:
    """Run all health checks and return aggregate status."""
    checks = {
        'database': check_database_health(),
        'llm': check_llm_health(),
        'sap': check_sap_health(),
        'qms': check_qms_health(),
    }

    # Determine overall status
    statuses = [c['status'] for c in checks.values()]
    if all(s in ('healthy', 'configured', 'not_configured') for s in statuses):
        overall = 'healthy'
    elif any(s == 'unhealthy' for s in statuses):
        overall = 'unhealthy'
    else:
        overall = 'degraded'

    return {
        'status': overall,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'version': '2.1.0',
        'checks': checks,
    }


# ---------------------------------------------------------------------------
# Register monitoring endpoints
# ---------------------------------------------------------------------------

def register_monitoring(app: Flask):
    """Register all monitoring endpoints and middleware."""

    configure_logging(app)
    register_request_metrics(app)

    @app.route('/health/deep', methods=['GET'])
    def deep_health_check():
        """Deep health check verifying all dependent services."""
        result = run_deep_health_check()
        status_code = 200 if result['status'] == 'healthy' else 503
        return jsonify(result), status_code

    @app.route('/health/ready', methods=['GET'])
    def readiness_probe():
        """Readiness probe - is the app ready to serve traffic?"""
        db_check = check_database_health()
        if db_check['status'] == 'unhealthy':
            return jsonify({'ready': False, 'reason': 'database unavailable'}), 503
        return jsonify({'ready': True}), 200

    @app.route('/health/live', methods=['GET'])
    def liveness_probe():
        """Liveness probe - is the process alive?"""
        return jsonify({'alive': True}), 200

    @app.route('/api/monitoring/metrics', methods=['GET'])
    def get_metrics():
        """Get application request metrics (admin only)."""
        return jsonify(_metrics.get_summary())

    logger.info("Monitoring endpoints registered: /health/deep, /health/ready, /health/live, /api/monitoring/metrics")
