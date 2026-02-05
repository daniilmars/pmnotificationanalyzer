"""
Pytest fixtures for PM Analyzer backend tests.
"""
import os
import sys
import pytest
import tempfile
import sqlite3

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Set test environment variables before importing app
os.environ['FLASK_DEBUG'] = 'false'
os.environ['AUTH_ENABLED'] = 'false'


@pytest.fixture
def app():
    """Create and configure a test application instance."""
    # Create a temporary database
    db_fd, db_path = tempfile.mkstemp(suffix='.db')

    # Set environment to use temp database
    os.environ['DATABASE_PATH'] = db_path

    from app.main import app as flask_app

    flask_app.config.update({
        'TESTING': True,
    })

    # Initialize the test database with schema
    schema_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'schema.sql')
    if os.path.exists(schema_path):
        with sqlite3.connect(db_path) as conn:
            with open(schema_path, 'r') as f:
                conn.executescript(f.read())

    yield flask_app

    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """Create a test client for the application."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test CLI runner."""
    return app.test_cli_runner()


@pytest.fixture
def sample_notification():
    """Sample notification data for testing."""
    return {
        "NotificationId": "TEST000001",
        "NotificationType": "M1",
        "NotificationTypeText": "Maintenance Request",
        "Description": "Test notification description",
        "EquipmentNumber": "EQ-001",
        "FunctionalLocation": "FL-001",
        "Priority": "2",
        "PriorityText": "High",
        "CreatedByUser": "TEST_USER",
        "CreationDate": "2024-01-15",
        "RequiredStartDate": "2024-01-16",
        "RequiredEndDate": "2024-01-20",
        "LongText": "This is a detailed description of the maintenance issue.",
        "SystemStatus": "OSDN"
    }


@pytest.fixture
def sample_analysis_response():
    """Sample analysis response for testing."""
    return {
        "score": 75,
        "summary": "The notification meets most quality standards.",
        "problems": [
            {
                "field": "LongText",
                "severity": "Minor",
                "description": "Consider adding more details about root cause."
            }
        ]
    }


@pytest.fixture
def db_with_data(app):
    """Set up database with sample data."""
    from app.database import DATABASE_PATH

    with sqlite3.connect(DATABASE_PATH) as conn:
        # Insert test notification
        conn.execute("""
            INSERT INTO QMEL (QMNUM, QMART, PRIOK, QMNAM, ERDAT, MZEIT, EQUNR, TPLNR)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ('TEST000001', 'M1', '2', 'TEST_USER', '2024-01-15', '10:00:00', 'EQ-001', 'FL-001'))

        conn.execute("""
            INSERT INTO NOTIF_CONTENT (QMNUM, SPRAS, QMTXT, TDLINE)
            VALUES (?, ?, ?, ?)
        """, ('TEST000001', 'en', 'Test Notification', 'Detailed long text for testing'))

        conn.execute("""
            INSERT INTO NOTIF_CONTENT (QMNUM, SPRAS, QMTXT, TDLINE)
            VALUES (?, ?, ?, ?)
        """, ('TEST000001', 'de', 'Test Meldung', 'Detaillierter Langtext zum Testen'))

        conn.commit()

    return app
