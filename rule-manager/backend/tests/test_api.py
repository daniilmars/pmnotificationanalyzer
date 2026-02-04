"""
Integration tests for Rule Manager API endpoints.
"""
import pytest
import json


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_check(self, client):
        """Test health check returns OK."""
        response = client.get('/health')
        assert response.status_code == 200
        assert response.data.decode() == 'OK'


class TestRulesetsEndpoint:
    """Tests for the rulesets list endpoint."""

    def test_get_rulesets_empty(self, client):
        """Test getting rulesets from empty database."""
        response = client.get('/api/v1/rulesets')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)

    def test_get_rulesets_with_filter(self, client):
        """Test getting rulesets with filters."""
        response = client.get('/api/v1/rulesets?notification_type=M1&status=Draft')
        assert response.status_code == 200

    def test_create_ruleset(self, client, sample_ruleset_data):
        """Test creating a new ruleset."""
        response = client.post(
            '/api/v1/rulesets',
            data=json.dumps(sample_ruleset_data),
            content_type='application/json'
        )
        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'id' in data
        assert data['name'] == sample_ruleset_data['name']
        assert data['version'] == 1
        assert data['status'] == 'Draft'

    def test_create_ruleset_missing_name(self, client):
        """Test creating ruleset without name."""
        response = client.post(
            '/api/v1/rulesets',
            data=json.dumps({
                'notification_type': 'M1',
                'created_by': 'test_user'
            }),
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_create_ruleset_invalid_notification_type(self, client):
        """Test creating ruleset with invalid notification type."""
        response = client.post(
            '/api/v1/rulesets',
            data=json.dumps({
                'name': 'Test',
                'notification_type': 'INVALID',
                'created_by': 'test_user'
            }),
            content_type='application/json'
        )
        assert response.status_code == 400


class TestRulesetDetailEndpoint:
    """Tests for the ruleset detail endpoint."""

    def test_get_ruleset_not_found(self, client):
        """Test getting non-existent ruleset."""
        response = client.get('/api/v1/rulesets/550e8400-e29b-41d4-a716-446655440000')
        assert response.status_code == 404

    def test_get_ruleset_invalid_id(self, client):
        """Test getting ruleset with invalid ID format."""
        response = client.get('/api/v1/rulesets/invalid-id')
        assert response.status_code == 400

    def test_get_ruleset(self, client, sample_ruleset_data):
        """Test getting existing ruleset."""
        # Create a ruleset first
        create_response = client.post(
            '/api/v1/rulesets',
            data=json.dumps(sample_ruleset_data),
            content_type='application/json'
        )
        ruleset_id = json.loads(create_response.data)['id']

        # Get the ruleset
        response = client.get(f'/api/v1/rulesets/{ruleset_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['id'] == ruleset_id
        assert data['name'] == sample_ruleset_data['name']
        assert 'rules' in data


class TestRulesetUpdateEndpoint:
    """Tests for the ruleset update endpoint."""

    def test_update_draft_ruleset(self, client, sample_ruleset_data):
        """Test updating a draft ruleset."""
        # Create a ruleset
        create_response = client.post(
            '/api/v1/rulesets',
            data=json.dumps(sample_ruleset_data),
            content_type='application/json'
        )
        ruleset_id = json.loads(create_response.data)['id']

        # Update the ruleset
        response = client.put(
            f'/api/v1/rulesets/{ruleset_id}',
            data=json.dumps({
                'name': 'Updated Name',
                'created_by': 'test_user'
            }),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['version'] == 2

    def test_update_ruleset_missing_created_by(self, client, sample_ruleset_data):
        """Test updating ruleset without created_by."""
        # Create a ruleset
        create_response = client.post(
            '/api/v1/rulesets',
            data=json.dumps(sample_ruleset_data),
            content_type='application/json'
        )
        ruleset_id = json.loads(create_response.data)['id']

        # Try to update without created_by
        response = client.put(
            f'/api/v1/rulesets/{ruleset_id}',
            data=json.dumps({'name': 'New Name'}),
            content_type='application/json'
        )
        assert response.status_code == 400


class TestRulesetActivationEndpoint:
    """Tests for the ruleset activation endpoint."""

    def test_activate_ruleset(self, client, sample_ruleset_data):
        """Test activating a draft ruleset."""
        # Create a ruleset
        create_response = client.post(
            '/api/v1/rulesets',
            data=json.dumps(sample_ruleset_data),
            content_type='application/json'
        )
        ruleset_id = json.loads(create_response.data)['id']

        # Activate the ruleset
        response = client.post(
            f'/api/v1/rulesets/{ruleset_id}/activate',
            data=json.dumps({'created_by': 'test_user'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'activated' in data['message'].lower()

    def test_activate_nonexistent_ruleset(self, client):
        """Test activating non-existent ruleset."""
        response = client.post(
            '/api/v1/rulesets/550e8400-e29b-41d4-a716-446655440000/activate',
            data=json.dumps({'created_by': 'test_user'}),
            content_type='application/json'
        )
        assert response.status_code == 404

    def test_activate_without_created_by(self, client, sample_ruleset_data):
        """Test activating without created_by."""
        # Create a ruleset
        create_response = client.post(
            '/api/v1/rulesets',
            data=json.dumps(sample_ruleset_data),
            content_type='application/json'
        )
        ruleset_id = json.loads(create_response.data)['id']

        # Try to activate without created_by
        response = client.post(
            f'/api/v1/rulesets/{ruleset_id}/activate',
            data=json.dumps({}),
            content_type='application/json'
        )
        assert response.status_code == 400


class TestRulesEndpoint:
    """Tests for the rules management endpoint."""

    def test_add_rules_to_ruleset(self, client, sample_ruleset_data, sample_rules_list):
        """Test adding rules to a draft ruleset."""
        # Create a ruleset
        create_response = client.post(
            '/api/v1/rulesets',
            data=json.dumps(sample_ruleset_data),
            content_type='application/json'
        )
        ruleset_id = json.loads(create_response.data)['id']

        # Add rules
        response = client.post(
            f'/api/v1/rulesets/{ruleset_id}/rules',
            data=json.dumps(sample_rules_list),
            content_type='application/json'
        )
        assert response.status_code == 201
        data = json.loads(response.data)
        assert '2 rules added' in data['message']

    def test_add_rules_empty_list(self, client, sample_ruleset_data):
        """Test adding empty rules list."""
        # Create a ruleset
        create_response = client.post(
            '/api/v1/rulesets',
            data=json.dumps(sample_ruleset_data),
            content_type='application/json'
        )
        ruleset_id = json.loads(create_response.data)['id']

        # Try to add empty list
        response = client.post(
            f'/api/v1/rulesets/{ruleset_id}/rules',
            data=json.dumps([]),
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_add_rules_invalid_rule(self, client, sample_ruleset_data):
        """Test adding invalid rule."""
        # Create a ruleset
        create_response = client.post(
            '/api/v1/rulesets',
            data=json.dumps(sample_ruleset_data),
            content_type='application/json'
        )
        ruleset_id = json.loads(create_response.data)['id']

        # Try to add invalid rule
        response = client.post(
            f'/api/v1/rulesets/{ruleset_id}/rules',
            data=json.dumps([{'name': 'Incomplete Rule'}]),  # Missing required fields
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_add_rules_to_nonexistent_ruleset(self, client, sample_rules_list):
        """Test adding rules to non-existent ruleset."""
        response = client.post(
            '/api/v1/rulesets/550e8400-e29b-41d4-a716-446655440000/rules',
            data=json.dumps(sample_rules_list),
            content_type='application/json'
        )
        assert response.status_code == 404


class TestAuditLogEndpoint:
    """Tests for the audit log endpoint."""

    def test_get_audit_log(self, client):
        """Test getting audit log."""
        response = client.get('/api/v1/audit-log')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)

    def test_audit_log_populated_after_create(self, client, sample_ruleset_data):
        """Test audit log contains entries after operations."""
        # Create a ruleset
        client.post(
            '/api/v1/rulesets',
            data=json.dumps(sample_ruleset_data),
            content_type='application/json'
        )

        # Check audit log
        response = client.get('/api/v1/audit-log')
        data = json.loads(response.data)
        assert len(data) >= 1
        assert data[0]['action_type'] == 'CREATE_RULESET'
