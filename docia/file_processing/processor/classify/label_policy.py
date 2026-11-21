from docia.file_processing.processor.classify.constants import (
    ANNEXE_FINANCIERE_LABEL,
    FINANCIAL_TARGETS,
    MIN_TRAIN_PER_CLASS,
)
from docia.file_processing.processor.classify.label_hierarchy import map_llm_to_coarse


def training_label(
    classification: str | None,
    merge_financial: bool,
    *,
    coarse_hierarchy: bool = False,
) -> str | None:
    if classification is None:
        return None
    if coarse_hierarchy:
        return map_llm_to_coarse(classification)
    if merge_financial and classification in FINANCIAL_TARGETS:
        return ANNEXE_FINANCIERE_LABEL
    return classification


def needs_annexe_financiere_merge(train_counts: dict[str, int]) -> bool:
    for label in FINANCIAL_TARGETS:
        if train_counts.get(label, 0) < MIN_TRAIN_PER_CLASS:
            return True
    return False