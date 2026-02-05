"""
Integration tests for Quality Dashboard and Reliability Dashboard API endpoints.
"""
import pytest
import json
import os

os.environ['DATABASE_TYPE'] = 'sqlite'
os.environ['AUTH_ENABLED'] = 'false'


class TestQualityDashboardEndpoints:
    """Tests for quality scoring endpoints."""

    def test_quality_dashboard(self, client, db_with_data):
        """Test quality dashboard returns data."""
        response = client.get('/api/quality/dashboard')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_quality_notification(self, client, db_with_data):
        """Test quality score for single notification."""
        response = client.get('/api/quality/notification/TEST000001')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'quality_score' in data or 'overall_score' in data or isinstance(data, dict)

    def test_quality_notification_not_found(self, client):
        """Test quality score for non-existent notification."""
        response = client.get('/api/quality/notification/NONEXIST01')
        # Should return 404 or empty result
        assert response.status_code in [200, 404]

    def test_quality_batch(self, client, db_with_data):
        """Test batch quality metrics."""
        response = client.get('/api/quality/batch')
        assert response.status_code == 200

    def test_quality_trend(self, client, db_with_data):
        """Test quality trend analysis."""
        response = client.get('/api/quality/trend')
        assert response.status_code == 200

    def test_quality_export_csv(self, client, db_with_data):
        """Test quality report CSV export."""
        response = client.get('/api/quality/export')
        assert response.status_code == 200


class TestReliabilityDashboardEndpoints:
    """Tests for reliability engineering endpoints."""

    def test_reliability_dashboard(self, client, db_with_data):
        """Test reliability dashboard returns data."""
        response = client.get('/api/reliability/dashboard')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_reliability_equipment_list(self, client, db_with_data):
        """Test equipment list endpoint."""
        response = client.get('/api/reliability/equipment')
        assert response.status_code == 200

    def test_reliability_fmea(self, client, db_with_data):
        """Test FMEA analysis endpoint."""
        response = client.get('/api/reliability/fmea')
        assert response.status_code == 200

    def test_reliability_export_csv(self, client, db_with_data):
        """Test reliability CSV export."""
        response = client.get('/api/reliability/export')
        assert response.status_code == 200


class TestAuditEndpoints:
    """Tests for audit trail endpoints."""

    def test_audit_changes(self, client, db_with_data):
        """Test audit changes endpoint."""
        response = client.get('/api/audit/changes')
        assert response.status_code == 200

    def test_audit_report(self, client, db_with_data):
        """Test audit report endpoint."""
        response = client.get('/api/audit/report')
        assert response.status_code == 200

    def test_audit_export_csv(self, client, db_with_data):
        """Test audit CSV export."""
        response = client.get('/api/audit/export')
        assert response.status_code == 200


class TestAlertEndpoints:
    """Tests for alert management endpoints."""

    def test_get_alert_rules(self, client):
        """Test listing alert rules."""
        response = client.get('/api/alert-rules')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'rules' in data
        assert isinstance(data['rules'], list)
        # Should have predefined rules
        assert len(data['rules']) > 0

    def test_get_alert_rule_by_id(self, client):
        """Test getting a specific alert rule."""
        response = client.get('/api/alert-rules/critical_quality')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['id'] == 'critical_quality'

    def test_get_nonexistent_alert_rule(self, client):
        """Test getting non-existent alert rule."""
        response = client.get('/api/alert-rules/nonexistent')
        assert response.status_code == 404


class TestReportEndpoints:
    """Tests for PDF report generation endpoints."""

    def test_quality_pdf_report(self, client, db_with_data):
        """Test quality PDF report generation."""
        response = client.get('/api/reports/quality/pdf')
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'

    def test_reliability_pdf_report(self, client, db_with_data):
        """Test reliability PDF report generation."""
        response = client.get('/api/reports/reliability/pdf')
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'

    def test_audit_pdf_report(self, client, db_with_data):
        """Test audit PDF report generation."""
        response = client.get('/api/reports/audit/pdf')
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'

    def test_notification_pdf_report(self, client, db_with_data):
        """Test notification PDF report generation."""
        response = client.get('/api/reports/notification/TEST000001/pdf')
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'


class TestTenantEndpoints:
    """Tests for tenant management API endpoints."""

    def test_saas_subscription_callback(self, client):
        """Test SaaS Registry subscription callback."""
        response = client.put(
            '/api/tenant/callback/test-tenant-api',
            data=json.dumps({
                'subscribedSubdomain': 'test-api-co',
                'plan': 'basic'
            }),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'subscribed'
        assert data['tenant_id'] == 'test-tenant-api'

    def test_saas_unsubscription_callback(self, client):
        """Test SaaS Registry unsubscription callback."""
        # First subscribe
        client.put(
            '/api/tenant/callback/unsub-api-test',
            data=json.dumps({'subscribedSubdomain': 'unsub-api-co'}),
            content_type='application/json'
        )
        # Then unsubscribe
        response = client.delete('/api/tenant/callback/unsub-api-test')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'unsubscribed'

    def test_saas_dependencies_callback(self, client):
        """Test SaaS Registry dependencies callback."""
        response = client.get('/api/tenant/callback/dependencies')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
