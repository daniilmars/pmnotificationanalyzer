"""
Change Document Service

Provides FDA 21 CFR Part 11 compliant audit trail functionality:
- CDHDR/CDPOS: Field-level change tracking
- JEST: System status management
- AFRU: Time confirmation recording
- QMIH: Notification version history

This service implements SAP-style change document handling for
complete traceability of all data modifications.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import uuid
import sqlite3
import os
import logging

logger = logging.getLogger(__name__)


class ChangeIndicator(Enum):
    """Change type indicators"""
    INSERT = 'I'
    UPDATE = 'U'
    DELETE = 'D'
    EXTENSION = 'E'  # For long text changes


class ObjectClass(Enum):
    """SAP object classes for change documents"""
    NOTIFICATION = 'QMEL'
    ORDER = 'AUFK'
    OPERATION = 'AFVC'
    EQUIPMENT = 'EQUI'
    FUNCLOC = 'IFLOT'


class SystemStatus(Enum):
    """Standard SAP PM system statuses"""
    CREATED = 'CRTD'         # Created
    OUTSTANDING = 'OSDN'     # Outstanding (notification)
    IN_PROCESS = 'INPR'      # In process
    RELEASED = 'REL'         # Released
    PARTIALLY_CONFIRMED = 'PCNF'  # Partially confirmed
    CONFIRMED = 'CNF'        # Confirmed
    TECHNICALLY_COMPLETE = 'TECO'  # Technically complete
    CLOSED = 'CLSD'          # Closed
    DELETED = 'DLFL'         # Deletion flag


@dataclass
class ChangeDocumentHeader:
    """Change document header record"""
    changenr: str
    objectclas: str
    objectid: str
    username: str
    udate: str
    utime: str
    tcode: Optional[str] = None
    change_ind: str = 'U'
    langu: str = 'en'


@dataclass
class ChangeDocumentItem:
    """Change document item (field-level change)"""
    changenr: str
    tabname: str
    tabkey: str
    fname: str
    value_new: Optional[str] = None
    value_old: Optional[str] = None
    chngind: str = 'U'


@dataclass
class ObjectStatus:
    """Object status record"""
    objnr: str
    stat: str
    inact: str = ''
    chgnr: Optional[str] = None


@dataclass
class TimeConfirmation:
    """Order time confirmation record"""
    ruession: str
    aufnr: str
    vornr: Optional[str] = None
    arbid: Optional[str] = None
    werks: Optional[str] = None
    budat: str = ''
    isdd: Optional[str] = None
    isdz: Optional[str] = None
    iedd: Optional[str] = None
    iedz: Optional[str] = None
    arbei: float = 0.0
    ismnw: float = 0.0
    ismne: str = 'H'
    ltxa1: Optional[str] = None
    aueru: str = ''  # Final confirmation flag
    ernam: str = ''
    erdat: str = ''
    erzet: str = ''


@dataclass
class ChangeHistoryEntry:
    """Formatted change history entry for display"""
    change_number: str
    timestamp: datetime
    user: str
    object_type: str
    object_id: str
    change_type: str
    fields_changed: List[Dict[str, Any]]
    transaction_code: Optional[str] = None


class ChangeDocumentService:
    """
    Service for managing change documents and audit trails.

    Implements SAP-style change document handling for FDA 21 CFR Part 11
    compliance, providing:
    - Automatic change logging for all data modifications
    - Field-level change tracking with old/new values
    - Status management with history
    - Time confirmation recording
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize the change document service."""
        if db_path is None:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'data', 'pm_notifications.db'
            )
        self.db_path = db_path
        self._ensure_tables_exist()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables_exist(self):
        """Ensure change document tables exist."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Check if CDHDR table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='CDHDR'
            """)

            if not cursor.fetchone():
                # Run schema to create tables
                schema_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    'data', 'schema.sql'
                )
                if os.path.exists(schema_path):
                    with open(schema_path, 'r') as f:
                        schema_sql = f.read()
                    conn.executescript(schema_sql)
                    conn.commit()
                    logger.info("Change document tables created")

            conn.close()
        except Exception as e:
            logger.warning(f"Could not ensure tables exist: {e}")

    def generate_change_number(self) -> str:
        """Generate a unique change document number."""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        unique_suffix = uuid.uuid4().hex[:6].upper()
        return f"CD{timestamp}{unique_suffix}"

    def record_change(
        self,
        object_class: str,
        object_id: str,
        username: str,
        changes: List[Dict[str, Any]],
        change_type: str = 'U',
        transaction_code: Optional[str] = None,
        reason: Optional[str] = None
    ) -> str:
        """
        Record a change document for an object.

        Args:
            object_class: Object class (QMEL, AUFK, etc.)
            object_id: Object identifier
            username: User making the change
            changes: List of field changes [{table, key, field, old, new}]
            change_type: I=Insert, U=Update, D=Delete
            transaction_code: Optional transaction code
            reason: Optional reason for change

        Returns:
            Change document number
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            changenr = self.generate_change_number()
            now = datetime.now()
            udate = now.strftime('%Y%m%d')
            utime = now.strftime('%H%M%S')

            # Insert header
            cursor.execute("""
                INSERT INTO CDHDR (CHANGENR, OBJECTCLAS, OBJECTID, USERNAME,
                                   UDATE, UTIME, TCODE, CHANGE_IND, LANGU)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (changenr, object_class, object_id, username,
                  udate, utime, transaction_code, change_type, 'en'))

            # Insert items (field-level changes)
            for change in changes:
                cursor.execute("""
                    INSERT INTO CDPOS (CHANGENR, TABNAME, TABKEY, FNAME,
                                       VALUE_NEW, VALUE_OLD, CHNGIND)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    changenr,
                    change.get('table', object_class),
                    change.get('key', object_id),
                    change.get('field', ''),
                    str(change.get('new', ''))[:255] if change.get('new') else None,
                    str(change.get('old', ''))[:255] if change.get('old') else None,
                    change.get('indicator', change_type)
                ))

            conn.commit()
            logger.info(f"Change document {changenr} created for {object_class}/{object_id}")

            return changenr

        except Exception as e:
            conn.rollback()
            logger.error(f"Error recording change document: {e}")
            raise
        finally:
            conn.close()

    def get_change_history(
        self,
        object_class: Optional[str] = None,
        object_id: Optional[str] = None,
        username: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 100
    ) -> List[ChangeHistoryEntry]:
        """
        Get change history for objects.

        Args:
            object_class: Filter by object class
            object_id: Filter by object ID
            username: Filter by user
            from_date: Start date (YYYYMMDD)
            to_date: End date (YYYYMMDD)
            limit: Maximum records to return

        Returns:
            List of change history entries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Build query
            query = """
                SELECT h.CHANGENR, h.OBJECTCLAS, h.OBJECTID, h.USERNAME,
                       h.UDATE, h.UTIME, h.TCODE, h.CHANGE_IND
                FROM CDHDR h
                WHERE 1=1
            """
            params = []

            if object_class:
                query += " AND h.OBJECTCLAS = ?"
                params.append(object_class)

            if object_id:
                query += " AND h.OBJECTID = ?"
                params.append(object_id)

            if username:
                query += " AND h.USERNAME = ?"
                params.append(username)

            if from_date:
                query += " AND h.UDATE >= ?"
                params.append(from_date)

            if to_date:
                query += " AND h.UDATE <= ?"
                params.append(to_date)

            query += " ORDER BY h.UDATE DESC, h.UTIME DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            headers = cursor.fetchall()

            results = []
            for header in headers:
                # Get items for this change
                cursor.execute("""
                    SELECT TABNAME, TABKEY, FNAME, VALUE_NEW, VALUE_OLD, CHNGIND
                    FROM CDPOS WHERE CHANGENR = ?
                """, (header['CHANGENR'],))
                items = cursor.fetchall()

                # Format timestamp
                try:
                    timestamp = datetime.strptime(
                        f"{header['UDATE']}{header['UTIME']}",
                        '%Y%m%d%H%M%S'
                    )
                except:
                    timestamp = datetime.now()

                # Format change type
                change_type_map = {
                    'I': 'Created',
                    'U': 'Modified',
                    'D': 'Deleted',
                    'E': 'Extended'
                }
                change_type = change_type_map.get(header['CHANGE_IND'], 'Modified')

                # Format fields changed
                fields_changed = []
                for item in items:
                    fields_changed.append({
                        'table': item['TABNAME'],
                        'key': item['TABKEY'],
                        'field': item['FNAME'],
                        'old_value': item['VALUE_OLD'],
                        'new_value': item['VALUE_NEW'],
                        'indicator': item['CHNGIND']
                    })

                results.append(ChangeHistoryEntry(
                    change_number=header['CHANGENR'],
                    timestamp=timestamp,
                    user=header['USERNAME'],
                    object_type=header['OBJECTCLAS'],
                    object_id=header['OBJECTID'],
                    change_type=change_type,
                    fields_changed=fields_changed,
                    transaction_code=header['TCODE']
                ))

            return results

        except Exception as e:
            logger.error(f"Error getting change history: {e}")
            return []
        finally:
            conn.close()

    def set_status(
        self,
        object_number: str,
        status: str,
        username: str,
        activate: bool = True
    ) -> bool:
        """
        Set or update object status.

        Args:
            object_number: Internal object number
            status: Status code (CRTD, REL, TECO, etc.)
            username: User making the change
            activate: True to activate, False to deactivate

        Returns:
            Success status
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get current status
            cursor.execute("""
                SELECT STAT, INACT FROM JEST WHERE OBJNR = ? AND STAT = ?
            """, (object_number, status))
            existing = cursor.fetchone()

            inact = '' if activate else 'X'
            changenr = self.generate_change_number()

            if existing:
                # Update existing status
                old_inact = existing['INACT']
                cursor.execute("""
                    UPDATE JEST SET INACT = ?, CHGNR = ?
                    WHERE OBJNR = ? AND STAT = ?
                """, (inact, changenr, object_number, status))

                # Record change
                self.record_change(
                    'JEST', object_number, username,
                    [{'table': 'JEST', 'key': f"{object_number}/{status}",
                      'field': 'INACT', 'old': old_inact, 'new': inact}],
                    'U'
                )
            else:
                # Insert new status
                cursor.execute("""
                    INSERT INTO JEST (OBJNR, STAT, INACT, CHGNR)
                    VALUES (?, ?, ?, ?)
                """, (object_number, status, inact, changenr))

                # Record change
                self.record_change(
                    'JEST', object_number, username,
                    [{'table': 'JEST', 'key': f"{object_number}/{status}",
                      'field': 'STAT', 'old': None, 'new': status, 'indicator': 'I'}],
                    'I'
                )

            conn.commit()
            return True

        except Exception as e:
            conn.rollback()
            logger.error(f"Error setting status: {e}")
            return False
        finally:
            conn.close()

    def get_status(self, object_number: str) -> List[Dict[str, Any]]:
        """
        Get all statuses for an object.

        Args:
            object_number: Internal object number

        Returns:
            List of status records
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT j.OBJNR, j.STAT, j.INACT, j.CHGNR,
                       t.TXT04, t.TXT30
                FROM JEST j
                LEFT JOIN TJ02T t ON j.STAT = t.ISTAT AND t.SPRAS = 'en'
                WHERE j.OBJNR = ? AND (j.INACT = '' OR j.INACT IS NULL)
            """, (object_number,))

            results = []
            for row in cursor.fetchall():
                results.append({
                    'object_number': row['OBJNR'],
                    'status': row['STAT'],
                    'inactive': row['INACT'] == 'X',
                    'short_text': row['TXT04'] or row['STAT'],
                    'description': row['TXT30'] or row['STAT']
                })

            return results

        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return []
        finally:
            conn.close()

    def record_time_confirmation(
        self,
        order_number: str,
        operation_number: Optional[str],
        username: str,
        actual_work_hours: float,
        actual_start: Optional[datetime] = None,
        actual_end: Optional[datetime] = None,
        confirmation_text: Optional[str] = None,
        final_confirmation: bool = False
    ) -> str:
        """
        Record a time confirmation for an order operation.

        Args:
            order_number: Order number
            operation_number: Operation number (optional)
            username: User recording the confirmation
            actual_work_hours: Actual work performed (hours)
            actual_start: Actual start datetime
            actual_end: Actual end datetime
            confirmation_text: Optional text note
            final_confirmation: True if this is the final confirmation

        Returns:
            Confirmation counter
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Generate confirmation counter
            ruession = f"CNF{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"
            now = datetime.now()

            # Format dates
            budat = now.strftime('%Y%m%d')
            erdat = now.strftime('%Y%m%d')
            erzet = now.strftime('%H%M%S')

            isdd = actual_start.strftime('%Y%m%d') if actual_start else None
            isdz = actual_start.strftime('%H%M%S') if actual_start else None
            iedd = actual_end.strftime('%Y%m%d') if actual_end else None
            iedz = actual_end.strftime('%H%M%S') if actual_end else None

            cursor.execute("""
                INSERT INTO AFRU (RUESSION, AUFNR, VORNR, BUDAT, ISDD, ISDZ,
                                  IEDD, IEDZ, ARBEI, LTXA1, AUERU, ERNAM, ERDAT, ERZET)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ruession, order_number, operation_number, budat,
                isdd, isdz, iedd, iedz, actual_work_hours,
                confirmation_text, 'X' if final_confirmation else '',
                username, erdat, erzet
            ))

            conn.commit()

            # Record change document
            self.record_change(
                'AFRU', order_number, username,
                [{'table': 'AFRU', 'key': ruession, 'field': 'ARBEI',
                  'old': None, 'new': str(actual_work_hours), 'indicator': 'I'}],
                'I', 'IW41'
            )

            logger.info(f"Time confirmation {ruession} recorded for order {order_number}")
            return ruession

        except Exception as e:
            conn.rollback()
            logger.error(f"Error recording time confirmation: {e}")
            raise
        finally:
            conn.close()

    def get_time_confirmations(
        self,
        order_number: str,
        operation_number: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get time confirmations for an order.

        Args:
            order_number: Order number
            operation_number: Optional operation filter

        Returns:
            List of confirmation records
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            query = """
                SELECT RUESSION, AUFNR, VORNR, BUDAT, ISDD, ISDZ, IEDD, IEDZ,
                       ARBEI, ISMNW, ISMNE, LTXA1, AUERU, ERNAM, ERDAT, ERZET
                FROM AFRU WHERE AUFNR = ?
            """
            params = [order_number]

            if operation_number:
                query += " AND VORNR = ?"
                params.append(operation_number)

            query += " ORDER BY ERDAT DESC, ERZET DESC"

            cursor.execute(query, params)

            results = []
            for row in cursor.fetchall():
                results.append({
                    'confirmation_number': row['RUESSION'],
                    'order_number': row['AUFNR'],
                    'operation_number': row['VORNR'],
                    'posting_date': row['BUDAT'],
                    'actual_start_date': row['ISDD'],
                    'actual_start_time': row['ISDZ'],
                    'actual_end_date': row['IEDD'],
                    'actual_end_time': row['IEDZ'],
                    'actual_work_hours': row['ARBEI'] or 0,
                    'machine_time': row['ISMNW'] or 0,
                    'machine_time_unit': row['ISMNE'],
                    'confirmation_text': row['LTXA1'],
                    'final_confirmation': row['AUERU'] == 'X',
                    'created_by': row['ERNAM'],
                    'created_date': row['ERDAT'],
                    'created_time': row['ERZET']
                })

            return results

        except Exception as e:
            logger.error(f"Error getting time confirmations: {e}")
            return []
        finally:
            conn.close()

    def record_notification_history(
        self,
        notification_id: str,
        username: str,
        change_reason: Optional[str] = None,
        notification_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Record a notification history entry (QMIH).

        Args:
            notification_id: Notification number
            username: User making the change
            change_reason: Reason for the change
            notification_data: Current notification data snapshot

        Returns:
            History counter
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get next history counter
            cursor.execute("""
                SELECT MAX(CAST(HESSION AS INTEGER)) as max_counter
                FROM QMIH WHERE QMNUM = ?
            """, (notification_id,))
            result = cursor.fetchone()
            counter = (result['max_counter'] or 0) + 1
            hession = str(counter).zfill(4)

            now = datetime.now()
            erdat = now.strftime('%Y%m%d')
            erzet = now.strftime('%H%M%S')

            # Extract data from notification if provided
            qmart = notification_data.get('QMART', '') if notification_data else ''
            priok = notification_data.get('PRIOK', '') if notification_data else ''
            stat = notification_data.get('STATUS', '') if notification_data else ''

            cursor.execute("""
                INSERT INTO QMIH (QMNUM, HESSION, ERDAT, ERZET, ERNAM,
                                  QMART, PRIESSION, STAT, CHANGE_REASON)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                notification_id, hession, erdat, erzet, username,
                qmart, priok, stat, change_reason
            ))

            conn.commit()
            logger.info(f"Notification history {hession} recorded for {notification_id}")

            return hession

        except Exception as e:
            conn.rollback()
            logger.error(f"Error recording notification history: {e}")
            raise
        finally:
            conn.close()

    def get_notification_history(
        self,
        notification_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get notification change history.

        Args:
            notification_id: Notification number

        Returns:
            List of history entries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT QMNUM, HESSION, ERDAT, ERZET, ERNAM, QMART,
                       PRIESSION, STAT, OTGRP, FESSION, URGRP,
                       MESSION, CHANGE_REASON
                FROM QMIH WHERE QMNUM = ?
                ORDER BY ERDAT DESC, ERZET DESC
            """, (notification_id,))

            results = []
            for row in cursor.fetchall():
                results.append({
                    'notification_id': row['QMNUM'],
                    'history_counter': row['HESSION'],
                    'change_date': row['ERDAT'],
                    'change_time': row['ERZET'],
                    'changed_by': row['ERNAM'],
                    'notification_type': row['QMART'],
                    'priority': row['PRIESSION'],
                    'status': row['STAT'],
                    'damage_code_group': row['FESSION'],
                    'cause_code_group': row['URGRP'],
                    'change_reason': row['CHANGE_REASON']
                })

            return results

        except Exception as e:
            logger.error(f"Error getting notification history: {e}")
            return []
        finally:
            conn.close()

    def get_audit_report(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        object_class: Optional[str] = None,
        username: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate an audit report for compliance purposes.

        Args:
            from_date: Start date (YYYYMMDD)
            to_date: End date (YYYYMMDD)
            object_class: Filter by object class
            username: Filter by user

        Returns:
            Audit report data
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Build base query
            where_clause = "WHERE 1=1"
            params = []

            if from_date:
                where_clause += " AND h.UDATE >= ?"
                params.append(from_date)

            if to_date:
                where_clause += " AND h.UDATE <= ?"
                params.append(to_date)

            if object_class:
                where_clause += " AND h.OBJECTCLAS = ?"
                params.append(object_class)

            if username:
                where_clause += " AND h.USERNAME = ?"
                params.append(username)

            # Get summary statistics
            cursor.execute(f"""
                SELECT
                    COUNT(*) as total_changes,
                    COUNT(DISTINCT h.OBJECTID) as objects_changed,
                    COUNT(DISTINCT h.USERNAME) as users_involved,
                    COUNT(CASE WHEN h.CHANGE_IND = 'I' THEN 1 END) as inserts,
                    COUNT(CASE WHEN h.CHANGE_IND = 'U' THEN 1 END) as updates,
                    COUNT(CASE WHEN h.CHANGE_IND = 'D' THEN 1 END) as deletes
                FROM CDHDR h
                {where_clause}
            """, params)

            summary = cursor.fetchone()

            # Get changes by object class
            cursor.execute(f"""
                SELECT h.OBJECTCLAS, COUNT(*) as change_count
                FROM CDHDR h
                {where_clause}
                GROUP BY h.OBJECTCLAS
                ORDER BY change_count DESC
            """, params)

            by_object_class = [
                {'object_class': row['OBJECTCLAS'], 'count': row['change_count']}
                for row in cursor.fetchall()
            ]

            # Get changes by user
            cursor.execute(f"""
                SELECT h.USERNAME, COUNT(*) as change_count
                FROM CDHDR h
                {where_clause}
                GROUP BY h.USERNAME
                ORDER BY change_count DESC
                LIMIT 20
            """, params)

            by_user = [
                {'username': row['USERNAME'], 'count': row['change_count']}
                for row in cursor.fetchall()
            ]

            # Get recent changes
            cursor.execute(f"""
                SELECT h.CHANGENR, h.OBJECTCLAS, h.OBJECTID, h.USERNAME,
                       h.UDATE, h.UTIME, h.CHANGE_IND
                FROM CDHDR h
                {where_clause}
                ORDER BY h.UDATE DESC, h.UTIME DESC
                LIMIT 50
            """, params)

            recent_changes = []
            for row in cursor.fetchall():
                recent_changes.append({
                    'change_number': row['CHANGENR'],
                    'object_class': row['OBJECTCLAS'],
                    'object_id': row['OBJECTID'],
                    'username': row['USERNAME'],
                    'date': row['UDATE'],
                    'time': row['UTIME'],
                    'change_type': row['CHANGE_IND']
                })

            return {
                'summary': {
                    'total_changes': summary['total_changes'] or 0,
                    'objects_changed': summary['objects_changed'] or 0,
                    'users_involved': summary['users_involved'] or 0,
                    'inserts': summary['inserts'] or 0,
                    'updates': summary['updates'] or 0,
                    'deletes': summary['deletes'] or 0
                },
                'by_object_class': by_object_class,
                'by_user': by_user,
                'recent_changes': recent_changes,
                'report_generated': datetime.now().isoformat(),
                'filters': {
                    'from_date': from_date,
                    'to_date': to_date,
                    'object_class': object_class,
                    'username': username
                }
            }

        except Exception as e:
            logger.error(f"Error generating audit report: {e}")
            return {'error': str(e)}
        finally:
            conn.close()


# Singleton instance
_change_document_service = None


def get_change_document_service() -> ChangeDocumentService:
    """Get or create the change document service instance."""
    global _change_document_service
    if _change_document_service is None:
        _change_document_service = ChangeDocumentService()
    return _change_document_service
