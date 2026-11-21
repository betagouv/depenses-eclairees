from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from docia.file_processing.processor.classify.clustering.cohort import CohortStats
from docia.file_processing.processor.classify.clustering.reduce import ReductionResult


def samples_per_cluster(cluster_size: int, default: int) -> int:
    if cluster_size <= 0:
        return 0
    return min(default, max(5, cluster_size // 10))


def write_review_sample(df: pd.DataFrame, labels: np.ndarray, out_path: Path, *, samples_per_cluster_cap: int, seed: int) -> None:
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    work = df.copy()
    work["cluster"] = labels.astype(int)
    for cluster_id, grp in work.groupby("cluster", observed=True):
        n_take = samples_per_cluster(len(grp), samples_per_cluster_cap)
        if n_take <= 0:
            continue
        take = grp if len(grp) <= n_take else grp.sample(n=n_take, random_state=int(rng.integers(0, 2**31 - 1)))
        for _, row in take.iterrows():
            text = str(row.get("text_2000") or "")
            rows.append(
                {
                    "id": str(row["id"]),
                    "hash": row.get("hash"),
                    "num_ej": row.get("num_ej"),
                    "split": row.get("split"),
                    "review_cluster": int(cluster_id),
                    "filename_normalized": row.get("filename_normalized"),
                    "text_preview": text[:500],
                }
            )
    pd.DataFrame(rows).to_csv(out_path, index=False)


def write_exports(
    out_dir: Path,
    classification: str,
    feature_mode: str,
    stats: CohortStats,
    k_rows: list[dict],
    best_k: int,
    best_silhouette: float,
    k_selection_criterion: str,
    labels: np.ndarray,
    df: pd.DataFrame,
    reduction: ReductionResult,
    term_rows: list[dict],
    *,
    seed: int,
    samples_per_cluster_cap: int,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_lines = [
        f"# Cohort {classification}",
        "",
        f"- feature_mode: {feature_mode}",
        "",
        f"- rows_matching_classification: {stats.rows_matching}",
        f"- rows_after_nonempty_text: {stats.rows_nonempty_text}",
        f"- rows_after_hash_dedup: {stats.rows_dedup}",
        f"- dropped_duplicate_hashes: {stats.dropped_duplicates}",
        "",
        "## Splits (deduped)",
        "",
    ]
    for k, v in sorted(stats.split_counts.items()):
        summary_lines.append(f"- {k}: {v}")
    summary_lines.extend(
        [
            "",
            f"## SVD",
            "",
            f"- n_components: {reduction.n_components}",
            f"- explained_variance_sum: {sum(reduction.explained_variance_ratio):.4f}",
            "",
        ]
    )
    (out_dir / "00_cohort_summary.md").write_text("\n".join(summary_lines), encoding="utf-8")

    pd.DataFrame(k_rows).to_csv(out_dir / "01_k_metrics.csv", index=False)
    (out_dir / "02_best_k.json").write_text(
        json.dumps(
            {
                "classification": classification,
                "best_k": best_k,
                "criterion": k_selection_criterion,
                "silhouette": best_silhouette,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    assign = df[["id", "hash", "num_ej", "split", "filename_normalized"]].copy()
    assign["cluster"] = labels.astype(int)
    reduced = np.asarray(reduction.reduced)
    for i in range(min(5, reduced.shape[1])):
        assign[f"svd_{i}"] = reduced[:, i]
    assign.to_parquet(out_dir / "03_assignments.parquet", index=False)

    pd.DataFrame(term_rows).to_csv(out_dir / "04_cluster_top_terms.csv", index=False)
    write_review_sample(df, labels, out_dir / "05_review_sample.csv", samples_per_cluster_cap=samples_per_cluster_cap, seed=seed)

    sizes = pd.Series(labels).value_counts().sort_index()
    pd.DataFrame({"cluster": sizes.index.astype(int), "n": sizes.values}).to_csv(
        out_dir / "06_cluster_sizes.csv",
        index=False,
    )