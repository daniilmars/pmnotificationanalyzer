"""
GDPR Compliance Service for PM Notification Analyzer.

Implements data subject rights under EU General Data Protection Regulation:
- Art. 15: Right of access (data export)
- Art. 17: Right to erasure (data deletion)
- Art. 20: Right to data portability (machine-readable export)
- Art. 7(3): Right to withdraw consent

Also provides:
- Data retention policy enforcement
- Personal data inventory
- Processing activity logging
- Consent management
"""

import os
import json
import uuid
import csv
import io
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from app.database import get_db_connection, DATABASE_TYPE

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class RequestType(Enum):
    ACCESS = 'access'           # Art. 15 - Right of access
    ERASURE = 'erasure'         # Art. 17 - Right to erasure
    PORTABILITY = 'portability' # Art. 20 - Right to data portability
    RECTIFICATION = 'rectification'  # Art. 16 - Right to rectification
    RESTRICTION = 'restriction'      # Art. 18 - Right to restriction


class RequestStatus(Enum):
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    REJECTED = 'rejected'


class ConsentPurpose(Enum):
    DATA_PROCESSING = 'data_processing'
    ANALYTICS = 'analytics'
    AI_ANALYSIS = 'ai_analysis'
    EMAIL_NOTIFICATIONS = 'email_notifications'
    THIRD_PARTY_QMS = 'third_party_qms'
    USAGE_TRACKING = 'usage_tracking'


@dataclass
class DataSubjectRequest:
    id: str
    tenant_id: str
    subject_id: str
    subject_email: str
    request_type: str
    status: str = RequestStatus.PENDING.value
    details: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ''
    completed_at: Optional[str] = None
    processed_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'subject_id': self.subject_id,
            'subject_email': self.subject_email,
            'request_type': self.request_type,
            'status': self.status,
            'details': self.details,
            'created_at': self.created_at,
            'completed_at': self.completed_at,
            'processed_by': self.processed_by,
        }


@dataclass
class ConsentRecord:
    id: str
    tenant_id: str
    user_id: str
    purpose: str
    granted: bool
    granted_at: str
    revoked_at: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'purpose': self.purpose,
            'granted': self.granted,
            'granted_at': self.granted_at,
            'revoked_at': self.revoked_at,
        }


# ---------------------------------------------------------------------------
# Personal Data Inventory
# ---------------------------------------------------------------------------

# Tables and columns that may contain personal data
PERSONAL_DATA_MAP = {
    'QMEL': {
        'columns': ['QMNAM'],
        'description': 'Notification creator username',
    },
    'CDHDR': {
        'columns': ['USERNAME'],
        'description': 'Change document author',
    },
    'AFRU': {
        'columns': ['ERNAM', 'ARBID'],
        'description': 'Time confirmation creator and worker ID',
    },
    'QMIH': {
        'columns': ['ERNAM'],
        'description': 'Notification history author',
    },
    'security_audit_log': {
        'columns': ['user_id', 'ip_address'],
        'description': 'Security audit trail user references',
    },
}


# ---------------------------------------------------------------------------
# GDPR Service
# ---------------------------------------------------------------------------

