"""
Seed data for SAP PM Compliance Enhancement Tables

This script populates the following tables with master data:
- TJ02T: System status texts (multi-language)
- QMCATALOG: Damage/cause/activity code master
- EQUI/EQKT: Equipment master with texts
- IFLOT/IFLOTX: Functional location master with texts
- JEST: Initial object statuses
"""

import sqlite3
import os
from datetime import datetime

DATABASE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'pm_notifications.db'
)


def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def seed_status_texts(cursor):
    """Seed TJ02T - System Status Texts"""
    print("--- Seeding TJ02T (Status Texts) ---")

    statuses = [
        # System Statuses - English
        ('CRTD', 'en', 'CRTD', 'Created'),
        ('OSDN', 'en', 'OSDN', 'Outstanding'),
        ('INPR', 'en', 'INPR', 'In Process'),
        ('REL', 'en', 'REL', 'Released'),
        ('PCNF', 'en', 'PCNF', 'Partially Confirmed'),
        ('CNF', 'en', 'CNF', 'Confirmed'),
        ('TECO', 'en', 'TECO', 'Technically Complete'),
        ('CLSD', 'en', 'CLSD', 'Closed'),
        ('DLFL', 'en', 'DLFL', 'Deletion Flag'),
        ('NOCO', 'en', 'NOCO', 'Not Completed'),
        ('MANC', 'en', 'MANC', 'Manually Completed'),
        ('SETC', 'en', 'SETC', 'Settlement Complete'),

        # System Statuses - German
        ('CRTD', 'de', 'ERST', 'Erstellt'),
        ('OSDN', 'de', 'OFFE', 'Offen'),
        ('INPR', 'de', 'BEAR', 'In Bearbeitung'),
        ('REL', 'de', 'FREI', 'Freigegeben'),
        ('PCNF', 'de', 'TRUC', 'Teilrückmeldung'),
        ('CNF', 'de', 'RÜCK', 'Rückgemeldet'),
        ('TECO', 'de', 'TABG', 'Technisch abgeschlossen'),
        ('CLSD', 'de', 'ABGS', 'Abgeschlossen'),
        ('DLFL', 'de', 'LÖKZ', 'Löschvormerkung'),
        ('NOCO', 'de', 'NIAB', 'Nicht abgeschlossen'),
        ('MANC', 'de', 'MABG', 'Manuell abgeschlossen'),
        ('SETC', 'de', 'ABGR', 'Abrechnung abgeschlossen'),
    ]

    for status in statuses:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO TJ02T (ISTAT, SPRAS, TXT04, TXT30)
                VALUES (?, ?, ?, ?)
            """, status)
        except Exception as e:
            print(f"  Warning: Could not insert status {status[0]}: {e}")

    print(f"  Inserted {len(statuses)} status texts")


def seed_catalog_codes(cursor):
    """Seed QMCATALOG - Damage/Cause/Activity Codes"""
    print("--- Seeding QMCATALOG (Catalog Codes) ---")

    today = datetime.now().strftime('%Y%m%d')

    catalog_codes = [
        # Damage Codes (KATALOG = 1) - English
        ('1', 'MECH', 'WEAR', 'en', 'Mechanical Wear', 'X', today, '99991231'),
        ('1', 'MECH', 'BROK', 'en', 'Broken/Fractured', 'X', today, '99991231'),
        ('1', 'MECH', 'LEAK', 'en', 'Leakage', 'X', today, '99991231'),
        ('1', 'MECH', 'CORR', 'en', 'Corrosion', 'X', today, '99991231'),
        ('1', 'MECH', 'VIBR', 'en', 'Excessive Vibration', 'X', today, '99991231'),
        ('1', 'ELEC', 'SHRT', 'en', 'Short Circuit', 'X', today, '99991231'),
        ('1', 'ELEC', 'OVHT', 'en', 'Overheating', 'X', today, '99991231'),
        ('1', 'ELEC', 'GRND', 'en', 'Ground Fault', 'X', today, '99991231'),
        ('1', 'ELEC', 'INSL', 'en', 'Insulation Failure', 'X', today, '99991231'),
        ('1', 'INST', 'DRFT', 'en', 'Sensor Drift', 'X', today, '99991231'),
        ('1', 'INST', 'FAIL', 'en', 'Instrument Failure', 'X', today, '99991231'),
        ('1', 'INST', 'CALB', 'en', 'Calibration Error', 'X', today, '99991231'),
        ('1', 'PROC', 'CLOG', 'en', 'Clogged/Blocked', 'X', today, '99991231'),
        ('1', 'PROC', 'CONT', 'en', 'Contamination', 'X', today, '99991231'),
        ('1', 'ENV', 'DUST', 'en', 'Dust Accumulation', 'X', today, '99991231'),
        ('1', 'ENV', 'TEMP', 'en', 'Temperature Issue', 'X', today, '99991231'),

        # Damage Codes (KATALOG = 1) - German
        ('1', 'MECH', 'WEAR', 'de', 'Mechanischer Verschleiß', 'X', today, '99991231'),
        ('1', 'MECH', 'BROK', 'de', 'Gebrochen/Gerissen', 'X', today, '99991231'),
        ('1', 'MECH', 'LEAK', 'de', 'Leckage', 'X', today, '99991231'),
        ('1', 'MECH', 'CORR', 'de', 'Korrosion', 'X', today, '99991231'),
        ('1', 'MECH', 'VIBR', 'de', 'Übermäßige Vibration', 'X', today, '99991231'),
        ('1', 'ELEC', 'SHRT', 'de', 'Kurzschluss', 'X', today, '99991231'),
        ('1', 'ELEC', 'OVHT', 'de', 'Überhitzung', 'X', today, '99991231'),
        ('1', 'ELEC', 'GRND', 'de', 'Erdschluss', 'X', today, '99991231'),
        ('1', 'ELEC', 'INSL', 'de', 'Isolationsfehler', 'X', today, '99991231'),
        ('1', 'INST', 'DRFT', 'de', 'Sensordrift', 'X', today, '99991231'),
        ('1', 'INST', 'FAIL', 'de', 'Instrumentenausfall', 'X', today, '99991231'),
        ('1', 'INST', 'CALB', 'de', 'Kalibrierfehler', 'X', today, '99991231'),
        ('1', 'PROC', 'CLOG', 'de', 'Verstopft/Blockiert', 'X', today, '99991231'),
        ('1', 'PROC', 'CONT', 'de', 'Kontamination', 'X', today, '99991231'),
        ('1', 'ENV', 'DUST', 'de', 'Staubansammlung', 'X', today, '99991231'),
        ('1', 'ENV', 'TEMP', 'de', 'Temperaturproblem', 'X', today, '99991231'),

        # Cause Codes (KATALOG = 2) - English
        ('2', 'OPER', 'ERRO', 'en', 'Operator Error', 'X', today, '99991231'),
        ('2', 'OPER', 'TRNG', 'en', 'Training Deficiency', 'X', today, '99991231'),
        ('2', 'MAIN', 'OMIT', 'en', 'Maintenance Omission', 'X', today, '99991231'),
        ('2', 'MAIN', 'SCHD', 'en', 'Scheduling Issue', 'X', today, '99991231'),
        ('2', 'MAIN', 'CLNG', 'en', 'Cleaning Deficiency', 'X', today, '99991231'),
        ('2', 'MATL', 'DEFV', 'en', 'Defective Material', 'X', today, '99991231'),
        ('2', 'MATL', 'AGNG', 'en', 'Material Aging', 'X', today, '99991231'),
        ('2', 'MATL', 'SPEC', 'en', 'Wrong Specification', 'X', today, '99991231'),
        ('2', 'DSGN', 'WEAK', 'en', 'Design Weakness', 'X', today, '99991231'),
        ('2', 'DSGN', 'UNDR', 'en', 'Under-dimensioned', 'X', today, '99991231'),
        ('2', 'EXTL', 'POWR', 'en', 'Power Supply Issue', 'X', today, '99991231'),
        ('2', 'EXTL', 'ENVR', 'en', 'Environmental Factor', 'X', today, '99991231'),
        ('2', 'UNKN', 'UNKN', 'en', 'Unknown/To Be Determined', 'X', today, '99991231'),

        # Cause Codes (KATALOG = 2) - German
        ('2', 'OPER', 'ERRO', 'de', 'Bedienerfehler', 'X', today, '99991231'),
        ('2', 'OPER', 'TRNG', 'de', 'Schulungsdefizit', 'X', today, '99991231'),
        ('2', 'MAIN', 'OMIT', 'de', 'Wartungsversäumnis', 'X', today, '99991231'),
        ('2', 'MAIN', 'SCHD', 'de', 'Terminierungsproblem', 'X', today, '99991231'),
        ('2', 'MAIN', 'CLNG', 'de', 'Reinigungsmangel', 'X', today, '99991231'),
        ('2', 'MATL', 'DEFV', 'de', 'Defektes Material', 'X', today, '99991231'),
        ('2', 'MATL', 'AGNG', 'de', 'Materialermüdung', 'X', today, '99991231'),
        ('2', 'MATL', 'SPEC', 'de', 'Falsche Spezifikation', 'X', today, '99991231'),
        ('2', 'DSGN', 'WEAK', 'de', 'Konstruktionsschwäche', 'X', today, '99991231'),
        ('2', 'DSGN', 'UNDR', 'de', 'Unterdimensioniert', 'X', today, '99991231'),
        ('2', 'EXTL', 'POWR', 'de', 'Stromversorgungsproblem', 'X', today, '99991231'),
        ('2', 'EXTL', 'ENVR', 'de', 'Umweltfaktor', 'X', today, '99991231'),
        ('2', 'UNKN', 'UNKN', 'de', 'Unbekannt/Zu ermitteln', 'X', today, '99991231'),

        # Activity Codes (KATALOG = 3) - English
        ('3', 'REPR', 'REPL', 'en', 'Replace Component', 'X', today, '99991231'),
        ('3', 'REPR', 'ADJT', 'en', 'Adjust/Align', 'X', today, '99991231'),
        ('3', 'REPR', 'CLNG', 'en', 'Clean', 'X', today, '99991231'),
        ('3', 'REPR', 'LUBR', 'en', 'Lubricate', 'X', today, '99991231'),
        ('3', 'REPR', 'TGTN', 'en', 'Tighten/Torque', 'X', today, '99991231'),
        ('3', 'INSP', 'VISL', 'en', 'Visual Inspection', 'X', today, '99991231'),
        ('3', 'INSP', 'TEST', 'en', 'Functional Test', 'X', today, '99991231'),
        ('3', 'INSP', 'MEAS', 'en', 'Measurement/Reading', 'X', today, '99991231'),
        ('3', 'CALB', 'CALB', 'en', 'Calibration', 'X', today, '99991231'),
        ('3', 'CALB', 'VERF', 'en', 'Verification', 'X', today, '99991231'),
        ('3', 'OVHL', 'FULL', 'en', 'Full Overhaul', 'X', today, '99991231'),
        ('3', 'OVHL', 'PART', 'en', 'Partial Overhaul', 'X', today, '99991231'),

        # Activity Codes (KATALOG = 3) - German
        ('3', 'REPR', 'REPL', 'de', 'Komponente ersetzen', 'X', today, '99991231'),
        ('3', 'REPR', 'ADJT', 'de', 'Einstellen/Ausrichten', 'X', today, '99991231'),
        ('3', 'REPR', 'CLNG', 'de', 'Reinigen', 'X', today, '99991231'),
        ('3', 'REPR', 'LUBR', 'de', 'Schmieren', 'X', today, '99991231'),
        ('3', 'REPR', 'TGTN', 'de', 'Anziehen/Drehmoment', 'X', today, '99991231'),
        ('3', 'INSP', 'VISL', 'de', 'Sichtprüfung', 'X', today, '99991231'),
        ('3', 'INSP', 'TEST', 'de', 'Funktionstest', 'X', today, '99991231'),
        ('3', 'INSP', 'MEAS', 'de', 'Messung/Ablesung', 'X', today, '99991231'),
        ('3', 'CALB', 'CALB', 'de', 'Kalibrierung', 'X', today, '99991231'),
        ('3', 'CALB', 'VERF', 'de', 'Verifizierung', 'X', today, '99991231'),
        ('3', 'OVHL', 'FULL', 'de', 'Generalüberholung', 'X', today, '99991231'),
        ('3', 'OVHL', 'PART', 'de', 'Teilüberholung', 'X', today, '99991231'),
    ]

    for code in catalog_codes:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO QMCATALOG
                (KATESSION, CODEGRUPPE, CODE, SPRAS, KUESSION, ACTIVE, VALID_FROM, VALID_TO)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, code)
        except Exception as e:
            print(f"  Warning: Could not insert catalog code {code}: {e}")

    print(f"  Inserted {len(catalog_codes)} catalog codes")


def seed_equipment_master(cursor):
    """Seed EQUI/EQKT - Equipment Master"""
    print("--- Seeding EQUI/EQKT (Equipment Master) ---")

    today = datetime.now().strftime('%Y%m%d')

    equipment = [
        # Equipment Header
        ('10005678', 'PROD', 'PRESS', today, 'ADMIN', 'FETTE', 'P3000', '2018', '20281231', 'PLANT-01-TP04', '20180601', '20180515'),
        ('10009999', 'UTIL', 'PUMP', today, 'ADMIN', 'GRUNDFOS', 'CR32', '2015', '20251231', 'PLANT-02-PUMP', '20150301', '20150215'),
        ('30001234', 'PACK', 'BLIST', today, 'ADMIN', 'UHLMANN', 'B1240', '2020', '20301231', 'PLANT-01-BLIST', '20200901', '20200815'),
        ('50008888', 'HVAC', 'AHU', today, 'ADMIN', 'CARRIER', 'AHU-500', '2017', '20271231', 'PLANT-03-HVAC', '20170601', '20170515'),
        ('60002222', 'LAB', 'INST', today, 'ADMIN', 'METTLER', 'S220', '2021', '20311231', 'LAB-01-PH', '20210301', '20210215'),
        ('EQ-500103', 'PROD', 'PRESS', today, 'ADMIN', 'KORSCH', 'XL400', '2019', '20291231', 'MAN-T-PRESS-03', '20190801', '20190715'),
    ]

    equipment_texts = [
        # English texts
        ('10005678', 'en', 'Tablet Press #4 - Main Production'),
        ('10009999', 'en', 'Coolant Circulation Pump #2'),
        ('30001234', 'en', 'Blister Packaging Machine Line 1'),
        ('50008888', 'en', 'HVAC Air Handling Unit #3'),
        ('60002222', 'en', 'Laboratory pH Meter #05'),
        ('EQ-500103', 'en', 'Tablet Press #3 - High Speed'),

        # German texts
        ('10005678', 'de', 'Tablettenpresse #4 - Hauptproduktion'),
        ('10009999', 'de', 'Kühlmittelumwälzpumpe #2'),
        ('30001234', 'de', 'Blisterverpackungsmaschine Linie 1'),
        ('50008888', 'de', 'RLT-Lüftungsgerät #3'),
        ('60002222', 'de', 'Labor pH-Messgerät #05'),
        ('EQ-500103', 'de', 'Tablettenpresse #3 - Hochgeschwindigkeit'),
    ]

    for eq in equipment:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO EQUI
                (EQUNR, EQART, EQTYP, ERDAT, ERNAM, HERST, TYPBZ, BAESSION, GEWRK, TPLNR, INBDT, ANSDT, ACTIVE)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'X')
            """, eq)
        except Exception as e:
            print(f"  Warning: Could not insert equipment {eq[0]}: {e}")

    for eqt in equipment_texts:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO EQKT (EQUNR, SPRAS, EQKTX)
                VALUES (?, ?, ?)
            """, eqt)
        except Exception as e:
            print(f"  Warning: Could not insert equipment text {eqt}: {e}")

    print(f"  Inserted {len(equipment)} equipment records with {len(equipment_texts)} texts")


def seed_functional_locations(cursor):
    """Seed IFLOT/IFLOTX - Functional Location Master"""
    print("--- Seeding IFLOT/IFLOTX (Functional Locations) ---")

    today = datetime.now().strftime('%Y%m%d')

    funclocations = [
        # Top Level
        ('PLANT-01', 'PLNT', today, 'ADMIN', '20150101', None),
        ('PLANT-02', 'PLNT', today, 'ADMIN', '20150101', None),
        ('PLANT-03', 'PLNT', today, 'ADMIN', '20170101', None),
        ('LAB-01', 'LAB', today, 'ADMIN', '20180101', None),

        # Production Areas
        ('PLANT-01-PROD', 'AREA', today, 'ADMIN', '20150101', 'PLANT-01'),
        ('PLANT-01-PACK', 'AREA', today, 'ADMIN', '20150101', 'PLANT-01'),
        ('PLANT-02-UTIL', 'AREA', today, 'ADMIN', '20150101', 'PLANT-02'),
        ('PLANT-03-HVAC', 'AREA', today, 'ADMIN', '20170101', 'PLANT-03'),

        # Equipment Locations
        ('PLANT-01-TP04', 'EQLC', today, 'ADMIN', '20180601', 'PLANT-01-PROD'),
        ('PLANT-02-PUMP', 'EQLC', today, 'ADMIN', '20150301', 'PLANT-02-UTIL'),
        ('PLANT-01-BLIST', 'EQLC', today, 'ADMIN', '20200901', 'PLANT-01-PACK'),
        ('LAB-01-PH', 'EQLC', today, 'ADMIN', '20210301', 'LAB-01'),
        ('MAN-T-PRESS-03', 'EQLC', today, 'ADMIN', '20190801', 'PLANT-01-PROD'),
    ]

    funclocation_texts = [
        # English texts
        ('PLANT-01', 'en', 'Manufacturing Plant 1 - Solid Dosage'),
        ('PLANT-02', 'en', 'Manufacturing Plant 2 - Utilities'),
        ('PLANT-03', 'en', 'Manufacturing Plant 3 - Support'),
        ('LAB-01', 'en', 'Quality Control Laboratory'),
        ('PLANT-01-PROD', 'en', 'Production Area - Tablets'),
        ('PLANT-01-PACK', 'en', 'Packaging Area - Blisters'),
        ('PLANT-02-UTIL', 'en', 'Utilities - Cooling Systems'),
        ('PLANT-03-HVAC', 'en', 'HVAC Systems Area'),
        ('PLANT-01-TP04', 'en', 'Tablet Press Station #4'),
        ('PLANT-02-PUMP', 'en', 'Pump Station #2'),
        ('PLANT-01-BLIST', 'en', 'Blister Line Station #1'),
        ('LAB-01-PH', 'en', 'pH Measurement Station'),
        ('MAN-T-PRESS-03', 'en', 'Tablet Press Station #3'),

        # German texts
        ('PLANT-01', 'de', 'Produktionswerk 1 - Feste Arzneiformen'),
        ('PLANT-02', 'de', 'Produktionswerk 2 - Versorgung'),
        ('PLANT-03', 'de', 'Produktionswerk 3 - Unterstützung'),
        ('LAB-01', 'de', 'Qualitätskontrolllabor'),
        ('PLANT-01-PROD', 'de', 'Produktionsbereich - Tabletten'),
        ('PLANT-01-PACK', 'de', 'Verpackungsbereich - Blister'),
        ('PLANT-02-UTIL', 'de', 'Versorgung - Kühlsysteme'),
        ('PLANT-03-HVAC', 'de', 'RLT-Anlagenbereich'),
        ('PLANT-01-TP04', 'de', 'Tablettenpressen-Station #4'),
        ('PLANT-02-PUMP', 'de', 'Pumpenstation #2'),
        ('PLANT-01-BLIST', 'de', 'Blisterlinien-Station #1'),
        ('LAB-01-PH', 'de', 'pH-Messstation'),
        ('MAN-T-PRESS-03', 'de', 'Tablettenpressen-Station #3'),
    ]

    for fl in funclocations:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO IFLOT
                (TPLNR, FLESSION, ERDAT, ERNAM, IESSION, PESSION, ACTIVE)
                VALUES (?, ?, ?, ?, ?, ?, 'X')
            """, fl)
        except Exception as e:
            print(f"  Warning: Could not insert functional location {fl[0]}: {e}")

    for flt in funclocation_texts:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO IFLOTX (TPLNR, SPRAS, PLTXT)
                VALUES (?, ?, ?)
            """, flt)
        except Exception as e:
            print(f"  Warning: Could not insert functional location text {flt}: {e}")

    print(f"  Inserted {len(funclocations)} functional locations with {len(funclocation_texts)} texts")


def seed_initial_statuses(cursor):
    """Seed JEST - Initial Object Statuses for existing notifications/orders"""
    print("--- Seeding JEST (Initial Statuses) ---")

    # Status for existing notifications (from seed_data.py)
    notification_statuses = [
        # Notification 10000001 - Released, In Process
        ('QM10000001', 'CRTD', '', None),
        ('QM10000001', 'REL', '', None),
        ('QM10000001', 'INPR', '', None),

        # Notification 10000002 - Outstanding
        ('QM10000002', 'CRTD', '', None),
        ('QM10000002', 'OSDN', '', None),

        # Notification 10000003 - Released
        ('QM10000003', 'CRTD', '', None),
        ('QM10000003', 'REL', '', None),

        # Notification 10000004 - Closed
        ('QM10000004', 'CRTD', '', None),
        ('QM10000004', 'TECO', '', None),
        ('QM10000004', 'CLSD', '', None),

        # Notification 10000005 - Technically Complete
        ('QM10000005', 'CRTD', '', None),
        ('QM10000005', 'REL', '', None),
        ('QM10000005', 'TECO', '', None),
    ]

    # Status for existing orders
    order_statuses = [
        # Order 40000001 - Released, Partially Confirmed
        ('OR40000001', 'CRTD', '', None),
        ('OR40000001', 'REL', '', None),
        ('OR40000001', 'PCNF', '', None),
    ]

    all_statuses = notification_statuses + order_statuses

    for status in all_statuses:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO JEST (OBJNR, STAT, INACT, CHGNR)
                VALUES (?, ?, ?, ?)
            """, status)
        except Exception as e:
            print(f"  Warning: Could not insert status {status}: {e}")

    print(f"  Inserted {len(all_statuses)} object statuses")


