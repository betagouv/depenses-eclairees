from __future__ import annotations

from pathlib import Path

from tabulate import tabulate

import pandas as pd

from docia.file_processing.processor.classify.constants import (
    ANALYZED_SCOPE_REPORTING,
    CLASSES_RATIO_MEDIAN,
)


def _reports_dir(output_dir: Path) -> Path:
    d = output_dir / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_dataset_reports(
    df: pd.DataFrame,
    stats,
    output_dir: Path,
    merge_financial: bool,
) -> Path:
    rep = _reports_dir(output_dir)

    summary_lines = [
        "# Dataset summary",
        "",
        f"- Rows: {len(df)}",
        f"- Targets: {(df['label_train'].notna()).sum()}",
        f"- Rejection: {(df['label_train'].isna()).sum()}",
        f"- Dedup dropped: {stats.dedup_dropped}",
        f"- Merge annexe_financiere: {merge_financial}",
        "",
        "Silver labels (`Document.classification`); metrics measure agreement with LLM.",
    ]
    (rep / "01_dataset_summary.md").write_text("\n".join(summary_lines), encoding="utf-8")

    df["classification"].value_counts().to_csv(rep / "01_class_counts.csv")
    pd.DataFrame(
        [{"class": k, "median_ratio": v} for k, v in stats.medians_by_class.items()]
    ).to_csv(rep / "01_median_by_class.csv", index=False)
    pd.DataFrame([{"reason": k, "count": v} for k, v in stats.exclusions.items()]).to_csv(
        rep / "01_sampling_exclusions.csv", index=False
    )

    crosstab = pd.crosstab(
        df["classification"],
        df["analyzed_at"].notna(),
        margins=True,
    )
    crosstab.to_csv(rep / "01_analyzed_crosstab.csv")
    (rep / "01_silver_label_notice.md").write_text(
        "# Silver standard\n\nLabels come from LLM classification in `Document.classification`.\n",
        encoding="utf-8",
    )

    prod = pd.Series(stats.prod_counts)
    draw = pd.Series(stats.rejection_draw)
    freq = pd.DataFrame({"prod": prod, "rejection_sample": draw}).fillna(0)
    freq.to_csv(rep / "01_rejection_freq_vs_prod.csv")

    uses_ratio = df["classification"].isin(CLASSES_RATIO_MEDIAN)
    scope = df["classification"].isin(ANALYZED_SCOPE_REPORTING)
    pd.DataFrame(
        {
            "classification": df["classification"],
            "in_analyzed_scope": scope,
            "uses_ratio_median_rule": uses_ratio,
            "analyzed_at_set": df["analyzed_at"].notna(),
        }
    ).to_csv(rep / "01_analyzed_scope_flags.csv", index=False)

    return rep / "01_dataset_summary.md"


def write_split_reports(df: pd.DataFrame, output_dir: Path, leakage: list[str], train_counts: dict) -> Path:
    rep = _reports_dir(output_dir)
    df.groupby(["split", "classification"], dropna=False).size().reset_index(name="n").to_csv(
        rep / "02_split_counts.csv", index=False
    )
    lines = ["# Split checks", "", "## Train class counts", "", tabulate(train_counts.items(), headers=["class", "n"])]
    if leakage:
        lines.extend(["", "## EJ leakage", ""] + [f"- {x}" for x in leakage])
    else:
        lines.extend(["", "## EJ leakage", "", "None detected."])
    (rep / "02_split_checks.md").write_text("\n".join(lines), encoding="utf-8")
    (rep / "02_ej_leakage_checks.md").write_text(
        "No EJ leakage.\n" if not leakage else "\n".join(leakage),
        encoding="utf-8",
    )
    return rep / "02_split_checks.md"


def write_train_reports(
    output_dir: Path,
    grid_rows: list[dict],
    best_c: float,
    baseline: dict,
) -> None:
    rep = _reports_dir(output_dir)
    pd.DataFrame(grid_rows).to_csv(rep / "03_grid_search.csv", index=False)
    lines = [
        "# Train summary",
        "",
        f"Best C: {best_c}",
        "",
        "## Baseline",
        "",
        tabulate(baseline.items(), headers=["metric", "value"]),
    ]
    (rep / "03_train_summary.md").write_text("\n".join(lines), encoding="utf-8")
    (rep / "03_baseline.md").write_text(
        "\n".join([f"- {k}: {v}" for k, v in baseline.items()]),
        encoding="utf-8",
    )


def write_calibration_report(output_dir: Path, mode: str, metrics: dict) -> None:
    rep = _reports_dir(output_dir)
    (rep / "04_calibration_mode.md").write_text(f"Mode: {mode}\n", encoding="utf-8")
    (rep / "04_calibration_summary.md").write_text(
        "\n".join(f"- {k}: {v}" for k, v in metrics.items()),
        encoding="utf-8",
    )


def write_test_reports(output_dir: Path, metrics: dict, confusion: pd.DataFrame, rejection_rows: list[dict]) -> None:
    import json

    rep = _reports_dir(output_dir)
    (rep / "05_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    confusion.to_csv(rep / "05_confusion_matrix.csv")
    pd.DataFrame(rejection_rows).to_csv(rep / "05_rejection_curve.csv", index=False)
    (rep / "05_test_summary.md").write_text(
        "\n".join(f"- {k}: {v}" for k, v in metrics.items()),
        encoding="utf-8",
    )


def write_run_summary(output_dir: Path, sections: dict[str, str]) -> None:
    lines = ["# Classify V2 run summary", ""]
    for title, body in sections.items():
        lines.extend([f"## {title}", "", body, ""])
    (output_dir / "reports" / "RUN_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")