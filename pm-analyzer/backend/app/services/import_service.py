"""
File Import Service for SAP PM Notification Data.

Supports importing notifications and related data from:
- CSV files (flat format, one notification per row)
- JSON files (hierarchical format with nested items/causes/orders)

Import flow:
1. Parse uploaded file (CSV or JSON)
2. Validate and map fields to SAP PM data model
3. Detect duplicates (by QMNUM)
4. Insert into database tables (QMEL, NOTIF_CONTENT, QMFE, QMUR, AUFK, etc.)
5. Record audit trail entries (CDHDR/CDPOS)
6. Return import result with success/error counts

CSV Format (flat):
    QMNUM,QMART,QMTXT,TDLINE,EQUNR,TPLNR,PRIOK,QMNAM,ERDAT,...

JSON Format (hierarchical):
    {
        "notifications": [
            {
                "QMNUM": "...", "QMART": "M1", ...,
                "items": [...], "causes": [...],
                "order": { "AUFNR": "...", "operations": [...] }
            }
        ]
    }
"""

import csv
import io
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.database import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_NOTIFICATION_TYPES = {'M1', 'M2', 'M3', 'M4', 'M5', 'Z1', 'Z2'}
VALID_PRIORITIES = {'1', '2', '3', '4'}
VALID_ORDER_TYPES = {'PM01', 'PM02', 'PM03'}

# Priority name-to-code mapping for friendly CSV input
PRIORITY_NAME_MAP = {
    'very high': '1', 'critical': '1',
    'high': '2', 'urgent': '2',
    'medium': '3', 'normal': '3',
    'low': '4', 'minor': '4',
}

# Notification type name-to-code mapping
NOTIF_TYPE_NAME_MAP = {
    'malfunction': 'M1', 'breakdown': 'M1',
    'maintenance request': 'M2', 'request': 'M2',
    'activity report': 'M3', 'report': 'M3',
}

# Maximum records per import
MAX_IMPORT_RECORDS = 5000

# CSV column aliases (SAP field name -> normalized field)
CSV_ALIASES = {
    # QMNUM aliases
    'notification_number': 'QMNUM',
    'notification_id': 'QMNUM',
    'notif_number': 'QMNUM',
    'notif_id': 'QMNUM',
    'id': 'QMNUM',

    # QMART aliases
    'notification_type': 'QMART',
    'notif_type': 'QMART',
    'type': 'QMART',

    # Text aliases
    'short_text': 'QMTXT',
    'description': 'QMTXT',
    'title': 'QMTXT',

    'long_text': 'TDLINE',
    'detail': 'TDLINE',
    'details': 'TDLINE',

    # Equipment aliases
    'equipment': 'EQUNR',
    'equipment_number': 'EQUNR',
    'equipment_id': 'EQUNR',

    # Functional location aliases
    'functional_location': 'TPLNR',
    'func_loc': 'TPLNR',
    'location': 'TPLNR',

    # Priority aliases
    'priority': 'PRIOK',
    'priority_code': 'PRIOK',

    # User aliases
    'created_by': 'QMNAM',
    'reporter': 'QMNAM',
    'reported_by': 'QMNAM',

    # Date aliases
    'creation_date': 'ERDAT',
    'created_date': 'ERDAT',
    'date': 'ERDAT',

    'creation_time': 'MZEIT',
    'time': 'MZEIT',

    'start_date': 'STRMN',
    'required_start': 'STRMN',

    'end_date': 'LTRMN',
    'required_end': 'LTRMN',
    'due_date': 'LTRMN',

    # Item/damage aliases
    'damage_code': 'FECOD',
    'damage_group': 'FEGRP',
    'object_part': 'OTEIL',
    'object_part_group': 'OTGRP',
    'item_text': 'FETXT',
    'damage_text': 'FETXT',

    # Cause aliases
    'cause_code': 'URCOD',
    'cause_group': 'URGRP',
    'cause_text': 'URTXT',

    # Order aliases
    'order_number': 'AUFNR',
    'work_order': 'AUFNR',
    'order_type': 'AUART',
    'order_text': 'KTEXT',
}


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------

@dataclass
class ImportError:
    """A single validation or import error."""
    row: int
    field: str
    message: str
    value: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'row': self.row,
            'field': self.field,
            'message': self.message,
        }
        if self.value is not None:
            result['value'] = self.value[:100]  # Truncate long values
        return result


@dataclass
class ImportResult:
    """Result of a file import operation."""
    import_id: str
    status: str  # 'completed', 'partial', 'failed'
    total_rows: int = 0
    imported: int = 0
    skipped: int = 0
    errors: List[ImportError] = field(default_factory=list)
    warnings: List[ImportError] = field(default_factory=list)
    duplicate_ids: List[str] = field(default_factory=list)
    imported_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'import_id': self.import_id,
            'status': self.status,
            'total_rows': self.total_rows,
            'imported': self.imported,
            'skipped': self.skipped,
            'error_count': len(self.errors),
            'warning_count': len(self.warnings),
            'errors': [e.to_dict() for e in self.errors[:50]],  # Limit error details
            'warnings': [w.to_dict() for w in self.warnings[:50]],
            'duplicate_ids': self.duplicate_ids[:50],
            'imported_ids': self.imported_ids[:100],
        }


# ---------------------------------------------------------------------------
# Field validation
# ---------------------------------------------------------------------------

