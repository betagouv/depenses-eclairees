"""Démo locale : classification logreg V2 sur PDF (Streamlit)."""

from __future__ import annotations

import importlib
import inspect
import sys
from functools import lru_cache
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd
import streamlit as st

from docia.file_processing.processor.classify import demo_infer as _demo_infer_mod
from docia.file_processing.processor.classify import demo_ocr_pipeline as _demo_ocr_mod
from docia.file_processing.processor.classify.constants import DEFAULT_OUTPUT_DIR

importlib.reload(_demo_ocr_mod)
importlib.reload(_demo_infer_mod)

DEMO_RAW_PREVIEW_CHARS = _demo_infer_mod.DEMO_RAW_PREVIEW_CHARS
DemoClassifyResult = _demo_infer_mod.DemoClassifyResult
load_demo_artifacts = _demo_infer_mod.load_demo_artifacts
run_demo_classify = _demo_infer_mod.run_demo_classify

_sig = inspect.signature(run_demo_classify).parameters
if "with_llm" not in _sig or "with_ocr_pipeline" not in _sig:
    raise RuntimeError(
        "demo_infer obsolète : redémarrez Streamlit ou vérifiez "
        "docia/file_processing/processor/classify/demo_infer.py."
    )


@lru_cache(maxsize=1)
def _cached_artifacts(model_dir: str):
    return load_demo_artifacts(Path(model_dir))


def _render_verdict(result: DemoClassifyResult) -> None:
    if result.inference_skipped:
        st.error("Texte insuffisant — logreg non lancé.")
        if result.sparse_warning:
            st.caption(result.sparse_warning)
        if result.with_llm:
            _render_llm_block(result)
        return

    if result.accepted:
        st.success(f"**Logreg (accepté)** — {result.decision_display}")
        st.caption(f"Libellé : `{result.decision}`")
    else:
        st.warning("**Logreg (rejet)** — routage LLM en production.")
        st.caption(f"Argmax : **{result.pred_display}** (`{result.pred_classifier}`)")

    if result.with_llm:
        _render_llm_block(result)


def _render_llm_block(result: DemoClassifyResult) -> None:
    st.markdown("---")
    st.markdown("**LLM (référence prod)**")
    if result.llm_error:
        st.error(f"Échec appel API : {result.llm_error}")
        return
    if not result.llm_label:
        st.info("Aucune classe reconnue (`Non classifié`).")
        return
    st.info(f"**{result.llm_display}** (`{result.llm_label}`)")
    if result.llm_coarse:
        st.caption(f"Coarse : **{result.llm_coarse_display}** (`{result.llm_coarse}`)")
    if result.logreg_llm_same_coarse is not None:
        if result.logreg_llm_same_coarse:
            st.success("Accord logreg / LLM (niveau coarse).")
        else:
            st.warning("Désaccord logreg / LLM (niveau coarse).")
    tok = ""
    if result.llm_prompt_tokens is not None:
        tok = f" · tokens {result.llm_prompt_tokens}+{result.llm_completion_tokens}"
    st.caption(f"Modèle `{result.llm_model}` · {result.llm_ms:.0f} ms{tok}")


def _render_top5(result: DemoClassifyResult) -> None:
    if not result.top5:
        return
    rows = []
    for rank, t in enumerate(result.top5, start=1):
        pct = 100.0 * t.probability
        rows.append(
            {
                "Rang": rank,
                "Classe": t.display_name,
                "Libellé": t.label,
                "%": pct,
            }
        )
    df = pd.DataFrame(rows)

    for _, row in df.iterrows():
        label = f"**{row['Classe']}** · `{row['Libellé']}`"
        st.markdown(label)
        st.progress(min(float(row["%"]) / 100.0, 1.0), text=f"{row['%']:.1f} %")
        if int(row["Rang"]) < len(df):
            st.markdown("")

    with st.expander("Tableau TOP 5"):
        st.dataframe(
            df.rename(columns={"%": "Probabilité (%)"}),
            width="stretch",
            hide_index=True,
        )


def _sequential_ms(result: DemoClassifyResult) -> float:
    total = result.extract_ms
    if not result.inference_skipped:
        total += result.infer_ms
    if result.with_llm:
        total += result.llm_ms
    return total


