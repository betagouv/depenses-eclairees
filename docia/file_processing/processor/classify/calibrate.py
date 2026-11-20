from __future__ import annotations

import logging

from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import brier_score_loss, log_loss

import numpy as np
import pandas as pd

from docia.file_processing.processor.classify.constants import MIN_TRAIN_PER_CLASS

logger = logging.getLogger(__name__)


def _xy(df: pd.DataFrame):
    sub = df[df["label_train"].notna()]
    x = sub[["text_2000", "filename_normalized", "nb_mot"]].copy()
    x["nb_mot"] = x["nb_mot"].fillna(0)
    y = sub["label_train"].astype(str)
    groups = sub["num_ej"].astype(str).fillna("unknown")
    return x, y, groups


def calibrate_model(pipe, calib_df: pd.DataFrame, use_group_cv: bool) -> tuple[object, str, dict]:
    x, y, groups = _xy(calib_df)
    classes = pipe.named_steps["clf"].classes_
    logger.info("Calibrating on n=%s labeled rows (%s classes)", len(y), len(classes))

    raw_proba = pipe.predict_proba(x)
    pre_loss = log_loss(y, raw_proba, labels=classes)
    logger.info("Pre-calibration log_loss=%.4f", pre_loss)

    if use_group_cv:
        logger.info("Fitting CalibratedClassifierCV(sigmoid, cv=3)...")
        calibrator = CalibratedClassifierCV(pipe, method="sigmoid", cv=3)
        calibrator.fit(x, y)
        mode = "sigmoid_cv3"
    else:
        logger.info("Fitting CalibratedClassifierCV(sigmoid, prefit)...")
        calibrator = CalibratedClassifierCV(FrozenEstimator(pipe), method="sigmoid")
        calibrator.fit(x, y)
        mode = "sigmoid_prefit"

    cal_proba = calibrator.predict_proba(x)
    post_loss = log_loss(y, cal_proba, labels=classes)
    brier = float(np.mean([brier_score_loss((y == c).astype(int), cal_proba[:, i]) for i, c in enumerate(classes)]))

    metrics = {
        "log_loss_before": float(pre_loss),
        "log_loss_after": float(post_loss),
        "brier_multiclass_mean": brier,
    }
    return calibrator, mode, metrics


def needs_group_cv_calibration(train_counts: dict[str, int]) -> bool:
    return any(n < MIN_TRAIN_PER_CLASS for n in train_counts.values())