def _normalize_date(value: str) -> Optional[str]:
    """Normalize date strings to YYYYMMDD format."""
    if not value:
        return None

    value = value.strip()

    # Already YYYYMMDD
    if re.match(r'^\d{8}$', value):
        return value

    # ISO 8601: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', value)
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}"

    # DD.MM.YYYY (German format)
    m = re.match(r'^(\d{2})\.(\d{2})\.(\d{4})$', value)
    if m:
        return f"{m.group(3)}{m.group(2)}{m.group(1)}"

    # DD/MM/YYYY
    m = re.match(r'^(\d{2})/(\d{2})/(\d{4})$', value)
    if m:
        return f"{m.group(3)}{m.group(2)}{m.group(1)}"

    # MM/DD/YYYY (US format) - ambiguous, try both
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', value)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if month <= 12:
            return f"{year:04d}{month:02d}{day:02d}"

    return None


def _normalize_time(value: str) -> Optional[str]:
    """Normalize time strings to HHMMSS format."""
    if not value:
        return None

    value = value.strip()

    # Already HHMMSS
    if re.match(r'^\d{6}$', value):
        return value

    # HH:MM:SS
    m = re.match(r'^(\d{2}):(\d{2}):(\d{2})$', value)
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}"

    # HH:MM
    m = re.match(r'^(\d{2}):(\d{2})$', value)
    if m:
        return f"{m.group(1)}{m.group(2)}00"

    return None


def _normalize_priority(value: str) -> Optional[str]:
    """Normalize priority to code (1-4)."""
    if not value:
        return None

    value = value.strip()

    # Already a code
    if value in VALID_PRIORITIES:
        return value

    # Try name mapping
    mapped = PRIORITY_NAME_MAP.get(value.lower())
    if mapped:
        return mapped

    return None


def _normalize_notif_type(value: str) -> Optional[str]:
    """Normalize notification type to code (M1-M5, Z1-Z2)."""
    if not value:
        return None

    value = value.strip().upper()

    # Already a code
    if value in VALID_NOTIFICATION_TYPES:
        return value

    # Try name mapping
    mapped = NOTIF_TYPE_NAME_MAP.get(value.lower())
    if mapped:
        return mapped

    return None


