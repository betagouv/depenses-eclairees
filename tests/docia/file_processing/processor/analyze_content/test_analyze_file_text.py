from unittest.mock import patch

from docia.file_processing.llm.client import LLMAskResult, LLMUsage
from docia.file_processing.processor.analyze_content import AnalyzeResult, analyze_file_text


def test_analyze_file_text():
    with patch("docia.file_processing.processor.analyze_content.LLMClient.ask_llm", autospec=True) as m:
        data = {
            "denomination": "Entreprise Test",
            "siren": "kbistest",
            "activite_principale": "Acivité test",
            "adresse_postale_insee": "1 rue du chocolat",
        }
        usage = LLMUsage(prompt_tokens=0, completion_tokens=0)
        m.return_value = LLMAskResult(content=data, usage=usage)
        r = analyze_file_text("Hello World", document_type="kbis")
        assert r == AnalyzeResult(
            llm_response=data,
            structured_data=data,
            usage=usage,
        )
