from flask import Flask, request, jsonify, g
from flask_cors import CORS
from dotenv import load_dotenv
import os
import re
from datetime import datetime
from typing import Tuple, Optional
from google.api_core import exceptions as google_exceptions
import logging

load_dotenv()

from app.services.analysis_service import analyze_text, chat_with_assistant
from app.services.data_service import get_all_notifications_summary, get_unified_notification
from app.models import AnalysisResponse
from app.config_manager import get_config, save_config
from app.database import close_db, close_pool, get_database_info, DATABASE_TYPE
from app.validators import (
    validate_notification_id,
    validate_language,
    validate_analysis_request,
    validate_chat_request,
    validate_configuration,
    ALLOWED_LANGUAGES
)
from app.ai_governance import init_governance_db, create_governance_blueprint
from app.openapi_spec import register_openapi
from app.clerk_auth import register_clerk_auth, require_auth, require_role, require_admin, get_current_user
from app.services.notification_service import get_notification_service, Alert, AlertSeverity, AlertType
from app.services.alert_rules_service import get_alert_rules_service, AlertRule, RuleCondition, Subscription

# Security infrastructure
from app.security import (
    register_rate_limiter,
    register_api_key_auth,
    register_ip_whitelist,
    register_audit_logger,
    register_session_manager,
    get_api_key_manager,
    get_audit_logger,
    AuditEventType,
    AuditSeverity as AuditSev,
    rate_limit
)

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# CORS Configuration - restrict origins in production
# Set CORS_ORIGINS env var to comma-separated list of allowed origins
# Example: CORS_ORIGINS=https://app.example.com,https://admin.example.com
cors_origins = os.environ.get('CORS_ORIGINS', '*')
if cors_origins != '*':
    cors_origins = [origin.strip() for origin in cors_origins.split(',')]
CORS(app, resources={r"/api/*": {"origins": cors_origins}})

# Initialize AI Governance database
try:
    init_governance_db()
    logger.info("AI Governance database initialized")
except Exception as e:
    logger.warning(f"Could not initialize AI Governance database: {e}")

# Register AI Governance blueprint
governance_blueprint = create_governance_blueprint()
app.register_blueprint(governance_blueprint, url_prefix='/api/governance')

# Register OpenAPI/Swagger documentation
register_openapi(app)
logger.info("OpenAPI documentation registered at /api/docs and /api/redoc")

# Register Clerk authentication
clerk_enabled = register_clerk_auth(app)
if clerk_enabled:
    logger.info("Clerk authentication enabled")
else:
    logger.warning("Clerk authentication is DISABLED - set CLERK_SECRET_KEY to enable")

# Register security infrastructure
# Note: Order matters - rate limiting should be checked early
rate_limit_enabled = register_rate_limiter(app)
api_key_enabled = register_api_key_auth(app)
ip_whitelist_enabled = register_ip_whitelist(app)
audit_log_enabled = register_audit_logger(app)
session_mgmt_enabled = register_session_manager(app)

logger.info(f"Security features: rate_limit={rate_limit_enabled}, api_keys={api_key_enabled}, "
            f"ip_whitelist={ip_whitelist_enabled}, audit_log={audit_log_enabled}, "
            f"session_mgmt={session_mgmt_enabled}")

# Register entitlement enforcement middleware
from app.middleware import register_entitlement_middleware
entitlement_enabled = register_entitlement_middleware(app)
logger.info(f"Entitlement enforcement: {entitlement_enabled}")

# Register monitoring, structured logging, and health checks
from app.monitoring import register_monitoring
register_monitoring(app)

@app.teardown_appcontext
def teardown_db(exception):
    close_db(exception)

@app.route('/health', methods=['GET'])
def health_check() -> Tuple[str, int]:
    """Health check endpoint for monitoring."""
    db_info = get_database_info()
    return jsonify({
        "status": "ok",
        "database": db_info['type'],
        "version": "2.2.0"
    }), 200

# --- Data Endpoints ---

@app.route('/api/notifications', methods=['GET'])
@require_auth
def get_notifications():
    """
    Fetches the list of notifications with optional language and pagination parameters.

    Query Parameters:
        language: Language code ('en' or 'de'), default 'en'
        page: Page number (1-indexed), default 1
        page_size: Items per page (1-100), default 50
        paginate: If 'true', returns paginated response with metadata

    Returns:
        If paginate=false: {"value": [...notifications...]}
        If paginate=true: {"items": [...], "total": N, "page": N, "page_size": N, "total_pages": N}
    """
    try:
        language = request.args.get('language', 'en')

        # Validate language
        is_valid, error = validate_language(language)
        if not is_valid:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": error}}), 400

        # Parse pagination parameters
        paginate = request.args.get('paginate', 'false').lower() == 'true'
        try:
            page = int(request.args.get('page', 1))
            page_size = int(request.args.get('page_size', 50))
        except ValueError:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "page and page_size must be integers"}}), 400

        if page < 1:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "page must be >= 1"}}), 400
        if page_size < 1 or page_size > 100:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "page_size must be between 1 and 100"}}), 400

        result = get_all_notifications_summary(language, page, page_size, paginate)

        if paginate:
            return jsonify(result), 200
        else:
            # Backward compatible response
            return jsonify({"value": result}), 200

    except Exception as e:
        logger.exception("Error fetching notifications.")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": "Failed to fetch notifications"}}), 500

@app.route('/api/notifications/<id>', methods=['GET'])
@require_auth
def get_notification_detail(id):
    """Fetches a single notification with details."""
    try:
        # Validate notification ID
        is_valid, error = validate_notification_id(id)
        if not is_valid:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": error}}), 400

        language = request.args.get('language', 'en')

        # Validate language
        is_valid, error = validate_language(language)
        if not is_valid:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": error}}), 400

        notification = get_unified_notification(id, language)
        if notification:
            return jsonify(notification), 200
        else:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "Notification not found"}}), 404
    except Exception as e:
        logger.exception(f"Error fetching notification {id}.")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": "Failed to fetch notification"}}), 500

# --- Analysis Endpoints ---

@app.route('/api/analyze', methods=['POST'])
@require_auth
def analyze() -> Tuple[str, int]:
    """Analyze a notification for quality issues."""
    data = request.get_json()

    # Validate request
    is_valid, error = validate_analysis_request(data)
    if not is_valid:
        return jsonify({"error": {"code": "BAD_REQUEST", "message": error}}), 400

    language = data.get('language', 'en')

    # Support both direct payload AND ID-based analysis
    if data.get('notificationId'):
        # Fetch from DB with correct language
        notification_data = get_unified_notification(data['notificationId'], language)
        if not notification_data:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "Notification ID not found"}}), 404
    else:
        # Use provided payload (Legacy/What-If mode)
        notification_data = data['notification']

    try:
        analysis_result = analyze_text(notification_data, language)
        return jsonify(analysis_result.dict())
    except google_exceptions.PermissionDenied as e:
        logger.error(f"Google API permission denied: {e}")
        return jsonify({
            "error": {
                "code": "API_PERMISSION_DENIED",
                "message": "The backend server was denied access by the analysis service. Please check API configuration."
            }
        }), 500
    except Exception as e:
        logger.exception("An unexpected error occurred during analysis.")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred during analysis"
            }
        }), 500


@app.route('/api/chat', methods=['POST'])
@require_auth
def chat() -> Tuple[str, int]:
    """Chat with the assistant about a notification analysis."""
    data = request.get_json()

    # Validate request
    is_valid, error = validate_chat_request(data)
    if not is_valid:
        return jsonify({"error": {"code": "BAD_REQUEST", "message": error}}), 400

    notification_data = data['notification']
    question = data['question']
    analysis_context_data = data['analysis']
    language = data.get('language', 'en')

    try:
        # Convert the analysis data back into an AnalysisResponse object
        analysis_context = AnalysisResponse(**analysis_context_data)

        # Call the chat assistant with the full context
        chat_result = chat_with_assistant(notification_data, question, analysis_context, language)
        return jsonify(chat_result)
    except ValueError as e:
        logger.warning(f"Invalid analysis context data: {e}")
        return jsonify({
            "error": {
                "code": "BAD_REQUEST",
                "message": "Invalid analysis context format"
            }
        }), 400
    except Exception as e:
        logger.exception("An unexpected error occurred during chat.")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred during chat"
            }
        }), 500


# --- Configuration Endpoints ---

@app.route('/api/configuration', methods=['GET'])
@require_auth
def get_configuration():
    """Get the current application configuration."""
    try:
        config = get_config()
        return jsonify(config)
    except Exception as e:
        logger.exception("Failed to read configuration.")
        return jsonify({"error": {"code": "CONFIG_READ_ERROR", "message": "Failed to read configuration"}}), 500

@app.route('/api/configuration', methods=['POST'])
@require_admin
def set_configuration():
    """Update the application configuration."""
    try:
        config_data = request.get_json()

        # Validate configuration
        is_valid, error = validate_configuration(config_data)
        if not is_valid:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": error}}), 400

        save_config(config_data)
        logger.info("Configuration updated successfully")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.exception("Failed to save configuration.")
        return jsonify({"error": {"code": "CONFIG_WRITE_ERROR", "message": "Failed to save configuration"}}), 500


# --- Data Quality Endpoints ---

from app.services.data_quality_service import (
    calculate_notification_quality,
    calculate_batch_quality,
    calculate_quality_trend,
    to_dict
)

@app.route('/api/quality/notification/<id>', methods=['GET'])
@require_auth
def get_notification_quality(id):
    """
    Get data quality score for a single notification.

    Returns comprehensive quality metrics including ALCOA+ compliance.
    """
    try:
        # Validate notification ID
        is_valid, error = validate_notification_id(id)
        if not is_valid:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": error}}), 400

        language = request.args.get('language', 'en')

        # Get notification data
        notification = get_unified_notification(id, language)
        if not notification:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "Notification not found"}}), 404

        # Calculate quality score
        quality_score = calculate_notification_quality(notification)

        return jsonify(to_dict(quality_score))

    except Exception as e:
        logger.exception(f"Error calculating quality for notification {id}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to calculate quality score"
            }
        }), 500


@app.route('/api/quality/batch', methods=['GET'])
@require_auth
def get_batch_quality():
    """
    Get aggregate quality metrics for all notifications.

    Query Parameters:
        language: Language code ('en' or 'de'), default 'en'
        limit: Max notifications to analyze (default 100, max 1000)

    Returns:
        Aggregate statistics, score distribution, common issues, ALCOA+ summary
    """
    try:
        language = request.args.get('language', 'en')
        limit = min(int(request.args.get('limit', 100)), 1000)

        # Get notifications
        result = get_all_notifications_summary(language, page=1, page_size=limit, paginate=False)

        if not result:
            return jsonify({
                'count': 0,
                'average_score': 0,
                'message': 'No notifications found'
            })

        # Calculate batch quality
        batch_stats = calculate_batch_quality(result)

        return jsonify(batch_stats)

    except Exception as e:
        logger.exception("Error calculating batch quality")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to calculate batch quality"
            }
        }), 500


@app.route('/api/quality/trend', methods=['GET'])
@require_auth
def get_quality_trend():
    """
    Get quality trend analysis over time.

    Query Parameters:
        language: Language code ('en' or 'de'), default 'en'
        period: 'daily', 'weekly', or 'monthly' (default 'weekly')
        limit: Max notifications to analyze (default 500, max 2000)

    Returns:
        List of trend data points with average scores per period
    """
    try:
        language = request.args.get('language', 'en')
        period = request.args.get('period', 'weekly')
        limit = min(int(request.args.get('limit', 500)), 2000)

        if period not in ['daily', 'weekly', 'monthly']:
            return jsonify({
                "error": {
                    "code": "BAD_REQUEST",
                    "message": "Period must be 'daily', 'weekly', or 'monthly'"
                }
            }), 400

        # Get notifications
        result = get_all_notifications_summary(language, page=1, page_size=limit, paginate=False)

        if not result:
            return jsonify([])

        # Calculate trend
        trends = calculate_quality_trend(result, period)

        return jsonify([to_dict(t) for t in trends])

    except Exception as e:
        logger.exception("Error calculating quality trend")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to calculate quality trend"
            }
        }), 500


@app.route('/api/quality/dashboard', methods=['GET'])
@require_auth
def get_quality_dashboard():
    """
    Get comprehensive data quality dashboard data.

    Returns all metrics needed for a quality dashboard in a single call.
    """
    try:
        language = request.args.get('language', 'en')
        limit = min(int(request.args.get('limit', 200)), 500)

        # Get notifications
        notifications = get_all_notifications_summary(language, page=1, page_size=limit, paginate=False)

        if not notifications:
            return jsonify({
                'summary': {'count': 0, 'average_score': 0},
                'trends': [],
                'top_issues': [],
                'alcoa_compliance': {}
            })

        # Calculate all metrics
        batch_stats = calculate_batch_quality(notifications)
        weekly_trends = calculate_quality_trend(notifications, 'weekly')

        # Get individual scores for distribution chart
        individual_scores = []
        for notif in notifications[:50]:  # Limit for performance
            quality = calculate_notification_quality(notif)
            individual_scores.append({
                'notification_id': quality.notification_id,
                'score': quality.overall_score,
                'completeness': quality.completeness_score,
                'accuracy': quality.accuracy_score
            })

        dashboard_data = {
            'summary': {
                'count': batch_stats['count'],
                'average_score': batch_stats['average_score'],
                'min_score': batch_stats.get('min_score', 0),
                'max_score': batch_stats.get('max_score', 100),
                'score_distribution': batch_stats['score_distribution']
            },
            'trends': [to_dict(t) for t in weekly_trends[-12:]],  # Last 12 weeks
            'top_issues': batch_stats['common_issues'][:10],
            'alcoa_compliance': batch_stats['alcoa_summary'],
            'sample_scores': individual_scores,
            'generated_at': datetime.now().isoformat()
        }

        return jsonify(dashboard_data)

    except Exception as e:
        logger.exception("Error generating quality dashboard")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to generate quality dashboard"
            }
        }), 500


