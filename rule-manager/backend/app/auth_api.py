"""
Authentication API endpoints for Rule Manager.

Provides:
- Login/logout
- User management (CRUD)
- Password management
- Electronic signatures
- Access logs
"""
import logging
from flask import Blueprint, jsonify, request, g
from .database import Session, User, Role, AccessLog, ElectronicSignature, seed_default_roles_and_permissions
from .auth_service import (
    require_auth, require_permission, authenticate_user, logout_user,
    change_password, create_electronic_signature, get_signatures_for_entity,
    hash_password, validate_password_strength, get_request_info,
    get_current_user_id, get_current_username, AUTH_ENABLED, PASSWORD_EXPIRY_DAYS
)
from .audit_service import log_event
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

auth_blueprint = Blueprint('auth', __name__)


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@auth_blueprint.route('/login', methods=['POST'])
def login():
    """
    Authenticate user and return JWT token.

    Request body:
        username: User's username
        password: User's password

    Returns:
        token: JWT access token
        user_id: User's ID
        username: User's username
        role: User's role name
        permissions: List of permission strings
        expires_in: Token expiry in seconds
    """
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Username and password required'}), 400

    ip_address, user_agent = get_request_info()

    session = Session()
    try:
        success, token_data, error = authenticate_user(
            session,
            data['username'],
            data['password'],
            ip_address,
            user_agent
        )

        if not success:
            return jsonify({'error': error}), 401

        return jsonify(token_data), 200
    finally:
        session.close()


@auth_blueprint.route('/logout', methods=['POST'])
@require_auth
def logout():
    """Log out the current user and invalidate session."""
    ip_address, user_agent = get_request_info()
    token = getattr(g, 'token', None)

    session = Session()
    try:
        logout_user(session, get_current_user_id(), token, ip_address, user_agent)
        return jsonify({'message': 'Logged out successfully'}), 200
    finally:
        session.close()


@auth_blueprint.route('/me', methods=['GET'])
@require_auth
def get_current_user():
    """Get current user's profile."""
    session = Session()
    try:
        user = session.query(User).filter_by(id=get_current_user_id()).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        return jsonify({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'full_name': user.full_name,
            'role': user.role.name,
            'status': user.status,
            'must_change_password': user.must_change_password,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'training_completed': user.training_completed,
            'training_date': user.training_date.isoformat() if user.training_date else None
        }), 200
    finally:
        session.close()


@auth_blueprint.route('/change-password', methods=['POST'])
@require_auth
def change_user_password():
    """
    Change current user's password.

    Request body:
        old_password: Current password
        new_password: New password
    """
    data = request.get_json()
    if not data or not data.get('old_password') or not data.get('new_password'):
        return jsonify({'error': 'Old password and new password required'}), 400

    ip_address, user_agent = get_request_info()

    session = Session()
    try:
        success, error = change_password(
            session,
            get_current_user_id(),
            data['old_password'],
            data['new_password'],
            ip_address,
            user_agent
        )

        if not success:
            return jsonify({'error': error}), 400

        return jsonify({'message': 'Password changed successfully. Please log in again.'}), 200
    finally:
        session.close()


# ============================================================================
# USER MANAGEMENT ENDPOINTS
# ============================================================================

@auth_blueprint.route('/users', methods=['GET'])
@require_auth
@require_permission('user', 'read')
def list_users():
    """List all users."""
    session = Session()
    try:
        users = session.query(User).all()
        return jsonify([{
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'full_name': u.full_name,
            'role': u.role.name if u.role else None,
            'status': u.status,
            'last_login': u.last_login.isoformat() if u.last_login else None,
            'training_completed': u.training_completed
        } for u in users]), 200
    finally:
        session.close()


@auth_blueprint.route('/users', methods=['POST'])
@require_auth
@require_permission('user', 'create')
def create_user():
    """
    Create a new user account.

    Request body:
        username: Unique username
        email: Email address
        full_name: Full name
        password: Initial password
        role_id: Role ID
    """
    data = request.get_json()
    required_fields = ['username', 'email', 'full_name', 'password', 'role_id']
    if not data or not all(f in data for f in required_fields):
        return jsonify({'error': f'Required fields: {required_fields}'}), 400

    # Validate password strength
    is_valid, error = validate_password_strength(data['password'])
    if not is_valid:
        return jsonify({'error': error}), 400

    session = Session()
    try:
        # Check username uniqueness
        if session.query(User).filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already exists'}), 400

        # Check email uniqueness
        if session.query(User).filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already exists'}), 400

        # Verify role exists
        role = session.query(Role).filter_by(id=data['role_id']).first()
        if not role:
            return jsonify({'error': 'Invalid role_id'}), 400

        # Create user
        user = User(
            username=data['username'],
            email=data['email'],
            full_name=data['full_name'],
            password_hash=hash_password(data['password']),
            role_id=data['role_id'],
            must_change_password=True,
            password_expires_at=datetime.utcnow() + timedelta(days=PASSWORD_EXPIRY_DAYS),
            created_by=get_current_user_id()
        )
        session.add(user)

        log_event(session, get_current_user_id(), "CREATE_USER", user.id,
                 new_value={'username': user.username, 'role': role.name})

        session.commit()

        logger.info(f"User created: {user.username} by {get_current_username()}")

        return jsonify({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'full_name': user.full_name,
            'role': role.name
        }), 201
    finally:
        session.close()


