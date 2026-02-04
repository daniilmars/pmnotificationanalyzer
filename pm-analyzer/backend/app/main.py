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
from app.database import close_db
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

@app.teardown_appcontext
def teardown_db(exception):
    close_db(exception)

@app.route('/health', methods=['GET'])
def health_check() -> Tuple[str, int]:
    """Health check endpoint for monitoring."""
    return jsonify({"status": "ok"}), 200

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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    # Use debug mode only in development
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, port=port, host='0.0.0.0')