from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
from typing import Tuple
from google.api_core import exceptions as google_exceptions
import logging

# Load environment variables from .env file at the very beginning
# This MUST be done before importing other app modules that need the variables.
load_dotenv()

from app.services.analysis_service import analyze_text
from app.models import AnalysisResponse
from app.auth import token_required

app = Flask(__name__)

# This enables Cross-Origin Resource Sharing (CORS), which is necessary
# for your frontend (running on a different port) to communicate with this backend.
CORS(app)

# Setup basic logging for better debugging
logging.basicConfig(level=logging.INFO)

@app.route('/health', methods=['GET'])
def health_check() -> Tuple[str, int]:
    """
    A simple health check endpoint to confirm the service is running.
    """
    return jsonify({"status": "ok"}), 200


@app.route('/api/analyze', methods=['POST'])
@token_required
def analyze() -> Tuple[str, int]:
    data = request.get_json()
    if not data or not data.get('text'):
        return jsonify({
            "error": {
                "code": "BAD_REQUEST",
                "message": "Missing 'text' in request body"
            }
        }), 400

    text_to_analyze = data['text']

    try:
        analysis_result = analyze_text(text_to_analyze)
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
        # In a production environment, you'd want to log the full traceback
        app.logger.exception("An unexpected error occurred during analysis.")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": f"An unexpected error occurred: {str(e)}"
            }
        }), 500

if __name__ == '__main__':
    # For development, debug=True is fine. For production, use a WSGI server like Gunicorn.
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, port=port, host='0.0.0.0')