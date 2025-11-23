from typing import List, Optional, Dict, Any
from app.database import get_db
from app.models import UnifiedPMObject, DBNotificationHeader, DBOrderHeader, DBNotificationItem, DBOperation, DBMaterial

# --- Mapping Helpers (unchanged) ---
def get_priority_text(code: str, language: str = 'en') -> str:
    mappings = {
        "en": { "1": "Very High", "2": "High", "3": "Medium", "4": "Low" },
        "de": { "1": "Sehr Hoch", "2": "Hoch", "3": "Mittel", "4": "Niedrig" }
    }
    lang_map = mappings.get(language, mappings["en"])
    return lang_map.get(code, code)

def get_notif_type_text(code: str, language: str = 'en') -> str:
    mappings = {
        "en": { "M1": "Maintenance Request", "M2": "Malfunction Report", "M3": "Activity Report" },
        "de": { "M1": "Instandhaltungsanforderung", "M2": "Störmeldung", "M3": "Tätigkeitsmeldung" }
    }
    lang_map = mappings.get(language, mappings["en"])
    return lang_map.get(code, code)

def get_order_type_text(code: str, language: str = 'en') -> str:
    mappings = {
        "en": { "PM01": "Maintenance Order", "PM02": "Planned Order", "PM03": "Refurbishment Order" },
        "de": { "PM01": "Instandhaltungsauftrag", "PM02": "Geplanter Auftrag", "PM03": "Aufarbeitungsauftrag" }
    }
    lang_map = mappings.get(language, mappings["en"])
    return lang_map.get(code, code)

# -----------------------

def get_all_notifications_summary(language: str = 'en') -> List[Dict[str, Any]]:
    """
    Returns a list of notifications for the Worklist with localized text.
    """
    db = get_db()
    cursor = db.execute("""
        SELECT n.QMNUM, n.QMART, n.PRIOK, n.QMNAM, n.ERDAT, n.MZEIT, n.STRMN, n.LTRMN, n.EQUNR, n.TPLNR,
               t.QMTXT
        FROM QMEL n
        LEFT JOIN NOTIF_CONTENT t ON n.QMNUM = t.QMNUM AND t.SPRAS = ?
        ORDER BY n.ERDAT DESC, n.MZEIT DESC
    """, (language,))
    rows = cursor.fetchall()
    
    results = []
    for row in rows:
        results.append({
            "NotificationId": row["QMNUM"],
            "NotificationType": row["QMART"],
            "NotificationTypeText": get_notif_type_text(row["QMART"], language), 
            "Description": row["QMTXT"] or "(No Description)", 
            "Priority": row["PRIOK"],
            "PriorityText": get_priority_text(row["PRIOK"], language), 
            "CreatedByUser": row["QMNAM"],
            "CreationDate": row["ERDAT"],
            "RequiredStartDate": row["STRMN"],
            "RequiredEndDate": row["LTRMN"],
            "EquipmentNumber": row["EQUNR"],
            "FunctionalLocation": row["TPLNR"],
            "SystemStatus": "OSDN", 
            "SystemStatusText": "Outstanding" 
        })
    return results

