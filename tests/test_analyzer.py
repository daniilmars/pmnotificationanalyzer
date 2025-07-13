import pytest
import os
from dotenv import load_dotenv
from app.analyzer import analyze_text
from app.models import AnalysisResult

# Lade die Umgebungsvariablen aus der .env Datei
load_dotenv()

# Prüfen, ob der API-Schlüssel vorhanden ist. Wenn nicht, werden die Tests übersprungen.
# Das ist nützlich für CI/CD-Umgebungen, in denen der Schlüssel nicht vorhanden sein soll.
API_KEY_VORHANDEN = os.getenv("GOOGLE_API_KEY") is not None
GRUND_FUER_UEBERSPRINGEN = "GOOGLE_API_KEY ist nicht gesetzt..."

@pytest.mark.skipif(not API_KEY_VORHANDEN, reason=GRUND_FUER_UEBERSPRINGEN)
def test_analyze_good_text():
    """
    Testet einen guten, detaillierten Text.
    Erwartung: Hoher Score, keine oder wenige Probleme.
    """
    # 1. Arrange
    test_text = "Pumpe P-101 ausgefallen wegen Lagerschaden an der Antriebsseite. Ursache war mangelnde Schmierung. Lager wurde getauscht, Pumpe neu geschmiert und Probelauf war erfolgreich."
    
    # 2. Act
    result = analyze_text(test_text)
    
    # 3. Assert
    # Wir prüfen die Struktur und Plausibilität, nicht exakte Werte
    assert isinstance(result, AnalysisResult)
    assert isinstance(result.score, int)
    assert 80 <= result.score <= 100  # Ein guter Text sollte einen hohen Score bekommen
    assert isinstance(result.issues, list)
    assert isinstance(result.summary, str)
    assert "erfolgreich" in result.summary.lower()

@pytest.mark.skipif(not API_KEY_VORHANDEN, reason=GRUND_FUER_UEBERSPRINGEN)
def test_analyze_bad_text():
    """
    Testet einen sehr kurzen, unvollständigen Text.
    Erwartung: Niedriger Score, mehrere Probleme gelistet.
    """
    # 1. Arrange
    test_text = "Pumpe kaputt. Repariert."
    
    # 2. Act
    result = analyze_text(test_text)
    
    # 3. Assert
    assert isinstance(result, AnalysisResult)
    assert isinstance(result.score, int)
    assert 0 <= result.score <= 50  # Ein schlechter Text sollte einen niedrigen Score bekommen
    assert len(result.issues) > 1   # Es sollten mehrere Probleme gefunden werden
    assert "ursache" in " ".join(result.issues).lower() # Eines der Probleme sollte die fehlende Ursache sein

@pytest.mark.skipif(not API_KEY_VORHANDEN, reason=GRUND_FUER_UEBERSPRINGEN)
def test_analyze_text_with_missing_cause():
    """
    Testet einen Text, bei dem die Ursache fehlt.
    Erwartung: Mittlerer Score, das Hauptproblem sollte die fehlende Ursache sein.
    """
    # 1. Arrange
    test_text = "An der Dichtung von Reaktor R-5 ist eine Leckage aufgetreten. Die Dichtung wurde ersetzt und die Anlage wieder angefahren."
    
    # 2. Act
    result = analyze_text(test_text)
    
    # 3. Assert
    assert isinstance(result, AnalysisResult)
    assert 40 <= result.score <= 80 # Score im mittleren Bereich
    assert any("ursache" in issue.lower() for issue in result.issues) # Prüft, ob "Ursache" in einem der Probleme erwähnt wird
    assert "dichtung" in result.summary.lower()