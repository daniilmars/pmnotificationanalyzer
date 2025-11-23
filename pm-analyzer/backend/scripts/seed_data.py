import sqlite3
import os
import random
from datetime import datetime, timedelta

# Configuration
DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'sap_pm.db')

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def seed_database():
    conn = get_db_connection()
    cursor = conn.cursor()

    print("--- Clearing existing data ---")
    tables = ['MAKT', 'RESB', 'AFVC_TEXT', 'AFVC', 'AUFK', 'QMAK', 'QMUR_TEXT', 'QMUR', 'QMFE_TEXT', 'QMFE', 'NOTIF_CONTENT', 'QMEL']
    for table in tables:
        try:
            cursor.execute(f"DELETE FROM {table}")
        except sqlite3.OperationalError:
            pass 
    
    print("--- Seeding Golden Batch (GMP Compliant) Data ---")

    # Scenario 1: Tablet Press Main Motor Overheating (Perfect GMP Record)
    # ... (Existing Scenario 1) ...
    notif_id = "10000001"
    order_id = "40000001"
    cursor.execute("""
        INSERT INTO QMEL (QMNUM, QMART, EQUNR, TPLNR, PRIOK, QMNAM, ERDAT, MZEIT, STRMN, LTRMN)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (notif_id, "M1", "10005678", "PLANT-01-TP04", "1", "D.MARSZALLEK", "2023-10-25", "09:15:00", "2023-10-25", "2023-10-26"))
    cursor.execute("INSERT INTO NOTIF_CONTENT (QMNUM, SPRAS, QMTXT, TDLINE) VALUES (?, ?, ?, ?)", 
                   (notif_id, "en", "Tablet Press 4 Main Motor Overheating", 
                    "During routine batch production (Batch #BP-2023-99), the main drive motor (Tag: M-101) triggered a high-temperature alarm (Alarm ID: H-TEMP-01). The localized temperature reading was 85°C, exceeding the threshold of 75°C. Production was immediately paused as per SOP-ENG-005. Visual inspection revealed restricted airflow at the fan intake due to dust accumulation. No abnormal noise or vibration was detected. The motor cooling fins were cleaned, and the temperature returned to nominal (65°C) within 15 minutes. Requesting full inspection of the cooling fan assembly."))
    cursor.execute("INSERT INTO NOTIF_CONTENT (QMNUM, SPRAS, QMTXT, TDLINE) VALUES (?, ?, ?, ?)", 
                   (notif_id, "de", "Tablettenpresse 4 Hauptmotor Überhitzung", 
                    "Während der routinemäßigen Chargenproduktion (Charge #BP-2023-99) löste der Hauptantriebsmotor (Tag: M-101) einen Hochtemperaturalarm aus (Alarm-ID: H-TEMP-01). Die lokale Temperaturmessung ergab 85°C und überschritt damit den Grenzwert von 75°C. Die Produktion wurde gemäß SOP-ENG-005 sofort gestoppt. Eine visuelle Inspektion ergab einen eingeschränkten Luftstrom am Lüftereinlass aufgrund von Staubansammlungen. Es wurden keine abnormalen Geräusche oder Vibrationen festgestellt. Die Kühlrippen des Motors wurden gereinigt und die Temperatur kehrte innerhalb von 15 Minuten auf den Nennwert (65°C) zurück. Es wird eine vollständige Inspektion der Lüfterbaugruppe angefordert."))
    cursor.execute("INSERT INTO QMFE (QMNUM, FENUM, OTGRP, OTEIL, FEGRP, FECOD) VALUES (?, ?, ?, ?, ?, ?)", (notif_id, "0001", "MOT", "FAN", "ENV", "DUST"))
    cursor.execute("INSERT INTO QMFE_TEXT (QMNUM, FENUM, SPRAS, FETXT) VALUES (?, ?, ?, ?)", (notif_id, "0001", "en", "Restricted Airflow"))
    cursor.execute("INSERT INTO QMFE_TEXT (QMNUM, FENUM, SPRAS, FETXT) VALUES (?, ?, ?, ?)", (notif_id, "0001", "de", "Eingeschränkter Luftstrom"))
    cursor.execute("INSERT INTO QMUR (QMNUM, FENUM, URNUM, URGRP, URCOD) VALUES (?, ?, ?, ?, ?)", (notif_id, "0001", "0001", "MN", "CLNG"))
    cursor.execute("INSERT INTO QMUR_TEXT (QMNUM, FENUM, URNUM, SPRAS, URTXT) VALUES (?, ?, ?, ?, ?)", (notif_id, "0001", "0001", "en", "Lack of Cleaning"))
    cursor.execute("INSERT INTO QMUR_TEXT (QMNUM, FENUM, URNUM, SPRAS, URTXT) VALUES (?, ?, ?, ?, ?)", (notif_id, "0001", "0001", "de", "Mangelnde Reinigung"))
    cursor.execute("INSERT INTO AUFK (AUFNR, QMNUM, AUART, KTEXT, GLTRP, GLTRS) VALUES (?, ?, ?, ?, ?, ?)", (order_id, notif_id, "PM01", "Insp & Clean Motor Fan TP-04", "2023-10-26", "2023-10-26"))
    cursor.execute("INSERT INTO AFVC (AUFNR, VORNR, ARBPL, STEUS, DAUER, DAUERE) VALUES (?, ?, ?, ?, ?, ?)", (order_id, "0010", "ELECT", "PM01", "0.5", "H"))
    cursor.execute("INSERT INTO AFVC_TEXT (AUFNR, VORNR, SPRAS, LTXA1) VALUES (?, ?, ?, ?)", (order_id, "0010", "en", "Isolate electrical supply (LOTO)"))
    cursor.execute("INSERT INTO AFVC_TEXT (AUFNR, VORNR, SPRAS, LTXA1) VALUES (?, ?, ?, ?)", (order_id, "0010", "de", "Stromversorgung trennen (LOTO)"))
    cursor.execute("INSERT INTO AFVC (AUFNR, VORNR, ARBPL, STEUS, DAUER, DAUERE) VALUES (?, ?, ?, ?, ?, ?)", (order_id, "0020", "MECH", "PM01", "1.0", "H"))
    cursor.execute("INSERT INTO AFVC_TEXT (AUFNR, VORNR, SPRAS, LTXA1) VALUES (?, ?, ?, ?)", (order_id, "0020", "en", "Inspect and clean cooling fan"))
    cursor.execute("INSERT INTO AFVC_TEXT (AUFNR, VORNR, SPRAS, LTXA1) VALUES (?, ?, ?, ?)", (order_id, "0020", "de", "Kühlgebläse inspizieren und reinigen"))
    cursor.execute("INSERT INTO RESB (AUFNR, VORNR, MATNR, MENGE, MEINS) VALUES (?, ?, ?, ?, ?)", (order_id, "0020", "500-100-FIL", 1.0, "EA"))
    cursor.execute("INSERT INTO MAKT (MATNR, SPRAS, MAKTX) VALUES (?, ?, ?)", ("500-100-FIL", "en", "Filter Element, Air Intake"))
    cursor.execute("INSERT INTO MAKT (MATNR, SPRAS, MAKTX) VALUES (?, ?, ?)", ("500-100-FIL", "de", "Filterelement, Lufteinlass"))


    print("--- Seeding Scenario 2: Bad Quality (Vague) ---")
    # ... (Existing Scenario 2) ...
    notif_id_bad = "10000002"
    cursor.execute("""
        INSERT INTO QMEL (QMNUM, QMART, EQUNR, TPLNR, PRIOK, QMNAM, ERDAT, MZEIT, STRMN, LTRMN)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (notif_id_bad, "M2", "10009999", "PLANT-02-PUMP", "3", "J.DOE", "2023-10-27", "14:00:00", "2023-10-28", "2023-10-30"))
    cursor.execute("INSERT INTO NOTIF_CONTENT (QMNUM, SPRAS, QMTXT, TDLINE) VALUES (?, ?, ?, ?)", (notif_id_bad, "en", "Broken pump", "Pump stopped working. Fix it."))
    cursor.execute("INSERT INTO NOTIF_CONTENT (QMNUM, SPRAS, QMTXT, TDLINE) VALUES (?, ?, ?, ?)", (notif_id_bad, "de", "Pumpe defekt", "Pumpe geht nicht mehr. Reparieren."))


    print("--- Seeding Scenario 3: Medium Quality (Missing Impact) ---")
    # Good description, but missing product impact check
    notif_id_med = "10000003"
    cursor.execute("""
        INSERT INTO QMEL (QMNUM, QMART, EQUNR, TPLNR, PRIOK, QMNAM, ERDAT, MZEIT, STRMN, LTRMN)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (notif_id_med, "M2", "30001234", "PLANT-01-BLIST", "2", "K.MUELLER", "2023-11-01", "10:30:00", "2023-11-01", "2023-11-02"))
    
    cursor.execute("INSERT INTO NOTIF_CONTENT (QMNUM, SPRAS, QMTXT, TDLINE) VALUES (?, ?, ?, ?)", 
                   (notif_id_med, "en", "Blister Machine Sealing Sensor Drift", 
                    "The sealing temperature sensor (S-202) showed a reading of 145°C, while the setpoint was 150°C. The deviation (-5°C) is within the technical alarm limit but indicates a drift. Re-calibrated the sensor using standard probe. Reading corrected to 149.8°C. Sensor replaced as a precaution."))
    cursor.execute("INSERT INTO NOTIF_CONTENT (QMNUM, SPRAS, QMTXT, TDLINE) VALUES (?, ?, ?, ?)", 
                   (notif_id_med, "de", "Blistermaschine Siegelsensor Drift", 
                    "Der Siegeltemperatursensor (S-202) zeigte einen Wert von 145°C an, während der Sollwert 150°C betrug. Die Abweichung (-5°C) liegt innerhalb der technischen Alarmgrenze, deutet aber auf eine Drift hin. Sensor mit Standardfühler neu kalibriert. Messwert auf 149,8°C korrigiert. Sensor vorsorglich ausgetauscht."))
    
    cursor.execute("INSERT INTO QMFE (QMNUM, FENUM, OTGRP, OTEIL, FEGRP, FECOD) VALUES (?, ?, ?, ?, ?, ?)", (notif_id_med, "0001", "INST", "SENS", "EL", "DRIFT"))
    cursor.execute("INSERT INTO QMFE_TEXT (QMNUM, FENUM, SPRAS, FETXT) VALUES (?, ?, ?, ?)", (notif_id_med, "0001", "en", "Sensor Drift"))
    cursor.execute("INSERT INTO QMFE_TEXT (QMNUM, FENUM, SPRAS, FETXT) VALUES (?, ?, ?, ?)", (notif_id_med, "0001", "de", "Sensor Drift"))


    print("--- Seeding Scenario 4: Low Quality (HVAC) ---")
    # Very common bad example: "Replaced filter" without context
    notif_id_low = "10000004"
    cursor.execute("""
        INSERT INTO QMEL (QMNUM, QMART, EQUNR, TPLNR, PRIOK, QMNAM, ERDAT, MZEIT, STRMN, LTRMN)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (notif_id_low, "M1", "50008888", "PLANT-03-HVAC", "3", "T.SMITH", "2023-11-05", "08:00:00", "2023-11-05", "2023-11-05"))
    
    cursor.execute("INSERT INTO NOTIF_CONTENT (QMNUM, SPRAS, QMTXT, TDLINE) VALUES (?, ?, ?, ?)", 
                   (notif_id_low, "en", "HVAC 3 Filter changed", "Filter was dirty. Replaced with new one. Unit restarted."))
    cursor.execute("INSERT INTO NOTIF_CONTENT (QMNUM, SPRAS, QMTXT, TDLINE) VALUES (?, ?, ?, ?)", 
                   (notif_id_low, "de", "RLT 3 Filter gewechselt", "Filter war schmutzig. Gegen neuen ausgetauscht. Anlage neu gestartet."))


    print("--- Seeding Scenario 5: High Quality (Calibration) ---")
    # Excellent GMP example
    notif_id_high = "10000005"
    cursor.execute("""
        INSERT INTO QMEL (QMNUM, QMART, EQUNR, TPLNR, PRIOK, QMNAM, ERDAT, MZEIT, STRMN, LTRMN)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (notif_id_high, "M2", "60002222", "LAB-01-PH", "2", "S.JOHNSON", "2023-11-10", "11:00:00", "2023-11-10", "2023-11-10"))
    
    cursor.execute("INSERT INTO NOTIF_CONTENT (QMNUM, SPRAS, QMTXT, TDLINE) VALUES (?, ?, ?, ?)", 
                   (notif_id_high, "en", "pH Meter 05 Calibration Failure", 
                    "During daily calibration check, pH Meter 05 failed the slope test at pH 4.01 (Slope: 92%, Spec: 95-105%). \n\n**Investigation:** \n- Buffer solutions checked (Lot #BUF-23-10, Exp: 12/2024). \n- Electrode inspected: No physical damage, but junction appears clogged. \n- Retest with fresh buffer confirmed failure. \n\n**Product Impact:** No impact. Calibration performed BEFORE any sample analysis for Batch #BP-2023-105. \n\n**Corrective Action:** Electrode replaced (New Lot #EL-999). Calibration passed (Slope 99%). \n**Preventive Action:** Electrode cleaning frequency increased to weekly (Update SOP-LAB-005 initiated)."))
    cursor.execute("INSERT INTO NOTIF_CONTENT (QMNUM, SPRAS, QMTXT, TDLINE) VALUES (?, ?, ?, ?)", 
                   (notif_id_high, "de", "pH Meter 05 Kalibrierfehler", 
                    "Bei der täglichen Kalibrierprüfung fiel pH Meter 05 beim Steigungstest bei pH 4,01 durch (Steilheit: 92%, Spez: 95-105%). \n\n**Untersuchung:** \n- Pufferlösungen geprüft (Charge #BUF-23-10, Exp: 12/2024). \n- Elektrode inspiziert: Keine physischen Schäden, aber Diaphragma scheint verstopft. \n- Nachtest mit frischem Puffer bestätigte Fehler. \n\n**Produktauswirkung:** Kein Einfluss. Kalibrierung erfolgte VOR der Probenanalyse für Charge #BP-2023-105. \n\n**Korrekturmaßnahme:** Elektrode ausgetauscht (Neue Charge #EL-999). Kalibrierung bestanden (Steilheit 99%). \n**Präventivmaßnahme:** Elektrodenreinigungsfrequenz auf wöchentlich erhöht (Update SOP-LAB-005 initiiert)."))

    conn.commit()
    conn.close()
    print("Database seeded successfully.")

if __name__ == "__main__":
    seed_database()
