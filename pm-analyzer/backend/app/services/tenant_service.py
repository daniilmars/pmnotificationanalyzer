"""
Multi-Tenancy Service for SAP BTP SaaS Provisioning.

Handles:
- Tenant lifecycle (provision, deprovision, update)
- Tenant-aware database schema management
- Usage metering and entitlement enforcement
- SaaS Registry callback endpoints

Tenant isolation is achieved via schema-per-tenant on PostgreSQL
and database-per-tenant on SQLite (dev mode).
"""

import os
import json
import uuid
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

from app.database import DATABASE_TYPE, get_db_connection, get_standalone_connection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class TenantStatus(Enum):
    ACTIVE = 'active'
    SUSPENDED = 'suspended'
    PROVISIONING = 'provisioning'
    DEPROVISIONING = 'deprovisioning'
    ERROR = 'error'


class SubscriptionPlan(Enum):
    TRIAL = 'trial'
    BASIC = 'basic'
    PROFESSIONAL = 'professional'
    ENTERPRISE = 'enterprise'


# Trial configuration
TRIAL_DURATION_DAYS = 14
TRIAL_FEATURES = ['analysis', 'quality_scoring', 'reliability', 'reporting', 'alerts']

PLAN_LIMITS = {
    SubscriptionPlan.TRIAL: {
        'max_users': 5,
        'max_notifications': 500,
        'features': TRIAL_FEATURES,
        'trial_duration_days': TRIAL_DURATION_DAYS,
    },
    SubscriptionPlan.BASIC: {
        'max_users': 10,
        'max_notifications': 5000,
        'features': ['analysis', 'quality_scoring'],
    },
    SubscriptionPlan.PROFESSIONAL: {
        'max_users': 50,
        'max_notifications': 25000,
        'features': ['analysis', 'quality_scoring', 'reliability', 'reporting', 'alerts'],
    },
    SubscriptionPlan.ENTERPRISE: {
        'max_users': -1,  # Unlimited
        'max_notifications': -1,  # Unlimited
        'features': ['analysis', 'quality_scoring', 'reliability', 'reporting',
                     'alerts', 'fda_compliance', 'qms_integration', 'api_access'],
    },
}


@dataclass
class Tenant:
    tenant_id: str
    subdomain: str
    display_name: str = ''
    status: str = TenantStatus.ACTIVE.value
    plan: str = SubscriptionPlan.BASIC.value
    max_users: int = 10
    max_notifications: int = 5000
    created_at: str = ''
    updated_at: str = ''
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'tenant_id': self.tenant_id,
            'subdomain': self.subdomain,
            'display_name': self.display_name,
            'status': self.status,
            'plan': self.plan,
            'max_users': self.max_users,
            'max_notifications': self.max_notifications,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'metadata': self.metadata,
        }


# ---------------------------------------------------------------------------
# Tenant Service
# ---------------------------------------------------------------------------

