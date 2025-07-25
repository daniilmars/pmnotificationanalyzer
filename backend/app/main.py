from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
from typing import Tuple
from google.api_core import exceptions as google_exceptions
import logging

load_dotenv()

from app.services.analysis_service import analyze_text
from app.models import AnalysisResponse
from app.auth import token_required

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

@app.route('/health', methods=['GET'])
def health_check() -> Tuple[str, int]:
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
    # Get the language from the request, defaulting to 'en'
    language = data.get('language', 'en')

    try:
        # Pass the language to the service function
        analysis_result = analyze_text(text_to_analyze, language)
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=True, port=port, host='0.0.0.0')