from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
from typing import Tuple
from google.api_core import exceptions as google_exceptions
import logging

load_dotenv()

from app.services.analysis_service import analyze_text, chat_with_assistant
from app.models import AnalysisResponse
from app.config_manager import get_config, save_config
from app.config_manager import get_config, save_config
# Removed: from app.auth import token_required # No longer needed

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

@app.route('/health', methods=['GET'])
def health_check() -> Tuple[str, int]:
    return jsonify({"status": "ok"}), 200


@app.route('/api/analyze', methods=['POST'])
# Removed: @token_required # No longer needed
def analyze() -> Tuple[str, int]:
    data = request.get_json()
    if not data or not data.get('notification'):
        return jsonify({
            "error": {
                "code": "BAD_REQUEST",
                "message": "Missing 'notification' object in request body"
            }
        }), 400

    notification_data = data['notification']
    language = data.get('language', 'en')

    try:
        analysis_result = analyze_text(notification_data, language)
        return jsonify(analysis_result.dict())
    except google_exceptions.PermissionDenied as e:
        app.logger.error(f"Google API permission denied. Please check your GOOGLE_API_KEY. Details: {e}")
        return jsonify({
            "error": {
                "code": "API_PERMISSION_DENIED",
                "message": "The backend server was denied access by the analysis service. This is likely due to an invalid or restricted API key."
            }
        }), 500
    except Exception as e:
        app.logger.exception("An unexpected error occurred during analysis.")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": f"An unexpected error occurred: {str(e)}"
            }
        }), 500


@app.route('/api/chat', methods=['POST'])
def chat() -> Tuple[str, int]:
    data = request.get_json()
    if not data or not data.get('notification') or not data.get('question') or not data.get('analysis'):
        return jsonify({
            "error": {
                "code": "BAD_REQUEST",
                "message": "Missing 'notification', 'question', or 'analysis' in request body"
            }
        }), 400

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
    except Exception as e:
        app.logger.exception("An unexpected error occurred during chat.")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": f"An unexpected error occurred: {str(e)}"
            }
        }), 500


@app.route('/api/configuration', methods=['GET'])
def get_configuration():
    try:
        config = get_config()
        return jsonify(config)
    except Exception as e:
        app.logger.exception("Failed to read configuration.")
        return jsonify({"error": {"code": "CONFIG_READ_ERROR", "message": str(e)}}), 500

@app.route('/api/configuration', methods=['POST'])
def set_configuration():
    try:
        config_data = request.get_json()
        if not config_data:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "Invalid JSON body"}}), 400
        save_config(config_data)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        app.logger.exception("Failed to save configuration.")
        return jsonify({"error": {"code": "CONFIG_WRITE_ERROR", "message": str(e)}}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=True, port=port, host='0.0.0.0')
