import os
import sys
import csv
from dotenv import load_dotenv
import time

# --- KORREKTUR: Projektverzeichnis zum Python-Pfad hinzufügen ---
# Dies ermöglicht dem Skript, das 'app'-Modul zu finden.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
# ---------------------------------------------------------------

# Dieser Import funktioniert jetzt, da der Pfad bekannt ist.
from app.services.analysis_service import analyze_text
from app.models import AnalysisResult

# Lädt Umgebungsvariablen aus der .env-Datei im Hauptverzeichnis
load_dotenv(os.path.join(project_root, '.env'))

def run_test_from_file(filename="test_meldungen.csv"):
    """
    Liest Meldungstexte aus einer CSV-Datei und führt für jeden eine Analyse durch.
    """
    # Prüfen, ob der API-Schlüssel verfügbar ist, bevor wir starten
    if not os.getenv("GOOGLE_API_KEY"):
        print("FEHLER: Der GOOGLE_API_KEY wurde nicht gefunden.")
        print("Bitte stelle sicher, dass eine .env-Datei im Hauptverzeichnis existiert.")
        return

    # Der Pfad zur CSV-Datei im Hauptverzeichnis des Projekts
    csv_path = os.path.join(project_root, filename)

    try:
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                meldung_id = row['id']
                test_text = row['meldungstext']

                print("=========================================================")
                print(f"▶️  TESTING NOTIFICATION ID: {meldung_id}")
                print(f"   Eingabetext: \"{test_text}\"")
                print("---------------------------------------------------------")
                
                try:
                    # Rufe die eigentliche Analyse-Funktion auf
                    result = analyze_text(test_text)
                    
                    # Gib das Ergebnis schön formatiert aus
                    print(f"   SCORE: {result.score}/100")
                    print("   PROBLEME:")
                    if result.issues:
                        for issue in result.issues:
                            print(f"     - {issue}")
                    else:
                        print("     - Keine Probleme gefunden.")
                    print(f"   ZUSAMMENFASSUNG: {result.summary}")
                
                except Exception as e:
                    print(f"!!! Ein unerwarteter Fehler ist aufgetreten: {e}")

                print("=========================================================\n")
                # Pause, um Rate-Limits der API zu vermeiden
                time.sleep(1.5) 

    except FileNotFoundError:
        print(f"FEHLER: Die Datei '{csv_path}' wurde nicht gefunden.")
        print("Bitte führe zuerst das Skript 'python3 scripts/generate_test_data.py' aus.")
    except Exception as e:
        print(f"Ein Fehler beim Lesen der Datei ist aufgetreten: {e}")


if __name__ == "__main__":
    run_test_from_file()
