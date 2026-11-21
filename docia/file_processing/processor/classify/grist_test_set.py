from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd

from docia.file_processing.processor.classify.constants import DEFAULT_OUTPUT_DIR
from docia.file_processing.processor.classify.grist_test_sources import (
    CLASSIF_GT_SOURCE,
    GristTestSource,
    priority_sources,
)
from docia.file_processing.processor.classify.label_hierarchy import (
    HIERARCHY_REVISION,
    map_llm_to_coarse,
)
from docia.file_processing.processor.classify.grist_test_db_enrich import enrich_test_final_from_db
from docia.file_processing.processor.classify.grist_test_train_align import (
    TRAIN_PARQUET_COLUMNS,
    align_with_train_schema,
)
from tests_e2e.grist_api import CLASSIF_GT_COLUMNS, fetch_all_records, load_classif_gt, parse_classification_list

logger = logging.getLogger(__name__)

DEFAULT_TEST_FINAL_DIR = Path("data/classify_test_final")

GOLDEN_ANNOTATION_COLUMNS = (
    "grist_record_id",
    "text",
    "is_ocr",
    "nb_pages",
    "dossier",
    "extension",
    "commentaire",
    "traitement",
    "classification_raw",
    "classification_prod",
    "label_fine",
    "label_coarse",
    "label_coarse_ok",
    "label_conflict",
    "source_table",
    "e2e_module",
    "hierarchy_revision",
    "in_database",
)

NORMALIZED_COLUMNS = (
    *TRAIN_PARQUET_COLUMNS,
    "in_classify_v2_parquet",
    "classify_v2_split",
    *GOLDEN_ANNOTATION_COLUMNS,
)


@dataclass
class BuildStats:
    rows_classif: int = 0
    rows_priority_branches: dict[str, int] = field(default_factory=dict)
    rows_rejected_priority: int = 0
    rows_before_dedupe: int = 0
    rows_after_dedupe: int = 0
    label_conflicts: int = 0
    unmapped_coarse: int = 0
    db_enrich: dict[str, Any] = field(default_factory=dict)
    train_align: dict[str, Any] = field(default_factory=dict)


def _dedupe_key(row: pd.Series) -> str:
    fn = str(row.get("filename") or "").strip()
    ej = row.get("num_ej")
    if ej is not None and not (isinstance(ej, float) and pd.isna(ej)) and str(ej).strip():
        return f"{fn}\0{str(ej).strip()}"
    return fn


def _normalize_priority_row(rec: pd.Series, source: GristTestSource) -> dict[str, Any]:
    grist_id = rec.get("id")
    classification_raw = None
    parsed = None
    if "classification" in rec.index and pd.notna(rec.get("classification")):
        parsed = parse_classification_list(rec["classification"])
        classification_raw = json.dumps(parsed) if parsed else None

    label = source.label_fine
    if parsed:
        label = parsed[0]

    return {
        "grist_record_id": int(grist_id) if pd.notna(grist_id) else None,
        "hash": rec.get("hash") if "hash" in rec.index else None,
        "filename": rec.get("filename"),
        "num_ej": rec.get("num_ej") if "num_ej" in rec.index else None,
        "text": rec.get("text"),
        "is_ocr": rec.get("is_ocr") if "is_ocr" in rec.index else None,
        "commentaire": rec.get("commentaire"),
        "traitement": rec.get("traitement") if "traitement" in rec.index else None,
        "classification_raw": classification_raw,
        "label_fine": label,
        "source_table": source.table,
        "e2e_module": source.e2e_module,
        "implicit_label_fine": source.label_fine,
    }


def build_classif_branch() -> pd.DataFrame:
    df = load_classif_gt(columns=CLASSIF_GT_COLUMNS)
    if df.empty:
        return pd.DataFrame(columns=list(NORMALIZED_COLUMNS))

    rows: list[dict[str, Any]] = []
    for _, rec in df.iterrows():
        parsed = rec["classification_parsed"]
        rows.append(
            {
                "grist_record_id": int(rec["id"]) if pd.notna(rec.get("id")) else None,
                "hash": rec.get("hash") if "hash" in rec.index else None,
                "filename": rec.get("filename"),
                "num_ej": rec.get("num_ej"),
                "text": rec.get("text"),
                "is_ocr": rec.get("is_ocr"),
                "commentaire": rec.get("commentaire"),
                "traitement": rec.get("traitement"),
                "classification_raw": json.dumps(parsed, ensure_ascii=False),
                "label_fine": rec["label_fine"],
                "source_table": CLASSIF_GT_SOURCE.table,
                "e2e_module": CLASSIF_GT_SOURCE.e2e_module,
                "implicit_label_fine": None,
                "label_conflict": False,
            }
        )
    return pd.DataFrame(rows)


