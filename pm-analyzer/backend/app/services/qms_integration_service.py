"""
Quality Management System (QMS) Integration Service.

Provides integration with various QMS platforms to retrieve:
- Standard Operating Procedures (SOPs)
- Work Instructions
- Quality Documents
- Controlled Documents

Supported QMS platforms:
- SAP QM (via OData/RFC)
- Veeva Vault QMS (REST API)
- MasterControl (REST API)
- SharePoint (Graph API)
- Generic REST API
"""

import os
import logging
import requests
import hashlib
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
from functools import lru_cache
import base64

logger = logging.getLogger(__name__)


class QMSProvider(Enum):
    """Supported QMS providers."""
    SAP_QM = 'sap_qm'
    VEEVA_VAULT = 'veeva_vault'
    MASTERCONTROL = 'mastercontrol'
    TRACKWISE = 'trackwise'
    ETQ_RELIANCE = 'etq_reliance'
    SHAREPOINT = 'sharepoint'
    CONFLUENCE = 'confluence'
    GENERIC_REST = 'generic_rest'


class DocumentType(Enum):
    """Types of quality documents."""
    SOP = 'sop'  # Standard Operating Procedure
    WORK_INSTRUCTION = 'work_instruction'
    QUALITY_MANUAL = 'quality_manual'
    FORM = 'form'
    TEMPLATE = 'template'
    SPECIFICATION = 'specification'
    POLICY = 'policy'
    TRAINING_MATERIAL = 'training_material'


class DocumentStatus(Enum):
    """Document lifecycle status."""
    DRAFT = 'draft'
    IN_REVIEW = 'in_review'
    APPROVED = 'approved'
    EFFECTIVE = 'effective'
    SUPERSEDED = 'superseded'
    OBSOLETE = 'obsolete'


@dataclass
class QMSDocument:
    """Represents a document from a QMS."""
    document_id: str
    title: str
    document_number: str
    document_type: DocumentType
    version: str
    status: DocumentStatus
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    content_url: Optional[str] = None
    content_text: Optional[str] = None
    category: Optional[str] = None
    department: Optional[str] = None
    owner: Optional[str] = None
    last_modified: Optional[datetime] = None
    keywords: List[str] = field(default_factory=list)
    equipment_types: List[str] = field(default_factory=list)
    functional_locations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'document_id': self.document_id,
            'title': self.title,
            'document_number': self.document_number,
            'document_type': self.document_type.value,
            'version': self.version,
            'status': self.status.value,
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'content_url': self.content_url,
            'category': self.category,
            'department': self.department,
            'owner': self.owner,
            'last_modified': self.last_modified.isoformat() if self.last_modified else None,
            'keywords': self.keywords,
            'equipment_types': self.equipment_types,
            'functional_locations': self.functional_locations,
            'metadata': self.metadata
        }


@dataclass
class QMSConfig:
    """Configuration for QMS connection."""
    provider: QMSProvider
    base_url: str
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    tenant_id: Optional[str] = None  # For Azure/SharePoint
    vault_id: Optional[str] = None   # For Veeva
    timeout_seconds: int = 30
    verify_ssl: bool = True
    cache_ttl_minutes: int = 60


