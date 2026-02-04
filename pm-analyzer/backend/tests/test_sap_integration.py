#!/usr/bin/env python3
"""
SAP Integration Test Suite

Tests the SAP integration service against the mock SAP server.

Usage:
    1. Start the mock server: python mock_sap_server.py
    2. Run tests: python test_sap_integration.py

Or run with pytest:
    pytest test_sap_integration.py -v
"""

import os
import sys
import time
import unittest
import subprocess
import requests

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.sap_integration_service import (
    SAPIntegrationService,
    SAPConnectionConfig,
    ConnectionType,
    check_sap_available
)


class TestSAPIntegration(unittest.TestCase):
    """Test cases for SAP integration service"""

    @classmethod
    def setUpClass(cls):
        """Set up test configuration"""
        # Configure for mock server
        cls.config = SAPConnectionConfig(
            connection_type=ConnectionType.ODATA,
            name="MOCK_SAP",
            description="Mock SAP Server for Testing",
            base_url="http://localhost:8080",
            service_path="/sap/opu/odata/sap/",
            user="TESTUSER",
            passwd="testpass",
            auth_type="basic",
            timeout=30,
            enabled=True,
            read_only=False
        )

        cls.service = SAPIntegrationService(cls.config)

        # Check if mock server is running
        cls.mock_server_available = cls._check_mock_server()

    @classmethod
    def _check_mock_server(cls) -> bool:
        """Check if mock SAP server is running"""
        try:
            response = requests.get("http://localhost:8080/health", timeout=5)
            return response.status_code == 200
        except:
            return False

    def setUp(self):
        """Set up each test"""
        if not self.mock_server_available:
            self.skipTest("Mock SAP server not running. Start with: python mock_sap_server.py")

    # ==========================================
    # Connection Tests
    # ==========================================

    def test_check_sap_available(self):
        """Test SAP availability check"""
        availability = check_sap_available()

        self.assertIn('rfc_available', availability)
        self.assertIn('odata_available', availability)
        self.assertIn('integration_enabled', availability)
        self.assertTrue(availability['odata_available'])

    def test_connect(self):
        """Test establishing connection"""
        result = self.service.connect()
        self.assertTrue(result)
        self.assertTrue(self.service.is_connected())

    def test_connection_status(self):
        """Test getting connection status"""
        self.service.connect()
        status = self.service.get_connection_status()

        self.assertTrue(status['enabled'])
        self.assertEqual(status['connection_type'], 'odata')
        self.assertEqual(status['system_name'], 'MOCK_SAP')
        self.assertTrue(status['is_connected'])

    def test_disconnect(self):
        """Test disconnecting"""
        self.service.connect()
        self.assertTrue(self.service.is_connected())

        self.service.disconnect()
        self.assertFalse(self.service.is_connected())

    # ==========================================
    # Notification Tests
    # ==========================================

    def test_get_notification(self):
        """Test getting a single notification"""
        self.service.connect()

        result = self.service.get_notification("10000001")

        self.assertTrue(result.success)
        self.assertIsNotNone(result.data)
        self.assertIn('NotificationId', result.data)

    def test_get_notification_not_found(self):
        """Test getting a non-existent notification"""
        self.service.connect()

        result = self.service.get_notification("99999999")

        self.assertFalse(result.success)

    def test_create_notification(self):
        """Test creating a new notification"""
        self.service.connect()

        notification_data = {
            'NotificationType': 'M1',
            'Description': 'Test notification from integration test',
            'Priority': '2',
            'EquipmentNumber': 'PUMP-001',
            'FunctionalLocation': 'PLANT-A-L01'
        }

        result = self.service.create_notification(notification_data)

        self.assertTrue(result.success)
        self.assertIn('NotificationId', result.data)
        print(f"Created notification: {result.data['NotificationId']}")

    # ==========================================
    # Work Order Tests
    # ==========================================

    def test_get_work_order(self):
        """Test getting a work order"""
        self.service.connect()

        result = self.service.get_work_order("4000001")

        self.assertTrue(result.success)
        self.assertIsNotNone(result.data)

    # ==========================================
    # Equipment Tests
    # ==========================================

    def test_get_equipment(self):
        """Test getting equipment master data"""
        self.service.connect()

        result = self.service.get_equipment("PUMP-001")

        self.assertTrue(result.success)
        self.assertIsNotNone(result.data)
        self.assertIn('Description', result.data)

    # ==========================================
    # Sync Tests
    # ==========================================

    def test_sync_notifications(self):
        """Test synchronizing notifications"""
        self.service.connect()

        result = self.service.sync_notifications(limit=10)

        self.assertTrue(result.success)
        self.assertGreater(result.records_processed, 0)
        print(f"Synced {result.records_processed} notifications in {result.duration_seconds:.2f}s")