@app.route('/api/quality/export', methods=['GET'])
@require_auth
def export_quality_report():
    """
    Export quality report as CSV.

    Query Parameters:
        language: Language code ('en' or 'de'), default 'en'
        limit: Max notifications (default 500)

    Returns:
        CSV file with quality scores for all notifications
    """
    import csv
    from io import StringIO
    from flask import Response

    try:
        language = request.args.get('language', 'en')
        limit = min(int(request.args.get('limit', 500)), 2000)

        # Get notifications
        notifications = get_all_notifications_summary(language, page=1, page_size=limit, paginate=False)

        if not notifications:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "No notifications found"}}), 404

        # Generate CSV
        output = StringIO()
        fieldnames = [
            'notification_id', 'overall_score', 'completeness_score',
            'accuracy_score', 'timeliness_score', 'consistency_score',
            'validity_score', 'alcoa_attributable', 'alcoa_legible',
            'alcoa_contemporaneous', 'alcoa_original', 'alcoa_accurate',
            'alcoa_complete', 'alcoa_consistent', 'alcoa_enduring',
            'alcoa_available', 'issue_count', 'recommendation_count'
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for notif in notifications:
            quality = calculate_notification_quality(notif)

            row = {
                'notification_id': quality.notification_id,
                'overall_score': quality.overall_score,
                'completeness_score': quality.completeness_score,
                'accuracy_score': quality.accuracy_score,
                'timeliness_score': quality.timeliness_score,
                'consistency_score': quality.consistency_score,
                'validity_score': quality.validity_score,
                'issue_count': len(quality.issues),
                'recommendation_count': len(quality.recommendations)
            }

            # Add ALCOA+ compliance
            for principle, met in quality.alcoa_compliance.items():
                row[f'alcoa_{principle}'] = 'Yes' if met else 'No'

            writer.writerow(row)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=quality_report_{timestamp}.csv'
            }
        )

    except Exception as e:
        logger.exception("Error exporting quality report")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to export quality report"
            }
        }), 500


# --- Reliability Engineering Endpoints ---

from app.services.reliability_engineering_service import (
    get_reliability_service,
    ReliabilityEngineeringService
)

@app.route('/api/reliability/equipment/<equipment_id>/mtbf', methods=['GET'])
@require_auth
def get_equipment_mtbf(equipment_id):
    """
    Get Mean Time Between Failures for equipment.

    Query Parameters:
        period_days: Analysis period in days (default 365)
        language: Language for notifications (default 'en')

    Returns:
        MTBF in hours and days, failure count, trend analysis
    """
    try:
        period_days = int(request.args.get('period_days', 365))
        language = request.args.get('language', 'en')

        # Get notifications to populate reliability data
        notifications = get_all_notifications_summary(language, page=1, page_size=1000, paginate=False)

        service = get_reliability_service()
        service.load_notifications_as_failures(notifications)

        mtbf = service.calculate_mtbf(equipment_id, period_days)

        return jsonify({
            'equipment_id': mtbf.equipment_id,
            'mtbf_hours': mtbf.mtbf_hours,
            'mtbf_days': mtbf.mtbf_days,
            'total_operating_hours': mtbf.total_operating_hours,
            'failure_count': mtbf.failure_count,
            'calculation_period_days': mtbf.calculation_period_days,
            'confidence_level': mtbf.confidence_level,
            'trend': mtbf.trend
        })

    except Exception as e:
        logger.exception(f"Error calculating MTBF for equipment {equipment_id}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to calculate MTBF"
            }
        }), 500


@app.route('/api/reliability/equipment/<equipment_id>/mttr', methods=['GET'])
@require_auth
def get_equipment_mttr(equipment_id):
    """
    Get Mean Time To Repair for equipment.

    Query Parameters:
        period_days: Analysis period in days (default 365)
        language: Language for notifications (default 'en')

    Returns:
        MTTR statistics including min, max, and trend
    """
    try:
        period_days = int(request.args.get('period_days', 365))
        language = request.args.get('language', 'en')

        notifications = get_all_notifications_summary(language, page=1, page_size=1000, paginate=False)

        service = get_reliability_service()
        service.load_notifications_as_failures(notifications)

        mttr = service.calculate_mttr(equipment_id, period_days)

        return jsonify({
            'equipment_id': mttr.equipment_id,
            'mttr_hours': mttr.mttr_hours,
            'min_repair_time': mttr.min_repair_time,
            'max_repair_time': mttr.max_repair_time,
            'repair_count': mttr.repair_count,
            'std_deviation': mttr.std_deviation,
            'trend': mttr.trend
        })

    except Exception as e:
        logger.exception(f"Error calculating MTTR for equipment {equipment_id}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to calculate MTTR"
            }
        }), 500


@app.route('/api/reliability/equipment/<equipment_id>/availability', methods=['GET'])
@require_auth
def get_equipment_availability(equipment_id):
    """
    Get equipment availability metrics.

    Query Parameters:
        period_days: Analysis period in days (default 365)
        language: Language for notifications (default 'en')

    Returns:
        Availability percentage, uptime/downtime hours
    """
    try:
        period_days = int(request.args.get('period_days', 365))
        language = request.args.get('language', 'en')

        notifications = get_all_notifications_summary(language, page=1, page_size=1000, paginate=False)

        service = get_reliability_service()
        service.load_notifications_as_failures(notifications)

        availability = service.calculate_availability(equipment_id, period_days)

        return jsonify({
            'equipment_id': availability.equipment_id,
            'availability_percent': availability.availability_percent,
            'uptime_hours': availability.uptime_hours,
            'downtime_hours': availability.downtime_hours,
            'planned_downtime_hours': availability.planned_downtime_hours,
            'unplanned_downtime_hours': availability.unplanned_downtime_hours,
            'total_period_hours': availability.total_period_hours
        })

    except Exception as e:
        logger.exception(f"Error calculating availability for equipment {equipment_id}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to calculate availability"
            }
        }), 500


@app.route('/api/reliability/equipment/<equipment_id>/score', methods=['GET'])
@require_auth
def get_equipment_reliability_score(equipment_id):
    """
    Get comprehensive reliability score for equipment.

    Query Parameters:
        period_days: Analysis period in days (default 365)
        language: Language for notifications (default 'en')

    Returns:
        Overall reliability score, component scores, risk level, recommendations
    """
    try:
        period_days = int(request.args.get('period_days', 365))
        language = request.args.get('language', 'en')

        notifications = get_all_notifications_summary(language, page=1, page_size=1000, paginate=False)

        service = get_reliability_service()
        service.load_notifications_as_failures(notifications)

        score = service.calculate_reliability_score(equipment_id, period_days)

        return jsonify({
            'equipment_id': score.equipment_id,
            'overall_score': score.overall_score,
            'mtbf_score': score.mtbf_score,
            'mttr_score': score.mttr_score,
            'availability_score': score.availability_score,
            'failure_trend_score': score.failure_trend_score,
            'maintenance_compliance_score': score.maintenance_compliance_score,
            'risk_level': score.risk_level,
            'recommendations': score.recommendations
        })

    except Exception as e:
        logger.exception(f"Error calculating reliability score for equipment {equipment_id}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to calculate reliability score"
            }
        }), 500


@app.route('/api/reliability/equipment/<equipment_id>/predictive', methods=['GET'])
@require_auth
def get_equipment_predictive(equipment_id):
    """
    Get predictive maintenance indicators for equipment.

    Query Parameters:
        period_days: Analysis period in days (default 365)
        language: Language for notifications (default 'en')

    Returns:
        Failure probability, recommended action, urgency, contributing factors
    """
    try:
        period_days = int(request.args.get('period_days', 365))
        language = request.args.get('language', 'en')

        notifications = get_all_notifications_summary(language, page=1, page_size=1000, paginate=False)

        service = get_reliability_service()
        service.load_notifications_as_failures(notifications)

        predictive = service.generate_predictive_indicators(equipment_id, period_days)

        return jsonify({
            'equipment_id': predictive.equipment_id,
            'predicted_failure_probability': predictive.predicted_failure_probability,
            'recommended_action': predictive.recommended_action,
            'urgency': predictive.urgency,
            'estimated_remaining_life_days': predictive.estimated_remaining_life_days,
            'confidence_level': predictive.confidence_level,
            'contributing_factors': predictive.contributing_factors
        })

    except Exception as e:
        logger.exception(f"Error generating predictive indicators for equipment {equipment_id}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to generate predictive indicators"
            }
        }), 500


@app.route('/api/reliability/equipment/<equipment_id>/weibull', methods=['GET'])
@require_auth
def get_equipment_weibull(equipment_id):
    """
    Get Weibull analysis for equipment failure patterns.

    Query Parameters:
        period_days: Analysis period in days (default 365)
        language: Language for notifications (default 'en')

    Returns:
        Weibull shape/scale parameters, failure pattern, reliability estimates
    """
    try:
        period_days = int(request.args.get('period_days', 365))
        language = request.args.get('language', 'en')

        notifications = get_all_notifications_summary(language, page=1, page_size=1000, paginate=False)

        service = get_reliability_service()
        service.load_notifications_as_failures(notifications)

        weibull = service.estimate_weibull_parameters(equipment_id, period_days)

        return jsonify({
            'equipment_id': weibull.equipment_id,
            'shape_parameter': weibull.shape_parameter,
            'scale_parameter': weibull.scale_parameter,
            'failure_pattern': weibull.failure_pattern,
            'reliability_at_time': weibull.reliability_at_time
        })

    except Exception as e:
        logger.exception(f"Error calculating Weibull parameters for equipment {equipment_id}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to calculate Weibull parameters"
            }
        }), 500


@app.route('/api/reliability/fmea', methods=['GET'])
@require_auth
def get_fmea_analysis():
    """
    Get Failure Mode and Effects Analysis (FMEA) for all equipment.

    Query Parameters:
        period_days: Analysis period in days (default 365)
        language: Language for notifications (default 'en')
        limit: Max items to return (default 20)

    Returns:
        List of failure modes with RPN (Risk Priority Number) scores
    """
    try:
        period_days = int(request.args.get('period_days', 365))
        language = request.args.get('language', 'en')
        limit = int(request.args.get('limit', 20))

        notifications = get_all_notifications_summary(language, page=1, page_size=1000, paginate=False)

        service = get_reliability_service()
        service.load_notifications_as_failures(notifications)

        fmea_items = service.perform_fmea_analysis(period_days)

        result = []
        for item in fmea_items[:limit]:
            result.append({
                'failure_mode': item.failure_mode,
                'potential_effect': item.potential_effect,
                'severity': item.severity,
                'occurrence': item.occurrence,
                'detection': item.detection,
                'rpn': item.rpn,
                'recommended_action': item.recommended_action,
                'current_controls': item.current_controls,
                'equipment_affected': item.equipment_affected,
                'occurrence_count': item.occurrence_count
            })

        return jsonify({
            'fmea_items': result,
            'total_count': len(fmea_items),
            'period_days': period_days
        })

    except Exception as e:
        logger.exception("Error performing FMEA analysis")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to perform FMEA analysis"
            }
        }), 500


@app.route('/api/reliability/dashboard', methods=['GET'])
@require_auth
def get_reliability_dashboard():
    """
    Get comprehensive reliability dashboard data.

    Query Parameters:
        period_days: Analysis period in days (default 365)
        language: Language for notifications (default 'en')

    Returns:
        Overall statistics, equipment summaries, top issues, FMEA highlights
    """
    try:
        period_days = int(request.args.get('period_days', 365))
        language = request.args.get('language', 'en')

        notifications = get_all_notifications_summary(language, page=1, page_size=1000, paginate=False)

        service = get_reliability_service()
        service.load_notifications_as_failures(notifications)

        # Get equipment summary
        summary = service.get_equipment_summary(period_days)

        # Get FMEA highlights
        fmea_items = service.perform_fmea_analysis(period_days)
        fmea_highlights = []
        for item in fmea_items[:5]:
            fmea_highlights.append({
                'failure_mode': item.failure_mode,
                'rpn': item.rpn,
                'severity': item.severity,
                'recommended_action': item.recommended_action
            })

        # Calculate overall metrics
        equipment_summaries = summary.get('equipment_summaries', [])

        # Get equipment requiring attention
        attention_required = [
            eq for eq in equipment_summaries
            if eq['risk_level'] in ['critical', 'high'] or eq['failure_probability'] > 0.5
        ]

        dashboard_data = {
            'summary': {
                'total_equipment': summary['total_equipment'],
                'average_reliability_score': summary['average_reliability_score'],
                'average_availability': summary['average_availability'],
                'critical_risk_count': summary['critical_risk_count'],
                'high_risk_count': summary['high_risk_count']
            },
            'equipment_list': equipment_summaries[:20],  # Top 20
            'attention_required': attention_required[:10],
            'fmea_highlights': fmea_highlights,
            'period_days': period_days,
            'generated_at': datetime.now().isoformat()
        }

        return jsonify(dashboard_data)

    except Exception as e:
        logger.exception("Error generating reliability dashboard")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to generate reliability dashboard"
            }
        }), 500


@app.route('/api/reliability/export', methods=['GET'])
@require_auth
def export_reliability_report():
    """
    Export reliability report as CSV.

    Query Parameters:
        period_days: Analysis period in days (default 365)
        language: Language for notifications (default 'en')

    Returns:
        CSV file with reliability metrics for all equipment
    """
    import csv
    from io import StringIO
    from flask import Response

    try:
        period_days = int(request.args.get('period_days', 365))
        language = request.args.get('language', 'en')

        notifications = get_all_notifications_summary(language, page=1, page_size=1000, paginate=False)

        service = get_reliability_service()
        service.load_notifications_as_failures(notifications)

        summary = service.get_equipment_summary(period_days)
        equipment_summaries = summary.get('equipment_summaries', [])

        output = StringIO()
        fieldnames = [
            'equipment_id', 'reliability_score', 'availability_percent',
            'risk_level', 'failure_probability', 'urgency',
            'top_recommendation'
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for eq in equipment_summaries:
            writer.writerow({
                'equipment_id': eq['equipment_id'],
                'reliability_score': eq['reliability_score'],
                'availability_percent': eq['availability'],
                'risk_level': eq['risk_level'],
                'failure_probability': eq['failure_probability'],
                'urgency': eq['urgency'],
                'top_recommendation': eq['recommendations'][0] if eq['recommendations'] else ''
            })

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=reliability_report_{timestamp}.csv'
            }
        )

    except Exception as e:
        logger.exception("Error exporting reliability report")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to export reliability report"
            }
        }), 500


