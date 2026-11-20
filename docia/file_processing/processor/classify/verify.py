from docia.file_processing.processor.classify.constants import MIN_TRAIN_PER_CLASS


def assert_min_train_counts(train_counts: dict[str, int], merge_applied: bool) -> list[str]:
    warnings = []
    for label, n in train_counts.items():
        if n < MIN_TRAIN_PER_CLASS:
            if merge_applied and label in ("bordereau_prix", "detail_quantitatif_estimatif"):
                continue
            warnings.append(f"Train count for {label} is {n} < {MIN_TRAIN_PER_CLASS}")
    return warnings