@auth_blueprint.route('/users/<user_id>', methods=['GET'])
@require_auth
@require_permission('user', 'read')
def get_user(user_id):
    """Get a specific user's details."""
    session = Session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        return jsonify({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'full_name': user.full_name,
            'role': user.role.name if user.role else None,
            'role_id': user.role_id,
            'status': user.status,
            'must_change_password': user.must_change_password,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'failed_login_attempts': user.failed_login_attempts,
            'locked_until': user.locked_until.isoformat() if user.locked_until else None,
            'training_completed': user.training_completed,
            'training_date': user.training_date.isoformat() if user.training_date else None,
            'qualification_notes': user.qualification_notes,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'created_by': user.created_by
        }), 200
    finally:
        session.close()


@auth_blueprint.route('/users/<user_id>', methods=['PUT'])
@require_auth
@require_permission('user', 'update')
def update_user(user_id):
    """Update a user's details."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    session = Session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        old_values = {
            'email': user.email,
            'full_name': user.full_name,
            'role_id': user.role_id,
            'status': user.status
        }

        # Update allowed fields
        if 'email' in data:
            # Check uniqueness
            existing = session.query(User).filter(User.email == data['email'], User.id != user_id).first()
            if existing:
                return jsonify({'error': 'Email already exists'}), 400
            user.email = data['email']

        if 'full_name' in data:
            user.full_name = data['full_name']

        if 'role_id' in data:
            role = session.query(Role).filter_by(id=data['role_id']).first()
            if not role:
                return jsonify({'error': 'Invalid role_id'}), 400
            user.role_id = data['role_id']

        if 'status' in data and data['status'] in ['Active', 'Inactive']:
            user.status = data['status']
            if data['status'] == 'Active':
                user.locked_until = None
                user.failed_login_attempts = 0

        if 'training_completed' in data:
            user.training_completed = data['training_completed']
            if data['training_completed']:
                user.training_date = datetime.utcnow()

        if 'qualification_notes' in data:
            user.qualification_notes = data['qualification_notes']

        new_values = {
            'email': user.email,
            'full_name': user.full_name,
            'role_id': user.role_id,
            'status': user.status
        }

        log_event(session, get_current_user_id(), "UPDATE_USER", user.id,
                 old_value=old_values, new_value=new_values)

        session.commit()

        logger.info(f"User updated: {user.username} by {get_current_username()}")

        return jsonify({'message': 'User updated successfully'}), 200
    finally:
        session.close()


@auth_blueprint.route('/users/<user_id>/reset-password', methods=['POST'])
@require_auth
@require_permission('user', 'update')
def reset_user_password(user_id):
    """
    Reset a user's password (admin function).

    Request body:
        new_password: New password to set
    """
    data = request.get_json()
    if not data or not data.get('new_password'):
        return jsonify({'error': 'new_password required'}), 400

    # Validate password strength
    is_valid, error = validate_password_strength(data['new_password'])
    if not is_valid:
        return jsonify({'error': error}), 400

    session = Session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        user.password_hash = hash_password(data['new_password'])
        user.must_change_password = True
        user.password_expires_at = datetime.utcnow() + timedelta(days=PASSWORD_EXPIRY_DAYS)
        user.failed_login_attempts = 0
        user.locked_until = None
        user.status = 'Active'

        log_event(session, get_current_user_id(), "RESET_PASSWORD", user.id)
        session.commit()

        logger.info(f"Password reset for: {user.username} by {get_current_username()}")

        return jsonify({'message': 'Password reset successfully'}), 200
    finally:
        session.close()


@auth_blueprint.route('/users/<user_id>/unlock', methods=['POST'])
@require_auth
@require_permission('user', 'update')
def unlock_user(user_id):
    """Unlock a locked user account."""
    session = Session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        user.locked_until = None
        user.failed_login_attempts = 0
        user.status = 'Active'

        log_event(session, get_current_user_id(), "UNLOCK_USER", user.id)
        session.commit()

        logger.info(f"User unlocked: {user.username} by {get_current_username()}")

        return jsonify({'message': 'User unlocked successfully'}), 200
    finally:
        session.close()


# ============================================================================
# ROLE MANAGEMENT ENDPOINTS
# ============================================================================

@auth_blueprint.route('/roles', methods=['GET'])
@require_auth
@require_permission('user', 'read')
def list_roles():
    """List all roles with their permissions."""
    session = Session()
    try:
        roles = session.query(Role).all()
        return jsonify([{
            'id': r.id,
            'name': r.name,
            'description': r.description,
            'is_system_role': r.is_system_role,
            'permissions': [f"{p.resource}:{p.action}" for p in r.permissions]
        } for r in roles]), 200
    finally:
        session.close()


# ============================================================================
# ELECTRONIC SIGNATURE ENDPOINTS
# ============================================================================

@auth_blueprint.route('/signatures', methods=['POST'])
@require_auth
@require_permission('signature', 'create')
def create_signature():
    """
    Create an electronic signature (requires re-authentication).

    Request body:
        password: User's password for re-authentication
        entity_type: Type of entity being signed (e.g., 'ruleset')
        entity_id: ID of entity being signed
        meaning: Signature meaning (Created, Reviewed, Approved, Rejected, Retired)
        reason: Optional reason for signature
        entity_version: Optional version number
    """
    data = request.get_json()
    required_fields = ['password', 'entity_type', 'entity_id', 'meaning']
    if not data or not all(f in data for f in required_fields):
        return jsonify({'error': f'Required fields: {required_fields}'}), 400

    ip_address, user_agent = get_request_info()

    session = Session()
    try:
        success, signature, error = create_electronic_signature(
            session,
            get_current_user_id(),
            data['password'],
            data['entity_type'],
            data['entity_id'],
            data['meaning'],
            data.get('reason'),
            data.get('entity_version'),
            ip_address,
            user_agent
        )

        if not success:
            return jsonify({'error': error}), 400

        return jsonify(signature), 201
    finally:
        session.close()


@auth_blueprint.route('/signatures/<entity_type>/<entity_id>', methods=['GET'])
@require_auth
@require_permission('signature', 'read')
def get_entity_signatures(entity_type, entity_id):
    """Get all signatures for a specific entity."""
    session = Session()
    try:
        signatures = get_signatures_for_entity(session, entity_type, entity_id)
        return jsonify(signatures), 200
    finally:
        session.close()


# ============================================================================
# ACCESS LOG ENDPOINTS
# ============================================================================

@auth_blueprint.route('/access-logs', methods=['GET'])
@require_auth
@require_permission('audit', 'read')
def list_access_logs():
    """
    List access logs with optional filtering.

    Query parameters:
        username: Filter by username
        action: Filter by action type
        success: Filter by success (true/false)
        from_date: Filter from date (ISO format)
        to_date: Filter to date (ISO format)
        limit: Maximum records (default 100)
    """
    session = Session()
    try:
        query = session.query(AccessLog)

        # Apply filters
        if request.args.get('username'):
            query = query.filter(AccessLog.username == request.args.get('username'))
        if request.args.get('action'):
            query = query.filter(AccessLog.action == request.args.get('action'))
        if request.args.get('success'):
            success = request.args.get('success').lower() == 'true'
            query = query.filter(AccessLog.success == success)
        if request.args.get('from_date'):
            query = query.filter(AccessLog.timestamp >= request.args.get('from_date'))
        if request.args.get('to_date'):
            query = query.filter(AccessLog.timestamp <= request.args.get('to_date'))

        limit = min(int(request.args.get('limit', 100)), 1000)
        logs = query.order_by(AccessLog.timestamp.desc()).limit(limit).all()

        return jsonify([log.to_dict() for log in logs]), 200
    finally:
        session.close()


# ============================================================================
# SYSTEM INITIALIZATION
# ============================================================================

@auth_blueprint.route('/init-roles', methods=['POST'])
def init_roles():
    """
    Initialize default roles and permissions.
    Only works if no roles exist yet.
    """
    session = Session()
    try:
        existing_roles = session.query(Role).count()
        if existing_roles > 0:
            return jsonify({'error': 'Roles already initialized'}), 400

        seed_default_roles_and_permissions(session)
        logger.info("Default roles and permissions initialized")

        return jsonify({'message': 'Roles and permissions initialized successfully'}), 201
    finally:
        session.close()


@auth_blueprint.route('/init-admin', methods=['POST'])
def init_admin():
    """
    Create initial admin user.
    Only works if no users exist yet.
    """
    data = request.get_json()
    required_fields = ['username', 'email', 'full_name', 'password']
    if not data or not all(f in data for f in required_fields):
        return jsonify({'error': f'Required fields: {required_fields}'}), 400

    session = Session()
    try:
        existing_users = session.query(User).count()
        if existing_users > 0:
            return jsonify({'error': 'Users already exist. Use admin to create more.'}), 400

        # Get Admin role
        admin_role = session.query(Role).filter_by(name='Admin').first()
        if not admin_role:
            return jsonify({'error': 'Roles not initialized. Call /init-roles first.'}), 400

        # Validate password
        is_valid, error = validate_password_strength(data['password'])
        if not is_valid:
            return jsonify({'error': error}), 400

        # Create admin user
        admin_user = User(
            username=data['username'],
            email=data['email'],
            full_name=data['full_name'],
            password_hash=hash_password(data['password']),
            role_id=admin_role.id,
            must_change_password=False,  # Initial admin doesn't need to change
            password_expires_at=datetime.utcnow() + timedelta(days=PASSWORD_EXPIRY_DAYS),
            created_by='system'
        )
        session.add(admin_user)
        session.commit()

        logger.info(f"Initial admin user created: {admin_user.username}")

        return jsonify({
            'message': 'Admin user created successfully',
            'username': admin_user.username
        }), 201
    finally:
        session.close()