# --- Audit Trail & Change Document Endpoints (FDA 21 CFR Part 11) ---

from app.services.change_document_service import (
    get_change_document_service,
    ChangeDocumentService
)

@app.route('/api/audit/changes', methods=['GET'])
@require_role('admin', 'auditor')
def get_change_history():
    """
    Get change document history for audit trail.

    Query Parameters:
        object_class: Filter by object class (QMEL, AUFK, etc.)
        object_id: Filter by specific object ID
        username: Filter by user who made changes
        from_date: Start date (YYYYMMDD)
        to_date: End date (YYYYMMDD)
        limit: Max records to return (default 100)

    Returns:
        List of change history entries with field-level details
    """
    try:
        object_class = request.args.get('object_class')
        object_id = request.args.get('object_id')
        username = request.args.get('username')
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        limit = int(request.args.get('limit', 100))

        service = get_change_document_service()
        history = service.get_change_history(
            object_class=object_class,
            object_id=object_id,
            username=username,
            from_date=from_date,
            to_date=to_date,
            limit=limit
        )

        # Convert to JSON-serializable format
        results = []
        for entry in history:
            results.append({
                'change_number': entry.change_number,
                'timestamp': entry.timestamp.isoformat(),
                'user': entry.user,
                'object_type': entry.object_type,
                'object_id': entry.object_id,
                'change_type': entry.change_type,
                'fields_changed': entry.fields_changed,
                'transaction_code': entry.transaction_code
            })

        return jsonify({
            'changes': results,
            'count': len(results)
        })

    except Exception as e:
        logger.exception("Error getting change history")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get change history"
            }
        }), 500


@app.route('/api/audit/changes/<object_class>/<object_id>', methods=['GET'])
@require_role('admin', 'auditor')
def get_object_change_history(object_class, object_id):
    """
    Get change history for a specific object.

    Path Parameters:
        object_class: Object class (QMEL, AUFK, etc.)
        object_id: Object identifier

    Returns:
        Complete change history for the object
    """
    try:
        service = get_change_document_service()
        history = service.get_change_history(
            object_class=object_class.upper(),
            object_id=object_id,
            limit=500
        )

        results = []
        for entry in history:
            results.append({
                'change_number': entry.change_number,
                'timestamp': entry.timestamp.isoformat(),
                'user': entry.user,
                'change_type': entry.change_type,
                'fields_changed': entry.fields_changed,
                'transaction_code': entry.transaction_code
            })

        return jsonify({
            'object_class': object_class.upper(),
            'object_id': object_id,
            'changes': results,
            'count': len(results)
        })

    except Exception as e:
        logger.exception(f"Error getting change history for {object_class}/{object_id}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get object change history"
            }
        }), 500


@app.route('/api/audit/report', methods=['GET'])
@require_role('admin', 'auditor')
def get_audit_report():
    """
    Generate comprehensive audit report for compliance.

    Query Parameters:
        from_date: Start date (YYYYMMDD)
        to_date: End date (YYYYMMDD)
        object_class: Filter by object class
        username: Filter by user

    Returns:
        Audit report with summary statistics, changes by user/object
    """
    try:
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        object_class = request.args.get('object_class')
        username = request.args.get('username')

        service = get_change_document_service()
        report = service.get_audit_report(
            from_date=from_date,
            to_date=to_date,
            object_class=object_class,
            username=username
        )

        return jsonify(report)

    except Exception as e:
        logger.exception("Error generating audit report")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to generate audit report"
            }
        }), 500


@app.route('/api/audit/notification/<notification_id>/history', methods=['GET'])
@require_role('admin', 'auditor')
def get_notification_change_history(notification_id):
    """
    Get notification-specific change history (QMIH).

    Path Parameters:
        notification_id: Notification number

    Returns:
        Notification version history with change reasons
    """
    try:
        # Validate notification ID
        is_valid, error = validate_notification_id(notification_id)
        if not is_valid:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": error}}), 400

        service = get_change_document_service()
        history = service.get_notification_history(notification_id)

        return jsonify({
            'notification_id': notification_id,
            'history': history,
            'count': len(history)
        })

    except Exception as e:
        logger.exception(f"Error getting notification history for {notification_id}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get notification history"
            }
        }), 500


@app.route('/api/status/<object_number>', methods=['GET'])
@require_auth
def get_object_status(object_number):
    """
    Get current status of an object (JEST).

    Path Parameters:
        object_number: Internal object number

    Returns:
        List of active statuses for the object
    """
    try:
        service = get_change_document_service()
        statuses = service.get_status(object_number)

        return jsonify({
            'object_number': object_number,
            'statuses': statuses
        })

    except Exception as e:
        logger.exception(f"Error getting status for {object_number}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get object status"
            }
        }), 500


@app.route('/api/confirmations/<order_number>', methods=['GET'])
@require_auth
def get_order_confirmations(order_number):
    """
    Get time confirmations for an order (AFRU).

    Path Parameters:
        order_number: Order number

    Query Parameters:
        operation: Filter by operation number

    Returns:
        List of time confirmation records
    """
    try:
        operation_number = request.args.get('operation')

        service = get_change_document_service()
        confirmations = service.get_time_confirmations(
            order_number,
            operation_number=operation_number
        )

        return jsonify({
            'order_number': order_number,
            'confirmations': confirmations,
            'count': len(confirmations),
            'total_hours': sum(c['actual_work_hours'] for c in confirmations)
        })

    except Exception as e:
        logger.exception(f"Error getting confirmations for order {order_number}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get order confirmations"
            }
        }), 500


@app.route('/api/confirmations/<order_number>', methods=['POST'])
@require_role('admin', 'editor')
def create_time_confirmation(order_number):
    """
    Record a time confirmation for an order.

    Path Parameters:
        order_number: Order number

    Request Body:
        operation_number: Operation number (optional)
        actual_work_hours: Hours worked
        actual_start: Start datetime (ISO format)
        actual_end: End datetime (ISO format)
        confirmation_text: Note/comment
        final_confirmation: Boolean
        username: User recording confirmation

    Returns:
        Confirmation number
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "Request body required"}}), 400

        username = data.get('username', 'SYSTEM')
        actual_work_hours = float(data.get('actual_work_hours', 0))

        # Parse datetime fields
        actual_start = None
        actual_end = None
        if data.get('actual_start'):
            actual_start = datetime.fromisoformat(data['actual_start'].replace('Z', '+00:00'))
        if data.get('actual_end'):
            actual_end = datetime.fromisoformat(data['actual_end'].replace('Z', '+00:00'))

        service = get_change_document_service()
        confirmation_number = service.record_time_confirmation(
            order_number=order_number,
            operation_number=data.get('operation_number'),
            username=username,
            actual_work_hours=actual_work_hours,
            actual_start=actual_start,
            actual_end=actual_end,
            confirmation_text=data.get('confirmation_text'),
            final_confirmation=data.get('final_confirmation', False)
        )

        return jsonify({
            'confirmation_number': confirmation_number,
            'order_number': order_number,
            'status': 'created'
        }), 201

    except Exception as e:
        logger.exception(f"Error creating confirmation for order {order_number}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to create time confirmation"
            }
        }), 500


@app.route('/api/audit/export', methods=['GET'])
@require_role('admin', 'auditor')
def export_audit_report():
    """
    Export audit report as CSV.

    Query Parameters:
        from_date: Start date (YYYYMMDD)
        to_date: End date (YYYYMMDD)
        object_class: Filter by object class
        username: Filter by user

    Returns:
        CSV file with audit trail data
    """
    import csv
    from io import StringIO
    from flask import Response

    try:
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        object_class = request.args.get('object_class')
        username = request.args.get('username')

        service = get_change_document_service()
        history = service.get_change_history(
            object_class=object_class,
            username=username,
            from_date=from_date,
            to_date=to_date,
            limit=5000
        )

        output = StringIO()
        fieldnames = [
            'change_number', 'timestamp', 'user', 'object_type', 'object_id',
            'change_type', 'table', 'field', 'old_value', 'new_value'
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for entry in history:
            for field_change in entry.fields_changed:
                writer.writerow({
                    'change_number': entry.change_number,
                    'timestamp': entry.timestamp.isoformat(),
                    'user': entry.user,
                    'object_type': entry.object_type,
                    'object_id': entry.object_id,
                    'change_type': entry.change_type,
                    'table': field_change.get('table', ''),
                    'field': field_change.get('field', ''),
                    'old_value': field_change.get('old_value', ''),
                    'new_value': field_change.get('new_value', '')
                })

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=audit_report_{timestamp}.csv'
            }
        )

    except Exception as e:
        logger.exception("Error exporting audit report")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to export audit report"
            }
        }), 500


# --- PDF Report Generation Endpoints ---

from app.services.report_generation_service import (
    ReportGenerationService,
    check_reportlab_available
)

# Get database path for reports
REPORT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'pm_data.db'
)


@app.route('/api/reports/notification/<notification_id>/pdf', methods=['GET'])
@require_auth
def get_notification_pdf_report(notification_id):
    """
    Generate PDF report for a single notification.

    Path Parameters:
        notification_id: Notification number

    Query Parameters:
        language: Language code ('en' or 'de'), default 'en'

    Returns:
        PDF file
    """
    from flask import Response

    try:
        # Validate notification ID
        is_valid, error = validate_notification_id(notification_id)
        if not is_valid:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": error}}), 400

        if not check_reportlab_available():
            return jsonify({
                "error": {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "PDF generation not available. Install reportlab package."
                }
            }), 503

        language = request.args.get('language', 'en')

        service = ReportGenerationService(REPORT_DB_PATH)
        pdf_bytes = service.generate_notification_report(notification_id, language)

        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename=notification_{notification_id}_report.pdf'
            }
        )

    except ValueError as e:
        return jsonify({"error": {"code": "NOT_FOUND", "message": str(e)}}), 404
    except Exception as e:
        logger.exception(f"Error generating PDF report for notification {notification_id}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to generate PDF report"
            }
        }), 500


@app.route('/api/reports/audit/pdf', methods=['GET'])
@require_role('admin', 'auditor')
def get_audit_pdf_report():
    """
    Generate PDF audit trail report.

    Query Parameters:
        from_date: Start date (YYYYMMDD)
        to_date: End date (YYYYMMDD)
        object_class: Filter by object class
        username: Filter by user

    Returns:
        PDF file
    """
    from flask import Response

    try:
        if not check_reportlab_available():
            return jsonify({
                "error": {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "PDF generation not available. Install reportlab package."
                }
            }), 503

        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        object_class = request.args.get('object_class')
        username = request.args.get('username')

        service = ReportGenerationService(REPORT_DB_PATH)
        pdf_bytes = service.generate_audit_report(
            from_date=from_date,
            to_date=to_date,
            object_class=object_class,
            username=username
        )

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename=audit_report_{timestamp}.pdf'
            }
        )

    except Exception as e:
        logger.exception("Error generating PDF audit report")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to generate PDF audit report"
            }
        }), 500


@app.route('/api/reports/quality/pdf', methods=['GET'])
@require_auth
def get_quality_pdf_report():
    """
    Generate PDF quality analytics report.

    Query Parameters:
        period_days: Analysis period in days (default 30)

    Returns:
        PDF file
    """
    from flask import Response

    try:
        if not check_reportlab_available():
            return jsonify({
                "error": {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "PDF generation not available. Install reportlab package."
                }
            }), 503

        period_days = int(request.args.get('period_days', 30))

        service = ReportGenerationService(REPORT_DB_PATH)
        pdf_bytes = service.generate_quality_report(period_days=period_days)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename=quality_report_{timestamp}.pdf'
            }
        )

    except Exception as e:
        logger.exception("Error generating PDF quality report")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to generate PDF quality report"
            }
        }), 500


@app.route('/api/reports/reliability/pdf', methods=['GET'])
@require_auth
def get_reliability_pdf_report():
    """
    Generate PDF reliability engineering report.

    Returns:
        PDF file
    """
    from flask import Response

    try:
        if not check_reportlab_available():
            return jsonify({
                "error": {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "PDF generation not available. Install reportlab package."
                }
            }), 503

        service = ReportGenerationService(REPORT_DB_PATH)
        pdf_bytes = service.generate_reliability_report()

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename=reliability_report_{timestamp}.pdf'
            }
        )

    except Exception as e:
        logger.exception("Error generating PDF reliability report")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to generate PDF reliability report"
            }
        }), 500


@app.route('/api/reports/available', methods=['GET'])
@require_auth
def get_available_reports():
    """
    Get list of available report types and their status.

    Returns:
        List of report types with availability status
    """
    pdf_available = check_reportlab_available()

    return jsonify({
        'pdf_generation_available': pdf_available,
        'reports': [
            {
                'type': 'notification',
                'name': 'Notification Report',
                'description': 'Detailed PDF report for a single notification',
                'endpoint': '/api/reports/notification/{id}/pdf',
                'formats': ['pdf'] if pdf_available else []
            },
            {
                'type': 'audit',
                'name': 'Audit Trail Report',
                'description': 'FDA 21 CFR Part 11 compliant audit report',
                'endpoint': '/api/reports/audit/pdf',
                'formats': ['pdf', 'csv'] if pdf_available else ['csv']
            },
            {
                'type': 'quality',
                'name': 'Quality Analytics Report',
                'description': 'Data quality metrics and ALCOA+ compliance',
                'endpoint': '/api/reports/quality/pdf',
                'formats': ['pdf', 'csv'] if pdf_available else ['csv']
            },
            {
                'type': 'reliability',
                'name': 'Reliability Engineering Report',
                'description': 'Equipment reliability metrics and FMEA analysis',
                'endpoint': '/api/reports/reliability/pdf',
                'formats': ['pdf', 'csv'] if pdf_available else ['csv']
            }
        ]
    })


# --- Email Notification & Alert Endpoints ---

@app.route('/api/alerts/test', methods=['POST'])
@require_auth
def send_test_alert():
    """
    Send a test alert email to verify notification configuration.

    Request Body:
        email: Email address to send test to

    Returns:
        Success status
    """
    try:
        data = request.get_json()

        if not data or not data.get('email'):
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "Email address required"}}), 400

        email = data['email']

        service = get_notification_service()

        # Send a test alert
        test_alert = Alert(
            alert_id='TEST-001',
            alert_type=AlertType.SYSTEM,
            severity=AlertSeverity.INFO,
            title='Test Alert',
            message='This is a test alert to verify your notification configuration is working correctly.',
            source='PM Notification Analyzer',
            context={'test': True}
        )

        success = service.send_alert(test_alert, [email])

        if success:
            return jsonify({
                'status': 'sent',
                'message': f'Test alert sent to {email}'
            })
        else:
            return jsonify({
                'status': 'failed',
                'message': 'Failed to send test alert. Check email configuration.'
            }), 500

    except Exception as e:
        logger.exception("Error sending test alert")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        }), 500


@app.route('/api/alerts/rules', methods=['GET'])
@require_auth
def get_alert_rules():
    """
    Get all configured alert rules.

    Returns:
        List of alert rules
    """
    try:
        service = get_alert_rules_service()
        rules = service.get_all_rules()

        return jsonify({
            'rules': [
                {
                    'rule_id': rule.rule_id,
                    'name': rule.name,
                    'description': rule.description,
                    'enabled': rule.enabled,
                    'severity': rule.severity.value,
                    'alert_type': rule.alert_type.value,
                    'conditions': [
                        {
                            'field': c.field,
                            'operator': c.operator,
                            'value': c.value,
                            'field_type': c.field_type
                        } for c in rule.conditions
                    ],
                    'cooldown_minutes': rule.cooldown_minutes
                }
                for rule in rules
            ],
            'count': len(rules)
        })

    except Exception as e:
        logger.exception("Error getting alert rules")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get alert rules"
            }
        }), 500


@app.route('/api/alerts/rules', methods=['POST'])
@require_role('admin', 'editor')
def create_alert_rule():
    """
    Create a new alert rule.

    Request Body:
        name: Rule name
        description: Rule description
        conditions: List of conditions
        severity: Alert severity (critical, high, medium, low, info)
        alert_type: Alert type (quality, reliability, compliance, overdue, system)
        cooldown_minutes: Minimum minutes between alerts

    Returns:
        Created rule
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "Request body required"}}), 400

        required_fields = ['name', 'conditions', 'severity', 'alert_type']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": {"code": "BAD_REQUEST", "message": f"Missing required field: {field}"}}), 400

        # Parse conditions
        conditions = []
        for cond in data['conditions']:
            conditions.append(RuleCondition(
                field=cond['field'],
                operator=cond['operator'],
                value=cond['value'],
                field_type=cond.get('field_type', 'string')
            ))

        # Create rule
        rule = AlertRule(
            rule_id=f"RULE-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            name=data['name'],
            description=data.get('description', ''),
            conditions=conditions,
            severity=AlertSeverity(data['severity']),
            alert_type=AlertType(data['alert_type']),
            enabled=data.get('enabled', True),
            cooldown_minutes=int(data.get('cooldown_minutes', 60))
        )

        service = get_alert_rules_service()
        created_rule = service.add_rule(rule)

        return jsonify({
            'rule_id': created_rule.rule_id,
            'name': created_rule.name,
            'status': 'created'
        }), 201

    except ValueError as e:
        return jsonify({"error": {"code": "BAD_REQUEST", "message": str(e)}}), 400
    except Exception as e:
        logger.exception("Error creating alert rule")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to create alert rule"
            }
        }), 500


