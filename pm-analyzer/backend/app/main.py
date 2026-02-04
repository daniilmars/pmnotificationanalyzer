from flask import Flask, request, jsonify, g
from flask_cors import CORS
from dotenv import load_dotenv
import os
import re
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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    # Use debug mode only in development
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, port=port, host='0.0.0.0')