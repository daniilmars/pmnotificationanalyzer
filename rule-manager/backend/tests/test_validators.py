"""
Unit tests for Rule Manager validators.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.validators import (
    validate_uuid,
    validate_string_field,
    validate_create_ruleset,
    validate_update_ruleset,
    validate_rule,
    validate_rules_list,
    validate_activation_request,
    validate_file_upload,
    ALLOWED_NOTIFICATION_TYPES,
    ALLOWED_CONDITIONS,
    ALLOWED_TARGET_FIELDS
)
from io import BytesIO


class TestValidateUuid:
    """Tests for validate_uuid function."""

    def test_valid_uuid_with_dashes(self):
        """Test valid UUID with dashes."""
        is_valid, error = validate_uuid('550e8400-e29b-41d4-a716-446655440000')
        assert is_valid is True
        assert error is None

    def test_valid_uuid_without_dashes(self):
        """Test valid UUID without dashes."""
        is_valid, error = validate_uuid('550e8400e29b41d4a716446655440000')
        assert is_valid is True
        assert error is None

    def test_empty_uuid(self):
        """Test empty UUID."""
        is_valid, error = validate_uuid('')
        assert is_valid is False
        assert 'required' in error.lower()

    def test_invalid_uuid_format(self):
        """Test invalid UUID format."""
        is_valid, error = validate_uuid('not-a-uuid')
        assert is_valid is False
        assert 'invalid' in error.lower()


class TestValidateStringField:
    """Tests for validate_string_field function."""

    def test_valid_string(self):
        """Test valid string field."""
        is_valid, error = validate_string_field('Test Value', 'name', 200)
        assert is_valid is True
        assert error is None

    def test_string_too_long(self):
        """Test string exceeding max length."""
        is_valid, error = validate_string_field('A' * 250, 'name', 200)
        assert is_valid is False
        assert 'exceeds maximum length' in error.lower()

    def test_required_empty_string(self):
        """Test required field that's empty."""
        is_valid, error = validate_string_field('', 'name', 200, required=True)
        assert is_valid is False
        assert 'required' in error.lower()

    def test_optional_empty_string(self):
        """Test optional field that's empty."""
        is_valid, error = validate_string_field('', 'name', 200, required=False)
        assert is_valid is True

    def test_non_string_value(self):
        """Test non-string value."""
        is_valid, error = validate_string_field(123, 'name', 200)
        assert is_valid is False
        assert 'must be a string' in error.lower()


class TestValidateCreateRuleset:
    """Tests for validate_create_ruleset function."""

    def test_valid_ruleset(self, sample_ruleset_data):
        """Test valid ruleset creation data."""
        is_valid, error = validate_create_ruleset(sample_ruleset_data)
        assert is_valid is True
        assert error is None

    def test_missing_name(self, sample_ruleset_data):
        """Test ruleset missing name."""
        del sample_ruleset_data['name']
        is_valid, error = validate_create_ruleset(sample_ruleset_data)
        assert is_valid is False
        assert 'name' in error.lower()

    def test_missing_notification_type(self, sample_ruleset_data):
        """Test ruleset missing notification_type."""
        del sample_ruleset_data['notification_type']
        is_valid, error = validate_create_ruleset(sample_ruleset_data)
        assert is_valid is False
        assert 'notification_type' in error.lower()

    def test_invalid_notification_type(self, sample_ruleset_data):
        """Test ruleset with invalid notification_type."""
        sample_ruleset_data['notification_type'] = 'INVALID'
        is_valid, error = validate_create_ruleset(sample_ruleset_data)
        assert is_valid is False
        assert 'notification_type' in error.lower()

    def test_missing_created_by(self, sample_ruleset_data):
        """Test ruleset missing created_by."""
        del sample_ruleset_data['created_by']
        is_valid, error = validate_create_ruleset(sample_ruleset_data)
        assert is_valid is False
        assert 'created_by' in error.lower()


