# rule-manager/backend/app/database.py
"""
Database models for Rule Manager with full regulatory compliance support.

Supports:
- FDA 21 CFR Part 11 electronic signatures
- Role-based access control (RBAC)
- Complete audit trail
- Session management
"""
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, JSON, Boolean, Enum
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
import uuid
import enum
from datetime import datetime

Base = declarative_base()


def generate_uuid():
    return str(uuid.uuid4())


# ============================================================================
# ENUMS
# ============================================================================

class RulesetStatus(enum.Enum):
    DRAFT = "Draft"
    TEST = "Test"
    ACTIVE = "Active"
    RETIRED = "Retired"


class SignatureMeaning(enum.Enum):
    """FDA 21 CFR Part 11 requires signature meaning declarations."""
    CREATED = "Created"
    REVIEWED = "Reviewed"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    RETIRED = "Retired"


class UserStatus(enum.Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    LOCKED = "Locked"


# ============================================================================
# USER & ROLE MODELS (RBAC)
# ============================================================================

class Permission(Base):
    """Individual permissions that can be assigned to roles."""
    __tablename__ = 'permissions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(255))
    resource = Column(String(50), nullable=False)  # e.g., 'ruleset', 'rule', 'audit_log'
    action = Column(String(50), nullable=False)    # e.g., 'create', 'read', 'update', 'delete', 'activate'

    def __repr__(self):
        return f"<Permission {self.resource}:{self.action}>"


class RolePermission(Base):
    """Association table for Role-Permission many-to-many relationship."""
    __tablename__ = 'role_permissions'

    role_id = Column(Integer, ForeignKey('roles.id'), primary_key=True)
    permission_id = Column(Integer, ForeignKey('permissions.id'), primary_key=True)


class Role(Base):
    """User roles with associated permissions."""
    __tablename__ = 'roles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255))
    is_system_role = Column(Boolean, default=False)  # System roles cannot be deleted

    permissions = relationship("Permission", secondary="role_permissions", backref="roles")
    users = relationship("User", back_populates="role")

    def has_permission(self, resource: str, action: str) -> bool:
        """Check if role has a specific permission."""
        for perm in self.permissions:
            if perm.resource == resource and perm.action == action:
                return True
        return False


class User(Base):
    """User accounts with full compliance support."""
    __tablename__ = 'users'

    id = Column(String, primary_key=True, default=generate_uuid)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey('roles.id'), nullable=False)
    status = Column(String(20), default=UserStatus.ACTIVE.value)

    # Compliance fields
    must_change_password = Column(Boolean, default=True)
    password_expires_at = Column(DateTime)
    last_login = Column(DateTime)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime)

    # Training/qualification tracking (Annex 11)
    training_completed = Column(Boolean, default=False)
    training_date = Column(DateTime)
    qualification_notes = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(255))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    role = relationship("Role", back_populates="users")
    signatures = relationship("ElectronicSignature", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")


class UserSession(Base):
    """Active user sessions for session management."""
    __tablename__ = 'user_sessions'

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    token_hash = Column(String(255), nullable=False)  # Hash of JWT token
    device_info = Column(String(255))  # Browser/device identification
    ip_address = Column(String(45))  # IPv4 or IPv6
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    last_activity = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="sessions")


# ============================================================================
# ELECTRONIC SIGNATURE (FDA 21 CFR Part 11)
# ============================================================================

class ElectronicSignature(Base):
    """
    Electronic signatures compliant with FDA 21 CFR Part 11.

    Requirements met:
    - Unique to signer (user_id)
    - Contains signature meaning (meaning field)
    - Linked to signed record (entity_type, entity_id)
    - Contains printed name (user.full_name via relationship)
    - Date/time of signature (timestamp)
    - Two-component authentication (recorded in auth_method)
    """
    __tablename__ = 'electronic_signatures'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)

    # What was signed
    entity_type = Column(String(50), nullable=False)  # e.g., 'ruleset', 'rule'
    entity_id = Column(String, nullable=False)
    entity_version = Column(Integer)  # Version at time of signing

    # Signature details (21 CFR Part 11 requirements)
    meaning = Column(String(50), nullable=False)  # SignatureMeaning enum value
    reason = Column(Text)  # Optional reason for signature

    # Authentication proof
    auth_method = Column(String(50), default="password")  # How user authenticated
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Additional compliance fields
    ip_address = Column(String(45))
    user_agent = Column(String(255))

    user = relationship("User", back_populates="signatures")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": self.user.full_name if self.user else None,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "entity_version": self.entity_version,
            "meaning": self.meaning,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "auth_method": self.auth_method
        }


