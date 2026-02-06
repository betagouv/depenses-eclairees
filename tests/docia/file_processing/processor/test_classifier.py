from unittest.mock import patch

from docia.file_processing.processor.classifier import DIC_CLASS_FILE_BY_NAME, classify_file_with_llm


def test_classify_file_with_llm():
    with patch("docia.file_processing.processor.analyze_content.LLMClient.ask_llm", autospec=True) as m:
        m.return_value = ["Extrait Kbis"]
        r = classify_file_with_llm("doc.pdf", "Hello World", DIC_CLASS_FILE_BY_NAME)
    assert r == "kbis"