def seed_sample_time_confirmations(cursor):
    """Seed AFRU - Sample Time Confirmations"""
    print("--- Seeding AFRU (Time Confirmations) ---")

    confirmations = [
        ('CNF20231026001', '40000001', '0010', 'ELECT', 'P01', '20231026', '20231026', '080000', '20231026', '083000', 0.5, 0.0, 'H', None, None, '', '', 'LOTO completed as per procedure', '', 'TECH001', '20231026', '083500'),
        ('CNF20231026002', '40000001', '0020', 'MECH', 'P01', '20231026', '20231026', '083000', '20231026', '100000', 1.5, 0.0, 'H', None, None, '', '', 'Fan cleaned, filter replaced', '', 'TECH002', '20231026', '100500'),
        ('CNF20231026003', '40000001', '0020', 'MECH', 'P01', '20231026', '20231026', '100000', '20231026', '103000', 0.5, 0.0, 'H', None, None, '', '', 'System test completed, motor temp normal', 'X', 'TECH002', '20231026', '104000'),
    ]

    for conf in confirmations:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO AFRU
                (RUESSION, AUFNR, VORNR, ARBID, WERKS, BUDAT, ISDD, ISDZ, IEDD, IEDZ,
                 ARBEI, ISMNW, ISMNE, AUFPL, APLZL, STOKZ, STEFB, LTXA1, AUERU, ERNAM, ERDAT, ERZET)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, conf)
        except Exception as e:
            print(f"  Warning: Could not insert confirmation {conf[0]}: {e}")

    print(f"  Inserted {len(confirmations)} time confirmations")


