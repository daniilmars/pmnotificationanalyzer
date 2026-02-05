"""Add multi-tenancy and security infrastructure tables.

Revision ID: 002_tenancy_security
Revises: 001_initial
Create Date: 2026-02-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '002_tenancy_security'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add tenancy, security, and alert tables."""

    # Multi-tenancy
    op.create_table('tenants',
        sa.Column('tenant_id', sa.Text(), primary_key=True),
        sa.Column('subdomain', sa.Text(), unique=True, nullable=False),
        sa.Column('display_name', sa.Text()),
        sa.Column('status', sa.Text(), nullable=False, server_default='active'),
        sa.Column('plan', sa.Text(), nullable=False, server_default='basic'),
        sa.Column('max_users', sa.Integer(), server_default='10'),
        sa.Column('max_notifications', sa.Integer(), server_default='5000'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('metadata', sa.Text(), server_default='{}'),
    )

    op.create_table('tenant_usage',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.Text(), sa.ForeignKey('tenants.tenant_id'), nullable=False),
        sa.Column('metric', sa.Text(), nullable=False),
        sa.Column('value', sa.Float(), nullable=False, server_default='0'),
        sa.Column('recorded_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # Security
    op.create_table('api_keys',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('key_hash', sa.Text(), nullable=False, unique=True),
        sa.Column('scopes', sa.Text(), server_default='[]'),
        sa.Column('created_by', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('expires_at', sa.DateTime()),
        sa.Column('last_used_at', sa.DateTime()),
        sa.Column('enabled', sa.Boolean(), server_default=sa.text('1')),
        sa.Column('request_count', sa.Integer(), server_default='0'),
    )

    op.create_table('security_audit_log',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('event_type', sa.Text(), nullable=False),
        sa.Column('severity', sa.Text(), nullable=False),
        sa.Column('user_id', sa.Text()),
        sa.Column('ip_address', sa.Text()),
        sa.Column('resource', sa.Text()),
        sa.Column('action', sa.Text()),
        sa.Column('details', sa.Text(), server_default='{}'),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # Alerts
    op.create_table('alert_rules',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('config', sa.Text(), nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_triggered', sa.DateTime()),
        sa.Column('trigger_count', sa.Integer(), server_default='0'),
    )

    op.create_table('subscriptions',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('config', sa.Text(), nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_table('alert_log',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('rule_id', sa.Text()),
        sa.Column('alert_type', sa.Text(), nullable=False),
        sa.Column('severity', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('message', sa.Text()),
        sa.Column('recipients', sa.Text()),
        sa.Column('triggered_at', sa.DateTime(), nullable=False),
        sa.Column('data', sa.Text()),
    )

    # Indexes
    op.create_index('idx_tenant_usage_tenant', 'tenant_usage', ['tenant_id'])
    op.create_index('idx_tenant_usage_metric', 'tenant_usage', ['metric'])
    op.create_index('idx_security_audit_event', 'security_audit_log', ['event_type'])
    op.create_index('idx_security_audit_user', 'security_audit_log', ['user_id'])
    op.create_index('idx_security_audit_ts', 'security_audit_log', ['timestamp'])
    op.create_index('idx_api_keys_hash', 'api_keys', ['key_hash'])


def downgrade() -> None:
    """Drop tenancy and security tables."""
    op.drop_table('alert_log')
    op.drop_table('subscriptions')
    op.drop_table('alert_rules')
    op.drop_table('security_audit_log')
    op.drop_table('api_keys')
    op.drop_table('tenant_usage')
    op.drop_table('tenants')