def build_priority_gt_branch(source: GristTestSource) -> pd.DataFrame:
    raw = fetch_all_records(source.table)
    if raw.empty:
        return pd.DataFrame()
    if "commentaire" not in raw.columns:
        logger.warning("Table %s sans colonne commentaire", source.table)
        return pd.DataFrame()
    sub = raw[raw["commentaire"].astype(str).str.strip() == "traité"].copy()
    if sub.empty:
        return pd.DataFrame()
    rows = [_normalize_priority_row(sub.loc[idx], source) for idx in sub.index]
    return pd.DataFrame(rows)


def build_priority_gt_branches(*, include_fiche_navette: bool = False) -> list[tuple[GristTestSource, pd.DataFrame]]:
    branches: list[tuple[GristTestSource, pd.DataFrame]] = []
    for source in priority_sources(include_fiche_navette=include_fiche_navette):
        frame = build_priority_gt_branch(source)
        branches.append((source, frame))
    return branches


def merge_and_dedupe(classif: pd.DataFrame, branches: list[tuple[GristTestSource, pd.DataFrame]]) -> tuple[pd.DataFrame, pd.DataFrame, BuildStats]:
    stats = BuildStats()
    stats.rows_classif = len(classif)

    parts: list[pd.DataFrame] = []
    if not classif.empty:
        parts.append(classif)
    for source, frame in branches:
        stats.rows_priority_branches[source.table] = len(frame)
        if not frame.empty:
            parts.append(frame)

    if not parts:
        return pd.DataFrame(columns=list(NORMALIZED_COLUMNS)), pd.DataFrame(), stats

    combined = pd.concat(parts, ignore_index=True)
    stats.rows_before_dedupe = len(combined)

    buckets: dict[str, list[dict[str, Any]]] = {}
    for _, row in combined.iterrows():
        key = _dedupe_key(row)
        if not key:
            stats.rows_rejected_priority += 1
            continue
        buckets.setdefault(key, []).append(row.to_dict())

    conflict_rows: list[dict[str, Any]] = []
    merged_rows: list[dict[str, Any]] = []

    for key, items in buckets.items():
        classif_rows = [r for r in items if r.get("source_table") == CLASSIF_GT_SOURCE.table]
        other_rows = [r for r in items if r.get("source_table") != CLASSIF_GT_SOURCE.table]
        base = (classif_rows[0] if classif_rows else other_rows[0]).copy()
        tables = sorted({str(r.get("source_table")) for r in items if r.get("source_table")})
        base["source_table"] = ";".join(tables)
        base["label_conflict"] = False

        if classif_rows:
            base["label_fine"] = classif_rows[0]["label_fine"]
        for col in ("text", "num_ej", "hash", "is_ocr", "commentaire", "classification_raw"):
            for r in items:
                if pd.notna(r.get(col)) and (col not in base or pd.isna(base.get(col))):
                    base[col] = r[col]

        classif_label = classif_rows[0]["label_fine"] if classif_rows else None
        for r in other_rows:
            impl = r.get("implicit_label_fine")
            if not impl:
                continue
            if classif_label and str(impl) != str(classif_label):
                base["label_conflict"] = True
                stats.label_conflicts += 1
                conflict_rows.append(
                    {
                        "dedupe_key": key,
                        "filename": base.get("filename"),
                        "num_ej": base.get("num_ej"),
                        "label_fine_classif": classif_label,
                        "label_fine_implicit": impl,
                        "source_tables": base["source_table"],
                    }
                )
            elif not classif_label:
                base["label_fine"] = impl

        merged_rows.append(base)

    out = pd.DataFrame(merged_rows)
    stats.rows_after_dedupe = len(out)
    return out, pd.DataFrame(conflict_rows), stats