@app.route('/api/alerts/rules/<rule_id>', methods=['PUT'])
@require_role('admin', 'editor')
def update_alert_rule(rule_id):
    """
    Update an existing alert rule.

    Path Parameters:
        rule_id: Rule identifier

    Request Body:
        enabled: Enable/disable rule
        Other rule fields to update

    Returns:
        Updated rule
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "Request body required"}}), 400

        service = get_alert_rules_service()

        # Get existing rule
        existing_rule = service.get_rule(rule_id)
        if not existing_rule:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "Rule not found"}}), 404

        # Update fields
        if 'enabled' in data:
            existing_rule.enabled = data['enabled']
        if 'name' in data:
            existing_rule.name = data['name']
        if 'description' in data:
            existing_rule.description = data['description']
        if 'cooldown_minutes' in data:
            existing_rule.cooldown_minutes = int(data['cooldown_minutes'])
        if 'conditions' in data:
            conditions = []
            for cond in data['conditions']:
                conditions.append(RuleCondition(
                    field=cond['field'],
                    operator=cond['operator'],
                    value=cond['value'],
                    field_type=cond.get('field_type', 'string')
                ))
            existing_rule.conditions = conditions

        service.update_rule(existing_rule)

        return jsonify({
            'rule_id': rule_id,
            'status': 'updated'
        })

    except Exception as e:
        logger.exception(f"Error updating alert rule {rule_id}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to update alert rule"
            }
        }), 500


@app.route('/api/alerts/rules/<rule_id>', methods=['DELETE'])
@require_admin
def delete_alert_rule(rule_id):
    """
    Delete an alert rule.

    Path Parameters:
        rule_id: Rule identifier

    Returns:
        Deletion status
    """
    try:
        service = get_alert_rules_service()

        success = service.remove_rule(rule_id)

        if success:
            return jsonify({
                'rule_id': rule_id,
                'status': 'deleted'
            })
        else:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "Rule not found"}}), 404

    except Exception as e:
        logger.exception(f"Error deleting alert rule {rule_id}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to delete alert rule"
            }
        }), 500


@app.route('/api/alerts/subscriptions', methods=['GET'])
@require_auth
def get_subscriptions():
    """
    Get alert subscriptions for current user or all (admin).

    Query Parameters:
        all: If 'true' and user is admin, return all subscriptions

    Returns:
        List of subscriptions
    """
    try:
        service = get_alert_rules_service()
        current_user = get_current_user()

        # Admins can see all subscriptions
        show_all = request.args.get('all', 'false').lower() == 'true'

        if show_all and current_user and 'admin' in current_user.get('roles', []):
            subscriptions = service.get_all_subscriptions()
        else:
            user_email = current_user.get('email') if current_user else None
            if not user_email:
                return jsonify({'subscriptions': [], 'count': 0})
            subscriptions = service.get_user_subscriptions(user_email)

        return jsonify({
            'subscriptions': [
                {
                    'subscription_id': sub.subscription_id,
                    'user_email': sub.user_email,
                    'alert_types': [t.value for t in sub.alert_types],
                    'severities': [s.value for s in sub.severities],
                    'equipment_filter': sub.equipment_filter,
                    'enabled': sub.enabled,
                    'created_at': sub.created_at.isoformat() if sub.created_at else None
                }
                for sub in subscriptions
            ],
            'count': len(subscriptions)
        })

    except Exception as e:
        logger.exception("Error getting subscriptions")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get subscriptions"
            }
        }), 500


@app.route('/api/alerts/subscriptions', methods=['POST'])
@require_auth
def create_subscription():
    """
    Create a new alert subscription.

    Request Body:
        user_email: Email to receive alerts (optional, defaults to current user)
        alert_types: List of alert types to subscribe to
        severities: List of severities to receive
        equipment_filter: Optional list of equipment IDs to filter

    Returns:
        Created subscription
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "Request body required"}}), 400

        current_user = get_current_user()

        # Use provided email or current user's email
        user_email = data.get('user_email')
        if not user_email and current_user:
            user_email = current_user.get('email')

        if not user_email:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "Email address required"}}), 400

        # Parse alert types
        alert_types = [AlertType(t) for t in data.get('alert_types', ['quality', 'reliability', 'compliance'])]

        # Parse severities
        severities = [AlertSeverity(s) for s in data.get('severities', ['critical', 'high'])]

        subscription = Subscription(
            subscription_id=f"SUB-{datetime.now().strftime('%Y%m%d%H%M%S')}-{user_email[:5]}",
            user_email=user_email,
            alert_types=alert_types,
            severities=severities,
            equipment_filter=data.get('equipment_filter'),
            enabled=data.get('enabled', True)
        )

        service = get_alert_rules_service()
        created = service.create_subscription(subscription)

        return jsonify({
            'subscription_id': created.subscription_id,
            'user_email': created.user_email,
            'status': 'created'
        }), 201

    except ValueError as e:
        return jsonify({"error": {"code": "BAD_REQUEST", "message": str(e)}}), 400
    except Exception as e:
        logger.exception("Error creating subscription")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to create subscription"
            }
        }), 500


@app.route('/api/alerts/subscriptions/<subscription_id>', methods=['PUT'])
@require_auth
def update_subscription(subscription_id):
    """
    Update an existing subscription.

    Path Parameters:
        subscription_id: Subscription identifier

    Request Body:
        enabled: Enable/disable subscription
        alert_types: Updated alert types
        severities: Updated severities

    Returns:
        Update status
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "Request body required"}}), 400

        service = get_alert_rules_service()
        current_user = get_current_user()

        # Get existing subscription
        existing = service.get_subscription(subscription_id)
        if not existing:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "Subscription not found"}}), 404

        # Check ownership (unless admin)
        is_admin = current_user and 'admin' in current_user.get('roles', [])
        if not is_admin and current_user.get('email') != existing.user_email:
            return jsonify({"error": {"code": "FORBIDDEN", "message": "Cannot modify another user's subscription"}}), 403

        # Update fields
        if 'enabled' in data:
            existing.enabled = data['enabled']
        if 'alert_types' in data:
            existing.alert_types = [AlertType(t) for t in data['alert_types']]
        if 'severities' in data:
            existing.severities = [AlertSeverity(s) for s in data['severities']]
        if 'equipment_filter' in data:
            existing.equipment_filter = data['equipment_filter']

        service.update_subscription(existing)

        return jsonify({
            'subscription_id': subscription_id,
            'status': 'updated'
        })

    except ValueError as e:
        return jsonify({"error": {"code": "BAD_REQUEST", "message": str(e)}}), 400
    except Exception as e:
        logger.exception(f"Error updating subscription {subscription_id}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to update subscription"
            }
        }), 500


@app.route('/api/alerts/subscriptions/<subscription_id>', methods=['DELETE'])
@require_auth
def delete_subscription(subscription_id):
    """
    Delete a subscription.

    Path Parameters:
        subscription_id: Subscription identifier

    Returns:
        Deletion status
    """
    try:
        service = get_alert_rules_service()
        current_user = get_current_user()

        # Get existing subscription
        existing = service.get_subscription(subscription_id)
        if not existing:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "Subscription not found"}}), 404

        # Check ownership (unless admin)
        is_admin = current_user and 'admin' in current_user.get('roles', [])
        if not is_admin and current_user.get('email') != existing.user_email:
            return jsonify({"error": {"code": "FORBIDDEN", "message": "Cannot delete another user's subscription"}}), 403

        service.remove_subscription(subscription_id)

        return jsonify({
            'subscription_id': subscription_id,
            'status': 'deleted'
        })

    except Exception as e:
        logger.exception(f"Error deleting subscription {subscription_id}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to delete subscription"
            }
        }), 500


@app.route('/api/alerts/evaluate', methods=['POST'])
@require_role('admin', 'editor')
def evaluate_alerts():
    """
    Evaluate alert rules against provided data and trigger alerts.

    Request Body:
        data: Dictionary of data to evaluate
        context: Optional context string

    Returns:
        List of triggered alerts
    """
    try:
        data = request.get_json()

        if not data or 'data' not in data:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "Data object required"}}), 400

        service = get_alert_rules_service()
        alerts = service.evaluate_and_alert(
            data=data['data'],
            context=data.get('context', '')
        )

        return jsonify({
            'alerts_triggered': len(alerts),
            'alerts': [
                {
                    'alert_id': alert.alert_id,
                    'title': alert.title,
                    'severity': alert.severity.value,
                    'alert_type': alert.alert_type.value,
                    'message': alert.message
                }
                for alert in alerts
            ]
        })

    except Exception as e:
        logger.exception("Error evaluating alerts")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to evaluate alerts"
            }
        }), 500


@app.route('/api/alerts/config', methods=['GET'])
@require_admin
def get_notification_config():
    """
    Get email notification configuration status (admin only).

    Returns:
        Configuration status (no sensitive data)
    """
    try:
        service = get_notification_service()
        config = service.get_config_status()

        return jsonify(config)

    except Exception as e:
        logger.exception("Error getting notification config")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get notification configuration"
            }
        }), 500


# --- SAP Integration Endpoints ---

from app.services.sap_integration_service import (
    get_sap_service,
    check_sap_available,
    SAPIntegrationService
)


@app.route('/api/sap/status', methods=['GET'])
@require_auth
def get_sap_status():
    """
    Get SAP integration status and availability.

    Returns:
        Connection status, availability info, and configuration
    """
    try:
        availability = check_sap_available()
        service = get_sap_service()
        connection_status = service.get_connection_status()

        return jsonify({
            'availability': availability,
            'connection': connection_status
        })

    except Exception as e:
        logger.exception("Error getting SAP status")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get SAP status"
            }
        }), 500


@app.route('/api/sap/connect', methods=['POST'])
@require_admin
def connect_to_sap():
    """
    Establish connection to SAP system.

    Returns:
        Connection result
    """
    try:
        service = get_sap_service()

        if service.is_connected():
            return jsonify({
                'status': 'already_connected',
                'message': 'Already connected to SAP'
            })

        success = service.connect()

        if success:
            return jsonify({
                'status': 'connected',
                'message': 'Successfully connected to SAP',
                'connection': service.get_connection_status()
            })
        else:
            return jsonify({
                'status': 'failed',
                'message': 'Failed to connect to SAP. Check configuration and credentials.'
            }), 503

    except Exception as e:
        logger.exception("Error connecting to SAP")
        return jsonify({
            "error": {
                "code": "CONNECTION_ERROR",
                "message": str(e)
            }
        }), 500


@app.route('/api/sap/disconnect', methods=['POST'])
@require_admin
def disconnect_from_sap():
    """
    Disconnect from SAP system.

    Returns:
        Disconnect result
    """
    try:
        service = get_sap_service()
        service.disconnect()

        return jsonify({
            'status': 'disconnected',
            'message': 'Disconnected from SAP'
        })

    except Exception as e:
        logger.exception("Error disconnecting from SAP")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        }), 500


@app.route('/api/sap/notifications/<notification_id>', methods=['GET'])
@require_auth
def get_sap_notification(notification_id):
    """
    Get notification from SAP system.

    Path Parameters:
        notification_id: SAP notification number

    Returns:
        Notification data from SAP
    """
    try:
        # Validate notification ID
        is_valid, error = validate_notification_id(notification_id)
        if not is_valid:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": error}}), 400

        service = get_sap_service()

        if not service.is_connected():
            return jsonify({
                "error": {
                    "code": "NOT_CONNECTED",
                    "message": "Not connected to SAP. Call /api/sap/connect first."
                }
            }), 503

        result = service.get_notification(notification_id)

        if result.success:
            return jsonify({
                'success': True,
                'data': result.data,
                'messages': result.return_messages
            })
        else:
            return jsonify({
                'success': False,
                'error': result.error_message,
                'messages': result.return_messages
            }), 404

    except Exception as e:
        logger.exception(f"Error getting SAP notification {notification_id}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        }), 500


@app.route('/api/sap/notifications', methods=['POST'])
@require_role('admin', 'editor')
def create_sap_notification():
    """
    Create notification in SAP system.

    Request Body:
        NotificationType: Notification type (M1, M2, etc.)
        Description: Short text
        Priority: Priority code
        EquipmentNumber: Equipment
        FunctionalLocation: Functional location

    Returns:
        Created notification ID
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "Request body required"}}), 400

        service = get_sap_service()

        if not service.is_connected():
            return jsonify({
                "error": {
                    "code": "NOT_CONNECTED",
                    "message": "Not connected to SAP. Call /api/sap/connect first."
                }
            }), 503

        result = service.create_notification(data)

        if result.success:
            return jsonify({
                'success': True,
                'data': result.data,
                'messages': result.return_messages
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': result.error_message,
                'messages': result.return_messages
            }), 400

    except Exception as e:
        logger.exception("Error creating SAP notification")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        }), 500


