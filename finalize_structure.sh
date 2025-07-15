#!/bin/bash

# Dieses Skript führt die letzten Aufräumarbeiten an der Projektstruktur durch.
# Es verschiebt verbliebene Dateien an ihren korrekten Ort.

echo "Starte finales Aufräumen der Projektstruktur..."

# 1. Sicherstellen, dass die Zielordner existieren
mkdir -p backend/data
mkdir -p .github/workflows
echo "Zielordner sichergestellt."

# 2. Testdaten und Mock-Daten in den 'backend/data'-Ordner verschieben
if [ -f "mock_data.json" ]; then
    mv mock_data.json backend/data/
    echo "'mock_data.json' nach 'backend/data' verschoben."
fi
if [ -f "test_meldungen.csv" ]; then
    mv test_meldungen.csv backend/data/
    echo "'test_meldungen.csv' nach 'backend/data' verschoben."
fi

# 3. Veraltete oder falsch platzierte Dateien löschen/verschieben
if [ -f "index.html" ]; then
    rm index.html
    echo "Veraltete 'index.html' gelöscht. (Die neue wird im Fiori-Projekt sein)."
fi
if [ -f "manifest.yml" ]; then
    rm manifest.yml
    echo "Veraltete 'manifest.yml' gelöscht. (Die neue ist die mta.yaml)."
fi
if [ -f "refactor_project.sh" ]; then
    rm refactor_project.sh
    echo "Altes Refactoring-Skript 'refactor_project.sh' gelöscht."
fi

# 4. CI/CD-Datei korrekt verschieben und umbenennen
if [ -f "deploy.yml # CI" ]; then
    mv "deploy.yml # CI" .github/workflows/deploy-mta.yml
    # Löscht den überflüssigen Ordner, falls er existiert
    if [ -d "CD für Deployment auf BTP" ]; then
        rm -rf "CD für Deployment auf BTP"
    fi
    echo "CI/CD-Workflow nach '.github/workflows/deploy-mta.yml' verschoben."
fi

echo "-----------------------------------------------------"
echo "✅ Finale Aufräumarbeiten abgeschlossen!"
echo "Die Projektstruktur ist jetzt sauber und bereit für die nächsten Schritte."
echo "-----------------------------------------------------"