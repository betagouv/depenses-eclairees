from __future__ import annotations

from sklearn.model_selection import train_test_split

import numpy as np
import pandas as pd

from docia.file_processing.processor.classify.constants import (
    DEFAULT_SEED,
    SPLIT_FRACS,
    TARGET_CLASSES,
)
from docia.file_processing.processor.classify.ej_groups import ej_stratify_label
from docia.file_processing.processor.classify.label_policy import needs_annexe_financiere_merge, training_label


def _assign_ej_splits(df_targets: pd.DataFrame, seed: int) -> dict[str, str]:
    ej_groups: dict[str, list[str]] = {}
    for _, row in df_targets.iterrows():
        ej = row.get("num_ej")
        if ej is None or (isinstance(ej, float) and np.isnan(ej)):
            continue
        ej_groups.setdefault(str(ej), []).append(str(row.get("label_train") or row["classification"]))

    ejs = list(ej_groups.keys())
    if not ejs:
        return {}

    rng = np.random.default_rng(seed)
    order = ejs.copy()
    rng.shuffle(order)

    n = len(order)
    if n < 8:
        n_train = max(1, int(round(n * SPLIT_FRACS["train"])))
        n_val = max(0, int(round(n * SPLIT_FRACS["val"])))
        n_calib = max(0, int(round(n * SPLIT_FRACS["calib"])))
        n_test = max(0, n - n_train - n_val - n_calib)
        if n_test == 0 and n > n_train:
            n_test = 1
            n_calib = max(0, n_calib - 1)
        train_ej = order[:n_train]
        val_ej = order[n_train : n_train + n_val]
        calib_ej = order[n_train + n_val : n_train + n_val + n_calib]
        test_ej = order[n_train + n_val + n_calib : n_train + n_val + n_calib + n_test]
    else:
        labels = [ej_stratify_label(ej_groups[ej]) for ej in ejs]
        from collections import Counter

        label_counts = Counter(labels)
        can_stratify = len(ejs) > 2 and min(label_counts.values()) >= 2

        train_ej, rest_ej, _, rest_labels = train_test_split(
            ejs,
            labels,
            test_size=SPLIT_FRACS["val"] + SPLIT_FRACS["calib"] + SPLIT_FRACS["test"],
            random_state=seed,
            stratify=labels if can_stratify else None,
        )
        relative_val = SPLIT_FRACS["val"] / (SPLIT_FRACS["val"] + SPLIT_FRACS["calib"] + SPLIT_FRACS["test"])
        rest_counts = Counter(rest_labels)
        can_stratify_rest = len(rest_ej) > 1 and min(rest_counts.values()) >= 2
        val_ej, rest2_ej, _, _ = train_test_split(
            rest_ej,
            rest_labels,
            test_size=1 - relative_val,
            random_state=seed,
            stratify=rest_labels if can_stratify_rest else None,
        )
        calib_frac = SPLIT_FRACS["calib"] / (SPLIT_FRACS["calib"] + SPLIT_FRACS["test"])
        calib_ej, test_ej = train_test_split(
            rest2_ej,
            test_size=1 - calib_frac,
            random_state=seed,
        )

    mapping: dict[str, str] = {}
    for ej in train_ej:
        mapping[ej] = "train"
    for ej in val_ej:
        mapping[ej] = "val"
    for ej in calib_ej:
        mapping[ej] = "calib"
    for ej in test_ej:
        mapping[ej] = "test"
    return mapping


def assign_splits(df: pd.DataFrame, seed: int = DEFAULT_SEED, *, coarse_hierarchy: bool = False) -> tuple[pd.DataFrame, bool]:
    out = df.copy()
    if coarse_hierarchy:
        if "label_train" not in out.columns:
            out["label_train"] = None
        missing = out["label_train"].isna() & out["classification"].notna()
        if missing.any():
            out.loc[missing, "label_train"] = out.loc[missing, "classification"].map(
                lambda c: training_label(c, False, coarse_hierarchy=True)
            )
        targets = out[out["label_train"].notna()].copy()
        merge_financial = False
    else:
        targets = out[out["classification"].isin(TARGET_CLASSES)].copy()
    ej_map = _assign_ej_splits(targets, seed)

    rng = np.random.default_rng(seed)

    def _split_for_row(row: pd.Series) -> str | None:
        if row["label_train"] is None or (isinstance(row["label_train"], float) and np.isnan(row["label_train"])):
            ej = row.get("num_ej")
            if ej is not None and not (isinstance(ej, float) and np.isnan(ej)):
                mapped = ej_map.get(str(ej))
                if mapped in ("calib", "test"):
                    return mapped
            return "calib" if rng.random() < 0.5 else "test"
        ej = row.get("num_ej")
        if ej is None or (isinstance(ej, float) and np.isnan(ej)):
            return None
        return ej_map.get(str(ej))

    out["split"] = out.apply(_split_for_row, axis=1)

    if not coarse_hierarchy:
        train_counts = out[out["split"] == "train"]["classification"].value_counts().to_dict()
        merge_financial = needs_annexe_financiere_merge({str(k): int(v) for k, v in train_counts.items()})
        if merge_financial:
            out["label_train"] = out["classification"].map(lambda c: training_label(c, True))
        else:
            out["label_train"] = out["classification"].where(out["classification"].isin(TARGET_CLASSES))

    return out, merge_financial


def split_leakage_check(df: pd.DataFrame) -> list[str]:
    issues: list[str] = []
    grouped: dict[str, set[str]] = {}
    for _, row in df.iterrows():
        ej = row.get("num_ej")
        if ej is None or (isinstance(ej, float) and np.isnan(ej)):
            continue
        split = row.get("split")
        if split is None:
            continue
        grouped.setdefault(str(ej), set()).add(str(split))
    for ej, splits in grouped.items():
        if len(splits) > 1:
            issues.append(f"EJ {ej} spans splits: {sorted(splits)}")
    return issues


def train_class_counts(df: pd.DataFrame) -> dict[str, int]:
    train = df[df["split"] == "train"]
    return {str(k): int(v) for k, v in train["label_train"].dropna().value_counts().items()}