def _validate_notification_row(row: Dict[str, Any], row_num: int) -> Tuple[Dict[str, Any], List[ImportError], List[ImportError]]:
    """
    Validate and normalize a single notification row.

    Returns (normalized_data, errors, warnings).
    """
    errors = []
    warnings = []
    data = {}

    # --- Required fields ---

    # QMNUM (required)
    qmnum = str(row.get('QMNUM', '')).strip()
    if not qmnum:
        errors.append(ImportError(row_num, 'QMNUM', 'Notification number is required'))
    elif len(qmnum) > 20:
        errors.append(ImportError(row_num, 'QMNUM', 'Notification number exceeds 20 characters', qmnum))
    elif not re.match(r'^[A-Za-z0-9_-]+$', qmnum):
        errors.append(ImportError(row_num, 'QMNUM', 'Notification number contains invalid characters', qmnum))
    else:
        data['QMNUM'] = qmnum

    # QMART (required)
    qmart_raw = str(row.get('QMART', '')).strip()
    qmart = _normalize_notif_type(qmart_raw)
    if not qmart_raw:
        errors.append(ImportError(row_num, 'QMART', 'Notification type is required'))
    elif not qmart:
        errors.append(ImportError(row_num, 'QMART',
                                  f'Invalid notification type. Must be one of: {", ".join(sorted(VALID_NOTIFICATION_TYPES))}',
                                  qmart_raw))
    else:
        data['QMART'] = qmart

    # --- Optional but recommended fields ---

    # QMTXT (short text / description)
    qmtxt = str(row.get('QMTXT', '')).strip()
    if qmtxt:
        if len(qmtxt) > 500:
            warnings.append(ImportError(row_num, 'QMTXT', 'Short text truncated to 500 characters'))
            qmtxt = qmtxt[:500]
        data['QMTXT'] = qmtxt
    else:
        warnings.append(ImportError(row_num, 'QMTXT', 'Short text/description is missing (recommended for analysis)'))

    # TDLINE (long text)
    tdline = str(row.get('TDLINE', '')).strip()
    if tdline:
        data['TDLINE'] = tdline
    else:
        warnings.append(ImportError(row_num, 'TDLINE', 'Long text is missing (recommended for AI analysis quality)'))

    # EQUNR (equipment)
    equnr = str(row.get('EQUNR', '')).strip()
    if equnr:
        data['EQUNR'] = equnr

    # TPLNR (functional location)
    tplnr = str(row.get('TPLNR', '')).strip()
    if tplnr:
        data['TPLNR'] = tplnr

    if not equnr and not tplnr:
        warnings.append(ImportError(row_num, 'EQUNR/TPLNR',
                                    'Neither equipment nor functional location specified'))

    # PRIOK (priority)
    priok_raw = str(row.get('PRIOK', '')).strip()
    if priok_raw:
        priok = _normalize_priority(priok_raw)
        if priok:
            data['PRIOK'] = priok
        else:
            warnings.append(ImportError(row_num, 'PRIOK',
                                        f'Unrecognized priority "{priok_raw}", must be 1-4 or name',
                                        priok_raw))

    # QMNAM (created by)
    qmnam = str(row.get('QMNAM', '')).strip()
    if qmnam:
        data['QMNAM'] = qmnam

    # ERDAT (creation date)
    erdat_raw = str(row.get('ERDAT', '')).strip()
    if erdat_raw:
        erdat = _normalize_date(erdat_raw)
        if erdat:
            data['ERDAT'] = erdat
        else:
            warnings.append(ImportError(row_num, 'ERDAT',
                                        f'Could not parse date "{erdat_raw}". '
                                        'Expected formats: YYYYMMDD, YYYY-MM-DD, DD.MM.YYYY',
                                        erdat_raw))

    # MZEIT (creation time)
    mzeit_raw = str(row.get('MZEIT', '')).strip()
    if mzeit_raw:
        mzeit = _normalize_time(mzeit_raw)
        if mzeit:
            data['MZEIT'] = mzeit

    # STRMN (required start date)
    strmn_raw = str(row.get('STRMN', '')).strip()
    if strmn_raw:
        strmn = _normalize_date(strmn_raw)
        if strmn:
            data['STRMN'] = strmn

    # LTRMN (required end date)
    ltrmn_raw = str(row.get('LTRMN', '')).strip()
    if ltrmn_raw:
        ltrmn = _normalize_date(ltrmn_raw)
        if ltrmn:
            data['LTRMN'] = ltrmn

    # --- Inline item/damage fields (CSV flat format) ---
    fecod = str(row.get('FECOD', '')).strip()
    fegrp = str(row.get('FEGRP', '')).strip()
    oteil = str(row.get('OTEIL', '')).strip()
    otgrp = str(row.get('OTGRP', '')).strip()
    fetxt = str(row.get('FETXT', '')).strip()
    if fecod or fegrp or oteil or otgrp or fetxt:
        data['_inline_item'] = {
            'FECOD': fecod, 'FEGRP': fegrp,
            'OTEIL': oteil, 'OTGRP': otgrp, 'FETXT': fetxt,
        }

    # --- Inline cause fields (CSV flat format) ---
    urcod = str(row.get('URCOD', '')).strip()
    urgrp = str(row.get('URGRP', '')).strip()
    urtxt = str(row.get('URTXT', '')).strip()
    if urcod or urgrp or urtxt:
        data['_inline_cause'] = {
            'URCOD': urcod, 'URGRP': urgrp, 'URTXT': urtxt,
        }

    # --- Inline order fields (CSV flat format) ---
    aufnr = str(row.get('AUFNR', '')).strip()
    auart = str(row.get('AUART', '')).strip()
    ktext = str(row.get('KTEXT', '')).strip()
    if aufnr:
        if auart and auart.upper() not in VALID_ORDER_TYPES:
            warnings.append(ImportError(row_num, 'AUART',
                                        f'Unrecognized order type "{auart}"', auart))
        data['_inline_order'] = {
            'AUFNR': aufnr,
            'AUART': auart.upper() if auart else 'PM01',
            'KTEXT': ktext,
        }

    return data, errors, warnings


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def _normalize_csv_header(header: str) -> str:
    """Normalize a CSV column header to SAP field name."""
    h = header.strip()

    # Already a SAP field name (uppercase)
    if h.upper() in ('QMNUM', 'QMART', 'QMTXT', 'TDLINE', 'EQUNR', 'TPLNR',
                      'PRIOK', 'QMNAM', 'ERDAT', 'MZEIT', 'STRMN', 'LTRMN',
                      'FECOD', 'FEGRP', 'OTEIL', 'OTGRP', 'FETXT',
                      'URCOD', 'URGRP', 'URTXT',
                      'AUFNR', 'AUART', 'KTEXT'):
        return h.upper()

    # Try alias mapping (case-insensitive)
    normalized = h.lower().strip().replace(' ', '_').replace('-', '_')
    mapped = CSV_ALIASES.get(normalized)
    if mapped:
        return mapped

    return h  # Return as-is, will be ignored


def parse_csv(file_content: str, delimiter: str = ',') -> Tuple[List[Dict[str, str]], List[ImportError]]:
    """
    Parse CSV content into a list of row dicts.

    Handles:
    - Auto-detection of delimiter (comma, semicolon, tab)
    - BOM removal
    - Header normalization via CSV_ALIASES
    """
    errors = []

    # Remove BOM
    if file_content.startswith('\ufeff'):
        file_content = file_content[1:]

    # Auto-detect delimiter
    first_line = file_content.split('\n')[0]
    if delimiter == ',' and ';' in first_line and ',' not in first_line:
        delimiter = ';'
    elif delimiter == ',' and '\t' in first_line and ',' not in first_line:
        delimiter = '\t'

    reader = csv.DictReader(io.StringIO(file_content), delimiter=delimiter)

    if not reader.fieldnames:
        errors.append(ImportError(0, '_header', 'CSV file has no header row'))
        return [], errors

    # Normalize headers
    header_map = {}
    for orig in reader.fieldnames:
        normalized = _normalize_csv_header(orig)
        header_map[orig] = normalized

    # Check for required columns
    mapped_fields = set(header_map.values())
    if 'QMNUM' not in mapped_fields:
        errors.append(ImportError(0, '_header',
                                  'Missing required column: notification number '
                                  '(QMNUM, notification_number, notification_id, or id)'))
    if 'QMART' not in mapped_fields:
        errors.append(ImportError(0, '_header',
                                  'Missing required column: notification type '
                                  '(QMART, notification_type, or type)'))

    if errors:
        return [], errors

    rows = []
    for i, raw_row in enumerate(reader, start=2):  # Row 2+ (row 1 is header)
        mapped_row = {}
        for orig_key, value in raw_row.items():
            if value is None:
                continue
            normalized_key = header_map.get(orig_key, orig_key)
            mapped_row[normalized_key] = value.strip()
        rows.append(mapped_row)

        if len(rows) >= MAX_IMPORT_RECORDS:
            errors.append(ImportError(i, '_limit',
                                      f'Import limited to {MAX_IMPORT_RECORDS} records. '
                                      f'Remaining rows skipped.'))
            break

    return rows, errors


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

