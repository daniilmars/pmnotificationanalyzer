"""
User Management Service for PM Notification Analyzer.

Links Clerk organizations to application tenants, providing:
- Organization-scoped user management (invite, list, roles)
- Clerk org <-> tenant bidirectional linking
- User provisioning during trial signup
- Role management within tenant context

The Clerk organization ID serves as the tenant ID for all downstream
operations (entitlement, usage metering, data isolation).
"""

import os
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

import requests

from app.clerk_auth import get_clerk_config, ClerkUser, ClerkClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class OrganizationMember:
    """A user within a Clerk organization (tenant)."""
    user_id: str
    email: str
    first_name: str = ""
    last_name: str = ""
    role: str = "org:member"
    joined_at: str = ""

    @property
    def full_name(self) -> str:
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.email.split('@')[0]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'user_id': self.user_id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'role': self.role,
            'joined_at': self.joined_at,
        }


@dataclass
class Organization:
    """A Clerk organization linked to a tenant."""
    id: str
    name: str
    slug: str
    members_count: int = 0
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'members_count': self.members_count,
            'created_at': self.created_at,
            'metadata': self.metadata,
        }


# ---------------------------------------------------------------------------
# User Management Service
# ---------------------------------------------------------------------------

class UserManagementService:
    """
    Manages users via Clerk organizations, linked to application tenants.

    Each tenant maps 1:1 to a Clerk organization. The Clerk org_id
    IS the tenant_id used throughout the application.
    """

    def __init__(self):
        self.config = get_clerk_config()
        self._session = requests.Session()
        if self.config.secret_key:
            self._session.headers.update({
                'Authorization': f'Bearer {self.config.secret_key}',
                'Content-Type': 'application/json',
            })

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    # ------------------------------------------------------------------
    # Organization (Tenant) Management
    # ------------------------------------------------------------------

    def create_organization(self, name: str, slug: str,
                            created_by_user_id: str,
                            metadata: Optional[Dict[str, Any]] = None) -> Optional[Organization]:
        """
        Create a Clerk organization for a new tenant.

        Args:
            name: Display name (e.g. "Acme Corp")
            slug: URL-safe identifier (e.g. "acme-corp"), becomes the subdomain
            created_by_user_id: Clerk user ID of the creator (becomes org admin)
            metadata: Additional metadata to store on the org

        Returns:
            Organization object with the Clerk org ID (used as tenant_id)
        """
        if not self.enabled:
            logger.warning("Clerk not enabled, cannot create organization")
            return None

        try:
            payload = {
                'name': name,
                'slug': slug,
                'created_by': created_by_user_id,
            }
            if metadata:
                payload['public_metadata'] = metadata

            resp = self._session.post(
                f"{self.config.api_url}/organizations",
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            org = Organization(
                id=data['id'],
                name=data.get('name', name),
                slug=data.get('slug', slug),
                members_count=data.get('members_count', 1),
                created_at=str(data.get('created_at', '')),
                metadata=data.get('public_metadata', {}),
            )

            logger.info(f"Created Clerk organization: {org.id} ({org.slug})")
            return org

        except requests.HTTPError as e:
            logger.error(f"Failed to create organization: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Error creating organization: {e}")
            return None

    def get_organization(self, org_id: str) -> Optional[Organization]:
        """Get organization details by ID."""
        if not self.enabled:
            return None

        try:
            resp = self._session.get(
                f"{self.config.api_url}/organizations/{org_id}",
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            return Organization(
                id=data['id'],
                name=data.get('name', ''),
                slug=data.get('slug', ''),
                members_count=data.get('members_count', 0),
                created_at=str(data.get('created_at', '')),
                metadata=data.get('public_metadata', {}),
            )
        except Exception as e:
            logger.error(f"Error getting organization {org_id}: {e}")
            return None

    def update_organization_metadata(self, org_id: str,
                                     metadata: Dict[str, Any]) -> bool:
        """Update organization public metadata (e.g. plan, tenant info)."""
        if not self.enabled:
            return False

        try:
            resp = self._session.patch(
                f"{self.config.api_url}/organizations/{org_id}",
                json={'public_metadata': metadata},
                timeout=30,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Error updating organization metadata: {e}")
            return False

    def delete_organization(self, org_id: str) -> bool:
        """Delete a Clerk organization (tenant deprovisioning)."""
        if not self.enabled:
            return False

        try:
            resp = self._session.delete(
                f"{self.config.api_url}/organizations/{org_id}",
                timeout=30,
            )
            resp.raise_for_status()
            logger.info(f"Deleted Clerk organization: {org_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting organization {org_id}: {e}")
            return False

    # ------------------------------------------------------------------
    # Member Management
    # ------------------------------------------------------------------

    def list_members(self, org_id: str, limit: int = 100,
                     offset: int = 0) -> List[OrganizationMember]:
        """List all members of an organization (tenant)."""
        if not self.enabled:
            return []

        try:
            resp = self._session.get(
                f"{self.config.api_url}/organizations/{org_id}/memberships",
                params={'limit': limit, 'offset': offset},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            members = []
            for m in data.get('data', []):
                pub = m.get('public_user_data', {})
                members.append(OrganizationMember(
                    user_id=pub.get('user_id', m.get('user_id', '')),
                    email=pub.get('identifier', ''),
                    first_name=pub.get('first_name', ''),
                    last_name=pub.get('last_name', ''),
                    role=m.get('role', 'org:member'),
                    joined_at=str(m.get('created_at', '')),
                ))
            return members

        except Exception as e:
            logger.error(f"Error listing members for org {org_id}: {e}")
            return []

    def invite_member(self, org_id: str, email: str,
                      role: str = 'org:member') -> Dict[str, Any]:
        """
        Invite a user to the organization by email.

        Valid roles: org:admin, org:member
        Clerk sends the invitation email automatically.
        """
        if not self.enabled:
            return {'error': 'Clerk not enabled'}

        try:
            resp = self._session.post(
                f"{self.config.api_url}/organizations/{org_id}/invitations",
                json={
                    'email_address': email,
                    'role': role,
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            logger.info(f"Invited {email} to org {org_id} as {role}")
            return {
                'status': 'invited',
                'invitation_id': data.get('id'),
                'email': email,
                'role': role,
            }

        except requests.HTTPError as e:
            error_body = e.response.text
            logger.error(f"Failed to invite {email}: {e.response.status_code} - {error_body}")
            return {'error': f'Invitation failed: {error_body}'}
        except Exception as e:
            logger.error(f"Error inviting member: {e}")
            return {'error': str(e)}

    def remove_member(self, org_id: str, user_id: str) -> bool:
        """Remove a user from the organization."""
        if not self.enabled:
            return False

        try:
            resp = self._session.delete(
                f"{self.config.api_url}/organizations/{org_id}/memberships/{user_id}",
                timeout=30,
            )
            resp.raise_for_status()
            logger.info(f"Removed user {user_id} from org {org_id}")
            return True
        except Exception as e:
            logger.error(f"Error removing member {user_id} from org {org_id}: {e}")
            return False

    def update_member_role(self, org_id: str, user_id: str,
                           role: str) -> bool:
        """
        Update a member's role within the organization.

        Valid roles: org:admin, org:member
        Application-level roles (editor, auditor) are stored in user public_metadata.
        """
        if not self.enabled:
            return False

        try:
            resp = self._session.patch(
                f"{self.config.api_url}/organizations/{org_id}/memberships/{user_id}",
                json={'role': role},
                timeout=30,
            )
            resp.raise_for_status()
            logger.info(f"Updated role for user {user_id} in org {org_id} to {role}")
            return True
        except Exception as e:
            logger.error(f"Error updating member role: {e}")
            return False

    def set_application_role(self, user_id: str,
                             app_role: str) -> bool:
        """
        Set the application-level role for a user.

        Application roles (viewer, editor, auditor, admin) are stored
        in Clerk user public_metadata.roles and checked by require_role().

        Args:
            user_id: Clerk user ID
            app_role: One of 'viewer', 'editor', 'auditor', 'admin'
        """
        valid_roles = ['viewer', 'editor', 'auditor', 'admin']
        if app_role not in valid_roles:
            logger.warning(f"Invalid application role: {app_role}")
            return False

        client = ClerkClient(self.config)
        return client.set_user_roles(user_id, [app_role])

    def list_pending_invitations(self, org_id: str) -> List[Dict[str, Any]]:
        """List pending invitations for an organization."""
        if not self.enabled:
            return []

        try:
            resp = self._session.get(
                f"{self.config.api_url}/organizations/{org_id}/invitations",
                params={'status': 'pending'},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            return [
                {
                    'id': inv.get('id'),
                    'email': inv.get('email_address'),
                    'role': inv.get('role'),
                    'status': inv.get('status'),
                    'created_at': str(inv.get('created_at', '')),
                }
                for inv in data.get('data', [])
            ]
        except Exception as e:
            logger.error(f"Error listing invitations for org {org_id}: {e}")
            return []

    def revoke_invitation(self, org_id: str, invitation_id: str) -> bool:
        """Revoke a pending invitation."""
        if not self.enabled:
            return False

        try:
            resp = self._session.post(
                f"{self.config.api_url}/organizations/{org_id}/invitations/{invitation_id}/revoke",
                timeout=30,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Error revoking invitation {invitation_id}: {e}")
            return False


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_user_mgmt_service: Optional[UserManagementService] = None


def get_user_management_service() -> UserManagementService:
    """Get or create the user management service singleton."""
    global _user_mgmt_service
    if _user_mgmt_service is None:
        _user_mgmt_service = UserManagementService()
    return _user_mgmt_service
