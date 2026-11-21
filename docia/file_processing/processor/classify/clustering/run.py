from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from docia.file_processing.processor.classify.clustering.cluster import grid_kmeans
from docia.file_processing.processor.classify.clustering.cohort import load_cohort
from docia.file_processing.processor.classify.clustering.export import write_exports
from docia.file_processing.processor.classify.clustering.reduce import reduce_svd
from docia.file_processing.processor.classify.clustering.terms import cluster_top_terms
from docia.file_processing.processor.classify.clustering.vectorize import FeatureMode, fit_transform_features
from docia.file_processing.processor.classify.constants import (
    AUDIT_SAMPLE_PER_CLASS,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SEED,
)

logger = logging.getLogger(__name__)

CORE_FIVE_LLM: tuple[str, ...] = (
    "acte_engagement",
    "ccap",
    "sous_traitance",
    "avenant",
    "rib",
)


def run_class_exploration(
    classification: str,
    *,
    parquet_path: Path | None = None,
    output_root: Path | None = None,
    seed: int = DEFAULT_SEED,
    k_min: int = 2,
    k_max: int = 8,
    svd_components: int = 100,
    samples_per_cluster: int = AUDIT_SAMPLE_PER_CLASS,
    feature_mode: FeatureMode = "text_only",
) -> Path:
    parquet_path = (parquet_path or (DEFAULT_OUTPUT_DIR / "documents_raw.parquet")).resolve()
    output_root = (output_root or (DEFAULT_OUTPUT_DIR / "clustering")).resolve()
    out_dir = output_root / classification / feature_mode

    logger.info("Cluster exploration: %s mode=%s parquet=%s", classification, feature_mode, parquet_path)
    df, stats = load_cohort(parquet_path, classification)
    if len(df) < 3:
        raise ValueError(f"Too few documents for {classification}: {len(df)}")

    matrix, preprocessor = fit_transform_features(df, mode=feature_mode)
    reduction = reduce_svd(matrix, svd_components, seed)
    reduced = np.asarray(reduction.reduced)

    k_rows, best_k, labels, k_criterion = grid_kmeans(reduced, k_min, k_max, seed)
    best_sil = next((r["silhouette"] for r in k_rows if r["k"] == best_k), float("nan"))
    term_rows = cluster_top_terms(matrix, labels, preprocessor)

    write_exports(
        out_dir,
        classification,
        feature_mode,
        stats,
        k_rows,
        best_k,
        float(best_sil) if best_sil is not None else float("nan"),
        k_criterion,
        labels,
        df,
        reduction,
        term_rows,
        seed=seed,
        samples_per_cluster_cap=samples_per_cluster,
    )
    logger.info("Wrote clustering artifacts to %s (best_k=%s)", out_dir, best_k)
    return out_dir