def parse_json(file_content: str) -> Tuple[List[Dict[str, Any]], List[ImportError]]:
    """
    Parse JSON content into a list of notification dicts.

    Accepted formats:
    1. { "notifications": [...] }
    2. [...] (array of notifications)
    3. { "QMNUM": "..." } (single notification)
    """
    errors = []

    try:
        data = json.loads(file_content)
    except json.JSONDecodeError as e:
        errors.append(ImportError(0, '_json', f'Invalid JSON: {e}'))
        return [], errors

    # Determine format
    if isinstance(data, dict):
        if 'notifications' in data:
            notifications = data['notifications']
        elif 'QMNUM' in data or 'notification_number' in data:
            # Single notification
            notifications = [data]
        else:
            # Try to find any list-like key
            for key, val in data.items():
                if isinstance(val, list) and len(val) > 0:
                    notifications = val
                    break
            else:
                errors.append(ImportError(0, '_json',
                                          'JSON must contain "notifications" array or be an array'))
                return [], errors
    elif isinstance(data, list):
        notifications = data
    else:
        errors.append(ImportError(0, '_json', 'JSON must be an object or array'))
        return [], errors

    if not isinstance(notifications, list):
        errors.append(ImportError(0, '_json', '"notifications" must be an array'))
        return [], errors

    if len(notifications) > MAX_IMPORT_RECORDS:
        errors.append(ImportError(0, '_limit',
                                  f'Import limited to {MAX_IMPORT_RECORDS} records. '
                                  f'{len(notifications) - MAX_IMPORT_RECORDS} records skipped.'))
        notifications = notifications[:MAX_IMPORT_RECORDS]

    # Normalize JSON keys (handle both SAP field names and friendly names)
    rows = []
    for i, notif in enumerate(notifications):
        if not isinstance(notif, dict):
            errors.append(ImportError(i + 1, '_json', 'Each notification must be a JSON object'))
            continue

        mapped = {}
        for key, value in notif.items():
            upper_key = key.upper()
            # Check SAP field names first
            if upper_key in ('QMNUM', 'QMART', 'QMTXT', 'TDLINE', 'EQUNR', 'TPLNR',
                             'PRIOK', 'QMNAM', 'ERDAT', 'MZEIT', 'STRMN', 'LTRMN',
                             'FECOD', 'FEGRP', 'OTEIL', 'OTGRP', 'FETXT',
                             'URCOD', 'URGRP', 'URTXT', 'AUFNR', 'AUART', 'KTEXT'):
                mapped[upper_key] = value
            else:
                # Try alias
                normalized = key.lower().strip().replace(' ', '_').replace('-', '_')
                alias = CSV_ALIASES.get(normalized)
                if alias:
                    mapped[alias] = value
                elif key in ('items', 'causes', 'order', 'activities'):
                    mapped[f'_{key}'] = value
                # Ignore unknown keys

        rows.append(mapped)

    return rows, errors


# ---------------------------------------------------------------------------
# Database insertion
# ---------------------------------------------------------------------------

def _get_existing_qmnums(db, qmnums: List[str]) -> set:
    """Check which QMNUMs already exist in the database."""
    if not qmnums:
        return set()

    existing = set()
    # Query in batches of 100
    for i in range(0, len(qmnums), 100):
        batch = qmnums[i:i+100]
        placeholders = ','.join(['?' for _ in batch])
        cursor = db.execute(
            f"SELECT QMNUM FROM QMEL WHERE QMNUM IN ({placeholders})",
            batch
        )
        for row in cursor.fetchall():
            existing.add(row['QMNUM'])

    return existing


