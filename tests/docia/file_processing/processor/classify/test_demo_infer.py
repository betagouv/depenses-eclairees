import pymupdf

from docia.file_processing.processor.classify.demo_infer import (
    build_feature_row,
    count_words,
    extract_pdf_text_pymupdf4llm,
    pipeline1_post_logreg_ocr_plan,
    run_demo_classify,
)


def _minimal_pdf_bytes(text: str = "Acte d engagement marche public test classification") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_build_feature_row_normalizes_filename_and_text():
    row = build_feature_row("Dossier/CCAP_lot-1.PDF", "  Bonjour\nMonde  ", nb_mot=3)
    assert row["filename_normalized"] == "ccap lot 1 pdf"
    assert row["nb_mot"] == 3
    assert isinstance(row["text_2000"], str)
    assert "bonjour monde" in str(row["text_2000"])


def test_pipeline1_post_logreg_ocr_plan():
    assert pipeline1_post_logreg_ocr_plan(decision="acte_engagement", accepted=True) == ("mistral-ocr", None)
    assert pipeline1_post_logreg_ocr_plan(decision="sous_traitance", accepted=True) == ("mistral-ocr", None)
    assert pipeline1_post_logreg_ocr_plan(decision="ccap", accepted=True) == ("tesseract", None)
    assert pipeline1_post_logreg_ocr_plan(decision="rib", accepted=True) == ("tesseract", None)
    engine, reason = pipeline1_post_logreg_ocr_plan(decision="courrier", accepted=True)
    assert engine == "none" and "hors périmètre" in (reason or "")
    engine, reason = pipeline1_post_logreg_ocr_plan(decision="acte_engagement", accepted=False)
    assert engine == "none" and reason


def test_count_words_basic():
    assert count_words("un deux trois") == 3
    assert count_words("") == 0


def test_extract_pdf_text_pymupdf4llm_minimal():
    content = _minimal_pdf_bytes()
    out = extract_pdf_text_pymupdf4llm(content)
    assert out.nb_pages == 1
    assert out.pages_extracted == 1
    assert out.nb_mot >= 5
    assert not out.too_sparse
    assert "engagement" in out.raw_text.lower() or "marche" in out.raw_text.lower()


def test_run_demo_classify_sparse_pdf_skips_inference():
    sparse = _minimal_pdf_bytes("x")
    result = run_demo_classify(sparse, "vide.pdf", tau=0.5, margin_threshold=0.0)
    assert result.inference_skipped
    assert result.too_sparse
    assert result.sparse_warning


def test_run_demo_classify_end_to_end_if_artifacts_present():
    content = _minimal_pdf_bytes("acte engagement ccap rib devis sous traitance avenant catalogue prix")
    try:
        result = run_demo_classify(content, "ae_demo.pdf")
    except FileNotFoundError:
        return
    assert not result.inference_skipped
    assert result.total_ms > 0
    assert result.filename == "ae_demo.pdf"
    assert len(result.top5) <= 5