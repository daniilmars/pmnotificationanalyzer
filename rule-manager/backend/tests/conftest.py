"""
Pytest fixtures for Rule Manager backend tests.
"""
import os
import sys
import pytest
import tempfile

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Set test environment variables before importing app
os.environ['FLASK_ENV'] = 'testing'


@pytest.fixture
def app():
    """Create and configure a test application instance."""
    # Create a temporary database
    db_fd, db_path = tempfile.mkstemp(suffix='.db')

    # Set environment to use temp database
    os.environ['DATABASE_URI'] = f'sqlite:///{db_path}'

    from app import create_app

    flask_app = create_app('testing')
    flask_app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}'
    })

    yield flask_app

    # Cleanup
    os.close(db_fd)
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def client(app):
    """Create a test client for the application."""
    return app.test_client()


@pytest.fixture
def sample_ruleset_data():
    """Sample ruleset creation data."""
    return {
        'name': 'Test Ruleset',
        'notification_type': 'M1',
        'created_by': 'test_user'
    }


@pytest.fixture
def sample_rule_data():
    """Sample rule data."""
    return {
        'name': 'Test Rule',
        'description': 'A test rule for validation',
        'target_field': 'Short Text',
        'condition': 'is not empty',
        'value': None,
        'score_impact': -10,
        'feedback_message': 'Short text should not be empty'
    }


@pytest.fixture
def sample_rules_list():
    """Sample list of rules."""
    return [
        {
            'name': 'Rule 1',
            'description': 'First test rule',
            'target_field': 'Short Text',
            'condition': 'is not empty',
            'value': None,
            'score_impact': -10,
            'feedback_message': 'Short text is required'
        },
        {
            'name': 'Rule 2',
            'description': 'Second test rule',
            'target_field': 'Long Text',
            'condition': 'has length greater than',
            'value': '50',
            'score_impact': -5,
            'feedback_message': 'Long text should be detailed'
        }
    ]