class QMSConnector(ABC):
    """Abstract base class for QMS connectors."""

    def __init__(self, config: QMSConfig):
        self.config = config
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._session = requests.Session()

    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the QMS."""
        pass

    @abstractmethod
    def search_documents(
        self,
        query: str = None,
        document_type: DocumentType = None,
        equipment_type: str = None,
        functional_location: str = None,
        status: DocumentStatus = DocumentStatus.EFFECTIVE,
        limit: int = 50
    ) -> List[QMSDocument]:
        """Search for documents in the QMS."""
        pass

    @abstractmethod
    def get_document(self, document_id: str) -> Optional[QMSDocument]:
        """Get a specific document by ID."""
        pass

    @abstractmethod
    def get_document_content(self, document_id: str) -> Optional[str]:
        """Get the content/body of a document."""
        pass

    def get_sops_for_equipment(self, equipment_type: str) -> List[QMSDocument]:
        """Get all effective SOPs for a specific equipment type."""
        return self.search_documents(
            document_type=DocumentType.SOP,
            equipment_type=equipment_type,
            status=DocumentStatus.EFFECTIVE
        )

    def get_sops_for_location(self, functional_location: str) -> List[QMSDocument]:
        """Get all effective SOPs for a functional location."""
        return self.search_documents(
            document_type=DocumentType.SOP,
            functional_location=functional_location,
            status=DocumentStatus.EFFECTIVE
        )


class VeevaVaultConnector(QMSConnector):
    """
    Connector for Veeva Vault QMS.

    Veeva Vault is widely used in Life Sciences for document management
    and quality management with 21 CFR Part 11 compliance.
    """

    def authenticate(self) -> bool:
        """Authenticate with Veeva Vault using username/password."""
        try:
            auth_url = f"{self.config.base_url}/api/v23.1/auth"
            response = self._session.post(
                auth_url,
                data={
                    'username': self.config.username,
                    'password': self.config.password
                },
                timeout=self.config.timeout_seconds,
                verify=self.config.verify_ssl
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('responseStatus') == 'SUCCESS':
                    self._token = data.get('sessionId')
                    # Veeva sessions typically last 20 minutes
                    self._token_expiry = datetime.utcnow() + timedelta(minutes=19)
                    self._session.headers['Authorization'] = self._token
                    logger.info("Successfully authenticated with Veeva Vault")
                    return True

            logger.error(f"Veeva authentication failed: {response.text}")
            return False

        except Exception as e:
            logger.error(f"Veeva authentication error: {e}")
            return False

    def _ensure_authenticated(self):
        """Ensure we have a valid authentication token."""
        if not self._token or (self._token_expiry and datetime.utcnow() >= self._token_expiry):
            if not self.authenticate():
                raise ConnectionError("Failed to authenticate with Veeva Vault")

    def search_documents(
        self,
        query: str = None,
        document_type: DocumentType = None,
        equipment_type: str = None,
        functional_location: str = None,
        status: DocumentStatus = DocumentStatus.EFFECTIVE,
        limit: int = 50
    ) -> List[QMSDocument]:
        """Search for documents in Veeva Vault."""
        self._ensure_authenticated()

        try:
            # Build VQL (Veeva Query Language) query
            vql_parts = ["SELECT id, name__v, document_number__v, version_id, status__v, ",
                        "type__v, subtype__v, classification__v, ",
                        "effective_date__c, expiration_date__c, owner__v, ",
                        "modified_date__v ",
                        "FROM documents ",
                        "WHERE status__v = 'Effective'"]

            if document_type == DocumentType.SOP:
                vql_parts.append("AND type__v = 'SOP'")
            elif document_type == DocumentType.WORK_INSTRUCTION:
                vql_parts.append("AND type__v = 'Work Instruction'")

            if query:
                vql_parts.append(f"AND (name__v CONTAINS '{query}' OR document_number__v CONTAINS '{query}')")

            if equipment_type:
                vql_parts.append(f"AND equipment_type__c CONTAINS '{equipment_type}'")

            if functional_location:
                vql_parts.append(f"AND functional_location__c CONTAINS '{functional_location}'")

            vql_parts.append(f"LIMIT {limit}")

            vql_query = " ".join(vql_parts)

            url = f"{self.config.base_url}/api/v23.1/query"
            response = self._session.get(
                url,
                params={'q': vql_query},
                timeout=self.config.timeout_seconds,
                verify=self.config.verify_ssl
            )

            if response.status_code == 200:
                data = response.json()
                documents = []

                for doc in data.get('data', []):
                    documents.append(QMSDocument(
                        document_id=doc.get('id'),
                        title=doc.get('name__v', ''),
                        document_number=doc.get('document_number__v', ''),
                        document_type=self._map_veeva_type(doc.get('type__v')),
                        version=doc.get('version_id', '1.0'),
                        status=self._map_veeva_status(doc.get('status__v')),
                        effective_date=self._parse_date(doc.get('effective_date__c')),
                        expiry_date=self._parse_date(doc.get('expiration_date__c')),
                        owner=doc.get('owner__v'),
                        last_modified=self._parse_date(doc.get('modified_date__v')),
                        category=doc.get('classification__v'),
                        metadata={'source': 'veeva_vault', 'subtype': doc.get('subtype__v')}
                    ))

                return documents

            logger.error(f"Veeva search failed: {response.text}")
            return []

        except Exception as e:
            logger.error(f"Veeva search error: {e}")
            return []

    def get_document(self, document_id: str) -> Optional[QMSDocument]:
        """Get a specific document from Veeva Vault."""
        self._ensure_authenticated()

        try:
            url = f"{self.config.base_url}/api/v23.1/objects/documents/{document_id}"
            response = self._session.get(
                url,
                timeout=self.config.timeout_seconds,
                verify=self.config.verify_ssl
            )

            if response.status_code == 200:
                doc = response.json().get('document', {})
                return QMSDocument(
                    document_id=document_id,
                    title=doc.get('name__v', ''),
                    document_number=doc.get('document_number__v', ''),
                    document_type=self._map_veeva_type(doc.get('type__v')),
                    version=doc.get('major_version_number__v', '1') + '.' + doc.get('minor_version_number__v', '0'),
                    status=self._map_veeva_status(doc.get('status__v')),
                    effective_date=self._parse_date(doc.get('effective_date__c')),
                    content_url=f"{self.config.base_url}/api/v23.1/objects/documents/{document_id}/file",
                    owner=doc.get('owner__v'),
                    last_modified=self._parse_date(doc.get('modified_date__v')),
                    metadata={'source': 'veeva_vault', 'full_response': doc}
                )

            return None

        except Exception as e:
            logger.error(f"Veeva get document error: {e}")
            return None

    def get_document_content(self, document_id: str) -> Optional[str]:
        """Get document content from Veeva Vault."""
        self._ensure_authenticated()

        try:
            url = f"{self.config.base_url}/api/v23.1/objects/documents/{document_id}/file"
            response = self._session.get(
                url,
                timeout=self.config.timeout_seconds,
                verify=self.config.verify_ssl
            )

            if response.status_code == 200:
                # For PDFs, we'd need to extract text
                # For now, return content type info
                content_type = response.headers.get('Content-Type', '')
                if 'text' in content_type:
                    return response.text
                else:
                    return f"[Binary content: {content_type}]"

            return None

        except Exception as e:
            logger.error(f"Veeva get content error: {e}")
            return None

    def _map_veeva_type(self, veeva_type: str) -> DocumentType:
        """Map Veeva document type to our enum."""
        type_map = {
            'SOP': DocumentType.SOP,
            'Standard Operating Procedure': DocumentType.SOP,
            'Work Instruction': DocumentType.WORK_INSTRUCTION,
            'Policy': DocumentType.POLICY,
            'Form': DocumentType.FORM,
            'Template': DocumentType.TEMPLATE,
            'Specification': DocumentType.SPECIFICATION,
            'Training': DocumentType.TRAINING_MATERIAL
        }
        return type_map.get(veeva_type, DocumentType.SOP)

    def _map_veeva_status(self, veeva_status: str) -> DocumentStatus:
        """Map Veeva status to our enum."""
        status_map = {
            'Draft': DocumentStatus.DRAFT,
            'In Review': DocumentStatus.IN_REVIEW,
            'Approved': DocumentStatus.APPROVED,
            'Effective': DocumentStatus.EFFECTIVE,
            'Superseded': DocumentStatus.SUPERSEDED,
            'Obsolete': DocumentStatus.OBSOLETE
        }
        return status_map.get(veeva_status, DocumentStatus.EFFECTIVE)

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse Veeva date string."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            return None


class MasterControlConnector(QMSConnector):
    """
    Connector for MasterControl QMS.

    MasterControl is a popular QMS in Life Sciences and Manufacturing
    with strong document control and training management.
    """

    def authenticate(self) -> bool:
        """Authenticate with MasterControl using OAuth2."""
        try:
            auth_url = f"{self.config.base_url}/oauth/token"
            response = self._session.post(
                auth_url,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': self.config.client_id,
                    'client_secret': self.config.client_secret
                },
                timeout=self.config.timeout_seconds,
                verify=self.config.verify_ssl
            )

            if response.status_code == 200:
                data = response.json()
                self._token = data.get('access_token')
                expires_in = data.get('expires_in', 3600)
                self._token_expiry = datetime.utcnow() + timedelta(seconds=expires_in - 60)
                self._session.headers['Authorization'] = f"Bearer {self._token}"
                logger.info("Successfully authenticated with MasterControl")
                return True

            logger.error(f"MasterControl authentication failed: {response.text}")
            return False

        except Exception as e:
            logger.error(f"MasterControl authentication error: {e}")
            return False

    def _ensure_authenticated(self):
        """Ensure we have a valid authentication token."""
        if not self._token or (self._token_expiry and datetime.utcnow() >= self._token_expiry):
            if not self.authenticate():
                raise ConnectionError("Failed to authenticate with MasterControl")

    def search_documents(
        self,
        query: str = None,
        document_type: DocumentType = None,
        equipment_type: str = None,
        functional_location: str = None,
        status: DocumentStatus = DocumentStatus.EFFECTIVE,
        limit: int = 50
    ) -> List[QMSDocument]:
        """Search for documents in MasterControl."""
        self._ensure_authenticated()

        try:
            params = {
                'status': 'Released',
                'limit': limit
            }

            if query:
                params['search'] = query

            if document_type == DocumentType.SOP:
                params['documentType'] = 'SOP'

            if equipment_type:
                params['equipmentType'] = equipment_type

            url = f"{self.config.base_url}/api/v1/documents"
            response = self._session.get(
                url,
                params=params,
                timeout=self.config.timeout_seconds,
                verify=self.config.verify_ssl
            )

            if response.status_code == 200:
                data = response.json()
                documents = []

                for doc in data.get('documents', []):
                    documents.append(QMSDocument(
                        document_id=doc.get('id'),
                        title=doc.get('title', ''),
                        document_number=doc.get('documentNumber', ''),
                        document_type=self._map_mc_type(doc.get('documentType')),
                        version=doc.get('version', '1.0'),
                        status=self._map_mc_status(doc.get('status')),
                        effective_date=self._parse_date(doc.get('effectiveDate')),
                        owner=doc.get('owner'),
                        department=doc.get('department'),
                        keywords=doc.get('keywords', []),
                        metadata={'source': 'mastercontrol'}
                    ))

                return documents

            logger.error(f"MasterControl search failed: {response.text}")
            return []

        except Exception as e:
            logger.error(f"MasterControl search error: {e}")
            return []

    def get_document(self, document_id: str) -> Optional[QMSDocument]:
        """Get a specific document from MasterControl."""
        self._ensure_authenticated()

        try:
            url = f"{self.config.base_url}/api/v1/documents/{document_id}"
            response = self._session.get(
                url,
                timeout=self.config.timeout_seconds,
                verify=self.config.verify_ssl
            )

            if response.status_code == 200:
                doc = response.json()
                return QMSDocument(
                    document_id=document_id,
                    title=doc.get('title', ''),
                    document_number=doc.get('documentNumber', ''),
                    document_type=self._map_mc_type(doc.get('documentType')),
                    version=doc.get('version', '1.0'),
                    status=self._map_mc_status(doc.get('status')),
                    effective_date=self._parse_date(doc.get('effectiveDate')),
                    content_url=doc.get('downloadUrl'),
                    owner=doc.get('owner'),
                    department=doc.get('department'),
                    keywords=doc.get('keywords', []),
                    metadata={'source': 'mastercontrol', 'full_response': doc}
                )

            return None

        except Exception as e:
            logger.error(f"MasterControl get document error: {e}")
            return None

    def get_document_content(self, document_id: str) -> Optional[str]:
        """Get document content from MasterControl."""
        self._ensure_authenticated()

        try:
            url = f"{self.config.base_url}/api/v1/documents/{document_id}/content"
            response = self._session.get(
                url,
                timeout=self.config.timeout_seconds,
                verify=self.config.verify_ssl
            )

            if response.status_code == 200:
                return response.text

            return None

        except Exception as e:
            logger.error(f"MasterControl get content error: {e}")
            return None

    def _map_mc_type(self, mc_type: str) -> DocumentType:
        """Map MasterControl document type to our enum."""
        type_map = {
            'SOP': DocumentType.SOP,
            'WI': DocumentType.WORK_INSTRUCTION,
            'POLICY': DocumentType.POLICY,
            'FORM': DocumentType.FORM,
            'SPEC': DocumentType.SPECIFICATION
        }
        return type_map.get(mc_type, DocumentType.SOP)

    def _map_mc_status(self, mc_status: str) -> DocumentStatus:
        """Map MasterControl status to our enum."""
        status_map = {
            'Draft': DocumentStatus.DRAFT,
            'Pending': DocumentStatus.IN_REVIEW,
            'Approved': DocumentStatus.APPROVED,
            'Released': DocumentStatus.EFFECTIVE,
            'Superseded': DocumentStatus.SUPERSEDED,
            'Obsolete': DocumentStatus.OBSOLETE
        }
        return status_map.get(mc_status, DocumentStatus.EFFECTIVE)

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse MasterControl date string."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            return None


class SharePointConnector(QMSConnector):
    """
    Connector for SharePoint/Microsoft 365.

    Many organizations use SharePoint for document management,
    including SOPs and controlled documents.
    """

    def authenticate(self) -> bool:
        """Authenticate with SharePoint using OAuth2 (client credentials)."""
        try:
            auth_url = f"https://login.microsoftonline.com/{self.config.tenant_id}/oauth2/v2.0/token"
            response = self._session.post(
                auth_url,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': self.config.client_id,
                    'client_secret': self.config.client_secret,
                    'scope': 'https://graph.microsoft.com/.default'
                },
                timeout=self.config.timeout_seconds
            )

            if response.status_code == 200:
                data = response.json()
                self._token = data.get('access_token')
                expires_in = data.get('expires_in', 3600)
                self._token_expiry = datetime.utcnow() + timedelta(seconds=expires_in - 60)
                self._session.headers['Authorization'] = f"Bearer {self._token}"
                logger.info("Successfully authenticated with SharePoint")
                return True

            logger.error(f"SharePoint authentication failed: {response.text}")
            return False

        except Exception as e:
            logger.error(f"SharePoint authentication error: {e}")
            return False

    def _ensure_authenticated(self):
        """Ensure we have a valid authentication token."""
        if not self._token or (self._token_expiry and datetime.utcnow() >= self._token_expiry):
            if not self.authenticate():
                raise ConnectionError("Failed to authenticate with SharePoint")

    def search_documents(
        self,
        query: str = None,
        document_type: DocumentType = None,
        equipment_type: str = None,
        functional_location: str = None,
        status: DocumentStatus = DocumentStatus.EFFECTIVE,
        limit: int = 50
    ) -> List[QMSDocument]:
        """Search for documents in SharePoint."""
        self._ensure_authenticated()

        try:
            # Build search query
            search_query = query or '*'
            if document_type == DocumentType.SOP:
                search_query += ' AND (ContentType:SOP OR FileType:pdf)'

            url = f"https://graph.microsoft.com/v1.0/sites/{self.config.base_url}/drive/root/search(q='{search_query}')"
            response = self._session.get(
                url,
                params={'$top': limit},
                timeout=self.config.timeout_seconds
            )

            if response.status_code == 200:
                data = response.json()
                documents = []

                for item in data.get('value', []):
                    # Extract document number from filename if present
                    name = item.get('name', '')
                    doc_number = name.split('_')[0] if '_' in name else name.split('.')[0]

                    documents.append(QMSDocument(
                        document_id=item.get('id'),
                        title=name,
                        document_number=doc_number,
                        document_type=DocumentType.SOP,
                        version='1.0',
                        status=DocumentStatus.EFFECTIVE,
                        content_url=item.get('webUrl'),
                        last_modified=self._parse_date(item.get('lastModifiedDateTime')),
                        owner=item.get('lastModifiedBy', {}).get('user', {}).get('displayName'),
                        metadata={
                            'source': 'sharepoint',
                            'size': item.get('size'),
                            'mimeType': item.get('file', {}).get('mimeType')
                        }
                    ))

                return documents

            logger.error(f"SharePoint search failed: {response.text}")
            return []

        except Exception as e:
            logger.error(f"SharePoint search error: {e}")
            return []

    def get_document(self, document_id: str) -> Optional[QMSDocument]:
        """Get a specific document from SharePoint."""
        self._ensure_authenticated()

        try:
            url = f"https://graph.microsoft.com/v1.0/sites/{self.config.base_url}/drive/items/{document_id}"
            response = self._session.get(
                url,
                timeout=self.config.timeout_seconds
            )

            if response.status_code == 200:
                item = response.json()
                name = item.get('name', '')

                return QMSDocument(
                    document_id=document_id,
                    title=name,
                    document_number=name.split('_')[0] if '_' in name else name.split('.')[0],
                    document_type=DocumentType.SOP,
                    version='1.0',
                    status=DocumentStatus.EFFECTIVE,
                    content_url=item.get('@microsoft.graph.downloadUrl'),
                    last_modified=self._parse_date(item.get('lastModifiedDateTime')),
                    metadata={'source': 'sharepoint', 'full_response': item}
                )

            return None

        except Exception as e:
            logger.error(f"SharePoint get document error: {e}")
            return None

    def get_document_content(self, document_id: str) -> Optional[str]:
        """Get document content from SharePoint."""
        self._ensure_authenticated()

        try:
            url = f"https://graph.microsoft.com/v1.0/sites/{self.config.base_url}/drive/items/{document_id}/content"
            response = self._session.get(
                url,
                timeout=self.config.timeout_seconds
            )

            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '')
                if 'text' in content_type:
                    return response.text
                else:
                    return f"[Binary content: {content_type}]"

            return None

        except Exception as e:
            logger.error(f"SharePoint get content error: {e}")
            return None

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse SharePoint date string."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            return None


class SAPQMConnector(QMSConnector):
    """
    Connector for SAP Quality Management (QM).

    Integrates with SAP QM via OData services to retrieve
    quality documents, inspection plans, and SOPs.
    """

    def authenticate(self) -> bool:
        """Authenticate with SAP using Basic Auth or OAuth."""
        try:
            # Set up basic auth
            if self.config.username and self.config.password:
                auth_string = base64.b64encode(
                    f"{self.config.username}:{self.config.password}".encode()
                ).decode()
                self._session.headers['Authorization'] = f"Basic {auth_string}"

            # Test connection
            test_url = f"{self.config.base_url}/sap/opu/odata/sap/API_QUALITYINFORECORD_SRV/"
            response = self._session.get(
                test_url,
                timeout=self.config.timeout_seconds,
                verify=self.config.verify_ssl
            )

            if response.status_code == 200:
                logger.info("Successfully authenticated with SAP QM")
                self._token = 'authenticated'
                return True

            logger.error(f"SAP QM authentication failed: {response.status_code}")
            return False

        except Exception as e:
            logger.error(f"SAP QM authentication error: {e}")
            return False

    def search_documents(
        self,
        query: str = None,
        document_type: DocumentType = None,
        equipment_type: str = None,
        functional_location: str = None,
        status: DocumentStatus = DocumentStatus.EFFECTIVE,
        limit: int = 50
    ) -> List[QMSDocument]:
        """Search for documents/inspection plans in SAP QM."""
        if not self._token:
            self.authenticate()

        try:
            # SAP QM stores SOPs linked to inspection plans
            url = f"{self.config.base_url}/sap/opu/odata/sap/API_INSPECTIONPLAN_SRV/A_InspectionPlan"

            params = {
                '$top': limit,
                '$format': 'json'
            }

            if equipment_type:
                params['$filter'] = f"Material eq '{equipment_type}'"

            response = self._session.get(
                url,
                params=params,
                timeout=self.config.timeout_seconds,
                verify=self.config.verify_ssl
            )

            if response.status_code == 200:
                data = response.json()
                documents = []

                for plan in data.get('d', {}).get('results', []):
                    documents.append(QMSDocument(
                        document_id=plan.get('InspectionPlan'),
                        title=plan.get('InspectionPlanDesc', ''),
                        document_number=plan.get('InspectionPlan', ''),
                        document_type=DocumentType.SOP,
                        version=str(plan.get('InspPlanInternalVersion', '1')),
                        status=DocumentStatus.EFFECTIVE,
                        category='Inspection Plan',
                        metadata={
                            'source': 'sap_qm',
                            'plant': plan.get('Plant'),
                            'material': plan.get('Material')
                        }
                    ))

                return documents

            logger.error(f"SAP QM search failed: {response.text}")
            return []

        except Exception as e:
            logger.error(f"SAP QM search error: {e}")
            return []

    def get_document(self, document_id: str) -> Optional[QMSDocument]:
        """Get a specific inspection plan from SAP QM."""
        if not self._token:
            self.authenticate()

        try:
            url = f"{self.config.base_url}/sap/opu/odata/sap/API_INSPECTIONPLAN_SRV/A_InspectionPlan('{document_id}')"
            response = self._session.get(
                url,
                params={'$format': 'json'},
                timeout=self.config.timeout_seconds,
                verify=self.config.verify_ssl
            )

            if response.status_code == 200:
                plan = response.json().get('d', {})
                return QMSDocument(
                    document_id=document_id,
                    title=plan.get('InspectionPlanDesc', ''),
                    document_number=plan.get('InspectionPlan', ''),
                    document_type=DocumentType.SOP,
                    version=str(plan.get('InspPlanInternalVersion', '1')),
                    status=DocumentStatus.EFFECTIVE,
                    metadata={'source': 'sap_qm', 'full_response': plan}
                )

            return None

        except Exception as e:
            logger.error(f"SAP QM get document error: {e}")
            return None

    def get_document_content(self, document_id: str) -> Optional[str]:
        """Get inspection plan operations/content from SAP QM."""
        if not self._token:
            self.authenticate()

        try:
            # Get inspection operations (the actual steps)
            url = f"{self.config.base_url}/sap/opu/odata/sap/API_INSPECTIONPLAN_SRV/A_InspectionPlan('{document_id}')/to_InspPlanOperation"
            response = self._session.get(
                url,
                params={'$format': 'json'},
                timeout=self.config.timeout_seconds,
                verify=self.config.verify_ssl
            )

            if response.status_code == 200:
                operations = response.json().get('d', {}).get('results', [])
                content_lines = [f"Inspection Plan: {document_id}\n"]

                for op in operations:
                    content_lines.append(
                        f"Step {op.get('InspectionOperation')}: {op.get('OperationDescription', '')}"
                    )

                return '\n'.join(content_lines)

            return None

        except Exception as e:
            logger.error(f"SAP QM get content error: {e}")
            return None


# ============================================================
# QMS Integration Service (Main Interface)
# ============================================================

class QMSIntegrationService:
    """
    Main service for QMS integration.

    Provides a unified interface for connecting to various QMS platforms.
    """

    def __init__(self):
        self._connectors: Dict[str, QMSConnector] = {}
        self._document_cache: Dict[str, tuple] = {}  # (document, timestamp)
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load QMS configuration from environment."""
        return {
            'provider': os.environ.get('QMS_PROVIDER', 'veeva_vault'),
            'base_url': os.environ.get('QMS_BASE_URL', ''),
            'username': os.environ.get('QMS_USERNAME', ''),
            'password': os.environ.get('QMS_PASSWORD', ''),
            'client_id': os.environ.get('QMS_CLIENT_ID', ''),
            'client_secret': os.environ.get('QMS_CLIENT_SECRET', ''),
            'tenant_id': os.environ.get('QMS_TENANT_ID', ''),
            'vault_id': os.environ.get('QMS_VAULT_ID', ''),
            'cache_ttl_minutes': int(os.environ.get('QMS_CACHE_TTL_MINUTES', '60'))
        }

    def _get_connector(self, provider: str = None) -> QMSConnector:
        """Get or create a connector for the specified provider."""
        provider = provider or self._config['provider']

        if provider not in self._connectors:
            config = QMSConfig(
                provider=QMSProvider(provider),
                base_url=self._config['base_url'],
                username=self._config['username'],
                password=self._config['password'],
                client_id=self._config['client_id'],
                client_secret=self._config['client_secret'],
                tenant_id=self._config['tenant_id'],
                vault_id=self._config['vault_id'],
                cache_ttl_minutes=self._config['cache_ttl_minutes']
            )

            connector_map = {
                'veeva_vault': VeevaVaultConnector,
                'mastercontrol': MasterControlConnector,
                'sharepoint': SharePointConnector,
                'sap_qm': SAPQMConnector
            }

            connector_class = connector_map.get(provider)
            if not connector_class:
                raise ValueError(f"Unsupported QMS provider: {provider}")

            self._connectors[provider] = connector_class(config)

        return self._connectors[provider]

    def test_connection(self, provider: str = None) -> Dict[str, Any]:
        """Test connection to the QMS."""
        try:
            connector = self._get_connector(provider)
            success = connector.authenticate()

            return {
                'success': success,
                'provider': provider or self._config['provider'],
                'message': 'Connection successful' if success else 'Connection failed'
            }
        except Exception as e:
            return {
                'success': False,
                'provider': provider or self._config['provider'],
                'message': str(e)
            }

    def search_sops(
        self,
        query: str = None,
        equipment_type: str = None,
        functional_location: str = None,
        limit: int = 50,
        provider: str = None
    ) -> List[QMSDocument]:
        """Search for SOPs in the QMS."""
        connector = self._get_connector(provider)
        return connector.search_documents(
            query=query,
            document_type=DocumentType.SOP,
            equipment_type=equipment_type,
            functional_location=functional_location,
            status=DocumentStatus.EFFECTIVE,
            limit=limit
        )

    def get_sops_for_notification(
        self,
        equipment_type: str = None,
        functional_location: str = None,
        notification_type: str = None,
        provider: str = None
    ) -> List[QMSDocument]:
        """
        Get relevant SOPs for a maintenance notification.

        This method intelligently searches for SOPs based on:
        - Equipment type
        - Functional location
        - Notification type (e.g., breakdown, preventive)
        """
        connector = self._get_connector(provider)
        sops = []

        # Search by equipment type
        if equipment_type:
            sops.extend(connector.get_sops_for_equipment(equipment_type))

        # Search by functional location
        if functional_location:
            location_sops = connector.get_sops_for_location(functional_location)
            # Add unique SOPs
            existing_ids = {s.document_id for s in sops}
            sops.extend([s for s in location_sops if s.document_id not in existing_ids])

        # Search by notification type keywords
        if notification_type:
            type_keywords = {
                'M1': 'breakdown maintenance',
                'M2': 'preventive maintenance',
                'M3': 'predictive maintenance'
            }
            keyword = type_keywords.get(notification_type, notification_type)
            keyword_sops = connector.search_documents(
                query=keyword,
                document_type=DocumentType.SOP,
                status=DocumentStatus.EFFECTIVE,
                limit=10
            )
            existing_ids = {s.document_id for s in sops}
            sops.extend([s for s in keyword_sops if s.document_id not in existing_ids])

        return sops

    def get_document(self, document_id: str, provider: str = None) -> Optional[QMSDocument]:
        """Get a specific document by ID."""
        # Check cache
        cache_key = f"{provider or self._config['provider']}:{document_id}"
        if cache_key in self._document_cache:
            doc, timestamp = self._document_cache[cache_key]
            if datetime.utcnow() - timestamp < timedelta(minutes=self._config['cache_ttl_minutes']):
                return doc

        # Fetch from QMS
        connector = self._get_connector(provider)
        doc = connector.get_document(document_id)

        if doc:
            self._document_cache[cache_key] = (doc, datetime.utcnow())

        return doc

    def get_document_content(self, document_id: str, provider: str = None) -> Optional[str]:
        """Get document content/body."""
        connector = self._get_connector(provider)
        return connector.get_document_content(document_id)

    def get_status(self) -> Dict[str, Any]:
        """Get QMS integration status."""
        return {
            'configured': bool(self._config['base_url']),
            'provider': self._config['provider'],
            'base_url': self._config['base_url'][:50] + '...' if len(self._config['base_url']) > 50 else self._config['base_url'],
            'cache_ttl_minutes': self._config['cache_ttl_minutes'],
            'cached_documents': len(self._document_cache)
        }


# Global service instance
_qms_service: Optional[QMSIntegrationService] = None


def get_qms_service() -> QMSIntegrationService:
    """Get or create the global QMS service instance."""
    global _qms_service
    if _qms_service is None:
        _qms_service = QMSIntegrationService()
    return _qms_service