class TestValidateRule:
    """Tests for validate_rule function."""

    def test_valid_rule(self, sample_rule_data):
        """Test valid rule data."""
        is_valid, error = validate_rule(sample_rule_data)
        assert is_valid is True
        assert error is None

    def test_valid_rule_with_value(self):
        """Test valid rule that requires value."""
        rule = {
            'name': 'Length Rule',
            'target_field': 'Long Text',
            'condition': 'has length greater than',
            'value': '100',
            'score_impact': -5,
            'feedback_message': 'Text should be longer'
        }
        is_valid, error = validate_rule(rule)
        assert is_valid is True

    def test_missing_required_field(self, sample_rule_data):
        """Test rule missing required field."""
        del sample_rule_data['name']
        is_valid, error = validate_rule(sample_rule_data)
        assert is_valid is False
        assert 'name' in error.lower()

    def test_invalid_target_field(self, sample_rule_data):
        """Test rule with invalid target_field."""
        sample_rule_data['target_field'] = 'Invalid Field'
        is_valid, error = validate_rule(sample_rule_data)
        assert is_valid is False
        assert 'target_field' in error.lower()

    def test_invalid_condition(self, sample_rule_data):
        """Test rule with invalid condition."""
        sample_rule_data['condition'] = 'invalid condition'
        is_valid, error = validate_rule(sample_rule_data)
        assert is_valid is False
        assert 'condition' in error.lower()

    def test_score_impact_out_of_range(self, sample_rule_data):
        """Test rule with score_impact out of range."""
        sample_rule_data['score_impact'] = -150
        is_valid, error = validate_rule(sample_rule_data)
        assert is_valid is False
        assert 'score_impact' in error.lower()

    def test_missing_value_for_condition(self):
        """Test rule missing value when condition requires it."""
        rule = {
            'name': 'Contains Rule',
            'target_field': 'Short Text',
            'condition': 'contains',
            'value': None,  # Missing required value
            'score_impact': -5,
            'feedback_message': 'Text should contain keyword'
        }
        is_valid, error = validate_rule(rule)
        assert is_valid is False
        assert 'value' in error.lower()


class TestValidateRulesList:
    """Tests for validate_rules_list function."""

    def test_valid_rules_list(self, sample_rules_list):
        """Test valid rules list."""
        is_valid, error = validate_rules_list(sample_rules_list)
        assert is_valid is True
        assert error is None

    def test_empty_rules_list(self):
        """Test empty rules list."""
        is_valid, error = validate_rules_list([])
        assert is_valid is False
        assert 'at least one rule' in error.lower()

    def test_not_a_list(self):
        """Test non-list input."""
        is_valid, error = validate_rules_list({'name': 'single rule'})
        assert is_valid is False
        assert 'list' in error.lower()

    def test_too_many_rules(self):
        """Test list with too many rules."""
        rules = [{'name': f'Rule {i}', 'target_field': 'Short Text', 'condition': 'is not empty',
                  'score_impact': -1, 'feedback_message': 'msg'} for i in range(101)]
        is_valid, error = validate_rules_list(rules)
        assert is_valid is False
        assert '100' in error.lower()

    def test_invalid_rule_in_list(self, sample_rules_list):
        """Test list containing invalid rule."""
        sample_rules_list[1]['condition'] = 'invalid'
        is_valid, error = validate_rules_list(sample_rules_list)
        assert is_valid is False
        assert 'Rule 2' in error


class TestValidateActivationRequest:
    """Tests for validate_activation_request function."""

    def test_valid_activation(self):
        """Test valid activation request."""
        is_valid, error = validate_activation_request({'created_by': 'test_user'})
        assert is_valid is True
        assert error is None

    def test_missing_created_by(self):
        """Test activation request missing created_by."""
        is_valid, error = validate_activation_request({})
        assert is_valid is False
        assert 'created_by' in error.lower()

    def test_empty_body(self):
        """Test empty request body."""
        is_valid, error = validate_activation_request(None)
        assert is_valid is False


class TestValidateFileUpload:
    """Tests for validate_file_upload function."""

    def test_valid_pdf(self):
        """Test valid PDF file."""

        class MockFile:
            filename = 'test.pdf'

            def seek(self, pos, whence=0):
                pass

            def tell(self):
                return 1024  # 1KB

        is_valid, error = validate_file_upload(MockFile())
        assert is_valid is True
        assert error is None

    def test_no_file(self):
        """Test no file provided."""
        is_valid, error = validate_file_upload(None)
        assert is_valid is False
        assert 'no file' in error.lower()

    def test_empty_filename(self):
        """Test empty filename."""

        class MockFile:
            filename = ''

        is_valid, error = validate_file_upload(MockFile())
        assert is_valid is False
        assert 'no file selected' in error.lower()

    def test_wrong_file_type(self):
        """Test non-PDF file."""

        class MockFile:
            filename = 'test.txt'

        is_valid, error = validate_file_upload(MockFile())
        assert is_valid is False
        assert 'pdf' in error.lower()

    def test_file_too_large(self):
        """Test file exceeding size limit."""

        class MockFile:
            filename = 'large.pdf'

            def seek(self, pos, whence=0):
                pass

            def tell(self):
                return 15 * 1024 * 1024  # 15MB

        is_valid, error = validate_file_upload(MockFile())
        assert is_valid is False
        assert '10MB' in error