# ============================================================================
# RULESET & RULES
# ============================================================================

class Ruleset(Base):
    """Ruleset with versioning and signature support."""
    __tablename__ = 'rulesets'

    id = Column(String, primary_key=True, default=generate_uuid)
    group_id = Column(String, nullable=False)  # ID shared between versions
    version = Column(Integer, nullable=False, default=1)
    name = Column(String(255), nullable=False)
    notification_type = Column(String(10), nullable=False)
    status = Column(String(20), nullable=False, default='Draft')
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(String(255), nullable=False)

    # Approval workflow fields
    reviewed_by = Column(String(255))
    reviewed_at = Column(DateTime)
    approved_by = Column(String(255))
    approved_at = Column(DateTime)

    rules = relationship("Rule", back_populates="ruleset", cascade="all, delete-orphan")
    signatures = relationship("ElectronicSignature",
                             primaryjoin="and_(Ruleset.id==foreign(ElectronicSignature.entity_id), "
                                        "ElectronicSignature.entity_type=='ruleset')",
                             viewonly=True)

    def to_dict(self, include_rules=False):
        data = {
            "id": self.id,
            "group_id": self.group_id,
            "version": self.version,
            "name": self.name,
            "notification_type": self.notification_type,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None
        }
        if include_rules:
            data["rules"] = [r.to_dict() for r in self.rules]
        return data


class Rule(Base):
    """Individual quality rules within a ruleset."""
    __tablename__ = 'rules'

    id = Column(String, primary_key=True, default=generate_uuid)
    ruleset_id = Column(String, ForeignKey('rulesets.id'), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    target_field = Column(String(50), nullable=False)
    condition = Column(String(50), nullable=False)
    value = Column(Text)
    score_impact = Column(Integer, nullable=False)
    feedback_message = Column(Text, nullable=False)

    ruleset = relationship("Ruleset", back_populates="rules")

    def to_dict(self):
        return {
            "id": self.id,
            "ruleset_id": self.ruleset_id,
            "name": self.name,
            "description": self.description,
            "target_field": self.target_field,
            "condition": self.condition,
            "value": self.value,
            "score_impact": self.score_impact,
            "feedback_message": self.feedback_message
        }


# ============================================================================
# AUDIT LOG
# ============================================================================

class AuditLog(Base):
    """
    Comprehensive audit log for compliance.

    Captures who, what, when, and why for all system changes.
    """
    __tablename__ = 'audit_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    user_id = Column(String(255), nullable=False)
    user_name = Column(String(255))  # Denormalized for historical accuracy
    action_type = Column(String(50), nullable=False)
    entity_type = Column(String(50))  # e.g., 'ruleset', 'rule', 'user'
    entity_id = Column(String(255))
    old_value_json = Column(JSON)
    new_value_json = Column(JSON)
    reason_for_change = Column(Text)
    ip_address = Column(String(45))
    user_agent = Column(String(255))

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "action_type": self.action_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "old_value": self.old_value_json,
            "new_value": self.new_value_json,
            "reason_for_change": self.reason_for_change
        }


# ============================================================================
# ACCESS LOG (Security)
# ============================================================================

class AccessLog(Base):
    """Log of all access attempts for security monitoring."""
    __tablename__ = 'access_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    username = Column(String(100))  # May be attempted username for failed logins
    user_id = Column(String)  # Actual user ID if login succeeded
    action = Column(String(50), nullable=False)  # 'login', 'logout', 'token_refresh', 'password_change'
    success = Column(Boolean, nullable=False)
    failure_reason = Column(String(255))
    ip_address = Column(String(45))
    user_agent = Column(String(255))

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "username": self.username,
            "user_id": self.user_id,
            "action": self.action,
            "success": self.success,
            "failure_reason": self.failure_reason,
            "ip_address": self.ip_address
        }


# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

engine = None
Session = None


def init_db(db_uri):
    """Initialize database and create all tables."""
    global engine, Session
    engine = create_engine(db_uri)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)


