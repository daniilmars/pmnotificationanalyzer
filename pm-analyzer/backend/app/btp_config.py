"""
SAP BTP Configuration Module

Handles Cloud Foundry environment detection and service binding extraction
for SAP BTP deployment including:
- XSUAA (Authentication)
- Destination Service (SAP System connectivity)
- Connectivity Service (Cloud Connector)
- Database Service (PostgreSQL/HANA)
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class XSUAAConfig:
    """XSUAA service configuration"""
    clientid: str
    clientsecret: str
    url: str
    xsappname: str
    identityzone: str
    verificationkey: str = ""
    uaadomain: str = ""


@dataclass
class DestinationConfig:
    """Destination service configuration"""
    uri: str
    clientid: str
    clientsecret: str
    url: str


@dataclass
class DatabaseConfig:
    """Database service configuration"""
    uri: str
    hostname: str
    port: int
    dbname: str
    username: str
    password: str


def is_cf_environment() -> bool:
    """Check if running in Cloud Foundry environment"""
    return 'VCAP_SERVICES' in os.environ or 'VCAP_APPLICATION' in os.environ


def get_vcap_services() -> Dict[str, Any]:
    """Get VCAP_SERVICES environment variable as dictionary"""
    vcap_services = os.environ.get('VCAP_SERVICES', '{}')
    try:
        return json.loads(vcap_services)
    except json.JSONDecodeError:
        logger.error("Failed to parse VCAP_SERVICES")
        return {}


def get_vcap_application() -> Dict[str, Any]:
    """Get VCAP_APPLICATION environment variable as dictionary"""
    vcap_app = os.environ.get('VCAP_APPLICATION', '{}')
    try:
        return json.loads(vcap_app)
    except json.JSONDecodeError:
        logger.error("Failed to parse VCAP_APPLICATION")
        return {}


def get_xsuaa_config() -> Optional[XSUAAConfig]:
    """Extract XSUAA configuration from VCAP_SERVICES"""
    services = get_vcap_services()

    # Look for xsuaa service
    xsuaa_services = services.get('xsuaa', [])
    if not xsuaa_services:
        logger.warning("No XSUAA service bound")
        return None

    credentials = xsuaa_services[0].get('credentials', {})

    return XSUAAConfig(
        clientid=credentials.get('clientid', ''),
        clientsecret=credentials.get('clientsecret', ''),
        url=credentials.get('url', ''),
        xsappname=credentials.get('xsappname', ''),
        identityzone=credentials.get('identityzone', ''),
        verificationkey=credentials.get('verificationkey', ''),
        uaadomain=credentials.get('uaadomain', '')
    )


def get_destination_config() -> Optional[DestinationConfig]:
    """Extract Destination service configuration from VCAP_SERVICES"""
    services = get_vcap_services()

    # Look for destination service
    dest_services = services.get('destination', [])
    if not dest_services:
        logger.warning("No Destination service bound")
        return None

    credentials = dest_services[0].get('credentials', {})

    return DestinationConfig(
        uri=credentials.get('uri', ''),
        clientid=credentials.get('clientid', ''),
        clientsecret=credentials.get('clientsecret', ''),
        url=credentials.get('url', '')
    )


def get_database_config() -> Optional[DatabaseConfig]:
    """Extract database configuration from VCAP_SERVICES"""
    services = get_vcap_services()

    # Check for PostgreSQL
    pg_services = services.get('postgresql-db', []) or services.get('postgresql', [])
    if pg_services:
        credentials = pg_services[0].get('credentials', {})
        return DatabaseConfig(
            uri=credentials.get('uri', ''),
            hostname=credentials.get('hostname', ''),
            port=int(credentials.get('port', 5432)),
            dbname=credentials.get('dbname', ''),
            username=credentials.get('username', ''),
            password=credentials.get('password', '')
        )

    # Check for HANA
    hana_services = services.get('hana', [])
    if hana_services:
        credentials = hana_services[0].get('credentials', {})
        return DatabaseConfig(
            uri=credentials.get('url', ''),
            hostname=credentials.get('host', ''),
            port=int(credentials.get('port', 443)),
            dbname=credentials.get('schema', ''),
            username=credentials.get('user', ''),
            password=credentials.get('password', '')
        )

    logger.warning("No database service bound")
    return None


def get_connectivity_config() -> Dict[str, Any]:
    """Extract Connectivity service configuration"""
    services = get_vcap_services()

    conn_services = services.get('connectivity', [])
    if not conn_services:
        return {}

    return conn_services[0].get('credentials', {})


async def fetch_destination(destination_name: str) -> Optional[Dict[str, Any]]:
    """
    Fetch destination configuration from SAP BTP Destination Service.

    This retrieves the full destination config including credentials
    for connecting to SAP systems.
    """
    import aiohttp

    dest_config = get_destination_config()
    xsuaa_config = get_xsuaa_config()

    if not dest_config or not xsuaa_config:
        logger.error("Missing destination or XSUAA configuration")
        return None

    try:
        # Get OAuth token from XSUAA
        async with aiohttp.ClientSession() as session:
            # Token request
            token_url = f"{xsuaa_config.url}/oauth/token"
            token_data = {
                'grant_type': 'client_credentials',
                'client_id': dest_config.clientid,
                'client_secret': dest_config.clientsecret
            }

            async with session.post(token_url, data=token_data) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to get OAuth token: {resp.status}")
                    return None
                token_response = await resp.json()
                access_token = token_response['access_token']

            # Fetch destination
            dest_url = f"{dest_config.uri}/destination-configuration/v1/destinations/{destination_name}"
            headers = {'Authorization': f'Bearer {access_token}'}

            async with session.get(dest_url, headers=headers) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to fetch destination: {resp.status}")
                    return None
                return await resp.json()

    except Exception as e:
        logger.exception(f"Error fetching destination: {e}")
        return None


def get_destination_sync(destination_name: str) -> Optional[Dict[str, Any]]:
    """
    Synchronous version of fetch_destination using requests library.
    """
    import requests

    dest_config = get_destination_config()
    xsuaa_config = get_xsuaa_config()

    if not dest_config or not xsuaa_config:
        logger.error("Missing destination or XSUAA configuration")
        return None

    try:
        # Get OAuth token from XSUAA
        token_url = f"{xsuaa_config.url}/oauth/token"
        token_data = {
            'grant_type': 'client_credentials',
            'client_id': dest_config.clientid,
            'client_secret': dest_config.clientsecret
        }

        token_resp = requests.post(token_url, data=token_data, timeout=30)
        token_resp.raise_for_status()
        access_token = token_resp.json()['access_token']

        # Fetch destination
        dest_url = f"{dest_config.uri}/destination-configuration/v1/destinations/{destination_name}"
        headers = {'Authorization': f'Bearer {access_token}'}

        dest_resp = requests.get(dest_url, headers=headers, timeout=30)
        dest_resp.raise_for_status()

        return dest_resp.json()

    except Exception as e:
        logger.exception(f"Error fetching destination: {e}")
        return None


def configure_sap_from_destination(destination_name: str = 'SAP_PM_SYSTEM') -> Dict[str, str]:
    """
    Configure SAP integration settings from BTP destination.

    Returns environment variable dict that can be used to configure
    the SAP integration service.
    """
    destination = get_destination_sync(destination_name)

    if not destination:
        logger.warning(f"Destination '{destination_name}' not found")
        return {}

    dest_config = destination.get('destinationConfiguration', {})
    auth_tokens = destination.get('authTokens', [])

    env_config = {
        'SAP_ODATA_URL': dest_config.get('URL', ''),
        'SAP_USER': dest_config.get('User', ''),
        'SAP_AUTH_TYPE': dest_config.get('Authentication', 'BasicAuthentication'),
    }

    # Handle different authentication types
    if dest_config.get('Authentication') == 'BasicAuthentication':
        env_config['SAP_PASSWORD'] = dest_config.get('Password', '')
    elif auth_tokens:
        # OAuth or other token-based auth
        env_config['SAP_TOKEN'] = auth_tokens[0].get('value', '')
        env_config['SAP_TOKEN_TYPE'] = auth_tokens[0].get('type', 'Bearer')

    # Check for Cloud Connector proxy
    if dest_config.get('ProxyType') == 'OnPremise':
        conn_config = get_connectivity_config()
        if conn_config:
            env_config['SAP_PROXY_HOST'] = conn_config.get('onpremise_proxy_host', '')
            env_config['SAP_PROXY_PORT'] = str(conn_config.get('onpremise_proxy_port', ''))

    return env_config


def get_application_url() -> str:
    """Get the application URL from VCAP_APPLICATION"""
    vcap_app = get_vcap_application()
    uris = vcap_app.get('application_uris', [])
    if uris:
        return f"https://{uris[0]}"
    return ""


def get_application_name() -> str:
    """Get the application name from VCAP_APPLICATION"""
    vcap_app = get_vcap_application()
    return vcap_app.get('application_name', 'pm-analyzer')


def initialize_btp_config():
    """
    Initialize BTP configuration on application startup.

    This should be called early in the application initialization
    to configure services based on bound BTP services.
    """
    if not is_cf_environment():
        logger.info("Not running in Cloud Foundry environment")
        return

    logger.info("Initializing SAP BTP configuration...")

    # Log bound services
    services = get_vcap_services()
    for service_type in services.keys():
        logger.info(f"  Bound service: {service_type}")

    # Configure SAP from destination if available
    sap_config = configure_sap_from_destination()
    for key, value in sap_config.items():
        if key not in os.environ:
            os.environ[key] = value
            logger.info(f"  Set {key} from destination")

    logger.info("BTP configuration initialized")
