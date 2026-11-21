import json
from pathlib import Path

import joblib

from docia.file_processing.processor.classify.constants import (
    CLASSIFIER_ARTIFACT_NAME,
    THRESHOLD_ARTIFACT_NAME,
)


def save_pipeline(output_dir: Path, model) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / CLASSIFIER_ARTIFACT_NAME
    joblib.dump(model, path)
    return path


def load_pipeline(output_dir: Path):
    return joblib.load(output_dir / CLASSIFIER_ARTIFACT_NAME)


def save_thresholds(output_dir: Path, tau: float, margin: float, *, extra: dict | None = None) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / THRESHOLD_ARTIFACT_NAME
    payload = {"tau": tau, "margin": margin}
    if extra:
        payload.update(extra)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path