"""
Unit tests for AI Governance module.
"""
import pytest
import sys
import os
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Set test database path before importing governance module
_test_db_fd, _test_db_path = tempfile.mkstemp(suffix='.db')
os.environ['AI_GOVERNANCE_DB_PATH'] = _test_db_path
os.environ['AI_GOVERNANCE_ENABLED'] = 'true'

from app.ai_governance import (
    init_governance_db,
    compute_hash,
    create_prompt_template,
    approve_prompt_template,
    get_active_prompt_template,
    get_prompt_template_history,
    log_ai_usage,
    get_ai_usage_logs,
    validate_model,
    register_model,
    validate_model_for_use,
    log_config_change,
    get_config_history,
    generate_request_id,
    APPROVED_MODELS
)


@pytest.fixture(scope='module', autouse=True)
def setup_governance_db():
    """Initialize governance database for tests."""
    init_governance_db()
    yield
    # Cleanup
    os.close(_test_db_fd)
    if os.path.exists(_test_db_path):
        os.unlink(_test_db_path)


class TestHashFunctions:
    """Tests for hash utility functions."""

    def test_compute_hash_returns_string(self):
        """Test that compute_hash returns a string."""
        result = compute_hash('test content')
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 hex length

    def test_compute_hash_deterministic(self):
        """Test that same input produces same hash."""
        content = 'test content'
        hash1 = compute_hash(content)
        hash2 = compute_hash(content)
        assert hash1 == hash2

    def test_compute_hash_different_inputs(self):
        """Test that different inputs produce different hashes."""
        hash1 = compute_hash('content1')
        hash2 = compute_hash('content2')
        assert hash1 != hash2


class TestPromptTemplates:
    """Tests for prompt template management."""

    def test_create_prompt_template(self):
        """Test creating a new prompt template."""
        success, data, error = create_prompt_template(
            template_name='test_prompt',
            template_content='This is a test prompt template',
            created_by='test_user',
            description='Test description',
            purpose='Testing'
        )

        assert success is True
        assert data is not None
        assert data['template_name'] == 'test_prompt'
        assert data['version'] == 1
        assert data['status'] == 'draft'
        assert error is None

    def test_create_prompt_template_version_increment(self):
        """Test that creating another template with same name increments version."""
        # Create first version
        create_prompt_template(
            template_name='versioned_prompt',
            template_content='Version 1 content',
            created_by='test_user'
        )

        # Create second version
        success, data, _ = create_prompt_template(
            template_name='versioned_prompt',
            template_content='Version 2 content',
            created_by='test_user'
        )

        assert success is True
        assert data['version'] == 2

    def test_get_prompt_template_history(self):
        """Test retrieving prompt template version history."""
        # Create multiple versions
        create_prompt_template(
            template_name='history_prompt',
            template_content='History v1',
            created_by='user1'
        )
        create_prompt_template(
            template_name='history_prompt',
            template_content='History v2',
            created_by='user2'
        )

        history = get_prompt_template_history('history_prompt')

        assert len(history) >= 2
        assert history[0]['version'] > history[1]['version']  # Sorted by version desc

    def test_get_active_prompt_template_none_approved(self):
        """Test getting active template when none are approved."""
        create_prompt_template(
            template_name='unapproved_prompt',
            template_content='Not approved',
            created_by='user'
        )

        active = get_active_prompt_template('unapproved_prompt')
        assert active is None  # No approved version


class TestAIUsageLogging:
    """Tests for AI usage logging."""

    def test_generate_request_id(self):
        """Test generating unique request IDs."""
        id1 = generate_request_id()
        id2 = generate_request_id()

        assert isinstance(id1, str)
        assert len(id1) > 0
        assert id1 != id2  # Should be unique

    def test_log_ai_usage_success(self):
        """Test logging successful AI usage."""
        request_id = generate_request_id()

        result = log_ai_usage(
            request_id=request_id,
            model_id='gemini-pro',
            input_data='Test input prompt',
            output_data='Test output response',
            template_name='test_template',
            template_version=1,
            user_id='test_user',
            latency_ms=150,
            status='success',
            context_type='notification_analysis',
            context_id='TEST001'
        )

        assert result is True

    def test_log_ai_usage_error(self):
        """Test logging failed AI usage."""
        request_id = generate_request_id()

        result = log_ai_usage(
            request_id=request_id,
            model_id='gemini-pro',
            input_data='Test input',
            status='error',
            error_message='API timeout'
        )

        assert result is True

    def test_get_ai_usage_logs(self):
        """Test retrieving AI usage logs."""
        # Create a log entry
        request_id = generate_request_id()
        log_ai_usage(
            request_id=request_id,
            model_id='gemini-pro',
            input_data='Query test',
            status='success'
        )

        logs = get_ai_usage_logs(limit=10)

        assert isinstance(logs, list)
        assert len(logs) > 0

    def test_get_ai_usage_logs_with_filter(self):
        """Test retrieving AI usage logs with filters."""
        # Create log entries with specific model
        for i in range(3):
            log_ai_usage(
                request_id=generate_request_id(),
                model_id='filter-test-model',
                input_data=f'Filter test {i}',
                status='success'
            )

        logs = get_ai_usage_logs(model_id='filter-test-model')

        assert all(log['model_id'] == 'filter-test-model' for log in logs)


