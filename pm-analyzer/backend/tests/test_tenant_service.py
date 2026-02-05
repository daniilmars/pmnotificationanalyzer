"""
Unit tests for the multi-tenancy service.
"""
import pytest
import os
import json

os.environ['DATABASE_TYPE'] = 'sqlite'
os.environ['AUTH_ENABLED'] = 'false'


class TestTenantService:
    """Tests for TenantService."""

    def test_create_and_get_tenant(self, app):
        """Test creating and retrieving a tenant."""
        with app.app_context():
            from app.services.tenant_service import get_tenant_service
            service = get_tenant_service()

            tenant = service.on_subscription('test-tenant-001', {
                'subscribedSubdomain': 'acme-corp',
                'plan': 'basic'
            })

            assert tenant.tenant_id == 'test-tenant-001'
            assert tenant.subdomain == 'acme-corp'
            assert tenant.status == 'active'
            assert tenant.plan == 'basic'

            # Retrieve
            retrieved = service.get_tenant('test-tenant-001')
            assert retrieved is not None
            assert retrieved.tenant_id == 'test-tenant-001'

    def test_list_tenants(self, app):
        """Test listing all tenants."""
        with app.app_context():
            from app.services.tenant_service import get_tenant_service
            service = get_tenant_service()

            service.on_subscription('list-test-001', {
                'subscribedSubdomain': 'company-a',
                'plan': 'basic'
            })
            service.on_subscription('list-test-002', {
                'subscribedSubdomain': 'company-b',
                'plan': 'professional'
            })

            tenants = service.list_tenants()
            ids = [t.tenant_id for t in tenants]
            assert 'list-test-001' in ids
            assert 'list-test-002' in ids

    def test_list_tenants_by_status(self, app):
        """Test filtering tenants by status."""
        with app.app_context():
            from app.services.tenant_service import get_tenant_service
            service = get_tenant_service()

            service.on_subscription('status-test-001', {
                'subscribedSubdomain': 'active-co',
                'plan': 'basic'
            })

            active = service.list_tenants(status='active')
            assert any(t.tenant_id == 'status-test-001' for t in active)

            suspended = service.list_tenants(status='suspended')
            assert not any(t.tenant_id == 'status-test-001' for t in suspended)

    def test_update_tenant_plan(self, app):
        """Test updating a tenant's plan."""
        with app.app_context():
            from app.services.tenant_service import get_tenant_service
            service = get_tenant_service()

            service.on_subscription('plan-test-001', {
                'subscribedSubdomain': 'upgrade-co',
                'plan': 'basic'
            })

            updated = service.update_tenant_plan('plan-test-001', 'enterprise')
            assert updated is not None
            assert updated.plan == 'enterprise'
            assert updated.max_users == -1  # Unlimited

    def test_update_tenant_invalid_plan(self, app):
        """Test updating with invalid plan returns None."""
        with app.app_context():
            from app.services.tenant_service import get_tenant_service
            service = get_tenant_service()

            service.on_subscription('bad-plan-001', {
                'subscribedSubdomain': 'bad-plan-co'
            })

            result = service.update_tenant_plan('bad-plan-001', 'nonexistent')
            assert result is None

    def test_unsubscription(self, app):
        """Test tenant unsubscription."""
        with app.app_context():
            from app.services.tenant_service import get_tenant_service
            service = get_tenant_service()

            service.on_subscription('unsub-test-001', {
                'subscribedSubdomain': 'leaving-co'
            })

            result = service.on_unsubscription('unsub-test-001')
            assert result is True

            tenant = service.get_tenant('unsub-test-001')
            assert tenant.status == 'deprovisioning'

    def test_get_nonexistent_tenant(self, app):
        """Test getting a tenant that doesn't exist."""
        with app.app_context():
            from app.services.tenant_service import get_tenant_service
            service = get_tenant_service()

            result = service.get_tenant('does-not-exist')
            assert result is None

    def test_get_dependencies(self, app):
        """Test SaaS Registry dependencies callback."""
        with app.app_context():
            from app.services.tenant_service import get_tenant_service
            service = get_tenant_service()

            deps = service.get_dependencies()
            assert isinstance(deps, list)
            assert len(deps) > 0
            assert 'xsappname' in deps[0]

    def test_tenant_to_dict(self, app):
        """Test tenant serialization."""
        with app.app_context():
            from app.services.tenant_service import get_tenant_service
            service = get_tenant_service()

            service.on_subscription('dict-test-001', {
                'subscribedSubdomain': 'dict-co',
                'plan': 'professional'
            })

            tenant = service.get_tenant('dict-test-001')
            d = tenant.to_dict()
            assert d['tenant_id'] == 'dict-test-001'
            assert d['subdomain'] == 'dict-co'
            assert d['plan'] == 'professional'
            assert 'created_at' in d