@app.route('/api/sap/orders/<order_number>', methods=['GET'])
@require_auth
def get_sap_order(order_number):
    """
    Get work order from SAP system.

    Path Parameters:
        order_number: SAP order number

    Returns:
        Work order data from SAP
    """
    try:
        service = get_sap_service()

        if not service.is_connected():
            return jsonify({
                "error": {
                    "code": "NOT_CONNECTED",
                    "message": "Not connected to SAP. Call /api/sap/connect first."
                }
            }), 503

        result = service.get_work_order(order_number)

        if result.success:
            return jsonify({
                'success': True,
                'data': result.data,
                'messages': result.return_messages
            })
        else:
            return jsonify({
                'success': False,
                'error': result.error_message,
                'messages': result.return_messages
            }), 404

    except Exception as e:
        logger.exception(f"Error getting SAP order {order_number}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        }), 500


@app.route('/api/sap/equipment/<equipment_number>', methods=['GET'])
@require_auth
def get_sap_equipment(equipment_number):
    """
    Get equipment master data from SAP system.

    Path Parameters:
        equipment_number: SAP equipment number

    Returns:
        Equipment data from SAP
    """
    try:
        service = get_sap_service()

        if not service.is_connected():
            return jsonify({
                "error": {
                    "code": "NOT_CONNECTED",
                    "message": "Not connected to SAP. Call /api/sap/connect first."
                }
            }), 503

        result = service.get_equipment(equipment_number)

        if result.success:
            return jsonify({
                'success': True,
                'data': result.data,
                'messages': result.return_messages
            })
        else:
            return jsonify({
                'success': False,
                'error': result.error_message,
                'messages': result.return_messages
            }), 404

    except Exception as e:
        logger.exception(f"Error getting SAP equipment {equipment_number}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        }), 500


@app.route('/api/sap/sync/notifications', methods=['POST'])
@require_admin
def sync_sap_notifications():
    """
    Synchronize notifications from SAP to local database.

    Request Body (optional):
        date_from: Start date (YYYYMMDD)
        date_to: End date (YYYYMMDD)
        notification_type: Filter by type
        limit: Max records (default 1000)

    Returns:
        Sync result with statistics
    """
    try:
        data = request.get_json() or {}

        service = get_sap_service()

        if not service.is_connected():
            return jsonify({
                "error": {
                    "code": "NOT_CONNECTED",
                    "message": "Not connected to SAP. Call /api/sap/connect first."
                }
            }), 503

        result = service.sync_notifications(
            date_from=data.get('date_from'),
            date_to=data.get('date_to'),
            notification_type=data.get('notification_type'),
            limit=int(data.get('limit', 1000))
        )

        return jsonify({
            'success': result.success,
            'records_processed': result.records_processed,
            'records_created': result.records_created,
            'records_updated': result.records_updated,
            'records_failed': result.records_failed,
            'errors': result.errors,
            'warnings': result.warnings,
            'duration_seconds': result.duration_seconds,
            'timestamp': result.timestamp.isoformat()
        })

    except Exception as e:
        logger.exception("Error syncing SAP notifications")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        }), 500


@app.route('/api/sap/changes/<object_class>/<object_id>', methods=['GET'])
@require_role('admin', 'auditor')
def get_sap_change_documents(object_class, object_id):
    """
    Get change documents from SAP for an object.

    Path Parameters:
        object_class: SAP object class (QMEL, AUFK, etc.)
        object_id: Object identifier

    Query Parameters:
        date_from: Start date (YYYYMMDD)
        date_to: End date (YYYYMMDD)

    Returns:
        Change documents from SAP
    """
    try:
        service = get_sap_service()

        if not service.is_connected():
            return jsonify({
                "error": {
                    "code": "NOT_CONNECTED",
                    "message": "Not connected to SAP. Call /api/sap/connect first."
                }
            }), 503

        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')

        result = service.get_change_documents(
            object_class=object_class.upper(),
            object_id=object_id,
            date_from=date_from,
            date_to=date_to
        )

        if result.success:
            return jsonify({
                'success': True,
                'data': result.data
            })
        else:
            return jsonify({
                'success': False,
                'error': result.error_message
            }), 400

    except Exception as e:
        logger.exception(f"Error getting SAP change documents for {object_class}/{object_id}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        }), 500


# --- Security Administration Endpoints ---

@app.route('/api/security/api-keys', methods=['GET'])
@require_admin
def list_api_keys():
    """
    List all API keys (admin only).

    Query Parameters:
        include_inactive: Include revoked/inactive keys

    Returns:
        List of API keys (without actual key values)
    """
    try:
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        manager = get_api_key_manager()
        keys = manager.list_keys(include_inactive=include_inactive)

        return jsonify({
            'api_keys': [
                {
                    'key_id': key.key_id,
                    'name': key.name,
                    'key_prefix': key.key_prefix,
                    'created_at': key.created_at.isoformat(),
                    'expires_at': key.expires_at.isoformat() if key.expires_at else None,
                    'last_used_at': key.last_used_at.isoformat() if key.last_used_at else None,
                    'is_active': key.is_active,
                    'scopes': key.scopes,
                    'created_by': key.created_by
                }
                for key in keys
            ],
            'count': len(keys)
        })

    except Exception as e:
        logger.exception("Error listing API keys")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to list API keys"
            }
        }), 500


@app.route('/api/security/api-keys', methods=['POST'])
@require_admin
def create_api_key():
    """
    Create a new API key (admin only).

    Request Body:
        name: Key name/description
        scopes: List of scopes (default: ['read'])
        expires_in_days: Days until expiry (optional)
        ip_whitelist: List of allowed IPs (optional)

    Returns:
        Created key info including the raw key (shown only once)
    """
    try:
        data = request.get_json()

        if not data or not data.get('name'):
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "Key name required"}}), 400

        current_user = get_current_user()
        created_by = current_user.get('email') if current_user else 'admin'

        manager = get_api_key_manager()
        raw_key, api_key = manager.generate_key(
            name=data['name'],
            created_by=created_by,
            scopes=data.get('scopes', ['read']),
            expires_in_days=data.get('expires_in_days'),
            ip_whitelist=data.get('ip_whitelist'),
            metadata=data.get('metadata', {})
        )

        # Log the creation
        audit_logger = get_audit_logger()
        audit_logger.log(
            AuditEventType.API_KEY_CREATE,
            AuditSev.WARNING,
            resource_type='api_key',
            resource_id=api_key.key_id,
            details={'name': api_key.name, 'scopes': api_key.scopes}
        )

        return jsonify({
            'key_id': api_key.key_id,
            'name': api_key.name,
            'api_key': raw_key,  # Only returned once!
            'key_prefix': api_key.key_prefix,
            'expires_at': api_key.expires_at.isoformat() if api_key.expires_at else None,
            'scopes': api_key.scopes,
            'warning': 'Store this API key securely. It will not be shown again.'
        }), 201

    except ValueError as e:
        return jsonify({"error": {"code": "BAD_REQUEST", "message": str(e)}}), 400
    except Exception as e:
        logger.exception("Error creating API key")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to create API key"
            }
        }), 500


@app.route('/api/security/api-keys/<key_id>/revoke', methods=['POST'])
@require_admin
def revoke_api_key(key_id):
    """
    Revoke an API key (admin only).

    Path Parameters:
        key_id: API key identifier

    Returns:
        Revocation status
    """
    try:
        current_user = get_current_user()
        revoked_by = current_user.get('email') if current_user else 'admin'

        manager = get_api_key_manager()
        success = manager.revoke_key(key_id, revoked_by)

        if success:
            audit_logger = get_audit_logger()
            audit_logger.log(
                AuditEventType.API_KEY_REVOKE,
                AuditSev.WARNING,
                resource_type='api_key',
                resource_id=key_id
            )

            return jsonify({
                'key_id': key_id,
                'status': 'revoked'
            })
        else:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "API key not found"}}), 404

    except Exception as e:
        logger.exception(f"Error revoking API key {key_id}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to revoke API key"
            }
        }), 500


@app.route('/api/security/audit-log', methods=['GET'])
@require_role('admin', 'auditor')
def get_security_audit_log():
    """
    Get security audit log entries (admin/auditor only).

    Query Parameters:
        event_type: Filter by event type
        user_id: Filter by user
        ip_address: Filter by IP
        severity: Filter by severity
        from_date: Start date (ISO format)
        to_date: End date (ISO format)
        limit: Max entries (default 100)
        offset: Pagination offset

    Returns:
        List of audit events
    """
    try:
        from datetime import datetime

        audit_logger = get_audit_logger()

        # Parse date parameters
        from_date = None
        to_date = None
        if request.args.get('from_date'):
            from_date = datetime.fromisoformat(request.args.get('from_date'))
        if request.args.get('to_date'):
            to_date = datetime.fromisoformat(request.args.get('to_date'))

        events = audit_logger.query_events(
            event_type=request.args.get('event_type'),
            user_id=request.args.get('user_id'),
            ip_address=request.args.get('ip_address'),
            severity=request.args.get('severity'),
            from_date=from_date,
            to_date=to_date,
            status=request.args.get('status'),
            limit=int(request.args.get('limit', 100)),
            offset=int(request.args.get('offset', 0))
        )

        return jsonify({
            'events': [event.to_dict() for event in events],
            'count': len(events)
        })

    except Exception as e:
        logger.exception("Error getting audit log")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get audit log"
            }
        }), 500


@app.route('/api/security/audit-log/summary', methods=['GET'])
@require_role('admin', 'auditor')
def get_audit_log_summary():
    """
    Get audit log summary statistics (admin/auditor only).

    Query Parameters:
        from_date: Start date (ISO format)
        to_date: End date (ISO format)

    Returns:
        Summary statistics
    """
    try:
        from datetime import datetime

        audit_logger = get_audit_logger()

        from_date = None
        to_date = None
        if request.args.get('from_date'):
            from_date = datetime.fromisoformat(request.args.get('from_date'))
        if request.args.get('to_date'):
            to_date = datetime.fromisoformat(request.args.get('to_date'))

        summary = audit_logger.get_summary(from_date, to_date)

        return jsonify(summary)

    except Exception as e:
        logger.exception("Error getting audit summary")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get audit summary"
            }
        }), 500


@app.route('/api/security/sessions', methods=['GET'])
@require_auth
def get_user_sessions():
    """
    Get active sessions for the current user.

    Returns:
        List of user's active sessions
    """
    try:
        from app.security import get_session_manager

        current_user = get_current_user()
        if not current_user:
            return jsonify({'sessions': [], 'count': 0})

        user_id = current_user.get('user_id') or current_user.get('email')
        manager = get_session_manager()
        sessions = manager.get_user_sessions(user_id)

        return jsonify({
            'sessions': [
                {
                    'session_id': s.session_id[:8] + '...',  # Partial ID for security
                    'created_at': s.created_at.isoformat(),
                    'last_activity': s.last_activity.isoformat(),
                    'ip_address': s.ip_address,
                    'device_info': s.device_info,
                    'is_current': hasattr(g, 'session_id') and g.session_id == s.session_id
                }
                for s in sessions
            ],
            'count': len(sessions)
        })

    except Exception as e:
        logger.exception("Error getting sessions")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get sessions"
            }
        }), 500


