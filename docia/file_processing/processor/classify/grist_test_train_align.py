"""Aligne le golden test set sur le schéma classify_v2 (documents_raw.parquet)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from docia.file_processing.processor.classify.constants import DEFAULT_OUTPUT_DIR, TEXT_HEAD_CHARS
from docia.file_processing.processor.classify.dataset import TEXT_FETCH_CHUNK, _chunked, _load_texts_map
from docia.file_processing.processor.classify.label_hierarchy import map_llm_to_coarse
from docia.file_processing.processor.classify.text_prep import normalize_filename, prepare_text_head

logger = logging.getLogger(__name__)

TRAIN_PARQUET_COLUMNS: tuple[str, ...] = (
    "id",
    "hash",
    "filename",
    "num_ej",
    "nb_mot",
    "text_2000",
    "filename_normalized",
    "classification",
    "label_train",
    "label_train_silver",
    "ratio_extracted",
    "analyzed_at",
    "sample_role",
    "split",
    "exclusion_reason",
)

_V2_COPY_COLUMNS: tuple[str, ...] = (
    "id",
    "filename",
    "num_ej",
    "nb_mot",
    "text_2000",
    "filename_normalized",
    "classification",
    "label_train",
    "ratio_extracted",
    "analyzed_at",
    "sample_role",
    "split",
    "exclusion_reason",
)


def _coalesce_series(primary: pd.Series, fallback: pd.Series) -> pd.Series:
    use_fb = primary.isna()
    if primary.dtype == object:
        use_fb |= primary.astype(str).str.strip() == ""
    return primary.where(~use_fb, fallback)


def _load_v2_by_hash(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    try:
        import pyarrow.parquet as pq

        available = set(pq.ParquetFile(path).schema_arrow.names)
    except Exception:
        logger.exception("Impossible de lire le schéma %s", path)
        return pd.DataFrame()
    if "hash" not in available:
        return pd.DataFrame()
    cols = ["hash", *[c for c in _V2_COPY_COLUMNS if c in available]]
    v2 = pd.read_parquet(path, columns=cols)
    v2["hash"] = v2["hash"].astype(str).str.strip()
    return v2.drop_duplicates(subset=["hash"], keep="first")


def _merge_v2_fields(out: pd.DataFrame, v2: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if v2.empty or "hash" not in out.columns:
        return out, 0

    pref = v2.rename(columns=lambda c: f"__v2_{c}")
    merged = out.merge(pref, left_on="hash", right_on="__v2_hash", how="left")
    matched = merged["__v2_hash"].notna()
    n = int(matched.sum())

    silver_v2 = merged["__v2_label_train"] if "__v2_label_train" in merged.columns else None

    for col in _V2_COPY_COLUMNS:
        vcol = f"__v2_{col}"
        if vcol not in merged.columns:
            continue
        if col not in merged.columns:
            merged[col] = merged[vcol]
        elif col == "label_train":
            continue  # géré plus bas (golden vs silver)
        else:
            merged[col] = _coalesce_series(merged[vcol], merged[col])

    merged = merged.drop(columns=[c for c in merged.columns if c.startswith("__v2_")])
    merged["classify_v2_split"] = None
    merged.loc[matched, "classify_v2_split"] = merged.loc[matched, "split"]
    merged["in_classify_v2_parquet"] = matched
    if silver_v2 is not None:
        merged["label_train_silver"] = silver_v2
    return merged, n


def align_with_train_schema(
    df: pd.DataFrame,
    *,
    classify_v2_parquet: Path | None = None,
    fetch_text_from_db: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Priorité features : documents_raw (hash) > BDD > Grist."""
    stats: dict[str, Any] = {"rows_from_v2_hash": 0, "text_from_db": 0, "text_from_grist": 0}
    if df.empty:
        return df, stats

    path = (classify_v2_parquet or (DEFAULT_OUTPUT_DIR / "documents_raw.parquet")).resolve()
    out = df.copy()
    v2 = _load_v2_by_hash(path)
    out, stats["rows_from_v2_hash"] = _merge_v2_fields(out, v2)

    if "document_id" in out.columns:
        if "id" not in out.columns:
            out["id"] = out["document_id"]
        else:
            out["id"] = _coalesce_series(out["id"].astype(object), out["document_id"].astype(object))

    if "classification_prod" in out.columns:
        if "classification" not in out.columns:
            out["classification"] = out["classification_prod"]
        else:
            out["classification"] = _coalesce_series(out["classification"].astype(object), out["classification_prod"].astype(object))

    db_texts: dict[str, str] = {}
    if fetch_text_from_db and "id" in out.columns:
        ids = [str(x) for x in out["id"].dropna().unique() if str(x).strip()]
        for chunk in _chunked(ids, TEXT_FETCH_CHUNK):
            db_texts.update(_load_texts_map(chunk))

    heads: list[str] = []
    for _, row in out.iterrows():
        cur = row.get("text_2000")
        if pd.notna(cur) and str(cur).strip():
            heads.append(str(cur))
            continue
        body = ""
        doc_id = row.get("id")
        if doc_id and str(doc_id) in db_texts and str(db_texts[str(doc_id)]).strip():
            body = db_texts[str(doc_id)]
            stats["text_from_db"] += 1
        elif row.get("text") is not None and str(row.get("text") or "").strip():
            body = str(row["text"])
            stats["text_from_grist"] += 1
        heads.append(prepare_text_head(body, TEXT_HEAD_CHARS))
    out["text_2000"] = heads

    if "filename_normalized" not in out.columns:
        out["filename_normalized"] = None
    missing_fn = out["filename_normalized"].isna() | (out["filename_normalized"].astype(str).str.strip() == "")
    if missing_fn.any():
        out.loc[missing_fn, "filename_normalized"] = (
            out.loc[missing_fn, "filename"].fillna("").astype(str).map(normalize_filename)
        )

    silver_from_llm = out["classification"].map(
        lambda c: map_llm_to_coarse(c) if pd.notna(c) and str(c).strip() else None
    )
    if "label_train_silver" not in out.columns:
        out["label_train_silver"] = silver_from_llm
    else:
        out["label_train_silver"] = _coalesce_series(out["label_train_silver"], silver_from_llm)

    if "label_coarse_ok" in out.columns:
        out["label_train"] = out["label_coarse"].where(out["label_coarse_ok"], None)
    else:
        out["label_train"] = out.get("label_coarse")

    if "sample_role" not in out.columns:
        out["sample_role"] = "golden_test"
    else:
        out["sample_role"] = out["sample_role"].fillna("golden_test")

    for col in ("split", "exclusion_reason", "ratio_extracted", "nb_mot", "analyzed_at", "num_ej"):
        if col not in out.columns:
            out[col] = None

    if "in_classify_v2_parquet" not in out.columns:
        out["in_classify_v2_parquet"] = False
    if "classify_v2_split" not in out.columns:
        out["classify_v2_split"] = out["split"]

    stats["rows_with_text_2000"] = int((out["text_2000"].fillna("").astype(str).str.strip() != "").sum())
    return out, stats