class TestModelGovernance:
    """Tests for AI model governance."""

    def test_validate_approved_model(self):
        """Test validating an approved model."""
        # gemini-pro should be in default approved list
        is_valid, error = validate_model('gemini-pro')
        assert is_valid is True
        assert error is None

    def test_validate_unapproved_model(self):
        """Test validating an unapproved model."""
        is_valid, error = validate_model('some-unapproved-model-xyz')
        assert is_valid is False
        assert error is not None
        assert 'not approved' in error.lower()

    def test_register_model(self):
        """Test registering a new AI model."""
        success, error = register_model(
            model_id='test-model-v1',
            model_name='Test Model',
            provider='TestProvider',
            version='1.0',
            intended_use='Testing only',
            risk_assessment='Low risk for testing'
        )

        assert success is True
        assert error is None

    def test_register_duplicate_model(self):
        """Test registering a duplicate model fails."""
        # Register first time
        register_model(
            model_id='duplicate-model',
            model_name='Duplicate Test',
            provider='Provider'
        )

        # Try to register again
        success, error = register_model(
            model_id='duplicate-model',
            model_name='Duplicate Test 2',
            provider='Provider'
        )

        assert success is False
        assert 'already registered' in error.lower()


class TestConfigurationVersioning:
    """Tests for configuration change logging."""

    def test_log_config_change(self):
        """Test logging a configuration change."""
        result = log_config_change(
            config_name='test_config',
            config_value={'setting': 'value'},
            changed_by='admin_user',
            change_reason='Initial configuration'
        )

        assert result is True

    def test_log_config_change_tracks_previous(self):
        """Test that config change logs track previous values."""
        # Set initial value
        log_config_change(
            config_name='tracked_config',
            config_value='initial_value',
            changed_by='user1'
        )

        # Update value
        log_config_change(
            config_name='tracked_config',
            config_value='updated_value',
            changed_by='user2'
        )

        history = get_config_history('tracked_config')

        assert len(history) >= 2
        # Most recent entry should have previous value set
        assert history[0]['previous_value'] is not None

    def test_get_config_history(self):
        """Test retrieving configuration history."""
        # Create some history
        for i in range(3):
            log_config_change(
                config_name='history_test_config',
                config_value=f'value_{i}',
                changed_by=f'user_{i}'
            )

        history = get_config_history('history_test_config')

        assert isinstance(history, list)
        assert len(history) >= 3

    def test_get_config_history_limit(self):
        """Test that config history respects limit."""
        # Create many entries
        for i in range(10):
            log_config_change(
                config_name='limited_config',
                config_value=f'value_{i}',
                changed_by='user'
            )

        history = get_config_history('limited_config', limit=5)

        assert len(history) <= 5


class TestIntegrity:
    """Tests for data integrity features."""

    def test_prompt_template_hash_integrity(self):
        """Test that prompt template content hash is computed correctly."""
        content = 'Test prompt content for hashing'
        expected_hash = compute_hash(content)

        success, data, _ = create_prompt_template(
            template_name='hash_test_prompt',
            template_content=content,
            created_by='user'
        )

        assert data['content_hash'] == expected_hash

    def test_ai_usage_log_hashes_input(self):
        """Test that AI usage logs compute input hashes."""
        request_id = generate_request_id()
        input_data = 'Test input for hash verification'

        log_ai_usage(
            request_id=request_id,
            model_id='test-model',
            input_data=input_data,
            status='success'
        )

        # Retrieve and verify hash
        logs = get_ai_usage_logs(limit=1)
        if logs:
            expected_hash = compute_hash(input_data)
            assert logs[0].get('input_hash') == expected_hash