@app.route('/api/security/sessions/invalidate-others', methods=['POST'])
@require_auth
def invalidate_other_sessions():
    """
    Invalidate all other sessions for the current user.

    Returns:
        Number of sessions invalidated
    """
    try:
        from app.security import get_session_manager

        current_user = get_current_user()
        if not current_user:
            return jsonify({"error": {"code": "UNAUTHORIZED", "message": "Not authenticated"}}), 401

        user_id = current_user.get('user_id') or current_user.get('email')
        current_session = getattr(g, 'session_id', None)

        manager = get_session_manager()
        count = manager.invalidate_user_sessions(user_id, 'user_requested', current_session)

        return jsonify({
            'sessions_invalidated': count,
            'status': 'success'
        })

    except Exception as e:
        logger.exception("Error invalidating sessions")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to invalidate sessions"
            }
        }), 500


@app.route('/api/security/status', methods=['GET'])
@require_admin
def get_security_status():
    """
    Get overall security infrastructure status (admin only).

    Returns:
        Status of all security features
    """
    try:
        from app.security import (
            get_rate_limiter,
            get_api_key_manager,
            get_ip_whitelist,
            get_audit_logger,
            get_session_manager
        )

        rate_limiter = get_rate_limiter()
        api_key_manager = get_api_key_manager()
        ip_whitelist = get_ip_whitelist()
        audit_logger = get_audit_logger()
        session_manager = get_session_manager()

        return jsonify({
            'rate_limiting': {
                'enabled': rate_limiter.config.enabled,
                'requests_per_minute': rate_limiter.config.default_requests_per_minute,
                'requests_per_hour': rate_limiter.config.default_requests_per_hour
            },
            'api_keys': {
                'enabled': api_key_manager.config.enabled,
                'total_keys': len(api_key_manager.list_keys(include_inactive=True)),
                'active_keys': len(api_key_manager.list_keys(include_inactive=False))
            },
            'ip_whitelist': {
                'enabled': ip_whitelist.config.enabled,
                'mode': ip_whitelist.config.mode,
                'allowed_count': len(ip_whitelist.list_allowed()),
                'blocked_count': len(ip_whitelist.list_blocked())
            },
            'audit_logging': {
                'enabled': audit_logger.config.enabled,
                'retention_days': audit_logger.config.retention_days
            },
            'session_management': {
                'enabled': session_manager.config.enabled,
                'max_concurrent': session_manager.config.max_concurrent_sessions,
                'timeout_minutes': session_manager.config.session_timeout_minutes
            }
        })

    except Exception as e:
        logger.exception("Error getting security status")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get security status"
            }
        }), 500


# --- QMS Integration Endpoints ---

from app.services.qms_integration_service import get_qms_service, DocumentType


@app.route('/api/qms/status', methods=['GET'])
@require_auth
def get_qms_status():
    """
    Get QMS integration status.

    Returns:
        Configuration status and connection info
    """
    try:
        service = get_qms_service()
        return jsonify(service.get_status())

    except Exception as e:
        logger.exception("Error getting QMS status")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get QMS status"
            }
        }), 500


@app.route('/api/qms/test-connection', methods=['POST'])
@require_admin
def test_qms_connection():
    """
    Test connection to the QMS (admin only).

    Request Body (optional):
        provider: QMS provider to test (default: configured provider)

    Returns:
        Connection test result
    """
    try:
        data = request.get_json() or {}
        provider = data.get('provider')

        service = get_qms_service()
        result = service.test_connection(provider)

        return jsonify(result)

    except Exception as e:
        logger.exception("Error testing QMS connection")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        }), 500


@app.route('/api/qms/sops', methods=['GET'])
@require_auth
def search_sops():
    """
    Search for SOPs in the QMS.

    Query Parameters:
        query: Search text
        equipment_type: Filter by equipment type
        functional_location: Filter by functional location
        limit: Max results (default 50)

    Returns:
        List of matching SOPs
    """
    try:
        service = get_qms_service()

        sops = service.search_sops(
            query=request.args.get('query'),
            equipment_type=request.args.get('equipment_type'),
            functional_location=request.args.get('functional_location'),
            limit=int(request.args.get('limit', 50))
        )

        return jsonify({
            'sops': [sop.to_dict() for sop in sops],
            'count': len(sops)
        })

    except Exception as e:
        logger.exception("Error searching SOPs")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to search SOPs"
            }
        }), 500


@app.route('/api/qms/sops/for-notification', methods=['GET'])
@require_auth
def get_sops_for_notification():
    """
    Get relevant SOPs for a maintenance notification.

    Query Parameters:
        equipment_type: Equipment type from notification
        functional_location: Functional location from notification
        notification_type: Notification type (M1, M2, etc.)

    Returns:
        List of relevant SOPs
    """
    try:
        service = get_qms_service()

        sops = service.get_sops_for_notification(
            equipment_type=request.args.get('equipment_type'),
            functional_location=request.args.get('functional_location'),
            notification_type=request.args.get('notification_type')
        )

        return jsonify({
            'sops': [sop.to_dict() for sop in sops],
            'count': len(sops),
            'context': {
                'equipment_type': request.args.get('equipment_type'),
                'functional_location': request.args.get('functional_location'),
                'notification_type': request.args.get('notification_type')
            }
        })

    except Exception as e:
        logger.exception("Error getting SOPs for notification")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get SOPs for notification"
            }
        }), 500


@app.route('/api/qms/documents/<document_id>', methods=['GET'])
@require_auth
def get_qms_document(document_id):
    """
    Get a specific document from the QMS.

    Path Parameters:
        document_id: Document identifier

    Returns:
        Document details
    """
    try:
        service = get_qms_service()
        document = service.get_document(document_id)

        if document:
            return jsonify(document.to_dict())
        else:
            return jsonify({
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Document not found"
                }
            }), 404

    except Exception as e:
        logger.exception(f"Error getting QMS document {document_id}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get document"
            }
        }), 500


@app.route('/api/qms/documents/<document_id>/content', methods=['GET'])
@require_auth
def get_qms_document_content(document_id):
    """
    Get the content/body of a document from the QMS.

    Path Parameters:
        document_id: Document identifier

    Returns:
        Document content (text)
    """
    try:
        service = get_qms_service()
        content = service.get_document_content(document_id)

        if content:
            return jsonify({
                'document_id': document_id,
                'content': content
            })
        else:
            return jsonify({
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Document content not found"
                }
            }), 404

    except Exception as e:
        logger.exception(f"Error getting QMS document content {document_id}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get document content"
            }
        }), 500


# ==========================================
# SaaS Tenant Management Endpoints
# ==========================================

from app.services.tenant_service import get_tenant_service


@app.route('/api/tenant/callback/<tenant_id>', methods=['PUT'])
def saas_subscription_callback(tenant_id):
    """
    SaaS Registry subscription callback.

    Called by SAP BTP SaaS Provisioning Service when a customer subscribes.
    """
    try:
        payload = request.get_json() or {}
        tenant_service = get_tenant_service()
        tenant = tenant_service.on_subscription(tenant_id, payload)

        # Return the application URL for the tenant
        app_url = os.environ.get('APP_URL', request.host_url.rstrip('/'))
        return jsonify({
            'status': 'subscribed',
            'tenant_id': tenant.tenant_id,
            'subdomain': tenant.subdomain,
            'app_url': f"https://{tenant.subdomain}.{app_url.replace('https://', '')}"
        }), 200

    except Exception as e:
        logger.exception(f"Tenant subscription failed: {tenant_id}")
        return jsonify({"error": {"code": "PROVISIONING_FAILED", "message": str(e)}}), 500


@app.route('/api/tenant/callback/<tenant_id>', methods=['DELETE'])
def saas_unsubscription_callback(tenant_id):
    """
    SaaS Registry unsubscription callback.

    Called by SAP BTP SaaS Provisioning Service when a customer unsubscribes.
    """
    try:
        tenant_service = get_tenant_service()
        tenant_service.on_unsubscription(tenant_id)
        return jsonify({'status': 'unsubscribed', 'tenant_id': tenant_id}), 200

    except Exception as e:
        logger.exception(f"Tenant unsubscription failed: {tenant_id}")
        return jsonify({"error": {"code": "DEPROVISIONING_FAILED", "message": str(e)}}), 500


@app.route('/api/tenant/callback/dependencies', methods=['GET'])
def saas_dependencies_callback():
    """SaaS Registry dependencies callback."""
    tenant_service = get_tenant_service()
    return jsonify(tenant_service.get_dependencies()), 200


@app.route('/api/tenants', methods=['GET'])
@require_admin
def list_tenants():
    """List all tenants (admin only)."""
    try:
        tenant_service = get_tenant_service()
        status_filter = request.args.get('status')
        tenants = tenant_service.list_tenants(status=status_filter)
        return jsonify({
            'tenants': [t.to_dict() for t in tenants],
            'total': len(tenants)
        })
    except Exception as e:
        logger.exception("Error listing tenants")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/tenants/<tenant_id>', methods=['GET'])
@require_admin
def get_tenant(tenant_id):
    """Get tenant details (admin only)."""
    try:
        tenant_service = get_tenant_service()
        tenant = tenant_service.get_tenant(tenant_id)
        if not tenant:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "Tenant not found"}}), 404

        usage = tenant_service.get_usage_summary(tenant_id)
        result = tenant.to_dict()
        result['usage'] = usage
        return jsonify(result)

    except Exception as e:
        logger.exception(f"Error getting tenant {tenant_id}")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/tenants/<tenant_id>/plan', methods=['PUT'])
@require_admin
def update_tenant_plan(tenant_id):
    """Update tenant subscription plan (admin only)."""
    try:
        data = request.get_json()
        plan = data.get('plan')
        if not plan:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "plan is required"}}), 400

        tenant_service = get_tenant_service()
        tenant = tenant_service.update_tenant_plan(tenant_id, plan)
        if not tenant:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "Invalid plan"}}), 400

        return jsonify(tenant.to_dict())

    except Exception as e:
        logger.exception(f"Error updating tenant plan {tenant_id}")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/tenants/<tenant_id>/usage', methods=['GET'])
@require_admin
def get_tenant_usage(tenant_id):
    """Get tenant usage metrics (admin only)."""
    try:
        tenant_service = get_tenant_service()
        usage = tenant_service.get_usage_summary(tenant_id)
        entitlements = {}
        for feature in ['analysis', 'quality_scoring', 'reliability', 'reporting',
                        'alerts', 'fda_compliance', 'qms_integration', 'api_access']:
            entitlements[feature] = tenant_service.check_entitlement(tenant_id, feature)

        return jsonify({
            'tenant_id': tenant_id,
            'usage': usage,
            'entitlements': entitlements,
            'notifications_limit': tenant_service.check_usage_limit(tenant_id, 'notifications_analyzed'),
            'users_limit': tenant_service.check_usage_limit(tenant_id, 'active_users'),
        })

    except Exception as e:
        logger.exception(f"Error getting tenant usage {tenant_id}")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


# ==========================================
# Trial & Demo Provisioning Endpoints
# ==========================================

from app.services.user_management_service import get_user_management_service


@app.route('/api/trial/provision', methods=['POST'])
def provision_trial():
    """
    Provision a new trial tenant with Clerk organization and sample data.

    Body: {
        "subdomain": "acme-trial",
        "display_name": "Acme Corp",
        "email": "admin@acme.com",
        "user_id": "clerk_user_id"  (optional, from authenticated signup)
    }

    Flow:
    1. Create Clerk organization (if Clerk enabled) -> org_id becomes tenant_id
    2. Create tenant record linked to the Clerk org
    3. Seed demo notification data
    """
    try:
        data = request.get_json() or {}
        subdomain = data.get('subdomain')
        if not subdomain:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "subdomain is required"}}), 400

        # Sanitize subdomain
        subdomain = re.sub(r'[^a-z0-9-]', '', subdomain.lower().strip())
        if len(subdomain) < 3:
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "subdomain must be at least 3 characters"}}), 400

        display_name = data.get('display_name', '')
        email = data.get('email', '')

        tenant_service = get_tenant_service()

        # Check for existing tenant with same subdomain
        existing = tenant_service.list_tenants()
        for t in existing:
            if t.subdomain == subdomain:
                return jsonify({"error": {"code": "CONFLICT",
                               "message": "Subdomain already in use"}}), 409

        # Try to create Clerk organization (org_id becomes tenant_id)
        user_mgmt = get_user_management_service()
        clerk_org = None
        user_id = data.get('user_id', '')

        # Resolve user_id from auth token if not provided
        if not user_id:
            user = get_current_user()
            if user:
                user_id = user.id

        if user_mgmt.enabled and user_id:
            clerk_org = user_mgmt.create_organization(
                name=display_name or subdomain,
                slug=subdomain,
                created_by_user_id=user_id,
                metadata={
                    'plan': 'trial',
                    'product': 'pm-notification-analyzer',
                },
            )

        # Use Clerk org ID as tenant_id if available, else generate UUID
        if clerk_org:
            tenant_id = clerk_org.id
        else:
            tenant_id = str(__import__('uuid').uuid4())

        tenant = tenant_service.provision_trial(tenant_id, subdomain, display_name, email)

        # Store Clerk org reference in tenant metadata
        if clerk_org:
            import json as _json
            metadata = tenant.metadata or {}
            metadata['clerk_org_id'] = clerk_org.id
            metadata['clerk_org_slug'] = clerk_org.slug
            from app.database import get_db_connection
            with get_db_connection() as conn:
                conn.execute(
                    "UPDATE tenants SET metadata = ? WHERE tenant_id = ?",
                    (_json.dumps(metadata), tenant_id)
                )

            # Set the creating user as admin
            if user_id:
                user_mgmt.set_application_role(user_id, 'admin')

        # Auto-seed demo data
        seed_result = tenant_service.seed_demo_data(tenant_id)

        app_url = os.environ.get('APP_URL', request.host_url.rstrip('/'))
        result = {
            'status': 'provisioned',
            'tenant': tenant.to_dict(),
            'tenant_id': tenant_id,
            'trial_expires': tenant.metadata.get('trial_expires'),
            'trial_duration_days': 14,
            'demo_data': seed_result,
            'app_url': f"https://{subdomain}.{app_url.replace('https://', '')}",
        }
        if clerk_org:
            result['organization'] = clerk_org.to_dict()

        return jsonify(result), 201

    except Exception as e:
        logger.exception("Error provisioning trial")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/trial/<tenant_id>/status', methods=['GET'])
