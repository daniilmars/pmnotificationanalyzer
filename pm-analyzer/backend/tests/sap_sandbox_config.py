"""
SAP API Business Hub Sandbox Configuration

SAP provides free sandbox APIs for testing. This module configures
the connection to real SAP OData services with sample data.

Setup:
1. Go to https://api.sap.com
2. Create a free account
3. Find the API you want to test
4. Get your API Key from the sandbox
5. Set SAP_API_KEY environment variable

Available Sandbox APIs for PM:
- Plant Maintenance Notification API
- Plant Maintenance Order API
- Equipment API
- Functional Location API
"""

import os
from dataclasses import dataclass
from typing import Optional, Dict, Any
import requests


@dataclass
class SAPSandboxConfig:
    """Configuration for SAP API Business Hub Sandbox"""

    # SAP API Business Hub base URL
    BASE_URL = "https://sandbox.api.sap.com"

    # Available PM-related APIs (S/4HANA Cloud)
    APIS = {
        # Maintenance Notification
        'notification': {
            'path': '/s4hanacloud/sap/opu/odata/sap/API_MAINTNOTIFICATION',
            'name': 'Maintenance Notification API',
            'entity_set': 'MaintenanceNotification'
        },
        # Maintenance Order
        'order': {
            'path': '/s4hanacloud/sap/opu/odata/sap/API_MAINTENANCEORDER',
            'name': 'Maintenance Order API',
            'entity_set': 'MaintenanceOrder'
        },
        # Equipment
        'equipment': {
            'path': '/s4hanacloud/sap/opu/odata/sap/API_EQUIPMENT',
            'name': 'Equipment API',
            'entity_set': 'Equipment'
        },
        # Functional Location
        'functional_location': {
            'path': '/s4hanacloud/sap/opu/odata/sap/API_FUNCTIONALLOCATION',
            'name': 'Functional Location API',
            'entity_set': 'FunctionalLocation'
        },
        # Measuring Point
        'measuring_point': {
            'path': '/s4hanacloud/sap/opu/odata/sap/API_MEASURINGPOINT',
            'name': 'Measuring Point API',
            'entity_set': 'MeasuringPoint'
        },
        # Bill of Material (for equipment BOM)
        'bom': {
            'path': '/s4hanacloud/sap/opu/odata/sap/API_BILL_OF_MATERIAL_SRV',
            'name': 'Bill of Material API',
            'entity_set': 'MaterialBOM'
        }
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('SAP_API_KEY', '')
        self.session = requests.Session()
        self._configure_session()

    def _configure_session(self):
        """Configure session with API key"""
        self.session.headers.update({
            'APIKey': self.api_key,
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })

    def get_api_url(self, api_name: str) -> str:
        """Get full URL for an API"""
        if api_name not in self.APIS:
            raise ValueError(f"Unknown API: {api_name}")
        return f"{self.BASE_URL}{self.APIS[api_name]['path']}"

    def test_connection(self) -> Dict[str, Any]:
        """Test connection to SAP API Hub"""
        results = {}

        for api_name, api_config in self.APIS.items():
            url = f"{self.BASE_URL}{api_config['path']}/$metadata"
            try:
                response = self.session.get(url, timeout=10)
                results[api_name] = {
                    'name': api_config['name'],
                    'status': response.status_code,
                    'available': response.status_code == 200
                }
            except Exception as e:
                results[api_name] = {
                    'name': api_config['name'],
                    'status': 'error',
                    'available': False,
                    'error': str(e)
                }

        return results

    def fetch_notifications(self, top: int = 10) -> Dict[str, Any]:
        """Fetch maintenance notifications from sandbox"""
        url = f"{self.get_api_url('notification')}/MaintenanceNotification"
        params = {
            '$top': top,
            '$format': 'json'
        }

        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def fetch_notification(self, notification_id: str) -> Dict[str, Any]:
        """Fetch single notification"""
        url = f"{self.get_api_url('notification')}/MaintenanceNotification('{notification_id}')"

        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.json()

    def fetch_equipment(self, top: int = 10) -> Dict[str, Any]:
        """Fetch equipment from sandbox"""
        url = f"{self.get_api_url('equipment')}/Equipment"
        params = {
            '$top': top,
            '$format': 'json'
        }

        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def fetch_orders(self, top: int = 10) -> Dict[str, Any]:
        """Fetch maintenance orders from sandbox"""
        url = f"{self.get_api_url('order')}/MaintenanceOrder"
        params = {
            '$top': top,
            '$format': 'json'
        }

        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()


def get_api_key_instructions():
    """Print instructions for getting SAP API key"""
    return """
╔══════════════════════════════════════════════════════════════════╗
║         How to Get Your SAP API Business Hub API Key             ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  1. Go to: https://api.sap.com                                   ║
║                                                                   ║
║  2. Click "Log On" and create a free account                     ║
║     (or use your existing SAP account)                           ║
║                                                                   ║
║  3. Search for "Maintenance Notification" API                    ║
║                                                                   ║
║  4. Click on the API, then go to "Try Out" tab                  ║
║                                                                   ║
║  5. Click "Show API Key" - copy this value                       ║
║                                                                   ║
║  6. Set the environment variable:                                 ║
║     export SAP_API_KEY="your-api-key-here"                       ║
║                                                                   ║
║  Available APIs to explore:                                       ║
║  • Maintenance Notification (API_MAINTNOTIFICATION)              ║
║  • Maintenance Order (API_MAINTENANCEORDER)                      ║
║  • Equipment (API_EQUIPMENT)                                      ║
║  • Functional Location (API_FUNCTIONALLOCATION)                  ║
║                                                                   ║
╚══════════════════════════════════════════════════════════════════╝
"""


if __name__ == '__main__':
    import json

    print(get_api_key_instructions())

    api_key = os.environ.get('SAP_API_KEY', '')

    if not api_key:
        print("\n⚠️  SAP_API_KEY not set. Set it to test the sandbox APIs.")
        print("   export SAP_API_KEY='your-key-here'\n")
    else:
        print(f"\n✓ API Key found: {api_key[:8]}...{api_key[-4:]}\n")

        config = SAPSandboxConfig(api_key)

        print("Testing API connections...\n")
        results = config.test_connection()

        for api, status in results.items():
            icon = "✓" if status['available'] else "✗"
            print(f"  {icon} {status['name']}: {status['status']}")

        # Try to fetch data
        print("\nFetching sample data...\n")

        try:
            notifications = config.fetch_notifications(top=3)
            print("Maintenance Notifications:")
            print(json.dumps(notifications.get('d', {}).get('results', [])[:2], indent=2))
        except Exception as e:
            print(f"  Error fetching notifications: {e}")