def seed_sample_change_documents(cursor):
    """Seed CDHDR/CDPOS - Sample Change Documents for Audit Trail"""
    print("--- Seeding CDHDR/CDPOS (Change Documents) ---")

    change_headers = [
        ('CD20231025091500A1B2C3', 'QMEL', '10000001', 'D.MARSZALLEK', '20231025', '091500', 'IW21', 'I', 'en'),
        ('CD20231025141500D4E5F6', 'QMEL', '10000002', 'J.DOE', '20231027', '140000', 'IW21', 'I', 'en'),
        ('CD20231026080000G7H8I9', 'AUFK', '40000001', 'SYSTEM', '20231026', '080000', 'IW31', 'I', 'en'),
        ('CD20231026103000J1K2L3', 'QMEL', '10000001', 'TECH001', '20231026', '103000', 'IW22', 'U', 'en'),
    ]

    change_items = [
        # Creation of notification 10000001
        ('CD20231025091500A1B2C3', 'QMEL', '10000001', 'QMNUM', '10000001', None, 'I'),
        ('CD20231025091500A1B2C3', 'QMEL', '10000001', 'QMART', 'M1', None, 'I'),
        ('CD20231025091500A1B2C3', 'QMEL', '10000001', 'EQUNR', '10005678', None, 'I'),
        ('CD20231025091500A1B2C3', 'QMEL', '10000001', 'PRIOK', '1', None, 'I'),

        # Creation of notification 10000002
        ('CD20231025141500D4E5F6', 'QMEL', '10000002', 'QMNUM', '10000002', None, 'I'),
        ('CD20231025141500D4E5F6', 'QMEL', '10000002', 'QMART', 'M2', None, 'I'),

        # Creation of order 40000001
        ('CD20231026080000G7H8I9', 'AUFK', '40000001', 'AUFNR', '40000001', None, 'I'),
        ('CD20231026080000G7H8I9', 'AUFK', '40000001', 'QMNUM', '10000001', None, 'I'),
        ('CD20231026080000G7H8I9', 'AUFK', '40000001', 'AUART', 'PM01', None, 'I'),

        # Update to notification 10000001 (status change)
        ('CD20231026103000J1K2L3', 'JEST', 'QM10000001/INPR', 'STAT', 'INPR', None, 'I'),
    ]

    for header in change_headers:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO CDHDR
                (CHANGENR, OBJECTCLAS, OBJECTID, USERNAME, UDATE, UTIME, TCODE, CHANGE_IND, LANGU)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, header)
        except Exception as e:
            print(f"  Warning: Could not insert change header {header[0]}: {e}")

    for item in change_items:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO CDPOS
                (CHANGENR, TABNAME, TABKEY, FNAME, VALUE_NEW, VALUE_OLD, CHNGIND)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, item)
        except Exception as e:
            print(f"  Warning: Could not insert change item {item}: {e}")

    print(f"  Inserted {len(change_headers)} change documents with {len(change_items)} items")


def main():
    """Main function to seed all compliance tables"""
    print("=" * 60)
    print("SAP PM Compliance Tables - Seed Data Script")
    print("=" * 60)

    # Check if database exists
    if not os.path.exists(DATABASE_PATH):
        print(f"Error: Database not found at {DATABASE_PATH}")
        print("Please run the main seed_data.py script first to create the database.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Seed all compliance tables
        seed_status_texts(cursor)
        seed_catalog_codes(cursor)
        seed_equipment_master(cursor)
        seed_functional_locations(cursor)
        seed_initial_statuses(cursor)
        seed_sample_time_confirmations(cursor)
        seed_sample_change_documents(cursor)

        conn.commit()
        print("=" * 60)
        print("Compliance tables seeded successfully!")
        print("=" * 60)

    except Exception as e:
        conn.rollback()
        print(f"Error seeding data: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