@require_auth
def get_trial_status(tenant_id):
    """Check trial expiration status."""
    try:
        tenant_service = get_tenant_service()
        status = tenant_service.check_trial_expiration(tenant_id)
        return jsonify(status)
    except Exception as e:
        logger.exception(f"Error checking trial status {tenant_id}")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/trial/<tenant_id>/convert', methods=['POST'])
@require_admin
def convert_trial(tenant_id):
    """
    Convert a trial tenant to a paid plan.

    Body: { "plan": "basic|professional|enterprise" }
    """
    try:
        data = request.get_json() or {}
        plan = data.get('plan')
        if not plan or plan not in ('basic', 'professional', 'enterprise'):
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "plan must be basic, professional, or enterprise"}}), 400

        tenant_service = get_tenant_service()
        tenant = tenant_service.convert_trial_to_paid(tenant_id, plan)
        if not tenant:
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "Conversion failed - tenant not found or not a trial"}}), 400

        return jsonify({
            'status': 'converted',
            'tenant': tenant.to_dict(),
            'new_plan': plan,
        })

    except Exception as e:
        logger.exception(f"Error converting trial {tenant_id}")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/trial/<tenant_id>/seed-demo-data', methods=['POST'])
@require_admin
def seed_tenant_demo_data(tenant_id):
    """Seed demo data into a tenant (admin only)."""
    try:
        tenant_service = get_tenant_service()
        result = tenant_service.seed_demo_data(tenant_id)
        if 'error' in result:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": result['error']}}), 400
        return jsonify(result), 201
    except Exception as e:
        logger.exception(f"Error seeding demo data {tenant_id}")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


# ==========================================
# User Management Endpoints (Clerk Organizations)
# ==========================================


@app.route('/api/users', methods=['GET'])
@require_role('admin')
def list_tenant_users():
    """
    List all users in the current tenant (Clerk organization).
    """
    try:
        tenant_id = getattr(g, 'tenant_id', None)
        if not tenant_id:
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "No tenant context"}}), 400

        user_mgmt = get_user_management_service()
        if not user_mgmt.enabled:
            return jsonify({"error": {"code": "SERVICE_UNAVAILABLE",
                           "message": "User management requires Clerk"}}), 503

        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        members = user_mgmt.list_members(tenant_id, limit=limit, offset=offset)

        return jsonify({
            'users': [m.to_dict() for m in members],
            'total': len(members),
            'tenant_id': tenant_id,
        })

    except Exception as e:
        logger.exception("Error listing tenant users")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/users/invite', methods=['POST'])
@require_role('admin')
def invite_user():
    """
    Invite a user to the tenant by email.

    Body: { "email": "user@example.com", "role": "org:member" }

    Clerk sends the invitation email automatically.
    """
    try:
        tenant_id = getattr(g, 'tenant_id', None)
        if not tenant_id:
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "No tenant context"}}), 400

        data = request.get_json() or {}
        email = data.get('email')
        if not email:
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "email is required"}}), 400

        role = data.get('role', 'org:member')
        if role not in ('org:admin', 'org:member'):
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "role must be org:admin or org:member"}}), 400

        # Check user limit for the tenant plan
        tenant_service = get_tenant_service()
        tenant = tenant_service.get_tenant(tenant_id)
        if tenant and tenant.max_users > 0:
            user_mgmt = get_user_management_service()
            current_members = user_mgmt.list_members(tenant_id)
            if len(current_members) >= tenant.max_users:
                return jsonify({"error": {
                    "code": "USER_LIMIT_REACHED",
                    "message": f"Your {tenant.plan} plan allows {tenant.max_users} users. "
                               f"Upgrade your plan to add more users.",
                    "current_users": len(current_members),
                    "max_users": tenant.max_users,
                }}), 403

        user_mgmt = get_user_management_service()
        result = user_mgmt.invite_member(tenant_id, email, role)

        if 'error' in result:
            return jsonify({"error": {"code": "INVITATION_FAILED",
                           "message": result['error']}}), 400

        return jsonify(result), 201

    except Exception as e:
        logger.exception("Error inviting user")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/users/<user_id>/remove', methods=['POST'])
@require_role('admin')
def remove_user(user_id):
    """Remove a user from the tenant organization."""
    try:
        tenant_id = getattr(g, 'tenant_id', None)
        if not tenant_id:
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "No tenant context"}}), 400

        # Prevent self-removal
        current_user = get_current_user()
        if current_user and current_user.id == user_id:
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "Cannot remove yourself"}}), 400

        user_mgmt = get_user_management_service()
        removed = user_mgmt.remove_member(tenant_id, user_id)

        if removed:
            return jsonify({'status': 'removed', 'user_id': user_id})
        else:
            return jsonify({"error": {"code": "REMOVE_FAILED",
                           "message": "Failed to remove user"}}), 400

    except Exception as e:
        logger.exception(f"Error removing user {user_id}")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/users/<user_id>/role', methods=['PUT'])
@require_role('admin')
def update_user_role(user_id):
    """
    Update a user's role within the tenant.

    Body: {
        "org_role": "org:admin|org:member",   (Clerk organization role)
        "app_role": "viewer|editor|auditor|admin"  (application-level role)
    }
    """
    try:
        tenant_id = getattr(g, 'tenant_id', None)
        if not tenant_id:
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "No tenant context"}}), 400

        data = request.get_json() or {}
        user_mgmt = get_user_management_service()

        results = {}

        # Update Clerk organization role
        org_role = data.get('org_role')
        if org_role:
            if org_role not in ('org:admin', 'org:member'):
                return jsonify({"error": {"code": "BAD_REQUEST",
                               "message": "org_role must be org:admin or org:member"}}), 400
            results['org_role'] = user_mgmt.update_member_role(tenant_id, user_id, org_role)

        # Update application role
        app_role = data.get('app_role')
        if app_role:
            if app_role not in ('viewer', 'editor', 'auditor', 'admin'):
                return jsonify({"error": {"code": "BAD_REQUEST",
                               "message": "app_role must be viewer, editor, auditor, or admin"}}), 400
            results['app_role'] = user_mgmt.set_application_role(user_id, app_role)

        if not org_role and not app_role:
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "Provide org_role and/or app_role"}}), 400

        return jsonify({'status': 'updated', 'user_id': user_id, 'results': results})

    except Exception as e:
        logger.exception(f"Error updating user role {user_id}")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/users/invitations', methods=['GET'])
@require_role('admin')
def list_invitations():
    """List pending invitations for the current tenant."""
    try:
        tenant_id = getattr(g, 'tenant_id', None)
        if not tenant_id:
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "No tenant context"}}), 400

        user_mgmt = get_user_management_service()
        invitations = user_mgmt.list_pending_invitations(tenant_id)

        return jsonify({
            'invitations': invitations,
            'total': len(invitations),
        })

    except Exception as e:
        logger.exception("Error listing invitations")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/users/invitations/<invitation_id>/revoke', methods=['POST'])
@require_role('admin')
def revoke_user_invitation(invitation_id):
    """Revoke a pending invitation."""
    try:
        tenant_id = getattr(g, 'tenant_id', None)
        if not tenant_id:
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "No tenant context"}}), 400

        user_mgmt = get_user_management_service()
        revoked = user_mgmt.revoke_invitation(tenant_id, invitation_id)

        if revoked:
            return jsonify({'status': 'revoked', 'invitation_id': invitation_id})
        else:
            return jsonify({"error": {"code": "REVOKE_FAILED",
                           "message": "Failed to revoke invitation"}}), 400

    except Exception as e:
        logger.exception(f"Error revoking invitation {invitation_id}")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/users/me/organization', methods=['GET'])
@require_auth
def get_my_organization():
    """
    Get the current user's organization (tenant) info.

    Returns organization details, tenant plan, and the user's role.
    """
    try:
        tenant_id = getattr(g, 'tenant_id', None)
        user = get_current_user()

        result = {
            'tenant_id': tenant_id,
            'user': user.to_dict() if user else None,
        }

        if tenant_id:
            # Get tenant info
            tenant_service = get_tenant_service()
            tenant = tenant_service.get_tenant(tenant_id)
            if tenant:
                result['tenant'] = {
                    'plan': tenant.plan,
                    'status': tenant.status,
                    'display_name': tenant.display_name,
                    'max_users': tenant.max_users,
                }

            # Get org info from Clerk
            user_mgmt = get_user_management_service()
            if user_mgmt.enabled:
                org = user_mgmt.get_organization(tenant_id)
                if org:
                    result['organization'] = org.to_dict()

        return jsonify(result)

    except Exception as e:
        logger.exception("Error getting user organization")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


# ==========================================
# Onboarding & Guided Setup Endpoints
# ==========================================

from app.services.onboarding_service import get_onboarding_service


@app.route('/api/onboarding/state', methods=['GET'])
@require_auth
def get_onboarding_state():
    """Get current onboarding state for the tenant."""
    try:
        tenant_id = getattr(g, 'tenant_id', 'default')
        service = get_onboarding_service()
        state = service.get_onboarding_state(tenant_id)
        return jsonify(state.to_dict())
    except Exception as e:
        logger.exception("Error getting onboarding state")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/onboarding/steps/<step_id>/complete', methods=['POST'])
@require_auth
def complete_onboarding_step(step_id):
    """
    Mark an onboarding step as completed.

    Body (optional): { "data": { ... step-specific data ... } }
    """
    try:
        tenant_id = getattr(g, 'tenant_id', 'default')
        data = request.get_json() or {}
        step_data = data.get('data')

        service = get_onboarding_service()
        state = service.complete_step(tenant_id, step_id, step_data)
        return jsonify(state.to_dict())

    except ValueError as e:
        return jsonify({"error": {"code": "BAD_REQUEST", "message": str(e)}}), 400
    except Exception as e:
        logger.exception(f"Error completing onboarding step {step_id}")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/onboarding/steps/<step_id>/skip', methods=['POST'])
@require_auth
def skip_onboarding_step(step_id):
    """Skip an optional onboarding step."""
    try:
        tenant_id = getattr(g, 'tenant_id', 'default')
        service = get_onboarding_service()
        state = service.skip_step(tenant_id, step_id)
        return jsonify(state.to_dict())

    except ValueError as e:
        return jsonify({"error": {"code": "BAD_REQUEST", "message": str(e)}}), 400
    except Exception as e:
        logger.exception(f"Error skipping onboarding step {step_id}")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/onboarding/steps/<step_id>/validate', methods=['GET'])
@require_auth
def validate_onboarding_step(step_id):
    """Run validation check for an onboarding step."""
    try:
        tenant_id = getattr(g, 'tenant_id', 'default')
        service = get_onboarding_service()
        result = service.validate_step(tenant_id, step_id)
        return jsonify(result)
    except Exception as e:
        logger.exception(f"Error validating onboarding step {step_id}")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/onboarding/reset', methods=['POST'])
@require_admin
def reset_onboarding():
    """Reset onboarding state for the tenant (admin only)."""
    try:
        tenant_id = getattr(g, 'tenant_id', 'default')
        service = get_onboarding_service()
        state = service.reset_onboarding(tenant_id)
        return jsonify(state.to_dict())
    except Exception as e:
        logger.exception("Error resetting onboarding")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/onboarding/setup-check', methods=['GET'])
@require_auth
def check_setup_status():
    """
    Quick setup validation check for all components.

    Returns validation results for all onboarding steps at once.
    """
    try:
        tenant_id = getattr(g, 'tenant_id', 'default')
        service = get_onboarding_service()

        checks = {}
        for step in ['sap_connection', 'ai_configuration', 'user_roles', 'data_import']:
            checks[step] = service.validate_step(tenant_id, step)

        all_valid = all(c.get('valid', False) for c in checks.values())

        return jsonify({
            'all_valid': all_valid,
            'checks': checks,
        })
    except Exception as e:
        logger.exception("Error running setup check")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


# ==========================================
# GDPR Compliance Endpoints
# ==========================================

from app.services.gdpr_service import get_gdpr_service


@app.route('/api/gdpr/requests', methods=['POST'])
@require_auth
def create_gdpr_request():
    """
    Create a data subject request (Art. 15/17/20).

    Body: { "request_type": "access|erasure|portability", "subject_email": "..." }
    """
    try:
        data = request.get_json()
        request_type = data.get('request_type')
        subject_email = data.get('subject_email')

        if request_type not in ('access', 'erasure', 'portability', 'rectification', 'restriction'):
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "Invalid request_type"}}), 400
        if not subject_email:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "subject_email is required"}}), 400

        user = get_current_user()
        tenant_id = getattr(g, 'tenant_id', 'default')
        subject_id = user.get('user_id', 'unknown') if user else 'unknown'

        gdpr = get_gdpr_service()
        dsr = gdpr.create_request(tenant_id, subject_id, subject_email, request_type, data.get('details'))

        return jsonify(dsr.to_dict()), 201

    except Exception as e:
        logger.exception("Error creating GDPR request")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/gdpr/requests', methods=['GET'])