def _render_pipeline1_post_logreg_ocr(result: DemoClassifyResult) -> None:
    if not result.with_ocr_pipeline:
        return
    st.caption(
        "Étape 3 · doc entier : mistral (AE, sous-traitance) ou Tesseract (autres classes analyse)"
    )
    if result.pipeline1_post_logreg_ran and not result.pipeline1_post_logreg_error:
        st.success(
            f"OCR `{result.pipeline1_post_logreg_engine}` · {result.pipeline1_post_logreg_ocr_ms:.0f} ms · "
            f"{result.pipeline1_post_logreg_nb_mot or 0} mots"
        )
    elif result.pipeline1_post_logreg_error:
        st.error(result.pipeline1_post_logreg_error)
    elif result.pipeline1_post_logreg_skip_reason:
        st.info(f"Arrêt P1 : {result.pipeline1_post_logreg_skip_reason}")
    else:
        st.caption("Pas de 2ᵉ extraction sur P1.")


def _render_pipeline2_verdict(result: DemoClassifyResult) -> None:
    st.markdown("---")
    st.markdown("**Pipeline 2 · OCR + LLM (prod)**")
    if result.pipeline2_error:
        st.error(result.pipeline2_error)
        return
    if result.pipeline2_display:
        st.info(f"**{result.pipeline2_display}** (`{result.pipeline2_label}`)")
        if result.pipeline2_coarse:
            st.caption(f"Coarse : **{result.pipeline2_coarse_display}** (`{result.pipeline2_coarse}`)")
    st.caption(
        f"OCR {result.pipeline2_ocr_ms:.0f} ms + classif. {result.pipeline2_classify_ms:.0f} ms "
        f"= **{result.pipeline2_total_ms:.0f} ms**"
    )


def _render_pipelines_timing(result: DemoClassifyResult) -> None:
    if not result.with_ocr_pipeline:
        _render_timing_comparison(result)
        return

    p1 = result.pipeline1_total_ms or result.total_ms
    p2 = result.pipeline2_total_ms

    st.markdown("**Pipelines complets** (lancés en parallèle)")
    pipelines = pd.DataFrame(
        [
            {
                "Pipeline": "P1 · Tesseract 3 p. → logreg → OCR doc entier (selon classe)",
                "Durée (ms)": p1,
            },
            {"Pipeline": "P2 · mistral OCR doc entier → LLM prod", "Durée (ms)": p2},
        ]
    )
    st.caption(
        "P1 étape 3 : mistral si AE / sous-traitance ; Tesseract complet sinon (ccap, rib, …) si logreg accepte. "
        "P2 : mistral systématique + LLM."
    )
    st.bar_chart(pipelines.set_index("Pipeline")["Durée (ms)"])
    st.dataframe(pipelines, width="stretch", hide_index=True)

    m1, m2, m3 = st.columns(3)
    m1.metric("Pipeline 1 total", f"{p1:.0f} ms")
    m2.metric("Pipeline 2 total", f"{p2:.0f} ms")
    m3.metric("Mur (les deux)", f"{result.pipelines_wall_ms:.0f} ms", help="max(P1, P2) quand exécutés en parallèle")

    if result.pipeline_speed_ratio and result.pipeline1_faster is not None:
        if result.pipeline1_faster:
            st.success(
                f"**Pipeline 1 ~{result.pipeline_speed_ratio:.1f}× plus rapide** que le pipeline 2 "
                f"({p1:.0f} ms vs {p2:.0f} ms)."
            )
        else:
            st.warning(
                f"**Pipeline 2 ~{result.pipeline_speed_ratio:.1f}× plus rapide** que le pipeline 1 "
                f"({p2:.0f} ms vs {p1:.0f} ms)."
            )

    with st.expander("Détail pipeline 1 (étapes)", expanded=False):
        _render_timing_comparison(result)

    with st.expander("Détail pipeline 2 (OCR → LLM)", expanded=False):
        d1, d2, d3 = st.columns(3)
        d1.metric("OCR mistral-ocr-2512", f"{result.pipeline2_ocr_ms:.0f} ms")
        d2.metric("Classif. openweight-medium", f"{result.pipeline2_classify_ms:.0f} ms")
        d3.metric("Total P2", f"{result.pipeline2_total_ms:.0f} ms")


