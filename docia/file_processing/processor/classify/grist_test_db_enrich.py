"""Enrichissement du golden test set via hash → Document (métadonnées prod manquantes dans Grist)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from docia.documents.models import Document
from docia.file_processing.processor.classify.constants import DEFAULT_OUTPUT_DIR
from docia.file_processing.processor.classify.dataset import TEXT_FETCH_CHUNK, _chunked, _ej_map_for_ids
from docia.file_processing.processor.classify.fill_ratio import compute_ratio_data_extraction
from docia.file_processing.processor.classify.text_prep import normalize_filename

logger = logging.getLogger(__name__)

_DB_DOCUMENT_FIELDS = (
    "id",
    "hash",
    "filename",
    "dossier",
    "extension",
    "nb_mot",
    "nb_pages",
    "is_ocr",
    "classification",
    "structured_data",
    "analyzed_at",
    "text",
)

_FILL_FROM_DB = (
    "num_ej",
    "is_ocr",
    "nb_mot",
    "nb_pages",
    "dossier",
    "extension",
    "filename_normalized",
    "classification_prod",
    "ratio_extracted",
    "analyzed_at",
    "text",
)


def _is_blank(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, float) and pd.isna(val):
        return True
    return str(val).strip() == ""


def _document_row_to_enrich(item: dict[str, Any], *, num_ej: str | None) -> dict[str, Any]:
    analyzed = item.get("analyzed_at")
    return {
        "document_id": str(item["id"]),
        "hash": item["hash"],
        "dossier": item.get("dossier"),
        "extension": item.get("extension"),
        "nb_mot": item.get("nb_mot"),
        "nb_pages": item.get("nb_pages"),
        "is_ocr": item.get("is_ocr"),
        "classification_prod": item.get("classification"),
        "ratio_extracted": compute_ratio_data_extraction(item.get("structured_data")),
        "analyzed_at": analyzed.isoformat() if analyzed is not None else None,
        "num_ej": num_ej,
        "filename_normalized": normalize_filename(item.get("filename") or ""),
    }


def _fetch_by_hashes(hashes: Iterable[str]) -> dict[str, dict[str, Any]]:
    uniq = sorted({h for h in hashes if h and str(h).strip()})
    out: dict[str, dict[str, Any]] = {}
    if not uniq:
        return out
    for chunk in _chunked(uniq, 500):
        rows = list(Document.objects.filter(hash__in=chunk).values(*_DB_DOCUMENT_FIELDS))
        if not rows:
            continue
        ej_map = _ej_map_for_ids([str(r["id"]) for r in rows])
        for row in rows:
            h = row["hash"]
            out[h] = _document_row_to_enrich(row, num_ej=ej_map.get(str(row["id"])))
    return out


def _resolve_hashes_from_v2(df: pd.DataFrame, path: Path) -> pd.Series:
    if df.empty or not path.is_file():
        return pd.Series([None] * len(df), index=df.index)
    v2 = pd.read_parquet(path, columns=["filename", "num_ej", "hash"])
    v2["num_ej"] = v2["num_ej"].fillna("").astype(str)
    v2["filename"] = v2["filename"].astype(str)
    v2 = v2.drop_duplicates(subset=["filename", "num_ej"], keep="first")
    left = df.copy()
    left["_num_ej"] = left["num_ej"].fillna("").astype(str)
    left["_filename"] = left["filename"].astype(str)
    merged = left[["_filename", "_num_ej"]].merge(
        v2,
        left_on=["_filename", "_num_ej"],
        right_on=["filename", "num_ej"],
        how="left",
    )
    return pd.Series(merged["hash"].values, index=df.index)


def _resolve_hashes_from_filename_ej(df: pd.DataFrame, *, missing_mask: pd.Series) -> dict[int, str]:
    """Dernier recours : lookup BDD (filename + engagement)."""
    resolved: dict[int, str] = {}
    if not missing_mask.any():
        return resolved
    sub = df.loc[missing_mask, ["filename", "num_ej"]]
    for idx, row in sub.iterrows():
        fn = str(row.get("filename") or "").strip()
        ej = row.get("num_ej")
        if not fn:
            continue
        qs = Document.objects.filter(filename=fn)
        if ej is not None and not _is_blank(ej):
            qs = qs.filter(engagements__num_ej=str(ej).strip())
        hit = qs.order_by("-analyzed_at", "-classified_at").values_list("hash", flat=True).first()
        if hit:
            resolved[idx] = hit
    return resolved


def resolve_hashes(
    df: pd.DataFrame,
    *,
    classify_v2_parquet: Path | None = None,
    resolve_filename_ej: bool = True,
) -> tuple[pd.Series, dict[str, int]]:
    """
    Complète la colonne hash : valeur Grist, puis parquet V2, puis BDD filename+num_ej.
    """
    stats = {"from_grist": 0, "from_v2": 0, "from_db_filename": 0, "unresolved": 0}
    if df.empty:
        return pd.Series(dtype=object), stats

    out = df["hash"].copy() if "hash" in df.columns else pd.Series([None] * len(df), index=df.index)
    present = out.notna() & (out.astype(str).str.strip() != "")
    stats["from_grist"] = int(present.sum())

    need = ~present
    if need.any():
        v2_path = classify_v2_parquet or (DEFAULT_OUTPUT_DIR / "documents_raw.parquet")
        from_v2 = _resolve_hashes_from_v2(df.loc[need], v2_path)
        filled_v2 = from_v2.notna() & (from_v2.astype(str).str.strip() != "")
        out.loc[filled_v2.index[filled_v2]] = from_v2.loc[filled_v2]
        stats["from_v2"] = int(filled_v2.sum())

    still_need = out.isna() | (out.astype(str).str.strip() == "")
    if resolve_filename_ej and still_need.any():
        from_fn = _resolve_hashes_from_filename_ej(df, missing_mask=still_need)
        for idx, h in from_fn.items():
            out.loc[idx] = h
        stats["from_db_filename"] = len(from_fn)

    stats["unresolved"] = int((out.isna() | (out.astype(str).str.strip() == "")).sum())
    return out, stats


def enrich_test_final_from_db(
    df: pd.DataFrame,
    *,
    classify_v2_parquet: Path | None = None,
    resolve_filename_ej: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Joint les métadonnées Document pour chaque hash résolu.
    Ne remplace pas les champs Grist déjà renseignés (sauf hash / document_id).
    """
    meta_stats: dict[str, Any] = {"hash_resolution": {}, "rows_with_document": 0, "rows_without_document": 0}
    if df.empty:
        return df, meta_stats

    out = df.copy()
    if "hash" not in out.columns:
        out["hash"] = None

    out["hash"], meta_stats["hash_resolution"] = resolve_hashes(
        out,
        classify_v2_parquet=classify_v2_parquet,
        resolve_filename_ej=resolve_filename_ej,
    )

    hashes = out["hash"].dropna().astype(str).str.strip()
    hashes = hashes[hashes != ""].unique().tolist()
    by_hash = _fetch_by_hashes(hashes)

    if "document_id" not in out.columns:
        out["document_id"] = None

    for col in _FILL_FROM_DB:
        if col in out.columns:
            out[col] = out[col].astype(object)

    for idx, row in out.iterrows():
        h = row.get("hash")
        if _is_blank(h):
            meta_stats["rows_without_document"] += 1
            continue
        doc = by_hash.get(str(h).strip())
        if not doc:
            meta_stats["rows_without_document"] += 1
            continue
        meta_stats["rows_with_document"] += 1
        out.at[idx, "document_id"] = doc["document_id"]
        if _is_blank(out.at[idx, "hash"]):
            out.at[idx, "hash"] = doc["hash"]
        for col in _FILL_FROM_DB:
            if col not in out.columns:
                out[col] = None
            if _is_blank(out.at[idx, col]) and not _is_blank(doc.get(col)):
                out.at[idx, col] = doc[col]

    out["in_database"] = out["document_id"].notna()
    return out, meta_stats