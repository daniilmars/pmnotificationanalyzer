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

@app.teardown_appcontext
def teardown_db(exception):
    close_db(exception)

@app.route('/health', methods=['GET'])
def health_check() -> Tuple[str, int]:
    """Health check endpoint for monitoring."""
    return jsonify({"status": "ok"}), 200

# --- Data Endpoints ---

@app.route('/api/notifications', methods=['GET'])
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
def get_configuration():
    """Get the current application configuration."""
    try:
        config = get_config()
        return jsonify(config)
    except Exception as e:
        logger.exception("Failed to read configuration.")
        return jsonify({"error": {"code": "CONFIG_READ_ERROR", "message": "Failed to read configuration"}}), 500

@app.route('/api/configuration', methods=['POST'])
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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    # Use debug mode only in development
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, port=port, host='0.0.0.0')