import os
import csv
from dotenv import load_dotenv
from app.analyzer import analyze_text
import time

# Lädt Umgebungsvariablen aus einer .env-Datei
load_dotenv()

def run_test_from_file(filename="test_meldungen.csv"):
    """
    Reads notification texts from a CSV file and runs analysis on each.
    """
    # Check if the API key is available before starting
    if not os.getenv("GOOGLE_API_KEY"):
        print("FEHLER: Der GOOGLE_API_KEY wurde nicht gefunden.")
        print("Bitte erstelle eine .env-Datei oder setze die Umgebungsvariable.")
        return

    try:
        with open(filename, 'r', encoding='utf-8') as csvfile:
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
        print(f"FEHLER: Die Datei '{filename}' wurde nicht gefunden.")
        print("Bitte führe zuerst das Skript 'generate_test_data.py' aus.")
    except Exception as e:
        print(f"Ein Fehler beim Lesen der Datei ist aufgetreten: {e}")


if __name__ == "__main__":
    run_test_from_file()

