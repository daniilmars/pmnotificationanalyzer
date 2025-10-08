import pytest
import os
from dotenv import load_dotenv
from app.services.analysis_service import analyze_text
from app.models import AnalysisResponse

load_dotenv()

API_KEY_VORHANDEN = os.getenv("GOOGLE_API_KEY") is not None
GRUND_FUER_UEBERSPRINGEN = "GOOGLE_API_KEY ist nicht gesetzt. Überspringe Integrationstest."

@pytest.mark.skipif(not API_KEY_VORHANDEN, reason=GRUND_FUER_UEBERSPRINGEN)
def test_analyze_good_text():
    test_text = "Anlage R-101, Charge 2024-07-B: Druckabfall am Ventil V-5. Ursache: Haarriss im Dichtungsring durch Materialermüdung. Dichtung (Mat-Nr. 12345) getauscht, Ventil auf 15 bar abgedrückt. Kein Einfluss auf Produktqualität, da vor Abfüllung bemerkt. Wartungsplan für Ventile dieses Typs wird überprüft."
    result = analyze_text({"LongText": test_text})
    assert isinstance(result, AnalysisResponse)
    assert 20 <= result.score <= 100

@pytest.mark.skipif(not API_KEY_VORHANDEN, reason=GRUND_FUER_UEBERSPRINGEN)
def test_analyze_bad_text():
    test_text = "ventil undicht. repariert."
    result = analyze_text({"LongText": test_text})
    assert isinstance(result, AnalysisResponse)
    assert 0 <= result.score <= 40
    assert len(result.problems) > 2

@pytest.mark.skipif(not API_KEY_VORHANDEN, reason=GRUND_FUER_UEBERSPRINGEN)
def test_analyze_text_with_missing_impact_assessment():
    test_text = "Leckage an Pumpe P-55 während Produktion von Charge 2024-07-C. Dichtung wurde ersetzt."
    result = analyze_text({"LongText": test_text})
    assert isinstance(result, AnalysisResponse)
    assert 10 <= result.score <= 70
    assert any("product impact" in issue.lower() or "produkteinfluss" in issue.lower() for issue in result.problems)
