from docia.file_processing.processor.classify.constants import MIN_TRAIN_PER_CLASS
from docia.file_processing.processor.classify.label_hierarchy import PRIORITY_COARSE_LABELS


def assert_min_train_counts(
    train_counts: dict[str, int],
    merge_applied: bool,
    *,
    coarse_hierarchy: bool = False,
) -> list[str]:
    warnings = []
    for label, n in train_counts.items():
        if n < MIN_TRAIN_PER_CLASS:
            if coarse_hierarchy:
                prefix = "PRIORITY coarse" if label in PRIORITY_COARSE_LABELS else "Coarse"
                warnings.append(f"{prefix} train count for {label} is {n} < {MIN_TRAIN_PER_CLASS}")
            elif merge_applied and label in ("bordereau_prix", "detail_quantitatif_estimatif"):
                continue
            else:
                warnings.append(f"Train count for {label} is {n} < {MIN_TRAIN_PER_CLASS}")
    return warnings