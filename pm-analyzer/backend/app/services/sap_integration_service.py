"""
SAP Integration Service for PM Notification Analyzer

Provides connectivity to SAP systems via:
- SAP RFC/BAPI calls (using pyrfc library)
- SAP OData services
- SAP IDoc processing

Supports both real-time data retrieval and batch synchronization.
"""

import os
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json

logger = logging.getLogger(__name__)

# Check for RFC library availability
try:
    from pyrfc import Connection
    RFC_AVAILABLE = True
except ImportError:
    RFC_AVAILABLE = False
    logger.warning("pyrfc not available - RFC connectivity disabled")

# Check for requests library (for OData)
try:
    import requests
    from requests.auth import HTTPBasicAuth
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("requests library not available - OData connectivity disabled")


class ConnectionType(Enum):
    """SAP connection types"""
    RFC = "rfc"
    ODATA = "odata"
    REST = "rest"


class SyncDirection(Enum):
    """Data synchronization direction"""
    INBOUND = "inbound"    # SAP -> Local
    OUTBOUND = "outbound"  # Local -> SAP
    BIDIRECTIONAL = "bidirectional"


@dataclass
class SAPConnectionConfig:
    """Configuration for SAP connection"""
    connection_type: ConnectionType
    name: str
    description: str = ""

    # RFC Configuration
    ashost: str = ""           # Application server host
    sysnr: str = "00"          # System number
    client: str = "100"        # SAP client
    user: str = ""             # SAP user
    passwd: str = ""           # Password (should be stored securely)
    lang: str = "EN"           # Login language

    # OData Configuration
    base_url: str = ""         # OData service base URL
    service_path: str = ""     # Service path (e.g., /sap/opu/odata/sap/)
    auth_type: str = "basic"   # Authentication type

    # Connection pool settings
    pool_size: int = 5
    timeout: int = 30

    # Feature flags
    enabled: bool = True
    read_only: bool = True     # Safety flag for production


@dataclass
class SyncResult:
    """Result of a synchronization operation"""
    success: bool
    records_processed: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_failed: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class BAPIResult:
    """Result of a BAPI call"""
    success: bool
    data: Any = None
    return_messages: List[Dict[str, str]] = field(default_factory=list)
    error_message: str = ""