class TenantService:
    """Manages tenant lifecycle and operations."""

    def __init__(self):
        self._ensure_tenant_tables()

    def _ensure_tenant_tables(self):
        """Create tenant management tables if they don't exist."""
        try:
            with get_db_connection() as conn:
                if DATABASE_TYPE == 'postgresql':
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS tenants (
                            tenant_id TEXT PRIMARY KEY,
                            subdomain TEXT UNIQUE NOT NULL,
                            display_name TEXT,
                            status TEXT NOT NULL DEFAULT 'active',
                            plan TEXT NOT NULL DEFAULT 'basic',
                            max_users INTEGER DEFAULT 10,
                            max_notifications INTEGER DEFAULT 5000,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            metadata JSONB DEFAULT '{}'
                        )
                    """)
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS tenant_usage (
                            id SERIAL PRIMARY KEY,
                            tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                            metric TEXT NOT NULL,
                            value REAL NOT NULL DEFAULT 0,
                            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                else:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS tenants (
                            tenant_id TEXT PRIMARY KEY,
                            subdomain TEXT UNIQUE NOT NULL,
                            display_name TEXT,
                            status TEXT NOT NULL DEFAULT 'active',
                            plan TEXT NOT NULL DEFAULT 'basic',
                            max_users INTEGER DEFAULT 10,
                            max_notifications INTEGER DEFAULT 5000,
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                            metadata TEXT DEFAULT '{}'
                        )
                    """)
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS tenant_usage (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            tenant_id TEXT NOT NULL,
                            metric TEXT NOT NULL,
                            value REAL NOT NULL DEFAULT 0,
                            recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id)
                        )
                    """)
        except Exception as e:
            logger.warning(f"Could not ensure tenant tables: {e}")

    # ------------------------------------------------------------------
    # SaaS Registry Callbacks
    # ------------------------------------------------------------------

    def on_subscription(self, tenant_id: str, payload: Dict[str, Any]) -> Tenant:
        """
        Handle SaaS Registry subscription callback (PUT).

        Called when a customer subscribes to the application.
        Creates tenant record and provisions resources.
        """
        subdomain = payload.get('subscribedSubdomain', tenant_id)
        display_name = payload.get('subscribedTenantId', tenant_id)
        plan_name = payload.get('plan', 'basic')

        try:
            plan = SubscriptionPlan(plan_name)
        except ValueError:
            plan = SubscriptionPlan.BASIC

        limits = PLAN_LIMITS[plan]

        tenant = Tenant(
            tenant_id=tenant_id,
            subdomain=subdomain,
            display_name=display_name,
            status=TenantStatus.PROVISIONING.value,
            plan=plan.value,
            max_users=limits['max_users'],
            max_notifications=limits['max_notifications'],
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
            metadata={
                'subscribed_apps': payload.get('subscribedApps', ''),
                'callback_url': payload.get('callbackUrl', ''),
            }
        )

        # Create tenant record
        self._create_tenant(tenant)

        # Provision tenant schema (PostgreSQL) or database (SQLite)
        self._provision_tenant_resources(tenant)

        # Mark as active
        tenant.status = TenantStatus.ACTIVE.value
        self._update_tenant_status(tenant.tenant_id, TenantStatus.ACTIVE.value)

        logger.info(f"Tenant provisioned: {tenant_id} (plan: {plan.value})")
        return tenant

    def on_unsubscription(self, tenant_id: str) -> bool:
        """
        Handle SaaS Registry unsubscription callback (DELETE).

        Called when a customer unsubscribes. Marks tenant for cleanup.
        """
        self._update_tenant_status(tenant_id, TenantStatus.DEPROVISIONING.value)
        logger.info(f"Tenant marked for deprovisioning: {tenant_id}")
        return True

    def get_dependencies(self) -> List[Dict[str, str]]:
        """
        Handle SaaS Registry dependencies callback (GET).

        Returns list of dependent services the app requires.
        """
        return [
            {
                'xsappname': os.environ.get('XSAPPNAME', 'pm-notification-analyzer'),
            }
        ]

    # ------------------------------------------------------------------
    # CRUD Operations
    # ------------------------------------------------------------------

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get a tenant by ID."""
        with get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM tenants WHERE tenant_id = ?",
                (tenant_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_tenant(row)
        return None

    def list_tenants(self, status: Optional[str] = None) -> List[Tenant]:
        """List all tenants, optionally filtered by status."""
        with get_db_connection() as conn:
            if status:
                cursor = conn.execute(
                    "SELECT * FROM tenants WHERE status = ? ORDER BY created_at DESC",
                    (status,)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM tenants ORDER BY created_at DESC"
                )
            rows = cursor.fetchall()
            return [self._row_to_tenant(row) for row in rows]

    def update_tenant_plan(self, tenant_id: str, plan_name: str) -> Optional[Tenant]:
        """Update a tenant's subscription plan."""
        try:
            plan = SubscriptionPlan(plan_name)
        except ValueError:
            return None

        limits = PLAN_LIMITS[plan]

        with get_db_connection() as conn:
            conn.execute(
                """UPDATE tenants
                   SET plan = ?, max_users = ?, max_notifications = ?, updated_at = ?
                   WHERE tenant_id = ?""",
                (plan.value, limits['max_users'], limits['max_notifications'],
                 datetime.utcnow().isoformat(), tenant_id)
            )

        return self.get_tenant(tenant_id)

    def delete_tenant(self, tenant_id: str) -> bool:
        """Permanently delete a tenant and its data."""
        self._deprovision_tenant_resources(tenant_id)

        with get_db_connection() as conn:
            conn.execute("DELETE FROM tenant_usage WHERE tenant_id = ?", (tenant_id,))
            conn.execute("DELETE FROM tenants WHERE tenant_id = ?", (tenant_id,))

        logger.info(f"Tenant deleted: {tenant_id}")
        return True

    # ------------------------------------------------------------------
    # Usage Metering
    # ------------------------------------------------------------------

    def record_usage(self, tenant_id: str, metric: str, value: float = 1.0):
        """Record a usage metric for a tenant."""
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO tenant_usage (tenant_id, metric, value) VALUES (?, ?, ?)",
                (tenant_id, metric, value)
            )

    def get_usage_summary(self, tenant_id: str) -> Dict[str, Any]:
        """Get usage summary for a tenant."""
        with get_db_connection() as conn:
            cursor = conn.execute(
                """SELECT metric, SUM(value) as total, COUNT(*) as count
                   FROM tenant_usage
                   WHERE tenant_id = ?
                   GROUP BY metric""",
                (tenant_id,)
            )
            rows = cursor.fetchall()
            return {row['metric']: {'total': row['total'], 'count': row['count']} for row in rows}

    def check_entitlement(self, tenant_id: str, feature: str) -> bool:
        """Check if a tenant is entitled to use a feature."""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return False

        if tenant.status != TenantStatus.ACTIVE.value:
            return False

        try:
            plan = SubscriptionPlan(tenant.plan)
        except ValueError:
            return False

        return feature in PLAN_LIMITS[plan]['features']

    def check_usage_limit(self, tenant_id: str, metric: str) -> Dict[str, Any]:
        """Check if a tenant has exceeded usage limits."""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return {'allowed': False, 'reason': 'tenant_not_found'}

        usage = self.get_usage_summary(tenant_id)
        metric_total = usage.get(metric, {}).get('total', 0)

        limit_map = {
            'notifications_analyzed': tenant.max_notifications,
            'active_users': tenant.max_users,
        }

        limit = limit_map.get(metric, -1)
        if limit == -1:
            return {'allowed': True, 'used': metric_total, 'limit': 'unlimited'}

        return {
            'allowed': metric_total < limit,
            'used': metric_total,
            'limit': limit,
            'remaining': max(0, limit - metric_total),
        }

    # ------------------------------------------------------------------
    # Trial Management
    # ------------------------------------------------------------------

    def provision_trial(self, tenant_id: str, subdomain: str,
                        display_name: str = '', email: str = '') -> Tenant:
        """
        Provision a trial tenant with sample data.

        Creates a trial tenant with Professional-level features,
        limited quotas, and a 14-day expiration.
        """
        limits = PLAN_LIMITS[SubscriptionPlan.TRIAL]
        now = datetime.utcnow()

        tenant = Tenant(
            tenant_id=tenant_id,
            subdomain=subdomain,
            display_name=display_name or f"Trial - {subdomain}",
            status=TenantStatus.ACTIVE.value,
            plan=SubscriptionPlan.TRIAL.value,
            max_users=limits['max_users'],
            max_notifications=limits['max_notifications'],
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            metadata={
                'is_trial': True,
                'trial_started': now.isoformat(),
                'trial_expires': (now + __import__('datetime').timedelta(
                    days=TRIAL_DURATION_DAYS)).isoformat(),
                'contact_email': email,
                'demo_data_seeded': False,
            }
        )

        self._create_tenant(tenant)
        self._provision_tenant_resources(tenant)

        logger.info(f"Trial tenant provisioned: {tenant_id} (expires in {TRIAL_DURATION_DAYS} days)")
        return tenant

    def check_trial_expiration(self, tenant_id: str) -> Dict[str, Any]:
        """
        Check if a trial tenant has expired.

        Returns:
            Dict with 'expired', 'days_remaining', 'expires_at' keys
        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return {'expired': True, 'reason': 'tenant_not_found'}

        if tenant.plan != SubscriptionPlan.TRIAL.value:
            return {'expired': False, 'is_trial': False}

        expires_str = tenant.metadata.get('trial_expires')
        if not expires_str:
            return {'expired': True, 'reason': 'no_expiration_date'}

        try:
            expires = datetime.fromisoformat(expires_str)
        except (ValueError, TypeError):
            return {'expired': True, 'reason': 'invalid_expiration_date'}

        now = datetime.utcnow()
        if now >= expires:
            # Auto-suspend expired trial
            if tenant.status == TenantStatus.ACTIVE.value:
                self._update_tenant_status(tenant_id, TenantStatus.SUSPENDED.value)
                logger.info(f"Trial expired and suspended: {tenant_id}")
            return {
                'expired': True,
                'is_trial': True,
                'expires_at': expires_str,
                'days_remaining': 0,
            }

        remaining = (expires - now).days
        return {
            'expired': False,
            'is_trial': True,
            'expires_at': expires_str,
            'days_remaining': remaining,
        }

    def convert_trial_to_paid(self, tenant_id: str, plan_name: str) -> Optional[Tenant]:
        """
        Convert a trial tenant to a paid subscription plan.

        Args:
            tenant_id: The trial tenant ID
            plan_name: Target plan ('basic', 'professional', or 'enterprise')

        Returns:
            Updated Tenant object or None if conversion fails
        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return None

        if tenant.plan != SubscriptionPlan.TRIAL.value:
            logger.warning(f"Tenant {tenant_id} is not a trial (plan: {tenant.plan})")
            return None

        try:
            target_plan = SubscriptionPlan(plan_name)
        except ValueError:
            return None

        if target_plan == SubscriptionPlan.TRIAL:
            return None

        limits = PLAN_LIMITS[target_plan]

        with get_db_connection() as conn:
            # Update plan and limits
            conn.execute(
                """UPDATE tenants
                   SET plan = ?, max_users = ?, max_notifications = ?,
                       status = ?, updated_at = ?,
                       metadata = ?
                   WHERE tenant_id = ?""",
                (target_plan.value, limits['max_users'], limits['max_notifications'],
                 TenantStatus.ACTIVE.value, datetime.utcnow().isoformat(),
                 json.dumps({
                     **tenant.metadata,
                     'is_trial': False,
                     'converted_from_trial': True,
                     'converted_at': datetime.utcnow().isoformat(),
                     'previous_plan': 'trial',
                 }),
                 tenant_id)
            )

        logger.info(f"Trial converted to {plan_name}: {tenant_id}")
        return self.get_tenant(tenant_id)

    def seed_demo_data(self, tenant_id: str) -> Dict[str, Any]:
        """
        Seed sample notification data for a trial/demo tenant.

        Returns:
            Summary of seeded data
        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return {'error': 'tenant_not_found'}

        seeded = {
            'notifications': 0,
            'equipment': 0,
            'work_orders': 0,
        }

        try:
            with get_db_connection() as conn:
                # Check if demo data already exists
                cursor = conn.execute(
                    "SELECT COUNT(*) as cnt FROM QMEL WHERE QMNUM LIKE 'DEMO%'"
                )
                row = cursor.fetchone()
                if row and row['cnt'] > 0:
                    return {'status': 'already_seeded', 'count': row['cnt']}

                # Seed sample notifications
                demo_notifications = [
                    ('DEMO000001', 'M1', '10', 'Pump P-101 bearing failure - unusual vibration detected',
                     'PLANT-A', 'PUMP-101', 'E001', 'DEMO_USER', '20260101', '2', 'MSPT', 'OSNO'),
                    ('DEMO000002', 'M2', '20', 'Conveyor belt CV-203 preventive maintenance due',
                     'PLANT-A', 'CONV-203', 'E002', 'DEMO_USER', '20260115', '3', 'MSPT', 'OSNO'),
                    ('DEMO000003', 'M1', '30', 'Compressor C-401 high temperature alarm triggered',
                     'PLANT-B', 'COMP-401', 'E003', 'DEMO_USER', '20260120', '1', 'MSPT', 'OSNO'),
                    ('DEMO000004', 'M3', '20', 'Valve V-305 inspection request per quarterly schedule',
                     'PLANT-A', 'VALV-305', 'E004', 'DEMO_USER', '20260125', '4', 'MSPT', 'OSNO'),
                    ('DEMO000005', 'M2', '10', 'Motor M-102 scheduled rewinding after 25000 hours',
                     'PLANT-B', 'MOTR-102', 'E005', 'DEMO_USER', '20260130', '2', 'MSPT', 'OSNO'),
                    ('DEMO000006', 'M1', '30', 'Heat exchanger HX-201 tube leak detected during rounds',
                     'PLANT-A', 'HTEX-201', 'E006', 'DEMO_USER', '20260201', '1', 'MSPT', 'OSNO'),
                    ('DEMO000007', 'M2', '20', 'Agitator AG-502 gearbox oil change per PM schedule',
                     'PLANT-B', 'AGIT-502', 'E007', 'DEMO_USER', '20260202', '3', 'MSPT', 'OSNO'),
                    ('DEMO000008', 'M1', '10', 'Filter press FP-103 hydraulic pressure drop',
                     'PLANT-A', 'FLTR-103', 'E008', 'DEMO_USER', '20260203', '2', 'MSPT', 'OSNO'),
                    ('DEMO000009', 'M3', '20', 'Safety valve SV-701 annual certification due',
                     'PLANT-B', 'SFVL-701', 'E009', 'DEMO_USER', '20260204', '1', 'MSPT', 'OSNO'),
                    ('DEMO000010', 'M2', '30', 'Centrifuge CF-301 vibration analysis routine check',
                     'PLANT-A', 'CENT-301', 'E010', 'DEMO_USER', '20260205', '3', 'MSPT', 'OSNO'),
                ]

                for notif in demo_notifications:
                    try:
                        conn.execute(
                            """INSERT INTO QMEL
                               (QMNUM, QMART, QMGRP, QMTXT, SWERK, EQUNR, TPLNR,
                                QMNAM, ERDAT, PRIESSION, MESSION, QMSTAT)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            notif
                        )
                        seeded['notifications'] += 1
                    except Exception:
                        pass  # Skip if already exists

            # Update tenant metadata
            if tenant.metadata:
                tenant.metadata['demo_data_seeded'] = True
                tenant.metadata['demo_data_seeded_at'] = datetime.utcnow().isoformat()
                with get_db_connection() as conn:
                    conn.execute(
                        "UPDATE tenants SET metadata = ? WHERE tenant_id = ?",
                        (json.dumps(tenant.metadata), tenant_id)
                    )

        except Exception as e:
            logger.error(f"Error seeding demo data for tenant {tenant_id}: {e}")
            return {'error': str(e)}

        seeded['status'] = 'seeded'
        logger.info(f"Demo data seeded for tenant {tenant_id}: {seeded}")
        return seeded

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _create_tenant(self, tenant: Tenant):
        """Insert tenant record into database."""
        with get_db_connection() as conn:
            conn.execute(
                """INSERT INTO tenants
                   (tenant_id, subdomain, display_name, status, plan,
                    max_users, max_notifications, created_at, updated_at, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (tenant.tenant_id, tenant.subdomain, tenant.display_name,
                 tenant.status, tenant.plan, tenant.max_users,
                 tenant.max_notifications, tenant.created_at, tenant.updated_at,
                 json.dumps(tenant.metadata))
            )

    def _update_tenant_status(self, tenant_id: str, status: str):
        """Update tenant status."""
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE tenants SET status = ?, updated_at = ? WHERE tenant_id = ?",
                (status, datetime.utcnow().isoformat(), tenant_id)
            )

    def _provision_tenant_resources(self, tenant: Tenant):
        """Provision tenant-specific database resources."""
        if DATABASE_TYPE == 'postgresql':
            schema_name = f"tenant_{tenant.tenant_id.replace('-', '_')}"
            try:
                with get_db_connection() as conn:
                    # Create tenant schema
                    conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
                    logger.info(f"Created schema: {schema_name}")
            except Exception as e:
                logger.error(f"Failed to provision tenant schema: {e}")
                raise
        else:
            logger.info(f"SQLite dev mode: tenant {tenant.tenant_id} uses shared database")

    def _deprovision_tenant_resources(self, tenant_id: str):
        """Remove tenant-specific database resources."""
        if DATABASE_TYPE == 'postgresql':
            schema_name = f"tenant_{tenant_id.replace('-', '_')}"
            try:
                with get_db_connection() as conn:
                    conn.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
                    logger.info(f"Dropped schema: {schema_name}")
            except Exception as e:
                logger.error(f"Failed to deprovision tenant schema: {e}")
        else:
            logger.info(f"SQLite dev mode: no resources to deprovision for {tenant_id}")

    def _row_to_tenant(self, row) -> Tenant:
        """Convert database row to Tenant object."""
        metadata = row.get('metadata', '{}') if hasattr(row, 'get') else (row['metadata'] or '{}')
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}

        return Tenant(
            tenant_id=row['tenant_id'],
            subdomain=row['subdomain'],
            display_name=row['display_name'] or '',
            status=row['status'],
            plan=row['plan'],
            max_users=row['max_users'],
            max_notifications=row['max_notifications'],
            created_at=str(row['created_at'] or ''),
            updated_at=str(row['updated_at'] or ''),
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_tenant_service: Optional[TenantService] = None


def get_tenant_service() -> TenantService:
    """Get or create the tenant service singleton."""
    global _tenant_service
    if _tenant_service is None:
        _tenant_service = TenantService()
    return _tenant_service
