from __future__ import annotations

import logging
import time
from pathlib import Path

from docia.file_processing.processor.classify.constants import DEFAULT_OUTPUT_DIR, DEFAULT_SEED
from docia.file_processing.processor.classify.corpus_profile.export import write_exports, write_summary
from docia.file_processing.processor.classify.corpus_profile.vocab_curve import (
    Scope,
    load_cohort,
    resolve_n_grid,
    vocab_curve_by_class,
    vocab_curve_global,
    labels_for_by_class,
)

logger = logging.getLogger(__name__)


def run_vocab_profile(
    *,
    parquet_path: Path | None = None,
    output_dir: Path | None = None,
    scope: Scope = "train",
    seed: int = DEFAULT_SEED,
    n_grid: list[int] | None = None,
    by_class: bool = False,
) -> Path:
    parquet_path = (parquet_path or (DEFAULT_OUTPUT_DIR / "documents_raw.parquet")).resolve()
    output_dir = (output_dir or (DEFAULT_OUTPUT_DIR / "corpus_profile")).resolve()
    t0 = time.perf_counter()

    df = load_cohort(parquet_path, scope=scope)
    if df.empty:
        raise ValueError(f"Aucune ligne pour scope={scope} dans {parquet_path}")

    grid = resolve_n_grid(n_grid, len(df))
    logger.info("Vocab curve: scope=%s n=%s grid=%s", scope, len(df), grid)

    global_rows = vocab_curve_global(df, grid, seed=seed)
    by_class_rows = None
    if by_class:
        class_labels = labels_for_by_class(df)
        by_class_rows = vocab_curve_by_class(df, grid, class_labels, seed=seed)
        logger.info("By-class curves for %s labels", len(class_labels))

    duration = time.perf_counter() - t0
    manifest = {
        "parquet_path": str(parquet_path),
        "scope": scope,
        "seed": seed,
        "n_grid": grid,
        "cohort_n": len(df),
        "by_class": by_class,
        "duration_seconds": round(duration, 2),
    }
    write_exports(output_dir, global_rows=global_rows, by_class_rows=by_class_rows, manifest=manifest)
    write_summary(output_dir, global_rows, scope=scope, cohort_n=len(df), duration_s=duration)
    logger.info("Wrote corpus profile to %s", output_dir)
    return output_dir