class TestUsageMetering:
    """Tests for usage metering and entitlements."""

    def test_record_and_get_usage(self, app):
        """Test recording and retrieving usage metrics."""
        with app.app_context():
            from app.services.tenant_service import get_tenant_service
            service = get_tenant_service()

            service.on_subscription('usage-test-001', {
                'subscribedSubdomain': 'usage-co',
                'plan': 'basic'
            })

            service.record_usage('usage-test-001', 'notifications_analyzed', 5)
            service.record_usage('usage-test-001', 'notifications_analyzed', 3)
            service.record_usage('usage-test-001', 'api_calls', 10)

            usage = service.get_usage_summary('usage-test-001')
            assert 'notifications_analyzed' in usage
            assert usage['notifications_analyzed']['total'] == 8
            assert 'api_calls' in usage

    def test_check_entitlement_basic(self, app):
        """Test feature entitlement for basic plan."""
        with app.app_context():
            from app.services.tenant_service import get_tenant_service
            service = get_tenant_service()

            service.on_subscription('entitle-basic', {
                'subscribedSubdomain': 'basic-co',
                'plan': 'basic'
            })

            assert service.check_entitlement('entitle-basic', 'analysis') is True
            assert service.check_entitlement('entitle-basic', 'quality_scoring') is True
            assert service.check_entitlement('entitle-basic', 'fda_compliance') is False
            assert service.check_entitlement('entitle-basic', 'qms_integration') is False

    def test_check_entitlement_enterprise(self, app):
        """Test feature entitlement for enterprise plan."""
        with app.app_context():
            from app.services.tenant_service import get_tenant_service
            service = get_tenant_service()

            service.on_subscription('entitle-enterprise', {
                'subscribedSubdomain': 'enterprise-co',
                'plan': 'enterprise'
            })

            assert service.check_entitlement('entitle-enterprise', 'analysis') is True
            assert service.check_entitlement('entitle-enterprise', 'fda_compliance') is True
            assert service.check_entitlement('entitle-enterprise', 'qms_integration') is True
            assert service.check_entitlement('entitle-enterprise', 'api_access') is True

    def test_check_entitlement_nonexistent_tenant(self, app):
        """Test entitlement check for non-existent tenant."""
        with app.app_context():
            from app.services.tenant_service import get_tenant_service
            service = get_tenant_service()
            assert service.check_entitlement('nonexistent', 'analysis') is False

    def test_check_usage_limit(self, app):
        """Test usage limit checking."""
        with app.app_context():
            from app.services.tenant_service import get_tenant_service
            service = get_tenant_service()

            service.on_subscription('limit-test', {
                'subscribedSubdomain': 'limit-co',
                'plan': 'basic'  # max 5000 notifications
            })

            service.record_usage('limit-test', 'notifications_analyzed', 100)

            result = service.check_usage_limit('limit-test', 'notifications_analyzed')
            assert result['allowed'] is True
            assert result['used'] == 100
            assert result['limit'] == 5000
            assert result['remaining'] == 4900


class TestPlanLimits:
    """Tests for subscription plan definitions."""

    def test_plan_limits_structure(self):
        """Test PLAN_LIMITS has correct structure."""
        from app.services.tenant_service import PLAN_LIMITS, SubscriptionPlan

        for plan in SubscriptionPlan:
            assert plan in PLAN_LIMITS
            limits = PLAN_LIMITS[plan]
            assert 'max_users' in limits
            assert 'max_notifications' in limits
            assert 'features' in limits
            assert isinstance(limits['features'], list)

    def test_enterprise_unlimited(self):
        """Test enterprise plan has unlimited values."""
        from app.services.tenant_service import PLAN_LIMITS, SubscriptionPlan

        enterprise = PLAN_LIMITS[SubscriptionPlan.ENTERPRISE]
        assert enterprise['max_users'] == -1
        assert enterprise['max_notifications'] == -1

    def test_plan_feature_hierarchy(self):
        """Test that higher plans include more features."""
        from app.services.tenant_service import PLAN_LIMITS, SubscriptionPlan

        basic = set(PLAN_LIMITS[SubscriptionPlan.BASIC]['features'])
        pro = set(PLAN_LIMITS[SubscriptionPlan.PROFESSIONAL]['features'])
        enterprise = set(PLAN_LIMITS[SubscriptionPlan.ENTERPRISE]['features'])

        assert basic.issubset(pro)
        assert pro.issubset(enterprise)
