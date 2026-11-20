from __future__ import annotations

import json
import logging
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from django.db.models import Count, Min

import pyarrow as pa
import pyarrow.parquet as pq

import numpy as np
import pandas as pd

from docia.documents.models import Document
from docia.file_processing.processor.classify.constants import (
    CLASSES_RATIO_MEDIAN,
    CLASSES_TEXT_DEDUP,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SEED,
    REJECTION_BUDGET_DEFAULT,
    REJECTION_BUDGET_FRAC_OF_TARGETS,
    TARGET_CLASSES,
    TARGET_RATIO_MEDIAN,
    TEXT_HEAD_CHARS,
)
from docia.file_processing.processor.classify.fill_ratio import compute_ratio_data_extraction
from docia.file_processing.processor.classify.text_prep import normalize_filename, prepare_text_head

logger = logging.getLogger(__name__)

SAMPLE_ROLE_TARGET_RATIO = "target_ratio"
SAMPLE_ROLE_TARGET_TEXT = "target_text"
SAMPLE_ROLE_REJECTION = "rejection"

ROW_BATCH_SIZE = 150
TEXT_FETCH_CHUNK = 100
MEDIAN_SAMPLE_CHUNK = 3000

_LIGHT_FIELDS = ("id", "hash", "filename", "nb_mot", "classification", "structured_data", "analyzed_at")


@dataclass
class DatasetBuildStats:
    exclusions: Counter = field(default_factory=Counter)
    medians_by_class: dict[str, float] = field(default_factory=dict)
    prod_counts: dict[str, int] = field(default_factory=dict)
    dedup_dropped: int = 0
    rejection_budget: int = 0
    rejection_draw: dict[str, int] = field(default_factory=dict)
    row_count: int = 0


def _row_score(row: dict[str, Any]) -> tuple:
    return (
        bool(row.get("analyzed_at")),
        float(row.get("ratio_extracted") or 0),
        len(row.get("text_2000") or ""),
    )


class _HashDedupStore:
    """Un seul enregistrement par hash en mémoire (texte tronqué)."""

    def __init__(self) -> None:
        self._by_hash: dict[str, dict[str, Any]] = {}
        self.dropped = 0

    def upsert(self, row: dict[str, Any]) -> None:
        h = row["hash"]
        prev = self._by_hash.get(h)
        if prev is None:
            self._by_hash[h] = row
            return
        self.dropped += 1
        if _row_score(row) > _row_score(prev):
            self._by_hash[h] = row

    def rows(self) -> list[dict[str, Any]]:
        return list(self._by_hash.values())

    def __len__(self) -> int:
        return len(self._by_hash)

    def hashes(self) -> set[str]:
        return set(self._by_hash.keys())


def _row_from_light(
    item: dict[str, Any],
    text: str | None,
    num_ej: str | None,
    sample_role: str | None,
) -> dict[str, Any]:
    ratio = compute_ratio_data_extraction(item.get("structured_data"))
    filename = item.get("filename") or ""
    cls = item["classification"]
    return {
        "id": str(item["id"]),
        "hash": item["hash"],
        "filename": filename,
        "nb_mot": item.get("nb_mot"),
        "text_2000": prepare_text_head(text or "", TEXT_HEAD_CHARS),
        "filename_normalized": normalize_filename(filename),
        "classification": cls,
        "label_train": cls if cls in TARGET_CLASSES else None,
        "ratio_extracted": ratio,
        "analyzed_at": item.get("analyzed_at"),
        "sample_role": sample_role,
        "num_ej": num_ej,
        "split": None,
        "exclusion_reason": None,
    }


def _chunked(ids: list[Any], size: int) -> Iterable[list[Any]]:
    for i in range(0, len(ids), size):
        yield ids[i : i + size]


def _median_by_class_floats(buckets: dict[str, list[float]]) -> dict[str, float]:
    return {cls: float(np.median(vals)) if vals else 0.0 for cls, vals in buckets.items()}


def _passes_ratio_median_light(cls: str, ratio: float, analyzed_at: Any, medians: dict[str, float]) -> bool:
    if cls not in medians or not analyzed_at:
        return False
    return ratio >= medians[cls]


def fetch_prod_counts() -> dict[str, int]:
    rows = (
        Document.objects.exclude(classification__isnull=True)
        .exclude(classification="")
        .values("classification")
        .annotate(n=Count("id"))
    )
    return {str(r["classification"]): int(r["n"]) for r in rows}


