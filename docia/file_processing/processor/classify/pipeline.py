from __future__ import annotations

import gc
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

from docia.file_processing.processor.classify.annotation_audit import import_audit_results, write_audit_reports
from docia.file_processing.processor.classify.artifacts import save_pipeline
from docia.file_processing.processor.classify.calibrate import calibrate_model, needs_group_cv_calibration
from docia.file_processing.processor.classify.dataset import build_dataset_frame, default_output_dir, save_dataset
from docia.file_processing.processor.classify.evaluate import (
    choose_thresholds,
    evaluate_test,
    rejection_curve_rows,
)
from docia.file_processing.processor.classify.reporting import (
    write_calibration_report,
    write_dataset_reports,
    write_run_summary,
    write_split_reports,
    write_test_reports,
    write_train_reports,
)
from docia.file_processing.processor.classify.splits import assign_splits, split_leakage_check, train_class_counts
from docia.file_processing.processor.classify.train import (
    baseline_filename_rule,
    baseline_majority,
    fit_classifier,
    grid_search_c,
)
from docia.file_processing.processor.classify.verify import assert_min_train_counts


def run_dataset_build(
    output_dir: Path | None = None,
    seed: int = 42,
    rejection_budget: int | None = None,
    strict_audit: bool = False,
    stop_after_audit: bool = False,
) -> Path:
    out = output_dir or default_output_dir()
    logger.info("Building dataset from DB...")
    df, stats = build_dataset_frame(seed=seed, rejection_budget=rejection_budget)
    logger.info("Assigning splits (%s rows)...", len(df))
    df, merge_financial = assign_splits(df, seed=seed)
    logger.info("Writing parquet...")
    save_dataset(df, stats, out)
    gc.collect()
    write_dataset_reports(df, stats, out, merge_financial)
    write_audit_reports(df, out, seed=seed, strict=strict_audit)
    leakage = split_leakage_check(df)
    train_counts = train_class_counts(df)
    write_split_reports(df, out, leakage, train_counts)
    assert_min_train_counts(train_counts, merge_financial)
    if stop_after_audit:
        return out / "documents_raw.parquet"
    return out / "documents_raw.parquet"


def run_training(
    output_dir: Path | None = None,
    seed: int = 42,
    require_human_audit: bool = False,
    audit_csv: Path | None = None,
) -> None:
    out = output_dir or default_output_dir()
    logger.info("Classify v2 training: output_dir=%s seed=%s", out, seed)
    parquet_path = out / "documents_raw.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(f"Missing {parquet_path}; run dataset build first.")

    audit_path = audit_csv or (out / "reports" / "01_annotation_audit_sample.csv")
    if require_human_audit:
        logger.info("Checking human audit: %s", audit_path)
        stats = import_audit_results(audit_path)
        if stats.get("reviewed", 0) == 0:
            raise RuntimeError(f"Human audit required but no reviews in {audit_path}")
        logger.info("Human audit OK: reviewed=%s accuracy=%s", stats.get("reviewed"), stats.get("accuracy"))

    logger.info("Loading %s", parquet_path)
    df = pd.read_parquet(parquet_path)
    train_df = df[df["split"] == "train"]
    val_df = df[df["split"] == "val"]
    calib_df = df[df["split"] == "calib"]
    test_df = df[df["split"] == "test"]
    logger.info(
        "Splits: train=%s val=%s calib=%s test=%s (total=%s)",
        len(train_df),
        len(val_df),
        len(calib_df),
        len(test_df),
        len(df),
    )

    logger.info("Baselines on val...")
    baseline = {
        **baseline_majority(train_df, val_df),
        **baseline_filename_rule(val_df),
    }
    logger.info("Baselines: %s", baseline)

    best_c, grid_rows = grid_search_c(train_df, val_df, seed=seed)
    logger.info("Writing train reports to %s/reports/", out)
    write_train_reports(out, grid_rows, best_c, baseline)

    pipe, _ = fit_classifier(train_df, best_c, seed=seed)
    train_counts = train_class_counts(df)
    use_group = needs_group_cv_calibration(train_counts)
    logger.info("Calibration: mode=%s (group_cv=%s)", "sigmoid_cv3" if use_group else "sigmoid_prefit", use_group)
    model, mode, calib_metrics = calibrate_model(pipe, calib_df, use_group_cv=use_group)
    logger.info("Calibration metrics: %s", calib_metrics)
    write_calibration_report(out, mode, calib_metrics)
    logger.info("Saving pipeline artifacts under %s", out)
    save_pipeline(out, model)

    logger.info("Choosing rejection thresholds on calib split (n=%s)...", len(calib_df))
    tau, margin = choose_thresholds(calib_df, model)
    logger.info("Thresholds: tau=%.3f margin=%.3f", tau, margin)
    logger.info("Evaluating on test split (n=%s)...", len(test_df))
    metrics, cm = evaluate_test(test_df, model, tau, margin)
    logger.info("Test macro_f1=%.4f", metrics.get("macro_f1"))
    logger.info("Writing test reports and rejection curve...")
    rej_rows = rejection_curve_rows(calib_df, model)
    write_test_reports(out, metrics, cm, rej_rows)
    write_run_summary(
        out,
        {
            "Training": f"Best C={best_c}, calibration={mode}",
            "Thresholds": f"tau={tau:.3f}, margin={margin:.3f}",
            "Test macro F1": str(metrics.get("macro_f1")),
        },
    )