def enrich_coarse_labels(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["label_coarse"] = out["label_fine"].map(lambda x: map_llm_to_coarse(x) if pd.notna(x) else None)
    out["label_coarse_ok"] = out["label_coarse"].notna()
    out["hierarchy_revision"] = HIERARCHY_REVISION
    return out


def build_test_final_dataframe(
    *,
    classif_only: bool = False,
    include_fiche_navette: bool = False,
    classify_v2_parquet: Path | None = None,
    enrich_from_db: bool = True,
    align_train: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, BuildStats]:
    classif = build_classif_branch()
    branches = [] if classif_only else build_priority_gt_branches(include_fiche_navette=include_fiche_navette)
    merged, conflicts, stats = merge_and_dedupe(classif, branches)
    merged = enrich_coarse_labels(merged)
    stats.unmapped_coarse = int((~merged["label_coarse_ok"]).sum()) if not merged.empty else 0
    if enrich_from_db:
        merged, enrich_meta = enrich_test_final_from_db(merged, classify_v2_parquet=classify_v2_parquet)
        stats.db_enrich = enrich_meta

    if align_train:
        merged, align_meta = align_with_train_schema(
            merged,
            classify_v2_parquet=classify_v2_parquet,
            fetch_text_from_db=enrich_from_db,
        )
        stats.train_align = align_meta

    for col in NORMALIZED_COLUMNS:
        if col not in merged.columns:
            merged[col] = None
    if "implicit_label_fine" in merged.columns:
        merged = merged.drop(columns=["implicit_label_fine"])
    return merged[list(NORMALIZED_COLUMNS)], conflicts, stats


def _normalize_export_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "is_ocr" in out.columns:

        def _as_bool(val: Any) -> bool | None:
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return None
            if isinstance(val, bool):
                return val
            text = str(val).strip().lower()
            if text in ("true", "1", "oui", "yes"):
                return True
            if text in ("false", "0", "non", "no", ""):
                return False
            return None

        out["is_ocr"] = out["is_ocr"].map(_as_bool).astype("boolean")
    for col in ("nb_mot", "nb_pages", "grist_record_id"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def write_test_final_dataset(
    output_dir: Path | None = None,
    *,
    dataset_version: str | None = None,
    classif_only: bool = False,
    include_fiche_navette: bool = False,
    classify_v2_parquet: Path | None = None,
    dry_run: bool = False,
    enrich_from_db: bool = True,
    align_train: bool = True,
) -> tuple[Path | None, BuildStats]:
    out_dir = (output_dir or DEFAULT_TEST_FINAL_DIR).resolve()
    version = dataset_version or datetime.now(UTC).strftime("%Y-%m-%d")
    df, conflicts, stats = build_test_final_dataframe(
        classif_only=classif_only,
        include_fiche_navette=include_fiche_navette,
        classify_v2_parquet=classify_v2_parquet,
        enrich_from_db=enrich_from_db,
        align_train=align_train,
    )

    if dry_run:
        logger.info("Dry-run: %s rows, conflicts=%s", len(df), len(conflicts))
        return None, stats

    out_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = out_dir / "documents_test_final.parquet"
    df["dataset_version"] = version
    df["exported_at"] = datetime.now(UTC).isoformat()
    if "num_ej" in df.columns:
        df["num_ej"] = df["num_ej"].map(lambda x: None if pd.isna(x) else str(x))
    if "id" in df.columns:
        df["id"] = df["id"].map(lambda x: None if pd.isna(x) else str(x))
    df = _normalize_export_dtypes(df)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, parquet_path, compression="zstd")

    manifest = {
        "dataset_version": version,
        "exported_at": datetime.now(UTC).isoformat(),
        "hierarchy_revision": HIERARCHY_REVISION,
        "rows": len(df),
        "stats": {
            "rows_classif": stats.rows_classif,
            "rows_priority_branches": stats.rows_priority_branches,
            "rows_before_dedupe": stats.rows_before_dedupe,
            "rows_after_dedupe": stats.rows_after_dedupe,
            "label_conflicts": stats.label_conflicts,
            "unmapped_coarse": stats.unmapped_coarse,
            "db_enrich": stats.db_enrich,
            "train_align": stats.train_align,
        },
        "label_fine_counts": df["label_fine"].value_counts().to_dict() if not df.empty else {},
        "label_coarse_counts": df["label_coarse"].value_counts().to_dict() if not df.empty else {},
        "source_table_counts": df["source_table"].value_counts().to_dict() if not df.empty else {},
        "in_classify_v2": int(df["in_classify_v2_parquet"].sum()) if not df.empty else 0,
    }
    (out_dir / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if not conflicts.empty:
        conflicts.to_csv(out_dir / "label_conflicts.csv", index=False)

    readme = out_dir / "README.md"
    if not readme.is_file():
        logger.warning("README absent — versionner data/classify_test_final/README.md dans le dépôt")

    logger.info("Wrote %s (%s rows)", parquet_path, len(df))
    return parquet_path, stats