class SAPIntegrationService:
    """
    Service for SAP system integration.

    Provides methods for:
    - Reading notifications from SAP (BAPI_ALM_NOTIF_GET_DETAIL)
    - Creating notifications in SAP (BAPI_ALM_NOTIF_CREATE)
    - Reading/Creating work orders (BAPI_ALM_ORDER_*)
    - Reading equipment master data
    - Reading functional locations
    - Change document retrieval
    """

    def __init__(self, config: Optional[SAPConnectionConfig] = None):
        """Initialize SAP integration service"""
        self.config = config or self._load_config_from_env()
        self._rfc_connection = None
        self._session = None

    def _load_config_from_env(self) -> SAPConnectionConfig:
        """Load configuration from environment variables"""
        conn_type = os.environ.get('SAP_CONNECTION_TYPE', 'odata')

        return SAPConnectionConfig(
            connection_type=ConnectionType(conn_type),
            name=os.environ.get('SAP_SYSTEM_NAME', 'DEFAULT'),
            description=os.environ.get('SAP_SYSTEM_DESC', 'SAP System'),
            # RFC settings
            ashost=os.environ.get('SAP_ASHOST', ''),
            sysnr=os.environ.get('SAP_SYSNR', '00'),
            client=os.environ.get('SAP_CLIENT', '100'),
            user=os.environ.get('SAP_USER', ''),
            passwd=os.environ.get('SAP_PASSWORD', ''),
            lang=os.environ.get('SAP_LANG', 'EN'),
            # OData settings
            base_url=os.environ.get('SAP_ODATA_URL', ''),
            service_path=os.environ.get('SAP_ODATA_PATH', '/sap/opu/odata/sap/'),
            auth_type=os.environ.get('SAP_AUTH_TYPE', 'basic'),
            # General settings
            timeout=int(os.environ.get('SAP_TIMEOUT', '30')),
            enabled=os.environ.get('SAP_ENABLED', 'false').lower() == 'true',
            read_only=os.environ.get('SAP_READ_ONLY', 'true').lower() == 'true'
        )

    # ==========================================
    # Connection Management
    # ==========================================

    def connect(self) -> bool:
        """Establish connection to SAP system"""
        if not self.config.enabled:
            logger.warning("SAP integration is disabled")
            return False

        try:
            if self.config.connection_type == ConnectionType.RFC:
                return self._connect_rfc()
            elif self.config.connection_type == ConnectionType.ODATA:
                return self._connect_odata()
            else:
                logger.error(f"Unsupported connection type: {self.config.connection_type}")
                return False
        except Exception as e:
            logger.exception(f"Failed to connect to SAP: {e}")
            return False

    def _connect_rfc(self) -> bool:
        """Establish RFC connection"""
        if not RFC_AVAILABLE:
            logger.error("pyrfc library not installed")
            return False

        try:
            self._rfc_connection = Connection(
                ashost=self.config.ashost,
                sysnr=self.config.sysnr,
                client=self.config.client,
                user=self.config.user,
                passwd=self.config.passwd,
                lang=self.config.lang
            )
            logger.info(f"RFC connection established to {self.config.name}")
            return True
        except Exception as e:
            logger.exception(f"RFC connection failed: {e}")
            return False

    def _connect_odata(self) -> bool:
        """Establish OData session"""
        if not REQUESTS_AVAILABLE:
            logger.error("requests library not installed")
            return False

        try:
            self._session = requests.Session()
            self._session.auth = HTTPBasicAuth(
                self.config.user,
                self.config.passwd
            )
            self._session.headers.update({
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            })

            # Test connection with metadata request
            test_url = f"{self.config.base_url}{self.config.service_path}$metadata"
            response = self._session.get(test_url, timeout=self.config.timeout)
            response.raise_for_status()

            logger.info(f"OData connection established to {self.config.name}")
            return True
        except Exception as e:
            logger.exception(f"OData connection failed: {e}")
            return False

    def disconnect(self):
        """Close SAP connection"""
        if self._rfc_connection:
            self._rfc_connection.close()
            self._rfc_connection = None

        if self._session:
            self._session.close()
            self._session = None

        logger.info("SAP connection closed")

    def is_connected(self) -> bool:
        """Check if connection is active"""
        if self.config.connection_type == ConnectionType.RFC:
            return self._rfc_connection is not None
        elif self.config.connection_type == ConnectionType.ODATA:
            return self._session is not None
        return False

    def get_connection_status(self) -> Dict[str, Any]:
        """Get detailed connection status"""
        return {
            'enabled': self.config.enabled,
            'connection_type': self.config.connection_type.value,
            'system_name': self.config.name,
            'is_connected': self.is_connected(),
            'read_only': self.config.read_only,
            'rfc_available': RFC_AVAILABLE,
            'odata_available': REQUESTS_AVAILABLE,
            'base_url': self.config.base_url if self.config.connection_type == ConnectionType.ODATA else None,
            'host': self.config.ashost if self.config.connection_type == ConnectionType.RFC else None
        }

    # ==========================================
    # Notification Operations (BAPI)
    # ==========================================

    def get_notification(self, notification_number: str) -> BAPIResult:
        """
        Get notification details from SAP.

        Uses BAPI_ALM_NOTIF_GET_DETAIL
        """
        if not self.is_connected():
            return BAPIResult(success=False, error_message="Not connected to SAP")

        try:
            if self.config.connection_type == ConnectionType.RFC:
                return self._get_notification_rfc(notification_number)
            else:
                return self._get_notification_odata(notification_number)
        except Exception as e:
            logger.exception(f"Error getting notification {notification_number}")
            return BAPIResult(success=False, error_message=str(e))

    def _get_notification_rfc(self, notification_number: str) -> BAPIResult:
        """Get notification via RFC/BAPI"""
        result = self._rfc_connection.call(
            'BAPI_ALM_NOTIF_GET_DETAIL',
            NUMBER=notification_number.zfill(12)
        )

        # Check return messages
        return_messages = result.get('RETURN', [])
        errors = [msg for msg in return_messages if msg.get('TYPE') in ('E', 'A')]

        if errors:
            return BAPIResult(
                success=False,
                return_messages=return_messages,
                error_message=errors[0].get('MESSAGE', 'Unknown error')
            )

        # Map SAP fields to our format
        header = result.get('NOTIFHEADER', {})
        notification_data = {
            'NotificationId': header.get('NOTIF_NO', '').lstrip('0'),
            'NotificationType': header.get('NOTIF_TYPE', ''),
            'Description': header.get('SHORT_TEXT', ''),
            'Priority': header.get('PRIORITY', ''),
            'EquipmentNumber': header.get('EQUIPMENT', '').lstrip('0'),
            'FunctionalLocation': header.get('FUNCT_LOC', ''),
            'CreationDate': header.get('CREATED_ON', ''),
            'CreatedByUser': header.get('CREATED_BY', ''),
            'RequiredStart': header.get('REQ_START_DATE', ''),
            'RequiredEnd': header.get('REQ_END_DATE', ''),
            'LongText': result.get('NOTIFTEXT', {}).get('LINES', ''),
            'Items': result.get('NOTIFITEM', []),
            'Causes': result.get('NOTIFCAUS', []),
            'Activities': result.get('NOTIFACTV', [])
        }

        return BAPIResult(
            success=True,
            data=notification_data,
            return_messages=return_messages
        )

    def _get_notification_odata(self, notification_number: str) -> BAPIResult:
        """Get notification via OData"""
        url = f"{self.config.base_url}{self.config.service_path}PM_NOTIFICATION_SRV/NotificationSet('{notification_number}')"

        try:
            response = self._session.get(url, timeout=self.config.timeout)
            response.raise_for_status()

            data = response.json().get('d', {})

            notification_data = {
                'NotificationId': data.get('NotificationNo', '').lstrip('0'),
                'NotificationType': data.get('NotificationType', ''),
                'Description': data.get('NotificationText', ''),
                'Priority': data.get('Priority', ''),
                'EquipmentNumber': data.get('Equipment', '').lstrip('0'),
                'FunctionalLocation': data.get('FunctionalLocation', ''),
                'CreationDate': data.get('CreatedOn', ''),
                'CreatedByUser': data.get('CreatedBy', ''),
            }

            return BAPIResult(success=True, data=notification_data)

        except requests.HTTPError as e:
            return BAPIResult(success=False, error_message=f"HTTP Error: {e}")

    def create_notification(self, notification_data: Dict[str, Any]) -> BAPIResult:
        """
        Create a notification in SAP.

        Uses BAPI_ALM_NOTIF_CREATE
        """
        if not self.is_connected():
            return BAPIResult(success=False, error_message="Not connected to SAP")

        if self.config.read_only:
            return BAPIResult(success=False, error_message="Connection is read-only")

        try:
            if self.config.connection_type == ConnectionType.RFC:
                return self._create_notification_rfc(notification_data)
            else:
                return self._create_notification_odata(notification_data)
        except Exception as e:
            logger.exception("Error creating notification")
            return BAPIResult(success=False, error_message=str(e))

    def _create_notification_rfc(self, notification_data: Dict[str, Any]) -> BAPIResult:
        """Create notification via RFC/BAPI"""
        # Prepare BAPI parameters
        notif_header = {
            'NOTIF_TYPE': notification_data.get('NotificationType', 'M1'),
            'SHORT_TEXT': notification_data.get('Description', ''),
            'PRIORITY': notification_data.get('Priority', '4'),
            'EQUIPMENT': notification_data.get('EquipmentNumber', '').zfill(18),
            'FUNCT_LOC': notification_data.get('FunctionalLocation', ''),
        }

        result = self._rfc_connection.call(
            'BAPI_ALM_NOTIF_CREATE',
            NOTIF_TYPE=notif_header['NOTIF_TYPE'],
            NOTIFHEADER=notif_header
        )

        # Check for errors
        return_messages = result.get('RETURN', [])
        errors = [msg for msg in return_messages if msg.get('TYPE') in ('E', 'A')]

        if errors:
            return BAPIResult(
                success=False,
                return_messages=return_messages,
                error_message=errors[0].get('MESSAGE', 'Unknown error')
            )

        # Get created notification number
        notif_number = result.get('NOTIFHEADER', {}).get('NOTIF_NO', '')

        # Commit the transaction
        self._rfc_connection.call('BAPI_TRANSACTION_COMMIT', WAIT='X')

        return BAPIResult(
            success=True,
            data={'NotificationId': notif_number.lstrip('0')},
            return_messages=return_messages
        )

    def _create_notification_odata(self, notification_data: Dict[str, Any]) -> BAPIResult:
        """Create notification via OData"""
        url = f"{self.config.base_url}{self.config.service_path}PM_NOTIFICATION_SRV/NotificationSet"

        payload = {
            'NotificationType': notification_data.get('NotificationType', 'M1'),
            'NotificationText': notification_data.get('Description', ''),
            'Priority': notification_data.get('Priority', '4'),
            'Equipment': notification_data.get('EquipmentNumber', ''),
            'FunctionalLocation': notification_data.get('FunctionalLocation', ''),
        }

        try:
            response = self._session.post(url, json=payload, timeout=self.config.timeout)
            response.raise_for_status()

            data = response.json().get('d', {})

            return BAPIResult(
                success=True,
                data={'NotificationId': data.get('NotificationNo', '').lstrip('0')}
            )

        except requests.HTTPError as e:
            return BAPIResult(success=False, error_message=f"HTTP Error: {e}")

    # ==========================================
    # Work Order Operations
    # ==========================================

    def get_work_order(self, order_number: str) -> BAPIResult:
        """
        Get work order details from SAP.

        Uses BAPI_ALM_ORDER_GET_DETAIL
        """
        if not self.is_connected():
            return BAPIResult(success=False, error_message="Not connected to SAP")

        try:
            if self.config.connection_type == ConnectionType.RFC:
                result = self._rfc_connection.call(
                    'BAPI_ALM_ORDER_GET_DETAIL',
                    NUMBER=order_number.zfill(12)
                )

                return_messages = result.get('RETURN', [])
                errors = [msg for msg in return_messages if msg.get('TYPE') in ('E', 'A')]

                if errors:
                    return BAPIResult(
                        success=False,
                        return_messages=return_messages,
                        error_message=errors[0].get('MESSAGE', 'Unknown error')
                    )

                header = result.get('ES_HEADER', {})
                order_data = {
                    'OrderNumber': header.get('ORDERID', '').lstrip('0'),
                    'OrderType': header.get('ORDER_TYPE', ''),
                    'Description': header.get('SHORT_TEXT', ''),
                    'NotificationNumber': header.get('NOTIF_NO', '').lstrip('0'),
                    'Equipment': header.get('EQUIPMENT', '').lstrip('0'),
                    'FunctionalLocation': header.get('FUNCT_LOC', ''),
                    'BasicStartDate': header.get('BASIC_START', ''),
                    'BasicEndDate': header.get('BASIC_FIN', ''),
                    'Operations': result.get('ET_OPERATIONS', []),
                    'Components': result.get('ET_COMPONENTS', [])
                }

                return BAPIResult(success=True, data=order_data, return_messages=return_messages)

            else:
                # OData implementation
                url = f"{self.config.base_url}{self.config.service_path}PM_ORDER_SRV/OrderSet('{order_number}')"
                response = self._session.get(url, timeout=self.config.timeout)
                response.raise_for_status()
                data = response.json().get('d', {})

                return BAPIResult(success=True, data=data)

        except Exception as e:
            logger.exception(f"Error getting work order {order_number}")
            return BAPIResult(success=False, error_message=str(e))

    # ==========================================
    # Equipment Master Data
    # ==========================================

    def get_equipment(self, equipment_number: str) -> BAPIResult:
        """Get equipment master data from SAP"""
        if not self.is_connected():
            return BAPIResult(success=False, error_message="Not connected to SAP")

        try:
            if self.config.connection_type == ConnectionType.RFC:
                result = self._rfc_connection.call(
                    'BAPI_EQUI_GETDETAIL',
                    EQUIPMENT=equipment_number.zfill(18)
                )

                return_messages = result.get('RETURN', [])
                errors = [msg for msg in return_messages if msg.get('TYPE') in ('E', 'A')]

                if errors:
                    return BAPIResult(
                        success=False,
                        return_messages=return_messages,
                        error_message=errors[0].get('MESSAGE', 'Unknown error')
                    )

                general = result.get('DATA_GENERAL', {})
                equipment_data = {
                    'EquipmentNumber': general.get('EQUIPMENT', '').lstrip('0'),
                    'Description': general.get('DESCRIPT', ''),
                    'Category': general.get('EQUICATGRY', ''),
                    'Manufacturer': general.get('MANFACTURE', ''),
                    'Model': general.get('MODELNUM', ''),
                    'FunctionalLocation': general.get('FUNCT_LOC', ''),
                    'StartupDate': general.get('START_FROM', ''),
                    'AcquisitionDate': general.get('ACQUISVAL_DATE', '')
                }

                return BAPIResult(success=True, data=equipment_data, return_messages=return_messages)

            else:
                # OData implementation
                url = f"{self.config.base_url}{self.config.service_path}EQUIPMENT_SRV/EquipmentSet('{equipment_number}')"
                response = self._session.get(url, timeout=self.config.timeout)
                response.raise_for_status()
                data = response.json().get('d', {})

                return BAPIResult(success=True, data=data)

        except Exception as e:
            logger.exception(f"Error getting equipment {equipment_number}")
            return BAPIResult(success=False, error_message=str(e))

    # ==========================================
    # Batch Synchronization
    # ==========================================

    def sync_notifications(self, date_from: Optional[str] = None,
                          date_to: Optional[str] = None,
                          notification_type: Optional[str] = None,
                          limit: int = 1000) -> SyncResult:
        """
        Synchronize notifications from SAP to local database.

        Args:
            date_from: Start date (YYYYMMDD)
            date_to: End date (YYYYMMDD)
            notification_type: Filter by notification type
            limit: Maximum records to sync
        """
        start_time = datetime.now()
        result = SyncResult(success=False)

        if not self.is_connected():
            result.errors.append("Not connected to SAP")
            return result

        try:
            # Build selection criteria
            if self.config.connection_type == ConnectionType.RFC:
                notifications = self._sync_notifications_rfc(
                    date_from, date_to, notification_type, limit
                )
            else:
                notifications = self._sync_notifications_odata(
                    date_from, date_to, notification_type, limit
                )

            result.records_processed = len(notifications)
            result.success = True

            # Here you would typically insert/update local database
            # This is a placeholder for the actual sync logic

            result.duration_seconds = (datetime.now() - start_time).total_seconds()
            logger.info(f"Synced {result.records_processed} notifications in {result.duration_seconds:.2f}s")

            return result

        except Exception as e:
            result.errors.append(str(e))
            result.duration_seconds = (datetime.now() - start_time).total_seconds()
            logger.exception("Notification sync failed")
            return result

    def _sync_notifications_rfc(self, date_from, date_to, notification_type, limit) -> List[Dict]:
        """Sync notifications via RFC"""
        # Build selection range
        i_date_range = []
        if date_from:
            i_date_range.append({
                'SIGN': 'I',
                'OPTION': 'GE',
                'LOW': date_from
            })
        if date_to:
            i_date_range.append({
                'SIGN': 'I',
                'OPTION': 'LE',
                'LOW': date_to
            })

        i_notif_type = []
        if notification_type:
            i_notif_type.append({
                'SIGN': 'I',
                'OPTION': 'EQ',
                'LOW': notification_type
            })

        result = self._rfc_connection.call(
            'BAPI_ALM_NOTIF_LIST',
            NOTIFTYPE_RA=i_notif_type if i_notif_type else None,
            CREATED_ON_RA=i_date_range if i_date_range else None,
            MAXROWS=limit
        )

        return result.get('NOTIFLIST', [])

    def _sync_notifications_odata(self, date_from, date_to, notification_type, limit) -> List[Dict]:
        """Sync notifications via OData"""
        url = f"{self.config.base_url}{self.config.service_path}PM_NOTIFICATION_SRV/NotificationSet"

        # Build OData filter
        filters = []
        if date_from:
            filters.append(f"CreatedOn ge datetime'{date_from}T00:00:00'")
        if date_to:
            filters.append(f"CreatedOn le datetime'{date_to}T23:59:59'")
        if notification_type:
            filters.append(f"NotificationType eq '{notification_type}'")

        params = {
            '$top': limit,
            '$format': 'json'
        }
        if filters:
            params['$filter'] = ' and '.join(filters)

        response = self._session.get(url, params=params, timeout=self.config.timeout)
        response.raise_for_status()

        return response.json().get('d', {}).get('results', [])

    # ==========================================
    # Change Document Retrieval
    # ==========================================

    def get_change_documents(self, object_class: str, object_id: str,
                            date_from: Optional[str] = None,
                            date_to: Optional[str] = None) -> BAPIResult:
        """
        Retrieve change documents from SAP.

        Uses CHANGEDOCUMENT_READ_ALL
        """
        if not self.is_connected():
            return BAPIResult(success=False, error_message="Not connected to SAP")

        if self.config.connection_type != ConnectionType.RFC:
            return BAPIResult(
                success=False,
                error_message="Change document retrieval only supported via RFC"
            )

        try:
            result = self._rfc_connection.call(
                'CHANGEDOCUMENT_READ_ALL',
                I_OBJECTCLASS=object_class,
                I_OBJECTID=object_id,
                I_DATE_OF_CHANGE_FROM=date_from or '',
                I_DATE_OF_CHANGE_TO=date_to or ''
            )

            headers = result.get('ET_CDREDADD_HDR', [])
            items = result.get('ET_CDREDADD_POS', [])

            changes = []
            for header in headers:
                change_items = [
                    item for item in items
                    if item.get('CHANGENR') == header.get('CHANGENR')
                ]
                changes.append({
                    'change_number': header.get('CHANGENR'),
                    'object_class': header.get('OBJECTCLAS'),
                    'object_id': header.get('OBJECTID'),
                    'username': header.get('USERNAME'),
                    'change_date': header.get('UDATE'),
                    'change_time': header.get('UTIME'),
                    'transaction_code': header.get('TCODE'),
                    'items': change_items
                })

            return BAPIResult(success=True, data=changes)

        except Exception as e:
            logger.exception(f"Error getting change documents for {object_class}/{object_id}")
            return BAPIResult(success=False, error_message=str(e))


# Global service instance
_sap_service: Optional[SAPIntegrationService] = None


def get_sap_service() -> SAPIntegrationService:
    """Get or create SAP integration service instance"""
    global _sap_service
    if _sap_service is None:
        _sap_service = SAPIntegrationService()
    return _sap_service


def check_sap_available() -> Dict[str, Any]:
    """Check SAP integration availability"""
    return {
        'rfc_available': RFC_AVAILABLE,
        'odata_available': REQUESTS_AVAILABLE,
        'integration_enabled': os.environ.get('SAP_ENABLED', 'false').lower() == 'true'
    }
