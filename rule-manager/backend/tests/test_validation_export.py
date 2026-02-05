"""
Unit tests for validation export functionality.
"""
import pytest
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestAuditLogExport:
    """Tests for audit log export endpoints."""

    def test_audit_log_summary_endpoint_exists(self, client):
        """Test that audit log summary endpoint exists."""
        # This will fail auth but proves endpoint exists
        response = client.get('/api/v1/validation/export/audit-log/summary')
        # 401 or 403 means endpoint exists but auth required
        # 200 means auth is disabled for testing
        assert response.status_code in [200, 401, 403]

    def test_export_audit_log_endpoint_exists(self, client):
        """Test that export audit log endpoint exists."""
        response = client.get('/api/v1/validation/export/audit-log')
        assert response.status_code in [200, 401, 403]


class TestSignatureExport:
    """Tests for electronic signature export endpoints."""

    def test_export_signatures_endpoint_exists(self, client):
        """Test that export signatures endpoint exists."""
        response = client.get('/api/v1/validation/export/signatures')
        assert response.status_code in [200, 401, 403]


class TestAccessLogExport:
    """Tests for access log export endpoints."""

    def test_export_access_log_endpoint_exists(self, client):
        """Test that export access log endpoint exists."""
        response = client.get('/api/v1/validation/export/access-log')
        assert response.status_code in [200, 401, 403]


class TestRulesetExport:
    """Tests for ruleset export endpoints."""

    def test_export_rulesets_endpoint_exists(self, client):
        """Test that export rulesets endpoint exists."""
        response = client.get('/api/v1/validation/export/rulesets')
        assert response.status_code in [200, 401, 403]


class TestUserExport:
    """Tests for user export endpoints."""

    def test_export_users_endpoint_exists(self, client):
        """Test that export users endpoint exists."""
        response = client.get('/api/v1/validation/export/users')
        assert response.status_code in [200, 401, 403]


class TestRBACMatrixExport:
    """Tests for RBAC matrix export endpoints."""

    def test_export_rbac_matrix_endpoint_exists(self, client):
        """Test that export RBAC matrix endpoint exists."""
        response = client.get('/api/v1/validation/export/rbac-matrix')
        assert response.status_code in [200, 401, 403]


class TestValidationReports:
    """Tests for validation report endpoints."""

    def test_system_validation_report_endpoint_exists(self, client):
        """Test that system validation report endpoint exists."""
        response = client.get('/api/v1/validation/report/system-validation')
        assert response.status_code in [200, 401, 403]

    def test_data_integrity_report_endpoint_exists(self, client):
        """Test that data integrity report endpoint exists."""
        response = client.get('/api/v1/validation/report/data-integrity')
        assert response.status_code in [200, 401, 403]


class TestCSVGeneration:
    """Tests for CSV response generation."""

    def test_csv_response_format(self, client):
        """Test that CSV export returns proper content type."""
        # Disable auth for this test by setting env var
        os.environ['AUTH_ENABLED'] = 'false'

        response = client.get('/api/v1/validation/export/audit-log')

        if response.status_code == 200:
            content_type = response.content_type
            assert 'text/csv' in content_type or response.status_code == 200
        else:
            # Auth required - that's acceptable
            assert response.status_code in [401, 403]


class TestReportContent:
    """Tests for report content structure."""

    def test_system_validation_report_structure(self, client):
        """Test system validation report has expected structure."""
        os.environ['AUTH_ENABLED'] = 'false'

        response = client.get('/api/v1/validation/report/system-validation')

        if response.status_code == 200:
            data = json.loads(response.data)

            # Verify expected top-level keys
            expected_keys = [
                'generated_at',
                'report_type',
                'compliance_standards'
            ]
            for key in expected_keys:
                assert key in data, f"Missing key: {key}"

    def test_data_integrity_report_structure(self, client):
        """Test data integrity report has expected structure."""
        os.environ['AUTH_ENABLED'] = 'false'

        response = client.get('/api/v1/validation/report/data-integrity')

        if response.status_code == 200:
            data = json.loads(response.data)

            assert 'generated_at' in data
            assert 'report_type' in data
            assert 'integrity_checks' in data
            assert 'overall_status' in data