def _insert_notification(db, data: Dict[str, Any], language: str, import_id: str, username: str):
    """Insert a single notification and its related records."""
    qmnum = data['QMNUM']

    # Insert QMEL (notification header)
    db.execute(
        """INSERT INTO QMEL (QMNUM, QMART, EQUNR, TPLNR, PRIOK, QMNAM, ERDAT, MZEIT, STRMN, LTRMN)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (qmnum, data.get('QMART'), data.get('EQUNR'), data.get('TPLNR'),
         data.get('PRIOK'), data.get('QMNAM'), data.get('ERDAT'),
         data.get('MZEIT'), data.get('STRMN'), data.get('LTRMN'))
    )

    # Insert NOTIF_CONTENT (short text + long text)
    qmtxt = data.get('QMTXT')
    tdline = data.get('TDLINE')
    if qmtxt or tdline:
        db.execute(
            """INSERT INTO NOTIF_CONTENT (QMNUM, SPRAS, QMTXT, TDLINE)
               VALUES (?, ?, ?, ?)""",
            (qmnum, language, qmtxt, tdline)
        )

    # Insert inline item (from CSV flat format)
    inline_item = data.get('_inline_item')
    if inline_item:
        fenum = '0001'
        db.execute(
            """INSERT INTO QMFE (QMNUM, FENUM, OTGRP, OTEIL, FEGRP, FECOD)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (qmnum, fenum, inline_item.get('OTGRP'), inline_item.get('OTEIL'),
             inline_item.get('FEGRP'), inline_item.get('FECOD'))
        )
        fetxt = inline_item.get('FETXT')
        if fetxt:
            db.execute(
                """INSERT INTO QMFE_TEXT (QMNUM, FENUM, SPRAS, FETXT)
                   VALUES (?, ?, ?, ?)""",
                (qmnum, fenum, language, fetxt)
            )

    # Insert inline cause (from CSV flat format)
    inline_cause = data.get('_inline_cause')
    if inline_cause and inline_item:
        fenum = '0001'
        urnum = '0001'
        db.execute(
            """INSERT INTO QMUR (QMNUM, FENUM, URNUM, URGRP, URCOD)
               VALUES (?, ?, ?, ?, ?)""",
            (qmnum, fenum, urnum, inline_cause.get('URGRP'), inline_cause.get('URCOD'))
        )
        urtxt = inline_cause.get('URTXT')
        if urtxt:
            db.execute(
                """INSERT INTO QMUR_TEXT (QMNUM, FENUM, URNUM, SPRAS, URTXT)
                   VALUES (?, ?, ?, ?, ?)""",
                (qmnum, fenum, urnum, language, urtxt)
            )

    # Insert JSON-format items (nested array)
    items = data.get('_items', [])
    if isinstance(items, list):
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            fenum = item.get('FENUM', f'{idx + 1:04d}')
            db.execute(
                """INSERT INTO QMFE (QMNUM, FENUM, OTGRP, OTEIL, FEGRP, FECOD)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (qmnum, fenum, item.get('OTGRP'), item.get('OTEIL'),
                 item.get('FEGRP'), item.get('FECOD'))
            )
            fetxt = item.get('FETXT', item.get('text', ''))
            if fetxt:
                db.execute(
                    """INSERT INTO QMFE_TEXT (QMNUM, FENUM, SPRAS, FETXT)
                       VALUES (?, ?, ?, ?)""",
                    (qmnum, fenum, language, fetxt)
                )

            # Nested causes within items
            item_causes = item.get('causes', [])
            if isinstance(item_causes, list):
                for cidx, cause in enumerate(item_causes):
                    if not isinstance(cause, dict):
                        continue
                    urnum = cause.get('URNUM', f'{cidx + 1:04d}')
                    db.execute(
                        """INSERT INTO QMUR (QMNUM, FENUM, URNUM, URGRP, URCOD)
                           VALUES (?, ?, ?, ?, ?)""",
                        (qmnum, fenum, urnum, cause.get('URGRP'), cause.get('URCOD'))
                    )
                    urtxt = cause.get('URTXT', cause.get('text', ''))
                    if urtxt:
                        db.execute(
                            """INSERT INTO QMUR_TEXT (QMNUM, FENUM, URNUM, SPRAS, URTXT)
                               VALUES (?, ?, ?, ?, ?)""",
                            (qmnum, fenum, urnum, language, urtxt)
                        )

    # Insert JSON-format causes at notification level (not nested under items)
    causes = data.get('_causes', [])
    if isinstance(causes, list) and not items:
        fenum = '0001'
        # Create a placeholder item if causes exist but no items
        if causes:
            try:
                db.execute(
                    """INSERT INTO QMFE (QMNUM, FENUM, OTGRP, OTEIL, FEGRP, FECOD)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (qmnum, fenum, None, None, None, None)
                )
            except Exception:
                pass  # Item might already exist

        for cidx, cause in enumerate(causes):
            if not isinstance(cause, dict):
                continue
            urnum = cause.get('URNUM', f'{cidx + 1:04d}')
            db.execute(
                """INSERT INTO QMUR (QMNUM, FENUM, URNUM, URGRP, URCOD)
                   VALUES (?, ?, ?, ?, ?)""",
                (qmnum, fenum, urnum, cause.get('URGRP'), cause.get('URCOD'))
            )
            urtxt = cause.get('URTXT', cause.get('text', ''))
            if urtxt:
                db.execute(
                    """INSERT INTO QMUR_TEXT (QMNUM, FENUM, URNUM, SPRAS, URTXT)
                       VALUES (?, ?, ?, ?, ?)""",
                    (qmnum, fenum, urnum, language, urtxt)
                )

    # Insert inline order (from CSV flat format or JSON)
    inline_order = data.get('_inline_order')
    order_data = data.get('_order')
    if isinstance(order_data, dict):
        inline_order = {
            'AUFNR': order_data.get('AUFNR', ''),
            'AUART': order_data.get('AUART', 'PM01'),
            'KTEXT': order_data.get('KTEXT', ''),
        }
        operations = order_data.get('operations', [])
    else:
        operations = []

    if inline_order and inline_order.get('AUFNR'):
        aufnr = inline_order['AUFNR']
        db.execute(
            """INSERT INTO AUFK (AUFNR, QMNUM, AUART, KTEXT)
               VALUES (?, ?, ?, ?)""",
            (aufnr, qmnum, inline_order.get('AUART', 'PM01'),
             inline_order.get('KTEXT'))
        )

        # Insert operations (JSON format only)
        if isinstance(operations, list):
            for oidx, op in enumerate(operations):
                if not isinstance(op, dict):
                    continue
                vornr = op.get('VORNR', f'{(oidx + 1) * 10:04d}')
                db.execute(
                    """INSERT INTO AFVC (AUFNR, VORNR, ARBPL, STEUS, DAUER, DAUERE)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (aufnr, vornr, op.get('ARBPL'), op.get('STEUS'),
                     op.get('DAUER'), op.get('DAUERE'))
                )
                ltxa1 = op.get('LTXA1', op.get('text', ''))
                if ltxa1:
                    db.execute(
                        """INSERT INTO AFVC_TEXT (AUFNR, VORNR, SPRAS, LTXA1)
                           VALUES (?, ?, ?, ?)""",
                        (aufnr, vornr, language, ltxa1)
                    )

                # Insert materials
                materials = op.get('materials', [])
                if isinstance(materials, list):
                    for mat in materials:
                        if not isinstance(mat, dict) or not mat.get('MATNR'):
                            continue
                        db.execute(
                            """INSERT INTO RESB (AUFNR, VORNR, MATNR, MENGE, MEINS)
                               VALUES (?, ?, ?, ?, ?)""",
                            (aufnr, vornr, mat['MATNR'],
                             float(mat.get('MENGE', 0)), mat.get('MEINS', 'EA'))
                        )
                        maktx = mat.get('MAKTX', mat.get('description', ''))
                        if maktx:
                            try:
                                db.execute(
                                    """INSERT INTO MAKT (MATNR, SPRAS, MAKTX)
                                       VALUES (?, ?, ?)""",
                                    (mat['MATNR'], language, maktx)
                                )
                            except Exception:
                                pass  # Material text may already exist

    # Record audit trail
    now = datetime.utcnow()
    changenr = f"IMP{import_id[:8]}{qmnum[:8]}"[:20]
    try:
        db.execute(
            """INSERT INTO CDHDR (CHANGENR, OBJECTCLAS, OBJECTID, USERNAME, UDATE, UTIME, TCODE, CHANGE_IND)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (changenr, 'QMEL', qmnum, username,
             now.strftime('%Y%m%d'), now.strftime('%H%M%S'),
             'FILE_IMPORT', 'I')
        )
        db.execute(
            """INSERT INTO CDPOS (CHANGENR, TABNAME, TABKEY, FNAME, VALUE_NEW, VALUE_OLD, CHNGIND)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (changenr, 'QMEL', qmnum, 'IMPORT_SOURCE', f'file_import:{import_id}', '', 'I')
        )
    except Exception:
        pass  # Don't fail the import over audit trail errors


# ---------------------------------------------------------------------------
# Main import functions
# ---------------------------------------------------------------------------

def import_csv(file_content: str, language: str = 'en',
               mode: str = 'skip', username: str = 'IMPORT',
               delimiter: str = ',') -> ImportResult:
    """
    Import notifications from CSV content.

    Args:
        file_content: Raw CSV string
        language: Language code for text fields (default 'en')
        mode: Duplicate handling - 'skip' (default), 'replace', or 'error'
        username: User performing the import (for audit trail)
        delimiter: CSV delimiter (auto-detected if not specified)

    Returns:
        ImportResult with success/error counts
    """
    import_id = uuid.uuid4().hex[:12]
    result = ImportResult(import_id=import_id, status='completed')

    # Parse CSV
    rows, parse_errors = parse_csv(file_content, delimiter)
    result.errors.extend(parse_errors)

    if not rows:
        result.status = 'failed'
        if not parse_errors:
            result.errors.append(ImportError(0, '_file', 'CSV file contains no data rows'))
        return result

    result.total_rows = len(rows)

    # Validate all rows
    validated = []
    for i, row in enumerate(rows, start=2):
        data, errors, warnings = _validate_notification_row(row, i)
        result.errors.extend(errors)
        result.warnings.extend(warnings)
        if not errors and 'QMNUM' in data:
            validated.append(data)

    if not validated:
        result.status = 'failed'
        return result

    # Check duplicates
    qmnums = [d['QMNUM'] for d in validated]
    db = get_db()
    existing = _get_existing_qmnums(db, qmnums)

    # Insert records
    for data in validated:
        qmnum = data['QMNUM']
        if qmnum in existing:
            if mode == 'skip':
                result.skipped += 1
                result.duplicate_ids.append(qmnum)
                continue
            elif mode == 'replace':
                _delete_notification(db, qmnum)
            elif mode == 'error':
                result.errors.append(ImportError(0, 'QMNUM',
                                                 f'Duplicate notification: {qmnum}', qmnum))
                result.skipped += 1
                result.duplicate_ids.append(qmnum)
                continue

        try:
            _insert_notification(db, data, language, import_id, username)
            result.imported += 1
            result.imported_ids.append(qmnum)
        except Exception as e:
            logger.error(f"Error inserting notification {qmnum}: {e}")
            result.errors.append(ImportError(0, 'QMNUM',
                                             f'Database error for {qmnum}: {str(e)[:200]}',
                                             qmnum))

    db.commit()

    if result.imported == 0:
        result.status = 'failed'
    elif result.errors:
        result.status = 'partial'

    return result


def import_json(file_content: str, language: str = 'en',
                mode: str = 'skip', username: str = 'IMPORT') -> ImportResult:
    """
    Import notifications from JSON content.

    Args:
        file_content: Raw JSON string
        language: Language code for text fields (default 'en')
        mode: Duplicate handling - 'skip' (default), 'replace', or 'error'
        username: User performing the import (for audit trail)

    Returns:
        ImportResult with success/error counts
    """
    import_id = uuid.uuid4().hex[:12]
    result = ImportResult(import_id=import_id, status='completed')

    # Parse JSON
    rows, parse_errors = parse_json(file_content)
    result.errors.extend(parse_errors)

    if not rows:
        result.status = 'failed'
        if not parse_errors:
            result.errors.append(ImportError(0, '_file', 'JSON contains no notifications'))
        return result

    result.total_rows = len(rows)

    # Validate all rows
    validated = []
    for i, row in enumerate(rows, start=1):
        data, errors, warnings = _validate_notification_row(row, i)
        result.errors.extend(errors)
        result.warnings.extend(warnings)
        if not errors and 'QMNUM' in data:
            # Preserve nested structures from JSON
            for key in ('_items', '_causes', '_order', '_activities'):
                if key in row:
                    data[key] = row[key]
            validated.append(data)

    if not validated:
        result.status = 'failed'
        return result

    # Check duplicates
    qmnums = [d['QMNUM'] for d in validated]
    db = get_db()
    existing = _get_existing_qmnums(db, qmnums)

    # Insert records
    for data in validated:
        qmnum = data['QMNUM']
        if qmnum in existing:
            if mode == 'skip':
                result.skipped += 1
                result.duplicate_ids.append(qmnum)
                continue
            elif mode == 'replace':
                _delete_notification(db, qmnum)
            elif mode == 'error':
                result.errors.append(ImportError(0, 'QMNUM',
                                                 f'Duplicate notification: {qmnum}', qmnum))
                result.skipped += 1
                result.duplicate_ids.append(qmnum)
                continue

        try:
            _insert_notification(db, data, language, import_id, username)
            result.imported += 1
            result.imported_ids.append(qmnum)
        except Exception as e:
            logger.error(f"Error inserting notification {qmnum}: {e}")
            result.errors.append(ImportError(0, 'QMNUM',
                                             f'Database error for {qmnum}: {str(e)[:200]}',
                                             qmnum))

    db.commit()

    if result.imported == 0:
        result.status = 'failed'
    elif result.errors:
        result.status = 'partial'

    return result


def validate_file(file_content: str, file_format: str = 'csv',
                  delimiter: str = ',') -> ImportResult:
    """
    Validate a file without importing (dry run).

    Returns an ImportResult with validation results but imported=0.
    """
    import_id = f"dry_{uuid.uuid4().hex[:8]}"
    result = ImportResult(import_id=import_id, status='completed')

    # Parse
    if file_format == 'json':
        rows, parse_errors = parse_json(file_content)
    else:
        rows, parse_errors = parse_csv(file_content, delimiter)

    result.errors.extend(parse_errors)

    if not rows:
        result.status = 'failed'
        return result

    result.total_rows = len(rows)

    # Validate all rows
    valid_count = 0
    start_row = 1 if file_format == 'json' else 2
    for i, row in enumerate(rows, start=start_row):
        _, errors, warnings = _validate_notification_row(row, i)
        result.errors.extend(errors)
        result.warnings.extend(warnings)
        if not errors:
            valid_count += 1

    # Check for duplicates
    qmnums = [str(row.get('QMNUM', '')).strip() for row in rows
              if str(row.get('QMNUM', '')).strip()]
    if qmnums:
        db = get_db()
        existing = _get_existing_qmnums(db, qmnums)
        result.duplicate_ids = list(existing)

    result.skipped = result.total_rows - valid_count

    if valid_count == 0 and result.total_rows > 0:
        result.status = 'failed'
    elif result.errors:
        result.status = 'partial'

    return result


def _delete_notification(db, qmnum: str):
    """Delete a notification and all related records (for replace mode)."""
    # Delete in reverse dependency order
    db.execute("DELETE FROM CDPOS WHERE CHANGENR IN (SELECT CHANGENR FROM CDHDR WHERE OBJECTID = ?)", (qmnum,))
    db.execute("DELETE FROM CDHDR WHERE OBJECTID = ?", (qmnum,))
    db.execute("DELETE FROM QMIH WHERE QMNUM = ?", (qmnum,))

    # Delete order-related records
    db.execute("DELETE FROM RESB WHERE AUFNR IN (SELECT AUFNR FROM AUFK WHERE QMNUM = ?)", (qmnum,))
    db.execute("DELETE FROM AFVC_TEXT WHERE AUFNR IN (SELECT AUFNR FROM AUFK WHERE QMNUM = ?)", (qmnum,))
    db.execute("DELETE FROM AFVC WHERE AUFNR IN (SELECT AUFNR FROM AUFK WHERE QMNUM = ?)", (qmnum,))
    db.execute("DELETE FROM AFRU WHERE AUFNR IN (SELECT AUFNR FROM AUFK WHERE QMNUM = ?)", (qmnum,))
    db.execute("DELETE FROM AUFK WHERE QMNUM = ?", (qmnum,))

    # Delete notification-related records
    db.execute("DELETE FROM QMUR_TEXT WHERE QMNUM = ?", (qmnum,))
    db.execute("DELETE FROM QMUR WHERE QMNUM = ?", (qmnum,))
    db.execute("DELETE FROM QMFE_TEXT WHERE QMNUM = ?", (qmnum,))
    db.execute("DELETE FROM QMFE WHERE QMNUM = ?", (qmnum,))
    db.execute("DELETE FROM QMAK WHERE QMNUM = ?", (qmnum,))
    db.execute("DELETE FROM NOTIF_CONTENT WHERE QMNUM = ?", (qmnum,))
    db.execute("DELETE FROM QMEL WHERE QMNUM = ?", (qmnum,))


def get_import_template(file_format: str = 'csv') -> str:
    """
    Generate a template file for import.

    Args:
        file_format: 'csv' or 'json'

    Returns:
        Template content as string
    """
    if file_format == 'json':
        template = {
            "notifications": [
                {
                    "QMNUM": "000300000001",
                    "QMART": "M1",
                    "QMTXT": "Pump P-101 bearing failure - excessive vibration detected",
                    "TDLINE": "During routine inspection, excessive vibration was detected on pump P-101. "
                              "Vibration readings exceeded 12mm/s on the drive-end bearing. "
                              "Bearing temperature also elevated to 85°C (normal: 45-55°C). "
                              "Immediate maintenance required to prevent catastrophic failure.",
                    "EQUNR": "PUMP-101",
                    "TPLNR": "PLANT-A-AREA1",
                    "PRIOK": "1",
                    "QMNAM": "JSMITH",
                    "ERDAT": "2025-01-15",
                    "MZEIT": "08:30:00",
                    "STRMN": "2025-01-15",
                    "LTRMN": "2025-01-16",
                    "items": [
                        {
                            "FENUM": "0001",
                            "OTGRP": "PUMP",
                            "OTEIL": "BEARING",
                            "FEGRP": "MECH",
                            "FECOD": "VIBRATION",
                            "FETXT": "Drive-end bearing excessive vibration >12mm/s",
                            "causes": [
                                {
                                    "URNUM": "0001",
                                    "URGRP": "WEAR",
                                    "URCOD": "BEARING_WEAR",
                                    "URTXT": "Normal bearing wear after 18000 operating hours"
                                }
                            ]
                        }
                    ],
                    "order": {
                        "AUFNR": "000400000001",
                        "AUART": "PM01",
                        "KTEXT": "Replace drive-end bearing on pump P-101",
                        "operations": [
                            {
                                "VORNR": "0010",
                                "LTXA1": "Isolate and lock-out pump P-101",
                                "ARBPL": "MECH01",
                                "DAUER": "0.5",
                                "DAUERE": "H"
                            },
                            {
                                "VORNR": "0020",
                                "LTXA1": "Remove and replace drive-end bearing",
                                "ARBPL": "MECH01",
                                "DAUER": "3.0",
                                "DAUERE": "H",
                                "materials": [
                                    {
                                        "MATNR": "BRG-6210-2RS",
                                        "MAKTX": "Deep groove ball bearing 6210-2RS",
                                        "MENGE": 1,
                                        "MEINS": "EA"
                                    },
                                    {
                                        "MATNR": "LUB-GREASE-01",
                                        "MAKTX": "High-temperature bearing grease",
                                        "MENGE": 0.5,
                                        "MEINS": "KG"
                                    }
                                ]
                            },
                            {
                                "VORNR": "0030",
                                "LTXA1": "Test run and vibration measurement",
                                "ARBPL": "MECH01",
                                "DAUER": "1.0",
                                "DAUERE": "H"
                            }
                        ]
                    }
                },
                {
                    "QMNUM": "000300000002",
                    "QMART": "M2",
                    "QMTXT": "Conveyor belt alignment check required",
                    "TDLINE": "Conveyor CV-201 showing signs of belt tracking issues. "
                              "Belt drifting to the left side. Preventive realignment needed.",
                    "EQUNR": "CONV-201",
                    "TPLNR": "PLANT-A-AREA2",
                    "PRIOK": "3",
                    "QMNAM": "MJONES",
                    "ERDAT": "2025-01-20"
                }
            ]
        }
        return json.dumps(template, indent=2)
    else:
        # CSV template
        lines = [
            "QMNUM,QMART,QMTXT,TDLINE,EQUNR,TPLNR,PRIOK,QMNAM,ERDAT,FECOD,FEGRP,FETXT,AUFNR,AUART",
            '"000300000001","M1","Pump P-101 bearing failure - excessive vibration","During routine inspection, excessive vibration detected on pump P-101. Vibration readings exceeded 12mm/s on drive-end bearing. Bearing temperature 85°C (normal: 45-55°C).","PUMP-101","PLANT-A-AREA1","1","JSMITH","2025-01-15","VIBRATION","MECH","Drive-end bearing excessive vibration","000400000001","PM01"',
            '"000300000002","M2","Conveyor belt alignment check required","Conveyor CV-201 showing signs of belt tracking issues. Belt drifting to the left side.","CONV-201","PLANT-A-AREA2","3","MJONES","2025-01-20","","","","",""',
            '"000300000003","M1","Compressor C-301 oil pressure low","Oil pressure gauge on compressor C-301 reading 2.1 bar (minimum: 2.5 bar). Oil level checked and normal. Possible pressure sensor or relief valve issue.","COMP-301","PLANT-B-AREA1","2","KLEE","2025-01-22","LOW_PRESS","HYDR","Oil pressure below minimum threshold","000400000002","PM01"',
        ]
        return '\n'.join(lines)
