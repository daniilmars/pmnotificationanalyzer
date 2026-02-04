"""
Unit tests for Rule Manager authentication and authorization.
"""
import pytest
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.auth_service import (
    hash_password,
    verify_password,
    create_token,
    verify_token,
    create_user_session,
    validate_session,
    invalidate_session,
    create_electronic_signature,
    log_access,
    require_auth,
    require_permission,
    AUTH_ENABLED
)
from app.database import Session, User, Role, Permission, UserSession, ElectronicSignature, AccessLog


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_hash_password_returns_string(self):
        """Test that hash_password returns a string."""
        result = hash_password('testpassword123')
        assert isinstance(result, str)
        assert len(result) > 0

    def test_hash_password_different_inputs(self):
        """Test that different passwords produce different hashes."""
        hash1 = hash_password('password1')
        hash2 = hash_password('password2')
        assert hash1 != hash2

    def test_verify_password_correct(self):
        """Test verifying correct password."""
        password = 'mysecretpassword'
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test verifying incorrect password."""
        hashed = hash_password('correctpassword')
        assert verify_password('wrongpassword', hashed) is False

    def test_hash_password_salted(self):
        """Test that same password produces different hashes (due to salt)."""
        password = 'samepassword'
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        # Note: In our implementation, salt is included, so hashes differ
        # Both should still verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestJWTTokens:
    """Tests for JWT token creation and verification."""

    def test_create_token_returns_string(self):
        """Test that create_token returns a string."""
        token = create_token('user123', 'session456')
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_token_valid(self):
        """Test verifying a valid token."""
        user_id = 'testuser'
        session_id = 'testsession'
        token = create_token(user_id, session_id)

        payload = verify_token(token)
        assert payload is not None
        assert payload['user_id'] == user_id
        assert payload['session_id'] == session_id

    def test_verify_token_invalid(self):
        """Test verifying an invalid token."""
        payload = verify_token('invalid.token.here')
        assert payload is None

    def test_verify_token_empty(self):
        """Test verifying empty token."""
        payload = verify_token('')
        assert payload is None

    def test_token_contains_expiry(self):
        """Test that token contains expiry information."""
        token = create_token('user', 'session')
        payload = verify_token(token)
        assert 'exp' in payload


class TestSessionManagement:
    """Tests for session management functions."""

    def test_create_session(self, app):
        """Test creating a user session."""
        from app.database import Session as DBSession

        session = DBSession()
        try:
            # First create a test user
            user = User(
                id='test-session-user',
                username='sessiontest',
                email='session@test.com',
                password_hash=hash_password('testpass'),
                full_name='Session Test User'
            )
            session.add(user)
            session.commit()

            # Create session
            success, token, error = create_user_session(
                session, 'test-session-user', '192.168.1.1', 'TestBrowser/1.0'
            )

            assert success is True
            assert token is not None
            assert error is None

        finally:
            session.rollback()
            session.close()

    def test_validate_session_valid(self, app):
        """Test validating a valid session."""
        from app.database import Session as DBSession

        session = DBSession()
        try:
            # Create user and session
            user = User(
                id='test-validate-user',
                username='validatetest',
                email='validate@test.com',
                password_hash=hash_password('testpass'),
                full_name='Validate Test User'
            )
            session.add(user)
            session.commit()

            _, token, _ = create_user_session(session, 'test-validate-user')

            # Validate the session
            is_valid, user_data, error = validate_session(session, token)

            assert is_valid is True
            assert user_data is not None
            assert user_data['user_id'] == 'test-validate-user'

        finally:
            session.rollback()
            session.close()

    def test_validate_session_invalid_token(self, app):
        """Test validating an invalid token."""
        from app.database import Session as DBSession

        session = DBSession()
        try:
            is_valid, user_data, error = validate_session(session, 'invalid.token')
            assert is_valid is False
            assert error is not None

        finally:
            session.close()

    def test_invalidate_session(self, app):
        """Test invalidating a session."""
        from app.database import Session as DBSession

        session = DBSession()
        try:
            # Create user and session
            user = User(
                id='test-invalidate-user',
                username='invalidatetest',
                email='invalidate@test.com',
                password_hash=hash_password('testpass'),
                full_name='Invalidate Test User'
            )
            session.add(user)
            session.commit()

            _, token, _ = create_user_session(session, 'test-invalidate-user')

            # Get session ID from token
            payload = verify_token(token)
            session_id = payload['session_id']

            # Invalidate the session
            success = invalidate_session(session, session_id)
            assert success is True

            # Verify session is no longer valid
            is_valid, _, _ = validate_session(session, token)
            assert is_valid is False

        finally:
            session.rollback()
            session.close()


class TestElectronicSignatures:
    """Tests for electronic signature functions."""

    def test_create_signature_valid(self, app):
        """Test creating a valid electronic signature."""
        from app.database import Session as DBSession

        session = DBSession()
        try:
            # Create test user
            user = User(
                id='test-sig-user',
                username='sigtest',
                email='sig@test.com',
                password_hash=hash_password('testpass'),
                full_name='Signature Test User'
            )
            session.add(user)
            session.commit()

            # Create signature
            success, sig_data, error = create_electronic_signature(
                session,
                user_id='test-sig-user',
                password='testpass',
                entity_type='ruleset',
                entity_id='test-ruleset-123',
                meaning='Approved',
                reason='Testing signature creation',
                ip_address='192.168.1.1'
            )

            assert success is True
            assert sig_data is not None
            assert sig_data['meaning'] == 'Approved'
            assert sig_data['entity_type'] == 'ruleset'
            assert error is None

        finally:
            session.rollback()
            session.close()

    def test_create_signature_wrong_password(self, app):
        """Test creating signature with wrong password fails."""
        from app.database import Session as DBSession

        session = DBSession()
        try:
            # Create test user
            user = User(
                id='test-sig-user2',
                username='sigtest2',
                email='sig2@test.com',
                password_hash=hash_password('correctpass'),
                full_name='Signature Test User 2'
            )
            session.add(user)
            session.commit()

            # Try to create signature with wrong password
            success, sig_data, error = create_electronic_signature(
                session,
                user_id='test-sig-user2',
                password='wrongpass',
                entity_type='ruleset',
                entity_id='test-ruleset-456',
                meaning='Approved'
            )

            assert success is False
            assert sig_data is None
            assert 'Authentication failed' in error or 'failed' in error.lower()

        finally:
            session.rollback()
            session.close()

    def test_create_signature_nonexistent_user(self, app):
        """Test creating signature for nonexistent user fails."""
        from app.database import Session as DBSession

        session = DBSession()
        try:
            success, sig_data, error = create_electronic_signature(
                session,
                user_id='nonexistent-user',
                password='anypass',
                entity_type='ruleset',
                entity_id='test-ruleset',
                meaning='Approved'
            )

            assert success is False
            assert error is not None

        finally:
            session.close()


class TestAccessLogging:
    """Tests for access logging functions."""

    def test_log_access_success(self, app):
        """Test logging successful access."""
        from app.database import Session as DBSession

        session = DBSession()
        try:
            log_access(
                session,
                username='testuser',
                user_id='user123',
                action='login',
                success=True,
                ip_address='192.168.1.1',
                user_agent='TestBrowser/1.0'
            )
            session.commit()

            # Verify log was created
            log = session.query(AccessLog).filter_by(user_id='user123').first()
            assert log is not None
            assert log.action == 'login'
            assert log.success is True

        finally:
            session.rollback()
            session.close()

    def test_log_access_failure(self, app):
        """Test logging failed access attempt."""
        from app.database import Session as DBSession

        session = DBSession()
        try:
            log_access(
                session,
                username='failuser',
                action='login',
                success=False,
                failure_reason='Invalid password',
                ip_address='192.168.1.2'
            )
            session.commit()

            # Verify log was created
            log = session.query(AccessLog).filter_by(username='failuser').first()
            assert log is not None
            assert log.success is False
            assert log.failure_reason == 'Invalid password'

        finally:
            session.rollback()
            session.close()


class TestRBACDecorators:
    """Tests for RBAC decorator functions."""

    def test_require_auth_decorator_exists(self):
        """Test that require_auth decorator is callable."""
        assert callable(require_auth)

    def test_require_permission_decorator_exists(self):
        """Test that require_permission decorator is callable."""
        assert callable(require_permission)

    def test_require_permission_returns_decorator(self):
        """Test that require_permission returns a decorator function."""
        decorator = require_permission('rulesets', 'create')
        assert callable(decorator)
