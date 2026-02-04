"""
Integration tests for PM Analyzer API endpoints.
"""
import pytest
import json


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_check(self, client):
        """Test health check returns OK."""
        response = client.get('/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'


class TestNotificationsEndpoint:
    """Tests for the notifications list endpoint."""

    def test_get_notifications_empty(self, client):
        """Test getting notifications from empty database."""
        response = client.get('/api/notifications')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'value' in data
        assert isinstance(data['value'], list)

    def test_get_notifications_with_language(self, client):
        """Test getting notifications with language parameter."""
        response = client.get('/api/notifications?language=de')
        assert response.status_code == 200

    def test_get_notifications_invalid_language(self, client):
        """Test getting notifications with invalid language."""
        response = client.get('/api/notifications?language=fr')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_get_notifications_with_pagination(self, client):
        """Test getting notifications with pagination."""
        response = client.get('/api/notifications?paginate=true&page=1&page_size=10')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'items' in data
        assert 'total' in data
        assert 'page' in data
        assert 'page_size' in data
        assert 'total_pages' in data

    def test_get_notifications_invalid_page(self, client):
        """Test getting notifications with invalid page number."""
        response = client.get('/api/notifications?paginate=true&page=0')
        assert response.status_code == 400

    def test_get_notifications_invalid_page_size(self, client):
        """Test getting notifications with invalid page size."""
        response = client.get('/api/notifications?paginate=true&page_size=200')
        assert response.status_code == 400

    def test_get_notifications_with_data(self, client, db_with_data):
        """Test getting notifications from database with data."""
        response = client.get('/api/notifications')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['value']) >= 1


class TestNotificationDetailEndpoint:
    """Tests for the notification detail endpoint."""

    def test_get_notification_not_found(self, client):
        """Test getting non-existent notification."""
        response = client.get('/api/notifications/NOTEXIST01')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['error']['code'] == 'NOT_FOUND'

    def test_get_notification_invalid_id(self, client):
        """Test getting notification with invalid ID format."""
        response = client.get('/api/notifications/<script>alert(1)</script>')
        assert response.status_code == 400

    def test_get_notification_with_data(self, client, db_with_data):
        """Test getting notification that exists."""
        response = client.get('/api/notifications/TEST000001')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['NotificationId'] == 'TEST000001'

    def test_get_notification_german(self, client, db_with_data):
        """Test getting notification in German."""
        response = client.get('/api/notifications/TEST000001?language=de')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['Description'] == 'Test Meldung'


class TestAnalyzeEndpoint:
    """Tests for the analyze endpoint."""

    def test_analyze_missing_body(self, client):
        """Test analyze with missing request body."""
        response = client.post('/api/analyze', content_type='application/json')
        assert response.status_code == 400

    def test_analyze_missing_notification(self, client):
        """Test analyze with missing notification data."""
        response = client.post(
            '/api/analyze',
            data=json.dumps({'language': 'en'}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'BAD_REQUEST'

    def test_analyze_notification_not_found(self, client):
        """Test analyze with non-existent notification ID."""
        response = client.post(
            '/api/analyze',
            data=json.dumps({'notificationId': 'NOTEXIST01'}),
            content_type='application/json'
        )
        assert response.status_code == 404

    def test_analyze_invalid_language(self, client, sample_notification):
        """Test analyze with invalid language."""
        response = client.post(
            '/api/analyze',
            data=json.dumps({
                'notification': sample_notification,
                'language': 'invalid'
            }),
            content_type='application/json'
        )
        assert response.status_code == 400


class TestChatEndpoint:
    """Tests for the chat endpoint."""

    def test_chat_missing_body(self, client):
        """Test chat with missing request body."""
        response = client.post('/api/chat', content_type='application/json')
        assert response.status_code == 400

    def test_chat_missing_notification(self, client, sample_analysis_response):
        """Test chat with missing notification."""
        response = client.post(
            '/api/chat',
            data=json.dumps({
                'question': 'What can I improve?',
                'analysis': sample_analysis_response
            }),
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_chat_missing_question(self, client, sample_notification, sample_analysis_response):
        """Test chat with missing question."""
        response = client.post(
            '/api/chat',
            data=json.dumps({
                'notification': sample_notification,
                'analysis': sample_analysis_response
            }),
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_chat_missing_analysis(self, client, sample_notification):
        """Test chat with missing analysis."""
        response = client.post(
            '/api/chat',
            data=json.dumps({
                'notification': sample_notification,
                'question': 'What can I improve?'
            }),
            content_type='application/json'
        )
        assert response.status_code == 400


class TestConfigurationEndpoint:
    """Tests for the configuration endpoints."""

    def test_get_configuration(self, client):
        """Test getting configuration."""
        response = client.get('/api/configuration')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_set_configuration_missing_body(self, client):
        """Test setting configuration with missing body."""
        response = client.post('/api/configuration', content_type='application/json')
        assert response.status_code == 400

    def test_set_configuration_empty_body(self, client):
        """Test setting configuration with empty body."""
        response = client.post(
            '/api/configuration',
            data=json.dumps({}),
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_set_configuration_valid(self, client):
        """Test setting valid configuration."""
        config = {
            'analysis_llm_settings': {
                'model': 'gemini-pro',
                'temperature': 0.3
            }
        }
        response = client.post(
            '/api/configuration',
            data=json.dumps(config),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'

    def test_set_configuration_invalid_temperature(self, client):
        """Test setting configuration with invalid temperature."""
        config = {
            'analysis_llm_settings': {
                'temperature': 5.0  # Too high
            }
        }
        response = client.post(
            '/api/configuration',
            data=json.dumps(config),
            content_type='application/json'
        )
        assert response.status_code == 400
