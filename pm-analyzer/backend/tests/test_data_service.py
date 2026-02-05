"""
Unit tests for the data service layer.
Tests notification retrieval, pagination, and localization.
"""
import pytest
import json
import sqlite3
import os

os.environ['DATABASE_TYPE'] = 'sqlite'
os.environ['AUTH_ENABLED'] = 'false'


class TestGetNotifications:
    """Tests for notification retrieval."""

    def test_get_empty_notifications(self, app):
        """Test getting notifications from empty database."""
        with app.app_context():
            from app.services.data_service import get_all_notifications_summary
            result = get_all_notifications_summary()
            assert isinstance(result, list)
            assert len(result) == 0

    def test_get_notifications_with_data(self, app, db_with_data):
        """Test getting notifications with data."""
        with app.app_context():
            from app.services.data_service import get_all_notifications_summary
            result = get_all_notifications_summary(language='en')
            assert len(result) >= 1
            notif = result[0]
            assert 'NotificationId' in notif
            assert 'Description' in notif
            assert 'Priority' in notif

    def test_get_notifications_german(self, app, db_with_data):
        """Test getting notifications in German."""
        with app.app_context():
            from app.services.data_service import get_all_notifications_summary
            result = get_all_notifications_summary(language='de')
            assert len(result) >= 1
            notif = result[0]
            assert notif['Description'] == 'Test Meldung'

    def test_get_notifications_paginated(self, app, db_with_data):
        """Test paginated notification retrieval."""
        with app.app_context():
            from app.services.data_service import get_all_notifications_summary
            result = get_all_notifications_summary(paginate=True, page=1, page_size=10)
            assert 'items' in result
            assert 'total' in result
            assert 'page' in result
            assert 'page_size' in result
            assert 'total_pages' in result
            assert result['page'] == 1

    def test_get_notifications_count(self, app, db_with_data):
        """Test notification count."""
        with app.app_context():
            from app.services.data_service import get_notifications_count
            count = get_notifications_count()
            assert count >= 1


class TestGetUnifiedNotification:
    """Tests for single notification detail retrieval."""

    def test_get_nonexistent_notification(self, app):
        """Test getting notification that doesn't exist."""
        with app.app_context():
            from app.services.data_service import get_unified_notification
            result = get_unified_notification('NONEXIST001')
            assert result is None

    def test_get_notification_detail(self, app, db_with_data):
        """Test getting notification detail with full object graph."""
        with app.app_context():
            from app.services.data_service import get_unified_notification
            result = get_unified_notification('TEST000001', language='en')
            assert result is not None
            assert result['NotificationId'] == 'TEST000001'
            assert result['NotificationType'] == 'M1'
            assert result['Priority'] == '2'
            assert result['Description'] == 'Test Notification'
            assert 'Items' in result
            assert 'Damage' in result
            assert 'Cause' in result

    def test_get_notification_detail_german(self, app, db_with_data):
        """Test getting notification detail in German."""
        with app.app_context():
            from app.services.data_service import get_unified_notification
            result = get_unified_notification('TEST000001', language='de')
            assert result is not None
            assert result['Description'] == 'Test Meldung'
            assert result['PriorityText'] == 'Hoch'
            assert result['NotificationTypeText'] == 'Instandhaltungsanforderung'


class TestMappingHelpers:
    """Tests for text mapping helper functions."""

    def test_priority_text_en(self):
        """Test priority text mapping in English."""
        from app.services.data_service import get_priority_text
        assert get_priority_text('1', 'en') == 'Very High'
        assert get_priority_text('2', 'en') == 'High'
        assert get_priority_text('3', 'en') == 'Medium'
        assert get_priority_text('4', 'en') == 'Low'

    def test_priority_text_de(self):
        """Test priority text mapping in German."""
        from app.services.data_service import get_priority_text
        assert get_priority_text('1', 'de') == 'Sehr Hoch'
        assert get_priority_text('2', 'de') == 'Hoch'

    def test_priority_text_unknown(self):
        """Test priority text for unknown code returns code."""
        from app.services.data_service import get_priority_text
        assert get_priority_text('9', 'en') == '9'

    def test_notif_type_text(self):
        """Test notification type text mapping."""
        from app.services.data_service import get_notif_type_text
        assert get_notif_type_text('M1', 'en') == 'Maintenance Request'
        assert get_notif_type_text('M2', 'en') == 'Malfunction Report'
        assert get_notif_type_text('M3', 'en') == 'Activity Report'

    def test_order_type_text(self):
        """Test order type text mapping."""
        from app.services.data_service import get_order_type_text
        assert get_order_type_text('PM01', 'en') == 'Maintenance Order'
        assert get_order_type_text('PM01', 'de') == 'Instandhaltungsauftrag'
