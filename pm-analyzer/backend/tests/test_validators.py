"""
Unit tests for input validators.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.validators import (
    validate_notification_id,
    validate_language,
    validate_text_field,
    validate_notification_data,
    validate_analysis_request,
    validate_chat_request,
    validate_configuration,
    ALLOWED_LANGUAGES,
    MAX_TEXT_LENGTH,
    MAX_QUESTION_LENGTH
)


class TestValidateNotificationId:
    """Tests for validate_notification_id function."""

    def test_valid_notification_id(self):
        """Test valid notification IDs."""
        valid_ids = ['TEST000001', 'NOTIF12345', 'A1B2C3D4E5']
        for nid in valid_ids:
            is_valid, error = validate_notification_id(nid)
            assert is_valid is True
            assert error is None

    def test_empty_notification_id(self):
        """Test empty notification ID."""
        is_valid, error = validate_notification_id('')
        assert is_valid is False
        assert 'required' in error.lower()

    def test_none_notification_id(self):
        """Test None notification ID."""
        is_valid, error = validate_notification_id(None)
        assert is_valid is False

    def test_notification_id_too_long(self):
        """Test notification ID that's too long."""
        is_valid, error = validate_notification_id('A' * 25)
        assert is_valid is False
        assert 'too long' in error.lower()

    def test_notification_id_invalid_characters(self):
        """Test notification ID with invalid characters."""
        is_valid, error = validate_notification_id('TEST<>001')
        assert is_valid is False
        assert 'invalid characters' in error.lower()


class TestValidateLanguage:
    """Tests for validate_language function."""

    def test_valid_language_en(self):
        """Test valid English language code."""
        is_valid, error = validate_language('en')
        assert is_valid is True
        assert error is None

    def test_valid_language_de(self):
        """Test valid German language code."""
        is_valid, error = validate_language('de')
        assert is_valid is True
        assert error is None

    def test_invalid_language(self):
        """Test invalid language code."""
        is_valid, error = validate_language('fr')
        assert is_valid is False
        assert 'must be one of' in error.lower()


class TestValidateTextField:
    """Tests for validate_text_field function."""

    def test_valid_text(self):
        """Test valid text field."""
        is_valid, error = validate_text_field('This is valid text', 'description')
        assert is_valid is True
        assert error is None

    def test_text_too_long(self):
        """Test text field that exceeds max length."""
        long_text = 'A' * (MAX_TEXT_LENGTH + 1)
        is_valid, error = validate_text_field(long_text, 'description')
        assert is_valid is False
        assert 'exceeds maximum length' in error.lower()

    def test_required_empty_text(self):
        """Test required text field that's empty."""
        is_valid, error = validate_text_field(None, 'description', required=True)
        assert is_valid is False
        assert 'required' in error.lower()

    def test_optional_empty_text(self):
        """Test optional text field that's empty."""
        is_valid, error = validate_text_field(None, 'description', required=False)
        assert is_valid is True

    def test_non_string_text(self):
        """Test non-string value."""
        is_valid, error = validate_text_field(123, 'description')
        assert is_valid is False
        assert 'must be a string' in error.lower()


class TestValidateNotificationData:
    """Tests for validate_notification_data function."""

    def test_valid_notification_data(self, sample_notification):
        """Test valid notification data."""
        is_valid, error = validate_notification_data(sample_notification)
        assert is_valid is True
        assert error is None

    def test_empty_notification_data(self):
        """Test empty notification data."""
        is_valid, error = validate_notification_data({})
        assert is_valid is False

    def test_none_notification_data(self):
        """Test None notification data."""
        is_valid, error = validate_notification_data(None)
        assert is_valid is False


class TestValidateAnalysisRequest:
    """Tests for validate_analysis_request function."""

    def test_valid_request_with_id(self):
        """Test valid request with notification ID."""
        data = {'notificationId': 'TEST000001', 'language': 'en'}
        is_valid, error = validate_analysis_request(data)
        assert is_valid is True
        assert error is None

    def test_valid_request_with_notification(self, sample_notification):
        """Test valid request with notification object."""
        data = {'notification': sample_notification, 'language': 'en'}
        is_valid, error = validate_analysis_request(data)
        assert is_valid is True
        assert error is None

    def test_missing_both_id_and_notification(self):
        """Test request missing both ID and notification."""
        data = {'language': 'en'}
        is_valid, error = validate_analysis_request(data)
        assert is_valid is False
        assert 'notificationId' in error or 'notification' in error

    def test_invalid_language(self):
        """Test request with invalid language."""
        data = {'notificationId': 'TEST000001', 'language': 'fr'}
        is_valid, error = validate_analysis_request(data)
        assert is_valid is False


class TestValidateChatRequest:
    """Tests for validate_chat_request function."""

    def test_valid_chat_request(self, sample_notification, sample_analysis_response):
        """Test valid chat request."""
        data = {
            'notification': sample_notification,
            'question': 'What improvements can I make?',
            'analysis': sample_analysis_response,
            'language': 'en'
        }
        is_valid, error = validate_chat_request(data)
        assert is_valid is True
        assert error is None

    def test_missing_notification(self, sample_analysis_response):
        """Test chat request missing notification."""
        data = {
            'question': 'What improvements can I make?',
            'analysis': sample_analysis_response
        }
        is_valid, error = validate_chat_request(data)
        assert is_valid is False
        assert 'notification' in error.lower()

    def test_missing_question(self, sample_notification, sample_analysis_response):
        """Test chat request missing question."""
        data = {
            'notification': sample_notification,
            'analysis': sample_analysis_response
        }
        is_valid, error = validate_chat_request(data)
        assert is_valid is False
        assert 'question' in error.lower()

    def test_question_too_long(self, sample_notification, sample_analysis_response):
        """Test chat request with question too long."""
        data = {
            'notification': sample_notification,
            'question': 'A' * (MAX_QUESTION_LENGTH + 1),
            'analysis': sample_analysis_response
        }
        is_valid, error = validate_chat_request(data)
        assert is_valid is False
        assert 'maximum length' in error.lower()


class TestValidateConfiguration:
    """Tests for validate_configuration function."""

    def test_valid_configuration(self):
        """Test valid configuration."""
        config = {
            'analysis_llm_settings': {
                'model': 'gemini-pro',
                'temperature': 0.5
            }
        }
        is_valid, error = validate_configuration(config)
        assert is_valid is True
        assert error is None

    def test_empty_configuration(self):
        """Test empty configuration."""
        is_valid, error = validate_configuration({})
        assert is_valid is False

    def test_invalid_temperature(self):
        """Test configuration with invalid temperature."""
        config = {
            'analysis_llm_settings': {
                'temperature': 5.0  # Too high
            }
        }
        is_valid, error = validate_configuration(config)
        assert is_valid is False
        assert 'temperature' in error.lower()