def get_unified_notification(notification_id: str, language: str = 'en') -> Optional[Dict[str, Any]]:
    """
    Fetches the full object graph (Notification + Order) with localized content.
    """
    db = get_db()
    
    # 1. Fetch Notification Header + Content
    cur = db.execute("""
        SELECT n.*, t.QMTXT, t.TDLINE as LongText
        FROM QMEL n
        LEFT JOIN NOTIF_CONTENT t ON n.QMNUM = t.QMNUM AND t.SPRAS = ?
        WHERE n.QMNUM = ?
    """, (language, notification_id))
    row = cur.fetchone()
    
    if not row:
        return None

    print(f"DEBUG: Fetched Row Values ({language}): {dict(row)}")

    # Map Header
    notification_data = {
        "NotificationId": row["QMNUM"],
        "NotificationType": row["QMART"],
        "NotificationTypeText": get_notif_type_text(row["QMART"], language), 
        "Description": row["QMTXT"] or "(No Description)",
        "EquipmentNumber": row["EQUNR"],
        "FunctionalLocation": row["TPLNR"],
        "Priority": row["PRIOK"],
        "PriorityText": get_priority_text(row["PRIOK"], language), 
        "CreatedByUser": row["QMNAM"],
        "CreationDate": row["ERDAT"],
        "RequiredStartDate": row["STRMN"],
        "RequiredEndDate": row["LTRMN"],
        "MalfunctionStartDate": row["STRMN"], 
        "MalfunctionEndDate": row["LTRMN"],  
        "LongText": row["LongText"] or "",
        "SystemStatus": "OSDN", 
        "Items": [],
        "Damage": {}, 
        "Cause": {}   
    }

    # 2. Fetch Items (Damage) + Localized Text
    cur_items = db.execute("""
        SELECT i.*, t.FETXT
        FROM QMFE i
        LEFT JOIN QMFE_TEXT t ON i.QMNUM = t.QMNUM AND i.FENUM = t.FENUM AND t.SPRAS = ?
        WHERE i.QMNUM = ?
    """, (language, notification_id))
    items = cur_items.fetchall()
    for item in items:
        description = item["FETXT"] or "(No Text)"
        notification_data["Items"].append({
            "ItemSortNo": item["FENUM"],
            "ObjectPartGroup": item["OTGRP"],
            "ObjectPart": item["OTEIL"],
            "DamageCodeGroup": item["FEGRP"],
            "DamageCode": item["FECOD"],
            "Description": description
        })
        if not notification_data["Damage"]:
             notification_data["Damage"] = {
                 "CodeGroup": item["FEGRP"],
                 "Code": item["FECOD"],
                 "Text": description
             }

    # 3. Fetch Causes + Localized Text
    cur_causes = db.execute("""
        SELECT c.*, t.URTXT
        FROM QMUR c
        LEFT JOIN QMUR_TEXT t ON c.QMNUM = t.QMNUM AND c.FENUM = t.FENUM AND c.URNUM = t.URNUM AND t.SPRAS = ?
        WHERE c.QMNUM = ?
    """, (language, notification_id))
    cause = cur_causes.fetchone()
    if cause:
        description = cause["URTXT"] or "(No Text)"
        notification_data["Cause"] = {
            "CodeGroup": cause["URGRP"],
            "Code": cause["URCOD"],
            "Text": description
        }

    # 4. Fetch Order Header
    cur_order = db.execute("SELECT * FROM AUFK WHERE QMNUM = ?", (notification_id,))
    order_row = cur_order.fetchone()
    
    work_order_data = None
    if order_row:
        work_order_data = {
            "OrderId": order_row["AUFNR"],
            "OrderType": order_row["AUART"],
            "OrderTypeText": get_order_type_text(order_row["AUART"], language), 
            "Description": order_row["KTEXT"],
            "BasicStartDate": order_row["GLTRP"],
            "BasicEndDate": order_row["GLTRS"],
            "SystemStatus": "REL", 
            "WorkCenter": "MECH-01", 
            "PlannerGroup": "PG1",   
            "Operations": [],
            "AllMaterials": [] 
        }

        # 5. Fetch Operations + Localized Text
        cur_ops = db.execute("""
            SELECT o.*, t.LTXA1
            FROM AFVC o
            LEFT JOIN AFVC_TEXT t ON o.AUFNR = t.AUFNR AND o.VORNR = t.VORNR AND t.SPRAS = ?
            WHERE o.AUFNR = ?
        """, (language, work_order_data["OrderId"]))
        ops = cur_ops.fetchall()
        for op in ops:
            op_desc = op["LTXA1"] or "(No Text)"
            op_data = {
                "OperationNumber": op["VORNR"],
                "Description": op_desc,
                "WorkCenter": op["ARBPL"],
                "Duration": op["DAUER"],
                "DurationUnit": op["DAUERE"],
                "Materials": []
            }
            
            # 6. Fetch Materials per Operation + Localized Text
            cur_mats = db.execute("""
                SELECT m.*, t.MAKTX
                FROM RESB m
                LEFT JOIN MAKT t ON m.MATNR = t.MATNR AND t.SPRAS = ?
                WHERE m.AUFNR = ? AND m.VORNR = ?
            """, (language, work_order_data["OrderId"], op["VORNR"]))
            mats = cur_mats.fetchall()
            for mat in mats:
                mat_desc = mat["MAKTX"] or "(No Text)"
                mat_data = {
                    "MaterialNumber": mat["MATNR"],
                    "Description": mat_desc,
                    "Quantity": mat["MENGE"],
                    "Unit": mat["MEINS"],
                    "ForOperation": op["VORNR"] 
                }
                op_data["Materials"].append(mat_data)
                work_order_data["AllMaterials"].append(mat_data)
            
            work_order_data["Operations"].append(op_data)

    # Construct final response
    response = notification_data
    if work_order_data:
        response["WorkOrder"] = work_order_data
    
    return response