@require_admin
def list_gdpr_requests():
    """List GDPR requests for the tenant (admin only)."""
    try:
        tenant_id = getattr(g, 'tenant_id', 'default')
        status_filter = request.args.get('status')
        gdpr = get_gdpr_service()
        requests_list = gdpr.list_requests(tenant_id, status=status_filter)
        return jsonify({'requests': [r.to_dict() for r in requests_list], 'total': len(requests_list)})
    except Exception as e:
        logger.exception("Error listing GDPR requests")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/gdpr/requests/<request_id>', methods=['GET'])
@require_auth
def get_gdpr_request(request_id):
    """Get a specific GDPR request."""
    try:
        gdpr = get_gdpr_service()
        dsr = gdpr.get_request(request_id)
        if not dsr:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "Request not found"}}), 404
        return jsonify(dsr.to_dict())
    except Exception as e:
        logger.exception(f"Error getting GDPR request {request_id}")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/gdpr/requests/<request_id>/execute', methods=['POST'])
@require_admin
def execute_gdpr_request(request_id):
    """Execute a GDPR request (admin only)."""
    try:
        gdpr = get_gdpr_service()
        dsr = gdpr.get_request(request_id)
        if not dsr:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "Request not found"}}), 404

        user = get_current_user()
        processed_by = user.get('user_id', 'admin') if user else 'admin'

        if dsr.request_type == 'access' or dsr.request_type == 'portability':
            export = gdpr.export_subject_data(dsr.tenant_id, dsr.subject_id)
            gdpr._update_request_status(request_id, 'completed', processed_by)
            return jsonify({'status': 'completed', 'data': export})

        elif dsr.request_type == 'erasure':
            result = gdpr.erase_subject_data(dsr.tenant_id, dsr.subject_id, processed_by)
            gdpr._update_request_status(request_id, 'completed', processed_by)
            return jsonify({'status': 'completed', 'result': result})

        else:
            return jsonify({"error": {"code": "NOT_IMPLEMENTED",
                           "message": f"Execution not implemented for {dsr.request_type}"}}), 501

    except Exception as e:
        logger.exception(f"Error executing GDPR request {request_id}")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/gdpr/export', methods=['GET'])
@require_auth
def export_my_data():
    """Export current user's personal data (Art. 15 self-service)."""
    try:
        user = get_current_user()
        subject_id = user.get('user_id', 'unknown') if user else 'unknown'
        tenant_id = getattr(g, 'tenant_id', 'default')
        fmt = request.args.get('format', 'json')

        gdpr = get_gdpr_service()

        if fmt == 'csv':
            csv_data = gdpr.export_subject_data_csv(tenant_id, subject_id)
            return csv_data, 200, {
                'Content-Type': 'text/csv',
                'Content-Disposition': f'attachment; filename=my_data_export_{subject_id}.csv'
            }
        else:
            export = gdpr.export_subject_data(tenant_id, subject_id)
            return jsonify(export)

    except Exception as e:
        logger.exception("Error exporting user data")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/gdpr/consent', methods=['POST'])
@require_auth
def record_consent():
    """Record user consent for a processing purpose."""
    try:
        data = request.get_json()
        purpose = data.get('purpose')
        granted = data.get('granted', True)

        if not purpose:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "purpose is required"}}), 400

        user = get_current_user()
        user_id = user.get('user_id', 'unknown') if user else 'unknown'
        tenant_id = getattr(g, 'tenant_id', 'default')

        gdpr = get_gdpr_service()
        record = gdpr.record_consent(
            tenant_id, user_id, purpose, granted,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        return jsonify(record.to_dict()), 201

    except Exception as e:
        logger.exception("Error recording consent")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/gdpr/consent', methods=['GET'])
@require_auth
def get_my_consents():
    """Get current user's consent records."""
    try:
        user = get_current_user()
        user_id = user.get('user_id', 'unknown') if user else 'unknown'
        tenant_id = getattr(g, 'tenant_id', 'default')

        gdpr = get_gdpr_service()
        consents = gdpr.get_consents(tenant_id, user_id)
        return jsonify({'consents': [c.to_dict() for c in consents]})

    except Exception as e:
        logger.exception("Error getting consents")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/gdpr/consent/<purpose>/revoke', methods=['POST'])
@require_auth
def revoke_consent(purpose):
    """Revoke consent for a specific purpose."""
    try:
        user = get_current_user()
        user_id = user.get('user_id', 'unknown') if user else 'unknown'
        tenant_id = getattr(g, 'tenant_id', 'default')

        gdpr = get_gdpr_service()
        revoked = gdpr.revoke_consent(tenant_id, user_id, purpose)

        if revoked:
            return jsonify({'status': 'revoked', 'purpose': purpose})
        else:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "No active consent found"}}), 404

    except Exception as e:
        logger.exception(f"Error revoking consent for {purpose}")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/gdpr/data-inventory', methods=['GET'])
@require_admin
def get_data_inventory():
    """Get personal data inventory / data mapping (admin only)."""
    try:
        gdpr = get_gdpr_service()
        inventory = gdpr.get_personal_data_inventory()
        return jsonify({'personal_data_inventory': inventory})
    except Exception as e:
        logger.exception("Error getting data inventory")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/gdpr/retention', methods=['GET'])
@require_admin
def get_retention_policies():
    """Get data retention policies (admin only)."""
    try:
        tenant_id = getattr(g, 'tenant_id', 'default')
        gdpr = get_gdpr_service()
        policies = gdpr.get_retention_policies(tenant_id)
        return jsonify({'policies': policies})
    except Exception as e:
        logger.exception("Error getting retention policies")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/gdpr/retention', methods=['POST'])
@require_admin
def set_retention_policy():
    """Set data retention policy (admin only)."""
    try:
        data = request.get_json()
        data_type = data.get('data_type')
        retention_days = data.get('retention_days')

        if not data_type or retention_days is None:
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "data_type and retention_days are required"}}), 400

        tenant_id = getattr(g, 'tenant_id', 'default')
        gdpr = get_gdpr_service()
        gdpr.set_retention_policy(tenant_id, data_type, retention_days, data.get('auto_delete', False))

        return jsonify({'status': 'ok', 'data_type': data_type, 'retention_days': retention_days}), 201

    except Exception as e:
        logger.exception("Error setting retention policy")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


# ========================================
# File Import Endpoints
# ========================================

@app.route('/api/import/upload', methods=['POST'])
@require_auth
def import_upload():
    """
    Import notifications from an uploaded file (CSV or JSON).

    Accepts multipart/form-data with:
    - file: The CSV or JSON file
    - format: 'csv' or 'json' (auto-detected from extension if omitted)
    - language: Language code for text fields (default: 'en')
    - mode: Duplicate handling - 'skip' (default), 'replace', or 'error'
    - delimiter: CSV delimiter (auto-detected if omitted)

    Or application/json with:
    - notifications: Array of notification objects (inline JSON import)
    - language, mode: Same as above
    """
    from app.services.import_service import import_csv, import_json

    try:
        user = get_current_user()
        username = user.email.split('@')[0] if user else 'IMPORT'

        # Check content type
        if request.content_type and 'application/json' in request.content_type:
            # Inline JSON import
            data = request.get_json()
            if not data:
                return jsonify({"error": {"code": "BAD_REQUEST",
                               "message": "Request body is required"}}), 400

            language = data.get('language', 'en')
            mode = data.get('mode', 'skip')
            # Build JSON content from the request body
            import json
            content = json.dumps(data)
            result = import_json(content, language=language, mode=mode, username=username)
            return jsonify(result.to_dict()), 200 if result.status != 'failed' else 400

        # File upload (multipart/form-data)
        if 'file' not in request.files:
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "No file provided. Send a file with key 'file'."}}), 400

        file = request.files['file']
        if not file.filename:
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "Empty filename"}}), 400

        # Read file content
        try:
            content = file.read().decode('utf-8-sig')  # Handle BOM
        except UnicodeDecodeError:
            try:
                file.seek(0)
                content = file.read().decode('latin-1')
            except Exception:
                return jsonify({"error": {"code": "BAD_REQUEST",
                               "message": "Could not decode file. Please use UTF-8 encoding."}}), 400

        if not content.strip():
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "File is empty"}}), 400

        # Determine format
        file_format = request.form.get('format', '').lower()
        if not file_format:
            if file.filename.lower().endswith('.json'):
                file_format = 'json'
            elif file.filename.lower().endswith(('.csv', '.tsv', '.txt')):
                file_format = 'csv'
            else:
                # Try to detect from content
                stripped = content.strip()
                if stripped.startswith('{') or stripped.startswith('['):
                    file_format = 'json'
                else:
                    file_format = 'csv'

        language = request.form.get('language', 'en')
        mode = request.form.get('mode', 'skip')
        delimiter = request.form.get('delimiter', ',')

        if language not in ('en', 'de'):
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "Language must be 'en' or 'de'"}}), 400
        if mode not in ('skip', 'replace', 'error'):
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "Mode must be 'skip', 'replace', or 'error'"}}), 400

        # Import
        if file_format == 'json':
            result = import_json(content, language=language, mode=mode, username=username)
        else:
            result = import_csv(content, language=language, mode=mode,
                              username=username, delimiter=delimiter)

        status_code = 200 if result.status != 'failed' else 400
        return jsonify(result.to_dict()), status_code

    except Exception as e:
        logger.exception("Error during file import")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/import/validate', methods=['POST'])
@require_auth
def import_validate():
    """
    Validate a file without importing (dry run).

    Same parameters as /api/import/upload but does not insert any data.
    Returns validation results including errors, warnings, and duplicate detection.
    """
    from app.services.import_service import validate_file

    try:
        if 'file' not in request.files:
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "No file provided"}}), 400

        file = request.files['file']
        if not file.filename:
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "Empty filename"}}), 400

        try:
            content = file.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                file.seek(0)
                content = file.read().decode('latin-1')
            except Exception:
                return jsonify({"error": {"code": "BAD_REQUEST",
                               "message": "Could not decode file"}}), 400

        if not content.strip():
            return jsonify({"error": {"code": "BAD_REQUEST",
                           "message": "File is empty"}}), 400

        # Determine format
        file_format = request.form.get('format', '').lower()
        if not file_format:
            if file.filename.lower().endswith('.json'):
                file_format = 'json'
            else:
                file_format = 'csv'

        delimiter = request.form.get('delimiter', ',')
        result = validate_file(content, file_format=file_format, delimiter=delimiter)

        return jsonify(result.to_dict()), 200

    except Exception as e:
        logger.exception("Error during file validation")
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500


@app.route('/api/import/template/<file_format>', methods=['GET'])
def import_template(file_format):
    """
    Download an import template file (CSV or JSON).

    Args:
        file_format: 'csv' or 'json'
    """
    from app.services.import_service import get_import_template
    from flask import Response

    if file_format not in ('csv', 'json'):
        return jsonify({"error": {"code": "BAD_REQUEST",
                       "message": "Format must be 'csv' or 'json'"}}), 400

    content = get_import_template(file_format)

    if file_format == 'json':
        return Response(
            content,
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment; filename=pm_notifications_template.json'}
        )
    else:
        return Response(
            content,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=pm_notifications_template.csv'}
        )


@app.route('/api/import/formats', methods=['GET'])
def import_formats():
    """
    Get information about supported import formats and field mappings.
    """
    from app.services.import_service import CSV_ALIASES, VALID_NOTIFICATION_TYPES, VALID_PRIORITIES

    return jsonify({
        'formats': ['csv', 'json'],
        'max_records': 5000,
        'duplicate_modes': {
            'skip': 'Skip duplicate notification numbers (default)',
            'replace': 'Replace existing notifications with imported data',
            'error': 'Report duplicates as errors without importing them',
        },
        'required_fields': {
            'QMNUM': 'Notification number (unique identifier)',
            'QMART': f'Notification type: {", ".join(sorted(VALID_NOTIFICATION_TYPES))}',
        },
        'recommended_fields': {
            'QMTXT': 'Short text / description (for analysis)',
            'TDLINE': 'Long text / detailed description (for AI analysis quality)',
            'EQUNR': 'Equipment number',
            'TPLNR': 'Functional location',
            'PRIOK': f'Priority: {", ".join(sorted(VALID_PRIORITIES))} (1=Very High, 4=Low)',
            'QMNAM': 'Created by (username)',
            'ERDAT': 'Creation date (YYYYMMDD, YYYY-MM-DD, DD.MM.YYYY)',
        },
        'optional_fields': {
            'MZEIT': 'Creation time (HHMMSS or HH:MM:SS)',
            'STRMN': 'Required start date',
            'LTRMN': 'Required end date / due date',
            'FECOD': 'Damage code',
            'FEGRP': 'Damage code group',
            'OTEIL': 'Object part (component)',
            'OTGRP': 'Object part group',
            'FETXT': 'Item/damage description text',
            'URCOD': 'Cause code',
            'URGRP': 'Cause code group',
            'URTXT': 'Cause description text',
            'AUFNR': 'Work order number',
            'AUART': 'Work order type (PM01, PM02, PM03)',
            'KTEXT': 'Work order description',
        },
        'csv_column_aliases': {
            field: alias for alias, field in sorted(CSV_ALIASES.items())
        },
        'date_formats': ['YYYYMMDD', 'YYYY-MM-DD', 'DD.MM.YYYY', 'DD/MM/YYYY'],
        'priority_names': {
            '1': ['Very High', 'Critical'],
            '2': ['High', 'Urgent'],
            '3': ['Medium', 'Normal'],
            '4': ['Low', 'Minor'],
        },
        'notification_types': {
            'M1': 'Malfunction Report',
            'M2': 'Maintenance Request',
            'M3': 'Activity Report',
            'M4': 'Service Request',
            'M5': 'Quality Notification',
            'Z1': 'Custom Type 1',
            'Z2': 'Custom Type 2',
        },
    }), 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    # Use debug mode only in development
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, port=port, host='0.0.0.0')