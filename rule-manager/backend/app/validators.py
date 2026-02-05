"""Input validation utilities for Rule Manager API."""
import re
from typing import Optional, Tuple, Any

# Validation constants
MAX_NAME_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000
MAX_FEEDBACK_LENGTH = 1000
ALLOWED_STATUSES = {'Draft', 'Active', 'Retired', 'Test'}
ALLOWED_CONDITIONS = {'is not empty', 'contains', 'starts with', 'has length greater than'}
ALLOWED_TARGET_FIELDS = {'Short Text', 'Long Text', 'Priority', 'Equipment', 'Functional Location'}
ALLOWED_NOTIFICATION_TYPES = {'M1', 'M2', 'M3'}  # SAP PM notification types


def validate_uuid(value: str, field_name: str = 'ID') -> Tuple[bool, Optional[str]]:
    """Validate UUID format."""
    if not value:
        return False, f"{field_name} is required"
    if not isinstance(value, str):
        return False, f"{field_name} must be a string"
    # UUID pattern (with or without dashes)
    uuid_pattern = re.compile(r'^[a-fA-F0-9]{8}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{12}$')
    if not uuid_pattern.match(value):
        return False, f"Invalid {field_name} format"
    return True, None


def validate_string_field(value: Any, field_name: str, max_length: int, required: bool = False) -> Tuple[bool, Optional[str]]:
    """Validate a string field."""
    if value is None or value == '':
        if required:
            return False, f"{field_name} is required"
        return True, None
    if not isinstance(value, str):
        return False, f"{field_name} must be a string"
    if len(value) > max_length:
        return False, f"{field_name} exceeds maximum length of {max_length} characters"
    return True, None


def validate_create_ruleset(data: dict) -> Tuple[bool, Optional[str]]:
    """Validate ruleset creation payload."""
    if not data:
        return False, "Request body is required"
    if not isinstance(data, dict):
        return False, "Request body must be an object"

    # Required fields
    required_fields = ['name', 'notification_type', 'created_by']
    for field in required_fields:
        if field not in data or not data[field]:
            return False, f"Missing required field: {field}"

    # Validate name
    is_valid, error = validate_string_field(data['name'], 'name', MAX_NAME_LENGTH, required=True)
    if not is_valid:
        return False, error

    # Validate notification_type
    if data['notification_type'] not in ALLOWED_NOTIFICATION_TYPES:
        return False, f"notification_type must be one of: {', '.join(ALLOWED_NOTIFICATION_TYPES)}"

    # Validate created_by
    is_valid, error = validate_string_field(data['created_by'], 'created_by', MAX_NAME_LENGTH, required=True)
    if not is_valid:
        return False, error

    return True, None


def validate_update_ruleset(data: dict) -> Tuple[bool, Optional[str]]:
    """Validate ruleset update payload."""
    if not data:
        return False, "Request body is required"
    if not isinstance(data, dict):
        return False, "Request body must be an object"

    # created_by is required for audit
    if 'created_by' not in data or not data['created_by']:
        return False, "Missing required field: created_by"

    # Validate optional fields if present
    if 'name' in data:
        is_valid, error = validate_string_field(data['name'], 'name', MAX_NAME_LENGTH)
        if not is_valid:
            return False, error

    if 'notification_type' in data:
        if data['notification_type'] not in ALLOWED_NOTIFICATION_TYPES:
            return False, f"notification_type must be one of: {', '.join(ALLOWED_NOTIFICATION_TYPES)}"

    return True, None


def validate_rule(rule_data: dict) -> Tuple[bool, Optional[str]]:
    """Validate a single rule object."""
    if not rule_data:
        return False, "Rule data is required"
    if not isinstance(rule_data, dict):
        return False, "Rule must be an object"

    # Required fields
    required_fields = ['name', 'target_field', 'condition', 'score_impact', 'feedback_message']
    for field in required_fields:
        if field not in rule_data:
            return False, f"Missing required field in rule: {field}"

    # Validate name
    is_valid, error = validate_string_field(rule_data['name'], 'name', MAX_NAME_LENGTH, required=True)
    if not is_valid:
        return False, error

    # Validate description (optional)
    if 'description' in rule_data:
        is_valid, error = validate_string_field(rule_data['description'], 'description', MAX_DESCRIPTION_LENGTH)
        if not is_valid:
            return False, error

    # Validate target_field
    if rule_data['target_field'] not in ALLOWED_TARGET_FIELDS:
        return False, f"target_field must be one of: {', '.join(ALLOWED_TARGET_FIELDS)}"

    # Validate condition
    if rule_data['condition'] not in ALLOWED_CONDITIONS:
        return False, f"condition must be one of: {', '.join(ALLOWED_CONDITIONS)}"

    # Validate score_impact
    score_impact = rule_data['score_impact']
    if not isinstance(score_impact, (int, float)):
        return False, "score_impact must be a number"
    if score_impact < -100 or score_impact > 100:
        return False, "score_impact must be between -100 and 100"

    # Validate feedback_message
    is_valid, error = validate_string_field(rule_data['feedback_message'], 'feedback_message', MAX_FEEDBACK_LENGTH, required=True)
    if not is_valid:
        return False, error

    # Validate value (optional, but required for some conditions)
    value_required_conditions = {'contains', 'starts with', 'has length greater than'}
    if rule_data['condition'] in value_required_conditions:
        if 'value' not in rule_data or rule_data['value'] is None:
            return False, f"'value' is required for condition '{rule_data['condition']}'"

    return True, None


def validate_rules_list(rules_data: Any) -> Tuple[bool, Optional[str]]:
    """Validate a list of rules."""
    if not isinstance(rules_data, list):
        return False, "Request must be a list of rule objects"
    if len(rules_data) == 0:
        return False, "At least one rule is required"
    if len(rules_data) > 100:
        return False, "Cannot add more than 100 rules at once"

    for i, rule in enumerate(rules_data):
        is_valid, error = validate_rule(rule)
        if not is_valid:
            return False, f"Rule {i + 1}: {error}"

    return True, None


def validate_activation_request(data: dict) -> Tuple[bool, Optional[str]]:
    """Validate activation request payload."""
    if not data:
        return False, "Request body is required"
    if not isinstance(data, dict):
        return False, "Request body must be an object"
    if 'created_by' not in data or not data['created_by']:
        return False, "Missing required field: created_by"
    return True, None


def validate_file_upload(file) -> Tuple[bool, Optional[str]]:
    """Validate file upload."""
    if not file:
        return False, "No file provided"
    if file.filename == '':
        return False, "No file selected"
    if not file.filename.lower().endswith('.pdf'):
        return False, "Only PDF files are supported"
    # Check file size (max 10MB)
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)  # Reset to beginning
    if size > 10 * 1024 * 1024:
        return False, "File size exceeds maximum of 10MB"
    return True, None