class GDPRService:
    """Handles GDPR data subject requests and consent management."""

    def __init__(self):
        self._ensure_tables()

    def _ensure_tables(self):
        """Create GDPR-related tables if they don't exist."""
        try:
            with get_db_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS gdpr_requests (
                        id TEXT PRIMARY KEY,
                        tenant_id TEXT NOT NULL,
                        subject_id TEXT NOT NULL,
                        subject_email TEXT NOT NULL,
                        request_type TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending',
                        details TEXT DEFAULT '{}',
                        created_at TEXT NOT NULL,
                        completed_at TEXT,
                        processed_by TEXT
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS consent_records (
                        id TEXT PRIMARY KEY,
                        tenant_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        purpose TEXT NOT NULL,
                        granted INTEGER NOT NULL DEFAULT 1,
                        granted_at TEXT NOT NULL,
                        revoked_at TEXT,
                        ip_address TEXT,
                        user_agent TEXT
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS data_retention_policies (
                        id TEXT PRIMARY KEY,
                        tenant_id TEXT NOT NULL,
                        data_type TEXT NOT NULL,
                        retention_days INTEGER NOT NULL,
                        auto_delete INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT
                    )
                """)
        except Exception as e:
            logger.warning(f"Could not ensure GDPR tables: {e}")

    # ------------------------------------------------------------------
    # Data Subject Requests (Art. 15, 17, 20)
    # ------------------------------------------------------------------

    def create_request(self, tenant_id: str, subject_id: str,
                       subject_email: str, request_type: str,
                       details: Optional[Dict] = None) -> DataSubjectRequest:
        """Create a new data subject request."""
        dsr = DataSubjectRequest(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            subject_id=subject_id,
            subject_email=subject_email,
            request_type=request_type,
            details=details or {},
            created_at=datetime.utcnow().isoformat(),
        )

        with get_db_connection() as conn:
            conn.execute(
                """INSERT INTO gdpr_requests
                   (id, tenant_id, subject_id, subject_email, request_type, status, details, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (dsr.id, dsr.tenant_id, dsr.subject_id, dsr.subject_email,
                 dsr.request_type, dsr.status, json.dumps(dsr.details), dsr.created_at)
            )

        logger.info(f"GDPR request created: {dsr.request_type} for {subject_id} (tenant: {tenant_id})")
        return dsr

    def get_request(self, request_id: str) -> Optional[DataSubjectRequest]:
        """Get a specific data subject request."""
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT * FROM gdpr_requests WHERE id = ?", (request_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_request(row)
        return None

    def list_requests(self, tenant_id: str, status: Optional[str] = None) -> List[DataSubjectRequest]:
        """List data subject requests for a tenant."""
        with get_db_connection() as conn:
            if status:
                cursor = conn.execute(
                    "SELECT * FROM gdpr_requests WHERE tenant_id = ? AND status = ? ORDER BY created_at DESC",
                    (tenant_id, status)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM gdpr_requests WHERE tenant_id = ? ORDER BY created_at DESC",
                    (tenant_id,)
                )
            return [self._row_to_request(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Art. 15 - Right of Access (Data Export)
    # ------------------------------------------------------------------

    def export_subject_data(self, tenant_id: str, subject_id: str) -> Dict[str, Any]:
        """
        Export all personal data associated with a data subject.

        Returns a structured JSON document containing all data
        from tables in PERSONAL_DATA_MAP where the subject appears.
        """
        export = {
            'export_date': datetime.utcnow().isoformat(),
            'subject_id': subject_id,
            'tenant_id': tenant_id,
            'data': {},
        }

        with get_db_connection() as conn:
            # Notifications created by subject
            cursor = conn.execute(
                "SELECT QMNUM, QMART, EQUNR, TPLNR, PRIOK, QMNAM, ERDAT FROM QMEL WHERE QMNAM = ?",
                (subject_id,)
            )
            rows = cursor.fetchall()
            if rows:
                export['data']['notifications_created'] = [
                    {k: row[k] for k in row.keys()} for row in rows
                ]

            # Change documents by subject
            cursor = conn.execute(
                "SELECT * FROM CDHDR WHERE USERNAME = ?",
                (subject_id,)
            )
            rows = cursor.fetchall()
            if rows:
                export['data']['change_documents'] = [
                    {k: row[k] for k in row.keys()} for row in rows
                ]

            # Time confirmations by subject
            cursor = conn.execute(
                "SELECT * FROM AFRU WHERE ERNAM = ? OR ARBID = ?",
                (subject_id, subject_id)
            )
            rows = cursor.fetchall()
            if rows:
                export['data']['time_confirmations'] = [
                    {k: row[k] for k in row.keys()} for row in rows
                ]

            # Notification history by subject
            cursor = conn.execute(
                "SELECT * FROM QMIH WHERE ERNAM = ?",
                (subject_id,)
            )
            rows = cursor.fetchall()
            if rows:
                export['data']['notification_history'] = [
                    {k: row[k] for k in row.keys()} for row in rows
                ]

            # Security audit log entries
            cursor = conn.execute(
                "SELECT * FROM security_audit_log WHERE user_id = ?",
                (subject_id,)
            )
            rows = cursor.fetchall()
            if rows:
                export['data']['security_audit_log'] = [
                    {k: row[k] for k in row.keys()} for row in rows
                ]

            # Consent records
            cursor = conn.execute(
                "SELECT * FROM consent_records WHERE user_id = ? AND tenant_id = ?",
                (subject_id, tenant_id)
            )
            rows = cursor.fetchall()
            if rows:
                export['data']['consent_records'] = [
                    {k: row[k] for k in row.keys()} for row in rows
                ]

        return export

    def export_subject_data_csv(self, tenant_id: str, subject_id: str) -> str:
        """Export subject data as CSV (Art. 20 portability)."""
        data = self.export_subject_data(tenant_id, subject_id)
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(['Category', 'Field', 'Value'])

        for category, records in data.get('data', {}).items():
            for record in records:
                for field_name, value in record.items():
                    writer.writerow([category, field_name, str(value) if value else ''])

        return output.getvalue()

    # ------------------------------------------------------------------
    # Art. 17 - Right to Erasure
    # ------------------------------------------------------------------

    def erase_subject_data(self, tenant_id: str, subject_id: str,
                           processed_by: str) -> Dict[str, Any]:
        """
        Erase all personal data for a data subject.

        Pseudonymizes rather than deletes to maintain referential integrity.
        Notification technical data is retained; personal identifiers are removed.
        """
        pseudonym = f"ERASED-{uuid.uuid4().hex[:8]}"
        erased = {
            'subject_id': subject_id,
            'pseudonym': pseudonym,
            'tables_affected': {},
            'erased_at': datetime.utcnow().isoformat(),
            'processed_by': processed_by,
        }

        with get_db_connection() as conn:
            # Pseudonymize notification creator
            cursor = conn.execute(
                "UPDATE QMEL SET QMNAM = ? WHERE QMNAM = ?",
                (pseudonym, subject_id)
            )
            erased['tables_affected']['QMEL'] = cursor.rowcount

            # Pseudonymize change document author
            cursor = conn.execute(
                "UPDATE CDHDR SET USERNAME = ? WHERE USERNAME = ?",
                (pseudonym, subject_id)
            )
            erased['tables_affected']['CDHDR'] = cursor.rowcount

            # Pseudonymize time confirmation creator
            cursor = conn.execute(
                "UPDATE AFRU SET ERNAM = ? WHERE ERNAM = ?",
                (pseudonym, subject_id)
            )
            erased['tables_affected']['AFRU_ERNAM'] = cursor.rowcount

            cursor = conn.execute(
                "UPDATE AFRU SET ARBID = ? WHERE ARBID = ?",
                (pseudonym, subject_id)
            )
            erased['tables_affected']['AFRU_ARBID'] = cursor.rowcount

            # Pseudonymize notification history
            cursor = conn.execute(
                "UPDATE QMIH SET ERNAM = ? WHERE ERNAM = ?",
                (pseudonym, subject_id)
            )
            erased['tables_affected']['QMIH'] = cursor.rowcount

            # Pseudonymize security audit log
            cursor = conn.execute(
                "UPDATE security_audit_log SET user_id = ? WHERE user_id = ?",
                (pseudonym, subject_id)
            )
            erased['tables_affected']['security_audit_log'] = cursor.rowcount

            # Delete consent records (no need to retain)
            cursor = conn.execute(
                "DELETE FROM consent_records WHERE user_id = ? AND tenant_id = ?",
                (subject_id, tenant_id)
            )
            erased['tables_affected']['consent_records_deleted'] = cursor.rowcount

        logger.info(f"GDPR erasure completed for {subject_id} -> {pseudonym} "
                     f"(tenant: {tenant_id}, by: {processed_by})")
        return erased

    # ------------------------------------------------------------------
    # Consent Management (Art. 7)
    # ------------------------------------------------------------------

    def record_consent(self, tenant_id: str, user_id: str, purpose: str,
                       granted: bool, ip_address: Optional[str] = None,
                       user_agent: Optional[str] = None) -> ConsentRecord:
        """Record a consent decision."""
        record = ConsentRecord(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            purpose=purpose,
            granted=granted,
            granted_at=datetime.utcnow().isoformat(),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        with get_db_connection() as conn:
            conn.execute(
                """INSERT INTO consent_records
                   (id, tenant_id, user_id, purpose, granted, granted_at, ip_address, user_agent)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (record.id, record.tenant_id, record.user_id, record.purpose,
                 1 if record.granted else 0, record.granted_at,
                 record.ip_address, record.user_agent)
            )

        return record

    def revoke_consent(self, tenant_id: str, user_id: str, purpose: str) -> bool:
        """Revoke a previously granted consent."""
        with get_db_connection() as conn:
            cursor = conn.execute(
                """UPDATE consent_records SET granted = 0, revoked_at = ?
                   WHERE tenant_id = ? AND user_id = ? AND purpose = ? AND granted = 1""",
                (datetime.utcnow().isoformat(), tenant_id, user_id, purpose)
            )
            return cursor.rowcount > 0

    def get_consents(self, tenant_id: str, user_id: str) -> List[ConsentRecord]:
        """Get all consent records for a user."""
        with get_db_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM consent_records
                   WHERE tenant_id = ? AND user_id = ?
                   ORDER BY granted_at DESC""",
                (tenant_id, user_id)
            )
            return [self._row_to_consent(row) for row in cursor.fetchall()]

    def check_consent(self, tenant_id: str, user_id: str, purpose: str) -> bool:
        """Check if a user has active consent for a purpose."""
        with get_db_connection() as conn:
            cursor = conn.execute(
                """SELECT granted FROM consent_records
                   WHERE tenant_id = ? AND user_id = ? AND purpose = ?
                   ORDER BY granted_at DESC LIMIT 1""",
                (tenant_id, user_id, purpose)
            )
            row = cursor.fetchone()
            return bool(row and row['granted'])

    # ------------------------------------------------------------------
    # Data Retention
    # ------------------------------------------------------------------

    def set_retention_policy(self, tenant_id: str, data_type: str,
                             retention_days: int, auto_delete: bool = False):
        """Set data retention policy for a data type."""
        with get_db_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO data_retention_policies
                   (id, tenant_id, data_type, retention_days, auto_delete, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (f"{tenant_id}_{data_type}", tenant_id, data_type, retention_days,
                 1 if auto_delete else 0,
                 datetime.utcnow().isoformat(), datetime.utcnow().isoformat())
            )

    def get_retention_policies(self, tenant_id: str) -> List[Dict]:
        """Get all retention policies for a tenant."""
        with get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM data_retention_policies WHERE tenant_id = ?",
                (tenant_id,)
            )
            return [{k: row[k] for k in row.keys()} for row in cursor.fetchall()]

    def get_personal_data_inventory(self) -> List[Dict]:
        """Return the personal data inventory (data mapping)."""
        return [
            {
                'table': table,
                'columns': info['columns'],
                'description': info['description'],
            }
            for table, info in PERSONAL_DATA_MAP.items()
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _row_to_request(self, row) -> DataSubjectRequest:
        details = row['details'] or '{}'
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except (json.JSONDecodeError, TypeError):
                details = {}

        return DataSubjectRequest(
            id=row['id'],
            tenant_id=row['tenant_id'],
            subject_id=row['subject_id'],
            subject_email=row['subject_email'],
            request_type=row['request_type'],
            status=row['status'],
            details=details,
            created_at=str(row['created_at'] or ''),
            completed_at=row['completed_at'],
            processed_by=row['processed_by'],
        )

    def _row_to_consent(self, row) -> ConsentRecord:
        return ConsentRecord(
            id=row['id'],
            tenant_id=row['tenant_id'],
            user_id=row['user_id'],
            purpose=row['purpose'],
            granted=bool(row['granted']),
            granted_at=str(row['granted_at'] or ''),
            revoked_at=row['revoked_at'],
            ip_address=row.get('ip_address'),
            user_agent=row.get('user_agent'),
        )

    def _update_request_status(self, request_id: str, status: str,
                                processed_by: Optional[str] = None):
        """Update the status of a data subject request."""
        with get_db_connection() as conn:
            if status == RequestStatus.COMPLETED.value:
                conn.execute(
                    """UPDATE gdpr_requests SET status = ?, completed_at = ?, processed_by = ?
                       WHERE id = ?""",
                    (status, datetime.utcnow().isoformat(), processed_by, request_id)
                )
            else:
                conn.execute(
                    "UPDATE gdpr_requests SET status = ? WHERE id = ?",
                    (status, request_id)
                )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_gdpr_service: Optional[GDPRService] = None


def get_gdpr_service() -> GDPRService:
    global _gdpr_service
    if _gdpr_service is None:
        _gdpr_service = GDPRService()
    return _gdpr_service
