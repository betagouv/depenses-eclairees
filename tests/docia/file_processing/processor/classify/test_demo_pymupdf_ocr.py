from docia.file_processing.processor.classify.demo_pymupdf_ocr import (
    _fast_ocr_attempts,
    resolve_pymupdf4llm_ocr,
)


def test_resolve_pymupdf4llm_ocr_fast_only():
    fn, label = resolve_pymupdf4llm_ocr()
    assert isinstance(label, str)
    assert _fast_ocr_attempts()[-1][1] == "auto PyMuPDF (hybride)"
    if fn is not None:
        assert "tesseract" in label.lower()