def _render_timing_comparison(result: DemoClassifyResult) -> None:
    logreg_ms = 0.0 if result.inference_skipped else result.infer_ms
    steps: list[dict[str, float | str]] = [
        {"Étape": "1. Extraction", "ms": result.extract_ms},
    ]
    if not result.inference_skipped:
        steps.append({"Étape": "2. Logreg", "ms": logreg_ms})
    if result.with_ocr_pipeline and result.pipeline1_post_logreg_ocr_ms > 0:
        label = result.pipeline1_post_logreg_engine or "OCR doc entier"
        steps.append({"Étape": f"3. {label}", "ms": result.pipeline1_post_logreg_ocr_ms})
    if result.with_llm:
        steps.append({"Étape": "LLM comparateur (texte P1)", "ms": result.llm_ms})
    steps_df = pd.DataFrame(steps)

    total = max(result.total_ms, 1.0)
    compare = steps_df.copy()
    compare["Part du total (%)"] = (compare["ms"] / total * 100).round(1)

    chart = steps_df.set_index("Étape")
    st.bar_chart(chart["ms"])
    st.dataframe(compare, width="stretch", hide_index=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total mesuré", f"{result.total_ms:.0f} ms", help="Extraction + mur d'inférence (max logreg, LLM)")
    if result.with_llm and not result.inference_skipped:
        saved = _sequential_ms(result) - result.total_ms
        c2.metric(
            "Gain parallèle",
            f"{saved:.0f} ms",
            help="Économie vs enchaînement extraction → logreg → LLM",
        )
    elif result.with_llm:
        c2.metric("Inférence (mur)", f"{result.parallel_infer_ms:.0f} ms")
    else:
        c2.metric("Inférence", f"{logreg_ms:.0f} ms")

    speed_ratio: float | None = None
    if result.with_llm and logreg_ms > 0 and not result.llm_error:
        speed_ratio = result.llm_ms / logreg_ms
        c3.metric(
            "Classif. logreg vs LLM",
            f"{speed_ratio:.0f}×",
            delta="plus rapide (logreg)",
            delta_color="normal",
            help=f"Logreg {logreg_ms:.0f} ms · LLM {result.llm_ms:.0f} ms (hors extraction)",
        )
    elif result.with_llm and logreg_ms > 0:
        c3.metric("Classif. logreg vs LLM", "—")
    else:
        c3.metric("Parallèle (mur)", f"{result.parallel_infer_ms:.0f} ms")

    if speed_ratio is not None:
        st.markdown(
            f"**Classification : le logreg est ~{speed_ratio:.0f}× plus rapide que le LLM** "
            f"({logreg_ms:.0f} ms contre {result.llm_ms:.0f} ms, extraction non incluse)."
        )

    if result.with_llm:
        seq = _sequential_ms(result)
        extra = ""
        if speed_ratio is not None:
            extra = f" · Rapport classif. LLM/logreg : {speed_ratio:.1f}×"
        st.caption(
            f"Hypothèse **séquentielle** (sans parallèle) : {seq:.0f} ms · "
            f"Mesuré : {result.total_ms:.0f} ms"
            f" (logreg {logreg_ms:.0f} ms, LLM {result.llm_ms:.0f} ms, "
            f"mur parallèle {result.parallel_infer_ms:.0f} ms){extra}."
        )
    else:
        st.caption(f"Pipeline : extraction {result.extract_ms:.0f} ms + logreg {logreg_ms:.0f} ms.")


def _render_confidence(result: DemoClassifyResult) -> None:
    if result.inference_skipped:
        return
    c1, c2 = st.columns(2)
    c1.metric("Confiance max", f"{result.max_proba:.1%}")
    c2.metric("Écart 1er / 2e", f"{result.margin:.1%}")

    st.markdown("**Seuils de routage**")
    tau_ok = "atteint" if result.passes_tau else "non atteint"
    margin_ok = "atteint" if result.passes_margin else "non atteint"
    st.markdown(
        f"- τ = {result.tau:.2f} → max_proba **{tau_ok}** ({result.max_proba:.3f})\n"
        f"- margin ≥ {result.margin_threshold:.2f} → **{margin_ok}** ({result.margin:.3f})"
    )


def _render_sidebar(default_model_dir: str) -> tuple[str, bool, bool]:
    with st.sidebar:
        st.header("Aide")
        with st.expander("Périmètre & limites", expanded=False):
            st.markdown(
                """
                - **P1** : 3 p. → logreg → mistral (AE, ST) ou **Tesseract doc entier** (autres analyse)
                - **P2** (option) : mistral-ocr doc entier → LLM (prod)
                - Texte **non stocké** sur disque
                - Entraînement sur texte prod (doc entier, OCR possible) : scores indicatifs
                """
            )
        st.subheader("Modèle")
        model_dir = st.text_input("Répertoire des artefacts", value=default_model_dir)
        with_llm = st.checkbox(
            "Comparer avec le LLM (même texte PyMuPDF)",
            value=False,
            help="LLM openweight-medium en parallèle du logreg sur le texte pipeline 1.",
        )
        with_ocr_pipeline = st.checkbox(
            "Comparer pipeline prod (mistral-ocr + LLM)",
            value=False,
            help="Compare P1 (OCR mistral conditionnel) et P2 (OCR mistral + LLM) en parallèle.",
        )
        return model_dir, with_llm, with_ocr_pipeline
    return default_model_dir, False, False


def main() -> None:
    st.set_page_config(page_title="Démo classify V2", layout="wide")
    model_dir, with_llm, with_ocr_pipeline = _render_sidebar(str(DEFAULT_OUTPUT_DIR.resolve()))

    header_left, header_right = st.columns([3, 1])
    with header_left:
        st.title("Démo classify V2")
        st.caption("Logreg · PDF · localhost · démo technique")
    with header_right:
        st.metric("Pipeline", "3 p. extraites")

    uploaded = st.file_uploader(
        "Déposer un PDF",
        type=["pdf"],
        accept_multiple_files=False,
        label_visibility="collapsed",
        help="Fichier traité uniquement en mémoire.",
    )

    if uploaded is None:
        st.info("Glissez un PDF ici ou utilisez le bouton ci-dessus pour afficher le verdict et le TOP 5.")
        return

    filename = uploaded.name or "document.pdf"
    file_bytes = uploaded.getvalue()

    try:
        model, tau, margin, artifact_path = _cached_artifacts(model_dir)
    except FileNotFoundError as exc:
        st.error(f"Artefacts introuvables (`{model_dir}`). {exc}")
        return
    except Exception as exc:
        st.error(f"Impossible de charger le modèle : {exc}")
        return

    if with_ocr_pipeline:
        spinner = "Pipelines 1 et 2 en parallèle…"
    elif with_llm:
        spinner = "Extraction, logreg et LLM…"
    else:
        spinner = "Extraction et classification…"
    with st.spinner(spinner):
        result = run_demo_classify(
            file_bytes,
            filename,
            model=model,
            tau=tau,
            margin_threshold=margin,
            with_llm=with_llm,
            with_ocr_pipeline=with_ocr_pipeline,
        )

    meta1, meta2, meta3, meta4, meta5 = st.columns(5)
    meta1.metric("Fichier", Path(filename).name[:28] + ("…" if len(filename) > 28 else ""))
    pages_label = f"{result.pages_extracted}/{result.nb_pages} (P1)"
    if result.with_ocr_pipeline and result.pipeline2_nb_mot is not None:
        pages_label += f" · P2: doc entier"
    meta2.metric("Pages", pages_label)
    meta3.metric("Mots", result.nb_mot)
    dur = result.pipelines_wall_ms if result.with_ocr_pipeline else result.total_ms
    meta4.metric("Durée", f"{dur:.0f} ms")
    meta5.metric("Classes", result.model_n_classes)

    st.markdown("---")

    verdict_col, detail_col = st.columns([1, 1.1], gap="large")

    with verdict_col:
        with st.container(border=True):
            st.subheader("Verdict · pipeline 1")
            _render_verdict(result)
            if result.with_ocr_pipeline:
                _render_pipeline1_post_logreg_ocr(result)

        if result.with_ocr_pipeline:
            with st.container(border=True):
                _render_pipeline2_verdict(result)

        if result.top5:
            with st.container(border=True):
                st.subheader("TOP 5")
                _render_top5(result)

    with detail_col:
        with st.container(border=True):
            st.subheader("Confiance & routage")
            _render_confidence(result)

        with st.container(border=True):
            st.subheader("Temps d'exécution")
            _render_pipelines_timing(result)

        with st.expander("Détails techniques", expanded=False):
            st.code(result.filename_normalized, language=None)
            st.caption(
                f"Artefacts : `{artifact_path}` · τ={result.tau:.3f}, margin≥{result.margin_threshold:.3f} · "
                f"OCR P1 : {result.extract_ocr_engine}"
            )

    st.markdown("---")
    with st.expander(f"Aperçu texte pipeline 1 (max {DEMO_RAW_PREVIEW_CHARS} car.)", expanded=True):
        st.text_area(
            "Contenu P1",
            value=result.raw_text_preview or "(vide)",
            height=280,
            disabled=True,
            label_visibility="collapsed",
        )
    if result.with_ocr_pipeline and result.pipeline1_post_logreg_raw_preview:
        with st.expander("Aperçu texte P1 · étape 3 (doc entier)", expanded=False):
            st.text_area(
                "Contenu P1 étape 3",
                value=result.pipeline1_post_logreg_raw_preview,
                height=280,
                disabled=True,
                label_visibility="collapsed",
            )
    if result.with_ocr_pipeline and result.pipeline2_raw_preview:
        with st.expander("Aperçu texte pipeline 2 (OCR)", expanded=False):
            st.text_area(
                "Contenu P2",
                value=result.pipeline2_raw_preview,
                height=280,
                disabled=True,
                label_visibility="collapsed",
            )


if __name__ == "__main__":
    main()