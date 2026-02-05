"""
Onboarding Service for PM Notification Analyzer.

Provides a guided setup experience for new tenants:
1. System connectivity check (SAP destination)
2. AI configuration (Google Gemini API key)
3. User role assignment verification
4. Sample data validation
5. First analysis run

Tracks onboarding progress per tenant so users can resume where they left off.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

from app.database import get_db_connection, DATABASE_TYPE

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Onboarding Steps Definition
# ---------------------------------------------------------------------------

ONBOARDING_STEPS = [
    {
        'id': 'welcome',
        'title': 'Welcome',
        'description': 'Welcome to PM Notification Analyzer',
        'required': True,
        'order': 1,
    },
    {
        'id': 'sap_connection',
        'title': 'SAP System Connection',
        'description': 'Configure and verify the connection to your SAP PM/EAM system',
        'required': True,
        'order': 2,
        'validation': 'check_sap_connection',
    },
    {
        'id': 'ai_configuration',
        'title': 'AI Configuration',
        'description': 'Set up the Google Gemini API key for AI-powered analysis',
        'required': True,
        'order': 3,
        'validation': 'check_ai_configuration',
    },
    {
        'id': 'user_roles',
        'title': 'User Roles',
        'description': 'Verify role collections are assigned to users',
        'required': True,
        'order': 4,
        'validation': 'check_user_roles',
    },
    {
        'id': 'data_import',
        'title': 'Data Import',
        'description': 'Import or verify notification data from SAP',
        'required': False,
        'order': 5,
        'validation': 'check_data_available',
    },
    {
        'id': 'first_analysis',
        'title': 'First Analysis',
        'description': 'Run your first AI-powered notification analysis',
        'required': False,
        'order': 6,
    },
    {
        'id': 'complete',
        'title': 'Setup Complete',
        'description': 'Your PM Notification Analyzer is ready to use',
        'required': True,
        'order': 7,
    },
]


@dataclass
class OnboardingState:
    tenant_id: str
    current_step: str = 'welcome'
    completed_steps: List[str] = field(default_factory=list)
    skipped_steps: List[str] = field(default_factory=list)
    started_at: str = ''
    completed_at: str = ''
    is_complete: bool = False
    step_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        total_steps = len(ONBOARDING_STEPS)
        done = len(self.completed_steps) + len(self.skipped_steps)
        return {
            'tenant_id': self.tenant_id,
            'current_step': self.current_step,
            'completed_steps': self.completed_steps,
            'skipped_steps': self.skipped_steps,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'is_complete': self.is_complete,
            'progress_percent': round((done / total_steps) * 100) if total_steps > 0 else 0,
            'steps': self._build_step_list(),
            'step_data': self.step_data,
        }

    def _build_step_list(self) -> List[Dict[str, Any]]:
        steps = []
        for step_def in ONBOARDING_STEPS:
            sid = step_def['id']
            status = 'pending'
            if sid in self.completed_steps:
                status = 'completed'
            elif sid in self.skipped_steps:
                status = 'skipped'
            elif sid == self.current_step:
                status = 'current'

            steps.append({
                'id': sid,
                'title': step_def['title'],
                'description': step_def['description'],
                'required': step_def['required'],
                'status': status,
                'order': step_def['order'],
            })
        return steps


# ---------------------------------------------------------------------------
# Onboarding Service
# ---------------------------------------------------------------------------

class OnboardingService:
    """Manages the onboarding workflow for new tenants."""

    def __init__(self):
        self._ensure_onboarding_table()

    def _ensure_onboarding_table(self):
        """Create onboarding state table if it doesn't exist."""
        try:
            with get_db_connection() as conn:
                if DATABASE_TYPE == 'postgresql':
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS onboarding_state (
                            tenant_id TEXT PRIMARY KEY,
                            current_step TEXT NOT NULL DEFAULT 'welcome',
                            completed_steps JSONB DEFAULT '[]',
                            skipped_steps JSONB DEFAULT '[]',
                            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            completed_at TIMESTAMP,
                            is_complete BOOLEAN DEFAULT FALSE,
                            step_data JSONB DEFAULT '{}'
                        )
                    """)
                else:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS onboarding_state (
                            tenant_id TEXT PRIMARY KEY,
                            current_step TEXT NOT NULL DEFAULT 'welcome',
                            completed_steps TEXT DEFAULT '[]',
                            skipped_steps TEXT DEFAULT '[]',
                            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                            completed_at TEXT,
                            is_complete INTEGER DEFAULT 0,
                            step_data TEXT DEFAULT '{}'
                        )
                    """)
        except Exception as e:
            logger.warning(f"Could not ensure onboarding table: {e}")

    def get_onboarding_state(self, tenant_id: str) -> OnboardingState:
        """Get or create onboarding state for a tenant."""
        with get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM onboarding_state WHERE tenant_id = ?",
                (tenant_id,)
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_state(row)

            # Create new onboarding state
            now = datetime.utcnow().isoformat()
            conn.execute(
                """INSERT INTO onboarding_state
                   (tenant_id, current_step, completed_steps, skipped_steps,
                    started_at, step_data)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (tenant_id, 'welcome', '[]', '[]', now, '{}')
            )

            return OnboardingState(
                tenant_id=tenant_id,
                current_step='welcome',
                started_at=now,
            )

    def complete_step(self, tenant_id: str, step_id: str,
                      step_data: Optional[Dict[str, Any]] = None) -> OnboardingState:
        """Mark an onboarding step as completed and advance to next."""
        state = self.get_onboarding_state(tenant_id)

        # Validate step exists
        step_ids = [s['id'] for s in ONBOARDING_STEPS]
        if step_id not in step_ids:
            raise ValueError(f"Unknown step: {step_id}")

        # Mark as completed
        if step_id not in state.completed_steps:
            state.completed_steps.append(step_id)

        # Store step data if provided
        if step_data:
            state.step_data[step_id] = step_data

        # Advance to next step
        current_order = next(
            (s['order'] for s in ONBOARDING_STEPS if s['id'] == step_id), 0
        )
        next_step = None
        for s in sorted(ONBOARDING_STEPS, key=lambda x: x['order']):
            if s['order'] > current_order and s['id'] not in state.completed_steps \
                    and s['id'] not in state.skipped_steps:
                next_step = s['id']
                break

        if next_step:
            state.current_step = next_step
        else:
            state.current_step = 'complete'
            state.is_complete = True
            state.completed_at = datetime.utcnow().isoformat()
            if 'complete' not in state.completed_steps:
                state.completed_steps.append('complete')

        self._save_state(state)
        return state

    def skip_step(self, tenant_id: str, step_id: str) -> OnboardingState:
        """Skip an optional onboarding step."""
        # Validate step is optional
        step_def = next((s for s in ONBOARDING_STEPS if s['id'] == step_id), None)
        if not step_def:
            raise ValueError(f"Unknown step: {step_id}")
        if step_def.get('required', True):
            raise ValueError(f"Cannot skip required step: {step_id}")

        state = self.get_onboarding_state(tenant_id)

        if step_id not in state.skipped_steps:
            state.skipped_steps.append(step_id)

        # Advance to next step
        current_order = step_def['order']
        next_step = None
        for s in sorted(ONBOARDING_STEPS, key=lambda x: x['order']):
            if s['order'] > current_order and s['id'] not in state.completed_steps \
                    and s['id'] not in state.skipped_steps:
                next_step = s['id']
                break

        if next_step:
            state.current_step = next_step
        else:
            state.current_step = 'complete'
            state.is_complete = True
            state.completed_at = datetime.utcnow().isoformat()
            if 'complete' not in state.completed_steps:
                state.completed_steps.append('complete')

        self._save_state(state)
        return state

    def reset_onboarding(self, tenant_id: str) -> OnboardingState:
        """Reset onboarding state for a tenant."""
        with get_db_connection() as conn:
            conn.execute("DELETE FROM onboarding_state WHERE tenant_id = ?", (tenant_id,))
        return self.get_onboarding_state(tenant_id)

    # ------------------------------------------------------------------
    # Validation Checks
    # ------------------------------------------------------------------

    def validate_step(self, tenant_id: str, step_id: str) -> Dict[str, Any]:
        """
        Run validation for a specific onboarding step.

        Returns:
            Dict with 'valid', 'message', and optional 'details'
        """
        validators = {
            'sap_connection': self._check_sap_connection,
            'ai_configuration': self._check_ai_configuration,
            'user_roles': self._check_user_roles,
            'data_import': self._check_data_available,
        }

        validator = validators.get(step_id)
        if not validator:
            return {'valid': True, 'message': 'No validation required for this step'}

        return validator(tenant_id)

    def _check_sap_connection(self, tenant_id: str) -> Dict[str, Any]:
        """Validate SAP system connectivity."""
        sap_enabled = os.environ.get('SAP_ENABLED', 'false').lower() == 'true'
        sap_url = os.environ.get('SAP_ODATA_URL', '')

        if not sap_enabled:
            return {
                'valid': False,
                'message': 'SAP integration is not enabled',
                'details': {
                    'sap_enabled': False,
                    'action': 'Set SAP_ENABLED=true and configure SAP_PM_SYSTEM destination'
                }
            }

        # Check if destination service is bound
        vcap = os.environ.get('VCAP_SERVICES', '{}')
        try:
            services = json.loads(vcap) if isinstance(vcap, str) else vcap
            has_destination = 'destination' in services
        except (json.JSONDecodeError, TypeError):
            has_destination = False

        if has_destination or sap_url:
            return {
                'valid': True,
                'message': 'SAP system connection is configured',
                'details': {
                    'sap_enabled': True,
                    'connection_type': os.environ.get('SAP_CONNECTION_TYPE', 'odata'),
                    'destination_service': has_destination,
                }
            }

        return {
            'valid': False,
            'message': 'SAP destination is not configured',
            'details': {
                'sap_enabled': True,
                'action': 'Configure SAP_PM_SYSTEM destination in BTP cockpit'
            }
        }

    def _check_ai_configuration(self, tenant_id: str) -> Dict[str, Any]:
        """Validate AI/LLM configuration."""
        api_key = os.environ.get('GOOGLE_API_KEY', '')
        if api_key:
            return {
                'valid': True,
                'message': 'Google Gemini API key is configured',
                'details': {'provider': 'google_generativeai', 'key_set': True}
            }

        return {
            'valid': False,
            'message': 'Google Gemini API key is not configured',
            'details': {
                'provider': 'google_generativeai',
                'key_set': False,
                'action': 'Set GOOGLE_API_KEY environment variable'
            }
        }

    def _check_user_roles(self, tenant_id: str) -> Dict[str, Any]:
        """Validate user role assignments."""
        auth_enabled = os.environ.get('AUTH_ENABLED', 'true').lower() == 'true'
        if not auth_enabled:
            return {
                'valid': True,
                'message': 'Authentication is disabled (development mode)',
                'details': {'auth_enabled': False}
            }

        return {
            'valid': True,
            'message': 'Authentication is enabled. Assign role collections in BTP cockpit.',
            'details': {
                'auth_enabled': True,
                'role_collections': [
                    'PM_Analyzer_Viewer',
                    'PM_Analyzer_Editor',
                    'PM_Analyzer_Auditor',
                    'PM_Analyzer_Admin',
                ],
                'action': 'Assign role collections to users in SAP BTP cockpit'
            }
        }

    def _check_data_available(self, tenant_id: str) -> Dict[str, Any]:
        """Check if notification data is available."""
        try:
            with get_db_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) as cnt FROM QMEL")
                row = cursor.fetchone()
                count = row['cnt'] if row else 0

                if count > 0:
                    return {
                        'valid': True,
                        'message': f'{count} notifications available',
                        'details': {'notification_count': count}
                    }

                return {
                    'valid': False,
                    'message': 'No notification data found',
                    'details': {
                        'notification_count': 0,
                        'action': 'Import notifications from SAP or seed demo data'
                    }
                }

        except Exception as e:
            return {
                'valid': False,
                'message': f'Could not check data: {str(e)}',
                'details': {'error': str(e)}
            }

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _save_state(self, state: OnboardingState):
        """Persist onboarding state to database."""
        with get_db_connection() as conn:
            conn.execute(
                """UPDATE onboarding_state
                   SET current_step = ?, completed_steps = ?, skipped_steps = ?,
                       completed_at = ?, is_complete = ?, step_data = ?
                   WHERE tenant_id = ?""",
                (state.current_step,
                 json.dumps(state.completed_steps),
                 json.dumps(state.skipped_steps),
                 state.completed_at or None,
                 1 if state.is_complete else 0,
                 json.dumps(state.step_data),
                 state.tenant_id)
            )

    def _row_to_state(self, row) -> OnboardingState:
        """Convert database row to OnboardingState."""
        def parse_json_field(val, default):
            if isinstance(val, list):
                return val
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    return default
            return default

        return OnboardingState(
            tenant_id=row['tenant_id'],
            current_step=row['current_step'],
            completed_steps=parse_json_field(row.get('completed_steps', '[]'), []),
            skipped_steps=parse_json_field(row.get('skipped_steps', '[]'), []),
            started_at=str(row.get('started_at', '')),
            completed_at=str(row.get('completed_at', '') or ''),
            is_complete=bool(row.get('is_complete', False)),
            step_data=parse_json_field(row.get('step_data', '{}'), {}),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_onboarding_service: Optional[OnboardingService] = None


def get_onboarding_service() -> OnboardingService:
    """Get or create the onboarding service singleton."""
    global _onboarding_service
    if _onboarding_service is None:
        _onboarding_service = OnboardingService()
    return _onboarding_service