def _compute_medians_from_db() -> dict[str, float]:
    """Spille les ratios sur disque pour éviter des listes géantes en RAM."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="classify_v2_ratios_"))
    handles: dict[str, Any] = {}
    try:
        qs = (
            Document.objects.filter(classification__in=CLASSES_RATIO_MEDIAN)
            .exclude(analyzed_at__isnull=True)
            .values("classification", "structured_data")
            .iterator(chunk_size=MEDIAN_SAMPLE_CHUNK)
        )
        n = 0
        for item in qs:
            cls = item["classification"]
            if cls not in handles:
                handles[cls] = open(tmp_dir / f"{cls}.txt", "w", encoding="utf-8")
            ratio = compute_ratio_data_extraction(item["structured_data"])
            handles[cls].write(f"{ratio}\n")
            n += 1
            if n % 10_000 == 0:
                logger.info("Median pass: %s docs", n)
        for fh in handles.values():
            fh.close()

        medians: dict[str, float] = {}
        for cls, fh in handles.items():
            path = tmp_dir / f"{cls}.txt"
            ratios = np.loadtxt(path, dtype=np.float64) if path.stat().st_size else np.array([], dtype=np.float64)
            medians[cls] = float(np.median(ratios)) if len(ratios) else 0.0
        return medians
    finally:
        for fh in handles.values():
            if not fh.closed:
                fh.close()
        for p in tmp_dir.glob("*.txt"):
            p.unlink(missing_ok=True)
        tmp_dir.rmdir()


def _ej_map_for_ids(doc_ids: list[str]) -> dict[str, str]:
    through = Document.engagements.through
    out: dict[str, str] = {}
    for chunk in _chunked(doc_ids, 500):
        for link in (
            through.objects.filter(document_id__in=chunk)
            .values("document_id")
            .annotate(num_ej=Min("engagement__num_ej"))
        ):
            if link["num_ej"]:
                out[str(link["document_id"])] = link["num_ej"]
    return out


def _load_texts_map(ids: list[Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for chunk in _chunked(list(ids), TEXT_FETCH_CHUNK):
        for row in Document.objects.filter(id__in=chunk).values("id", "text"):
            out[str(row["id"])] = row["text"] or ""
    return out


def _flush_batch_to_store(batch_items: list[dict], texts: dict[str, str], role: str, store: _HashDedupStore) -> None:
    if not batch_items:
        return
    ej_map = _ej_map_for_ids([str(i["id"]) for i in batch_items])
    for item in batch_items:
        row = _row_from_light(item, texts.get(str(item["id"]), ""), ej_map.get(str(item["id"])), role)
        if not (row["text_2000"] or "").strip():
            continue
        store.upsert(row)


def _stream_ratio_targets(medians: dict[str, float], store: _HashDedupStore, stats: DatasetBuildStats) -> None:
    batch: list[dict] = []
    qs = (
        Document.objects.filter(classification__in=TARGET_RATIO_MEDIAN)
        .exclude(analyzed_at__isnull=True)
        .exclude(text__isnull=True)
        .exclude(text="")
        .values(*_LIGHT_FIELDS)
        .iterator(chunk_size=MEDIAN_SAMPLE_CHUNK)
    )
    for item in qs:
        ratio = compute_ratio_data_extraction(item["structured_data"])
        if not _passes_ratio_median_light(item["classification"], ratio, item.get("analyzed_at"), medians):
            stats.exclusions["below_median"] += 1
            continue
        batch.append(item)
        if len(batch) >= ROW_BATCH_SIZE:
            texts = _load_texts_map([i["id"] for i in batch])
            _flush_batch_to_store(batch, texts, SAMPLE_ROLE_TARGET_RATIO, store)
            batch.clear()
    if batch:
        texts = _load_texts_map([i["id"] for i in batch])
        _flush_batch_to_store(batch, texts, SAMPLE_ROLE_TARGET_RATIO, store)
    logger.info("Ratio-median targets in store: %s", len(store))


def _stream_text_dedup_classes(store: _HashDedupStore) -> None:
    text_classes = [c for c in CLASSES_TEXT_DEDUP if c in TARGET_CLASSES]
    for cls in text_classes:
        batch: list[dict] = []
        qs = (
            Document.objects.filter(classification=cls)
            .exclude(text__isnull=True)
            .exclude(text="")
            .values(*_LIGHT_FIELDS)
            .iterator(chunk_size=MEDIAN_SAMPLE_CHUNK)
        )
        for item in qs:
            batch.append(item)
            if len(batch) >= ROW_BATCH_SIZE:
                texts = _load_texts_map([i["id"] for i in batch])
                _flush_batch_to_store(batch, texts, SAMPLE_ROLE_TARGET_TEXT, store)
                batch.clear()
        if batch:
            texts = _load_texts_map([i["id"] for i in batch])
            _flush_batch_to_store(batch, texts, SAMPLE_ROLE_TARGET_TEXT, store)


def _stream_cctp(store: _HashDedupStore) -> None:
    batch: list[dict] = []
    qs = (
        Document.objects.filter(classification="cctp")
        .exclude(text__isnull=True)
        .exclude(text="")
        .values(*_LIGHT_FIELDS)
        .iterator(chunk_size=MEDIAN_SAMPLE_CHUNK)
    )
    for item in qs:
        batch.append(item)
        if len(batch) >= ROW_BATCH_SIZE:
            texts = _load_texts_map([i["id"] for i in batch])
            _flush_batch_to_store(batch, texts, SAMPLE_ROLE_REJECTION, store)
            batch.clear()
    if batch:
        texts = _load_texts_map([i["id"] for i in batch])
        _flush_batch_to_store(batch, texts, SAMPLE_ROLE_REJECTION, store)


def _sample_rejection_into_store(
    prod_counts: dict[str, int],
    medians: dict[str, float],
    budget: int,
    seed: int,
    store: _HashDedupStore,
) -> dict[str, int]:
    seen_hashes = store.hashes()
    eligible = {c: n for c, n in prod_counts.items() if c not in TARGET_CLASSES and c != "cctp" and n > 0}
    total_prod = sum(eligible.values())
    if total_prod == 0 or budget <= 0:
        return {}

    rng = np.random.default_rng(seed)
    draws: dict[str, int] = {}
    for cls, n_prod in eligible.items():
        share = budget * (n_prod / total_prod)
        draws[cls] = max(1, int(round(share)))

    value_fields = _LIGHT_FIELDS
    for cls, n_draw in draws.items():
        qs = Document.objects.filter(classification=cls).exclude(text__isnull=True).exclude(text="")
        if cls in CLASSES_RATIO_MEDIAN:
            qs = qs.exclude(analyzed_at__isnull=True)
        total = qs.count()
        if total == 0:
            continue
        k = min(n_draw, total)

        if cls in CLASSES_RATIO_MEDIAN and medians.get(cls) is not None:
            reservoir: list[dict] = []
            seen = 0
            for item in qs.values(*value_fields).iterator(chunk_size=500):
                ratio = compute_ratio_data_extraction(item["structured_data"])
                if not _passes_ratio_median_light(cls, ratio, item.get("analyzed_at"), medians):
                    continue
                seen += 1
                if len(reservoir) < k:
                    reservoir.append(item)
                else:
                    j = int(rng.integers(0, seen))
                    if j < k:
                        reservoir[j] = item
            picks = reservoir
        else:
            offset = int(rng.integers(0, max(1, total - k + 1)))
            picks = list(qs.order_by("id").values(*value_fields)[offset : offset + k])

        for chunk_start in range(0, len(picks), ROW_BATCH_SIZE):
            chunk = picks[chunk_start : chunk_start + ROW_BATCH_SIZE]
            texts = _load_texts_map([p["id"] for p in chunk])
            for item in chunk:
                if item["hash"] in seen_hashes:
                    continue
                row = _row_from_light(item, texts.get(str(item["id"]), ""), None, SAMPLE_ROLE_REJECTION)
                row["label_train"] = None
                if not (row["text_2000"] or "").strip():
                    continue
                store.upsert(row)
                seen_hashes.add(item["hash"])
    return draws


def build_dataset_frame(
    seed: int = DEFAULT_SEED,
    rejection_budget: int | None = None,
) -> tuple[pd.DataFrame, DatasetBuildStats]:
    stats = DatasetBuildStats()
    stats.prod_counts = fetch_prod_counts()
    stats.medians_by_class = _compute_medians_from_db()

    store = _HashDedupStore()
    _stream_ratio_targets(stats.medians_by_class, store, stats)
    _stream_text_dedup_classes(store)
    _stream_cctp(store)
    stats.dedup_dropped = store.dropped

    target_n = sum(1 for r in store.rows() if r.get("label_train"))
    budget = rejection_budget
    if budget is None:
        budget = min(REJECTION_BUDGET_DEFAULT, max(int(target_n * REJECTION_BUDGET_FRAC_OF_TARGETS), 1))
    stats.rejection_budget = budget
    stats.rejection_draw = _sample_rejection_into_store(
        stats.prod_counts, stats.medians_by_class, budget, seed, store
    )
    stats.row_count = len(store)
    rows = store.rows()
    del store
    df = pd.DataFrame(rows)
    del rows
    return df, stats


def write_dataset_parquet(df: pd.DataFrame, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = output_dir / "documents_raw.parquet"
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, parquet_path, compression="zstd")
    return parquet_path


def save_dataset(df: pd.DataFrame, stats: DatasetBuildStats, output_dir: Path) -> Path:
    parquet_path = write_dataset_parquet(df, output_dir)
    manifest = {
        "silver_standard": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "medians_by_class": stats.medians_by_class,
        "prod_counts": stats.prod_counts,
        "exclusions": dict(stats.exclusions),
        "dedup_dropped": stats.dedup_dropped,
        "rejection_budget": stats.rejection_budget,
        "rejection_draw": stats.rejection_draw,
        "row_count": stats.row_count or len(df),
    }
    (output_dir / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return parquet_path


def default_output_dir() -> Path:
    return DEFAULT_OUTPUT_DIR.resolve()


# rétrocompat tests
def dedupe_by_hash(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    store = _HashDedupStore()
    for row in rows:
        store.upsert(row)
    return store.rows(), store.dropped