def seed_default_roles_and_permissions(db_session=None):
    """
    Seed default roles and permissions for compliance.

    Roles (per GMP requirements):
    - Admin: Full system access, user management
    - QA Expert: Create, edit, approve rules
    - Reviewer: Review rules (cannot approve own work)
    - Viewer: Read-only access
    - Auditor: Read access to all data including audit logs
    """
    # Create session if not provided
    if db_session is None:
        db_session = Session()
        should_close = True
    else:
        should_close = False

    try:
        # Define permissions
        permissions_data = [
            # Ruleset permissions
            ("rulesets:create", "Create new rulesets", "rulesets", "create"),
            ("rulesets:read", "View rulesets", "rulesets", "read"),
            ("rulesets:update", "Modify draft rulesets", "rulesets", "update"),
            ("rulesets:delete", "Delete draft rulesets", "rulesets", "delete"),
            ("rulesets:activate", "Activate rulesets (requires signature)", "rulesets", "activate"),
            ("rulesets:retire", "Retire active rulesets", "rulesets", "retire"),
            ("rulesets:export", "Export rulesets to CSV", "rulesets", "export"),

            # Rule permissions
            ("rules:create", "Add rules to rulesets", "rules", "create"),
            ("rules:read", "View rules", "rules", "read"),
            ("rules:update", "Modify rules", "rules", "update"),
            ("rules:delete", "Delete rules", "rules", "delete"),

            # User management
            ("users:create", "Create user accounts", "users", "create"),
            ("users:read", "View user accounts", "users", "read"),
            ("users:update", "Modify user accounts", "users", "update"),
            ("users:delete", "Deactivate user accounts", "users", "delete"),
            ("users:export", "Export user list to CSV", "users", "export"),

            # Audit access
            ("audit_log:view", "View audit logs", "audit_log", "view"),
            ("audit_log:export", "Export audit logs to CSV", "audit_log", "export"),

            # Access log
            ("access_log:view", "View access logs", "access_log", "view"),
            ("access_log:export", "Export access logs to CSV", "access_log", "export"),

            # Electronic signatures
            ("signatures:create", "Create electronic signatures", "signatures", "create"),
            ("signatures:view", "View signatures", "signatures", "view"),
            ("signatures:export", "Export signatures to CSV", "signatures", "export"),

            # Permissions/RBAC
            ("permissions:view", "View permissions", "permissions", "view"),
            ("permissions:export", "Export RBAC matrix to CSV", "permissions", "export"),

            # Validation reports
            ("validation:view", "View validation reports", "validation", "view"),

            # SOP extraction
            ("sop:extract", "Extract rules from SOP documents", "sop", "extract"),

            # System configuration
            ("config:read", "View system configuration", "config", "read"),
            ("config:update", "Modify system configuration", "config", "update"),
        ]

        # Create permissions
        permissions = {}
        for name, desc, resource, action in permissions_data:
            perm = db_session.query(Permission).filter_by(name=name).first()
            if not perm:
                perm = Permission(name=name, description=desc, resource=resource, action=action)
                db_session.add(perm)
            permissions[name] = perm

        db_session.flush()

        # Define roles with their permissions
        roles_data = {
            "Admin": {
                "description": "Full system access including user management",
                "is_system_role": True,
                "permissions": list(permissions.keys())  # All permissions
            },
            "QA Expert": {
                "description": "Create, edit, and approve quality rules",
                "is_system_role": True,
                "permissions": [
                    "rulesets:create", "rulesets:read", "rulesets:update", "rulesets:activate", "rulesets:retire",
                    "rules:create", "rules:read", "rules:update", "rules:delete",
                    "signatures:create", "signatures:view",
                    "audit_log:view", "sop:extract"
                ]
            },
            "Reviewer": {
                "description": "Review rules (cannot approve own work)",
                "is_system_role": True,
                "permissions": [
                    "rulesets:read", "rulesets:update",
                    "rules:read",
                    "signatures:create", "signatures:view",
                    "audit_log:view"
                ]
            },
            "Viewer": {
                "description": "Read-only access to rules",
                "is_system_role": True,
                "permissions": [
                    "rulesets:read",
                    "rules:read"
                ]
            },
            "Auditor": {
                "description": "Full read access including audit logs and exports",
                "is_system_role": True,
                "permissions": [
                    "rulesets:read", "rulesets:export",
                    "rules:read",
                    "users:read", "users:export",
                    "audit_log:view", "audit_log:export",
                    "access_log:view", "access_log:export",
                    "signatures:view", "signatures:export",
                    "permissions:view", "permissions:export",
                    "validation:view"
                ]
            }
        }

        # Create roles
        for role_name, role_data in roles_data.items():
            role = db_session.query(Role).filter_by(name=role_name).first()
            if not role:
                role = Role(
                    name=role_name,
                    description=role_data["description"],
                    is_system_role=role_data["is_system_role"]
                )
                db_session.add(role)
                db_session.flush()

            # Assign permissions to role
            for perm_name in role_data["permissions"]:
                if perm_name in permissions and permissions[perm_name] not in role.permissions:
                    role.permissions.append(permissions[perm_name])

        db_session.commit()

    finally:
        if should_close:
            db_session.close()
