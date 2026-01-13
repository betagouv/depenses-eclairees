from unittest.mock import patch

from docia.file_processing.processor.analyze_content import analyze_file_text


def test_analyze_file_text():
    with patch("docia.file_processing.processor.analyze_content.LLMClient.ask_llm", autospec=True) as m:
        data = {
            "denomination_insee": "Entreprise Test",
            "siren_kbis": "kbistest",
            "activite_principale": "Acivité test",
            "adresse_postale_insee": "1 rue du chocolat",
        }
        m.return_value = data
        r = analyze_file_text("Hello World", document_type="kbis")
        assert r == {
            "llm_response": data,
            "structured_data": data,
            "json_error": None,
        }
