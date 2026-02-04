"""Input validation utilities for PM Analyzer API."""
import re
from typing import Optional, Tuple, Any
from functools import wraps
from flask import request, jsonify

# Validation patterns
NOTIFICATION_ID_PATTERN = re.compile(r'^[A-Z0-9]{10,12}$')  # SAP notification IDs are typically 10-12 alphanumeric
ALLOWED_LANGUAGES = {'en', 'de'}
MAX_TEXT_LENGTH = 10000  # Maximum length for text fields
MAX_QUESTION_LENGTH = 1000  # Maximum length for chat questions


def validate_notification_id(notification_id: str) -> Tuple[bool, Optional[str]]:
    """
    Validate notification ID format.
    Returns (is_valid, error_message).
    """
    if not notification_id:
        return False, "Notification ID is required"
    if not isinstance(notification_id, str):
        return False, "Notification ID must be a string"
    if len(notification_id) > 20:
        return False, "Notification ID is too long"
    # Allow alphanumeric characters only
    if not re.match(r'^[A-Za-z0-9_-]+$', notification_id):
        return False, "Notification ID contains invalid characters"
    return True, None


def validate_language(language: str) -> Tuple[bool, Optional[str]]:
    """
    Validate language code.
    Returns (is_valid, error_message).
    """
    if language not in ALLOWED_LANGUAGES:
        return False, f"Language must be one of: {', '.join(ALLOWED_LANGUAGES)}"
    return True, None


def validate_text_field(value: Any, field_name: str, max_length: int = MAX_TEXT_LENGTH, required: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Validate a text field.
    Returns (is_valid, error_message).
    """
    if value is None:
        if required:
            return False, f"{field_name} is required"
        return True, None
    if not isinstance(value, str):
        return False, f"{field_name} must be a string"
    if len(value) > max_length:
        return False, f"{field_name} exceeds maximum length of {max_length} characters"
    return True, None


def validate_notification_data(data: dict) -> Tuple[bool, Optional[str]]:
    """
    Validate notification data structure.
    Returns (is_valid, error_message).
    """
    if not data:
        return False, "Notification data is required"
    if not isinstance(data, dict):
        return False, "Notification data must be an object"

    # Validate key fields if present
    if 'Description' in data:
        is_valid, error = validate_text_field(data['Description'], 'Description')
        if not is_valid:
            return False, error

    if 'LongText' in data:
        is_valid, error = validate_text_field(data['LongText'], 'LongText')
        if not is_valid:
            return False, error

    return True, None


def validate_analysis_request(data: dict) -> Tuple[bool, Optional[str]]:
    """
    Validate analysis request payload.
    Returns (is_valid, error_message).
    """
    if not data:
        return False, "Request body is required"

    # Must have either notificationId OR notification object
    has_id = 'notificationId' in data and data['notificationId']
    has_notification = 'notification' in data and data['notification']

    if not has_id and not has_notification:
        return False, "Missing 'notificationId' or 'notification' object in request body"

    if has_id:
        is_valid, error = validate_notification_id(data['notificationId'])
        if not is_valid:
            return False, error

    if has_notification:
        is_valid, error = validate_notification_data(data['notification'])
        if not is_valid:
            return False, error

    if 'language' in data:
        is_valid, error = validate_language(data['language'])
        if not is_valid:
            return False, error

    return True, None


def validate_chat_request(data: dict) -> Tuple[bool, Optional[str]]:
    """
    Validate chat request payload.
    Returns (is_valid, error_message).
    """
    if not data:
        return False, "Request body is required"

    # Required fields
    if 'notification' not in data or not data['notification']:
        return False, "Missing 'notification' in request body"
    if 'question' not in data or not data['question']:
        return False, "Missing 'question' in request body"
    if 'analysis' not in data or not data['analysis']:
        return False, "Missing 'analysis' in request body"

    # Validate notification
    is_valid, error = validate_notification_data(data['notification'])
    if not is_valid:
        return False, error

    # Validate question length
    is_valid, error = validate_text_field(data['question'], 'question', MAX_QUESTION_LENGTH, required=True)
    if not is_valid:
        return False, error

    # Validate analysis is a dict
    if not isinstance(data['analysis'], dict):
        return False, "'analysis' must be an object"

    if 'language' in data:
        is_valid, error = validate_language(data['language'])
        if not is_valid:
            return False, error

    return True, None


def validate_configuration(data: dict) -> Tuple[bool, Optional[str]]:
    """
    Validate configuration payload.
    Returns (is_valid, error_message).
    """
    if not data:
        return False, "Configuration data is required"
    if not isinstance(data, dict):
        return False, "Configuration must be an object"

    # Validate specific config fields if present
    allowed_keys = {'analysis_llm_settings', 'chat_llm_settings', 'model', 'temperature'}

    # Check for LLM settings
    for setting_key in ['analysis_llm_settings', 'chat_llm_settings']:
        if setting_key in data:
            settings = data[setting_key]
            if not isinstance(settings, dict):
                return False, f"{setting_key} must be an object"
            if 'temperature' in settings:
                temp = settings['temperature']
                if not isinstance(temp, (int, float)) or temp < 0 or temp > 2:
                    return False, f"Temperature in {setting_key} must be a number between 0 and 2"

    return True, None