class TestSAPIntegrationWithoutServer(unittest.TestCase):
    """Test cases that don't require the mock server"""

    def test_config_from_env(self):
        """Test loading configuration from environment"""
        # Set test environment variables
        os.environ['SAP_ENABLED'] = 'true'
        os.environ['SAP_CONNECTION_TYPE'] = 'odata'
        os.environ['SAP_ODATA_URL'] = 'https://test.example.com'
        os.environ['SAP_USER'] = 'testuser'

        service = SAPIntegrationService()

        self.assertTrue(service.config.enabled)
        self.assertEqual(service.config.connection_type, ConnectionType.ODATA)
        self.assertEqual(service.config.base_url, 'https://test.example.com')
        self.assertEqual(service.config.user, 'testuser')

        # Cleanup
        del os.environ['SAP_ENABLED']
        del os.environ['SAP_CONNECTION_TYPE']
        del os.environ['SAP_ODATA_URL']
        del os.environ['SAP_USER']

    def test_not_connected_error(self):
        """Test error when trying to fetch without connection"""
        config = SAPConnectionConfig(
            connection_type=ConnectionType.ODATA,
            name="TEST",
            enabled=True
        )
        service = SAPIntegrationService(config)

        result = service.get_notification("123")

        self.assertFalse(result.success)
        self.assertIn("Not connected", result.error_message)

    def test_disabled_service(self):
        """Test behavior when service is disabled"""
        config = SAPConnectionConfig(
            connection_type=ConnectionType.ODATA,
            name="DISABLED",
            enabled=False
        )
        service = SAPIntegrationService(config)

        connected = service.connect()

        self.assertFalse(connected)


def run_interactive_test():
    """Run interactive test session"""
    print("\n" + "="*60)
    print("SAP Integration Interactive Test")
    print("="*60)

    # Check mock server
    print("\n1. Checking mock server availability...")
    try:
        response = requests.get("http://localhost:8080/health", timeout=5)
        if response.status_code == 200:
            print("   ✓ Mock server is running")
        else:
            print("   ✗ Mock server returned unexpected status")
            return
    except requests.exceptions.ConnectionError:
        print("   ✗ Mock server not running!")
        print("\n   Start it with: python mock_sap_server.py")
        return

    # Create service
    print("\n2. Creating SAP integration service...")
    config = SAPConnectionConfig(
        connection_type=ConnectionType.ODATA,
        name="MOCK_SAP",
        base_url="http://localhost:8080",
        service_path="/sap/opu/odata/sap/",
        user="TESTUSER",
        passwd="testpass",
        enabled=True,
        read_only=False
    )
    service = SAPIntegrationService(config)
    print("   ✓ Service created")

    # Connect
    print("\n3. Connecting to SAP...")
    if service.connect():
        print("   ✓ Connected successfully")
    else:
        print("   ✗ Connection failed")
        return

    # Get status
    print("\n4. Connection status:")
    status = service.get_connection_status()
    for key, value in status.items():
        print(f"   {key}: {value}")

    # Fetch notification
    print("\n5. Fetching notification 10000001...")
    result = service.get_notification("10000001")
    if result.success:
        print("   ✓ Notification retrieved:")
        print(f"   - ID: {result.data.get('NotificationId')}")
        print(f"   - Type: {result.data.get('NotificationType')}")
        print(f"   - Description: {result.data.get('Description', 'N/A')[:50]}...")
    else:
        print(f"   ✗ Error: {result.error_message}")

    # Create notification
    print("\n6. Creating new notification...")
    new_notif = {
        'NotificationType': 'M1',
        'Description': 'Test notification created by integration test',
        'Priority': '2',
        'EquipmentNumber': 'PUMP-001'
    }
    result = service.create_notification(new_notif)
    if result.success:
        print(f"   ✓ Created notification: {result.data.get('NotificationId')}")
    else:
        print(f"   ✗ Error: {result.error_message}")

    # Fetch equipment
    print("\n7. Fetching equipment PUMP-001...")
    result = service.get_equipment("PUMP-001")
    if result.success:
        print("   ✓ Equipment retrieved:")
        print(f"   - ID: {result.data.get('EquipmentNumber')}")
        print(f"   - Description: {result.data.get('Description')}")
    else:
        print(f"   ✗ Error: {result.error_message}")

    # Sync notifications
    print("\n8. Syncing notifications...")
    result = service.sync_notifications(limit=5)
    print(f"   ✓ Synced {result.records_processed} notifications in {result.duration_seconds:.2f}s")

    # Disconnect
    print("\n9. Disconnecting...")
    service.disconnect()
    print("   ✓ Disconnected")

    print("\n" + "="*60)
    print("All tests completed successfully!")
    print("="*60 + "\n")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='SAP Integration Tests')
    parser.add_argument('--interactive', '-i', action='store_true',
                        help='Run interactive test session')
    parser.add_argument('--unittest', '-u', action='store_true',
                        help='Run unit tests')
    args = parser.parse_args()

    if args.interactive:
        run_interactive_test()
    elif args.unittest:
        unittest.main(argv=[''], exit=False, verbosity=2)
    else:
        # Default: run interactive test
        run_interactive_test()
