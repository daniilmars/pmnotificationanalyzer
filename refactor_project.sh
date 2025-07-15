#!/bin/bash

# Dieses Skript strukturiert das Projekt "sap-pm-textanalyzer" neu.
# Es trennt das Projekt in ein 'backend' und ein 'fiori-app' Verzeichnis.
# Führen Sie es vom Hauptverzeichnis des Projekts aus aus.

# Stoppt das Skript sofort, wenn ein Befehl fehlschlägt.
set -e

echo "Starte Projekt-Refactoring..."

# --- 1. Hauptordner für Backend und Frontend erstellen ---
echo "Erstelle Hauptordner: backend/ und fiori-app/..."
mkdir -p backend
mkdir -p fiori-app

# --- 2. Backend-Dateien und -Ordner verschieben ---
echo "Verschiebe Backend-Komponenten..."
# Verschiebe den Kern der Applikation
mv app backend/
# Verschiebe die Hilfsskripte
mv scripts backend/
# Verschiebe die Tests
mv tests backend/
# Verschiebe die Konfigurationsdateien
mv Dockerfile backend/
mv requirements.txt backend/
mv run.py backend/
mv .venv backend/ # Verschiebe auch die virtuelle Umgebung

# --- 3. Frontend-Dateien verschieben (Annahme) ---
# Dieser Teil ist eine Annahme. Wenn Ihre Fiori-App-Dateien
# (z.B. webapp/, package.json, etc.) im Hauptverzeichnis liegen,
# müssen Sie diese Zeilen anpassen.
echo "Verschiebe Frontend-Komponenten (Annahme)..."
# Beispiel: mv webapp fiori-app/
# Beispiel: mv package.json fiori-app/
# Beispiel: mv ui5.yaml fiori-app/
echo "WARNUNG: Frontend-Dateien müssen eventuell manuell in den 'fiori-app' Ordner verschoben werden."


# --- 4. Übergeordnete Konfigurationsdateien belassen ---
# mta.yaml, .gitignore, README.md bleiben im Hauptverzeichnis.
echo "Übergeordnete Konfigurationsdateien bleiben im Hauptverzeichnis."

echo "-----------------------------------------------------"
echo "✅ Projektstruktur erfolgreich aufgeräumt!"
echo ""
echo "WICHTIGE NÄCHSTE SCHRITTE:"
echo "1. Aktualisieren Sie die 'import'-Pfade in Ihren Python-Dateien (z.B. in app/main.py)."
echo "2. Passen Sie die Pfade in Ihrer 'mta.yaml' an, damit sie auf 'backend/' und 'fiori-app/' verweisen."
echo "3. Überprüfen Sie Ihre CI/CD-Skripte (.github/workflows/), um sicherzustellen, dass die neuen Pfade verwendet werden."
echo "-----------------------------------------------------"

