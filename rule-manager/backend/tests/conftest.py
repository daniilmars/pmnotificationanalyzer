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


@pytest.fixture
def sample_user_data():
    """Sample user creation data."""
    return {
        'username': 'testuser',
        'email': 'testuser@example.com',
        'password': 'TestPassword123!',
        'full_name': 'Test User',
        'department': 'Quality Assurance',
        'title': 'QA Engineer'
    }


@pytest.fixture
def authenticated_client(client, sample_user_data):
    """Create a test client with authenticated user."""
    from app.database import Session, User
    from app.auth_service import hash_password, create_user_session

    session = Session()
    try:
        # Create test user
        user = User(
            id='test-auth-user',
            username=sample_user_data['username'],
            email=sample_user_data['email'],
            password_hash=hash_password(sample_user_data['password']),
            full_name=sample_user_data['full_name']
        )
        session.add(user)
        session.commit()

        # Create session and get token
        success, token, _ = create_user_session(session, 'test-auth-user')

        # Return client with auth header
        client.environ_base['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        return client

    finally:
        session.close()
