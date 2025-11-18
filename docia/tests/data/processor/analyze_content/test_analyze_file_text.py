import json
from unittest.mock import patch

from app.processor.analyze_content import analyze_file_text
from app.processor.attributes_query import ATTRIBUTES


def test_analyze_file_text():
    with patch("app.processor.analyze_content.LLMEnvironment.ask_llm", autospec=True) as m:
        data = {
            "denomination_insee": "Entreprise Test",
            "siren_kbis": "kbistest",
            "activite_principale": "Acivité test",
            "adresse_postale_insee": "1 rue du chocolat",
        }
        m.return_value = json.dumps(data)
        r = analyze_file_text("doc.pdf", "Hello World", ATTRIBUTES, classification="kbis")
        assert r == {
            "llm_response": data,
            "json_error": None,
        }


def test_analyze_file_text_bad_json():
    with patch("app.processor.analyze_content.LLMEnvironment.ask_llm", autospec=True) as m:
        m.return_value = '{"wrong json"}'
        r = analyze_file_text("doc.pdf", "Hello World", ATTRIBUTES, classification="kbis")
        assert r == {
            "llm_response": None,
            "json_error": "Format JSON invalide: Expecting ':' delimiter: line 1 column 14 (char 13)",
        }
