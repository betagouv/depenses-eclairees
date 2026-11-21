from pathlib import Path

from docia.views import CLASSIFICATIONS_AFFICHEES

TARGET_CLASSES: frozenset[str] = frozenset(
    {
        "acte_engagement",
        "ccap",
        "sous_traitance",
        "avenant",
        "devis",
        "rib",
        "bordereau_prix",
        "detail_quantitatif_estimatif",
    }
)

# Fine labels (V1) encore utilisés pour audits cœur quatre
CORE_FOUR_MISSED_TRACKING: frozenset[str] = frozenset(
    {
        "acte_engagement",
        "ccap",
        "sous_traitance",
        "rib",
    }
)

CLASSES_RATIO_MEDIAN: frozenset[str] = CLASSIFICATIONS_AFFICHEES | {"devis"}

TARGET_RATIO_MEDIAN: frozenset[str] = CLASSES_RATIO_MEDIAN & TARGET_CLASSES

CLASSES_TEXT_DEDUP: frozenset[str] = frozenset(
    {
        "bordereau_prix",
        "detail_quantitatif_estimatif",
        "cctp",
    }
)

ANALYZED_SCOPE_REPORTING: frozenset[str] = CLASSES_RATIO_MEDIAN | {"cctp"}

CONFUSION_PAIRS: tuple[tuple[str, str], ...] = (
    ("devis", "bordereau_prix"),
    ("bordereau_prix", "detail_quantitatif_estimatif"),
    ("acte_engagement", "ccp_vae"),
    ("acte_engagement", "ccp_simple"),
    ("ccap", "cctp"),
    ("avenant", "acte_engagement"),
)

TEXT_HEAD_CHARS = 2000
DEFAULT_SEED = 42
AUDIT_SAMPLE_PER_CLASS = 30
KEYWORD_MISMATCH_WARN_RATIO = 0.15
MIN_TRAIN_PER_CLASS = 10
REJECTION_BUDGET_DEFAULT = 8000
REJECTION_BUDGET_FRAC_OF_TARGETS = 0.20
MAX_TFIDF_FEATURES = 50_000

ANNEXE_FINANCIERE_LABEL = "annexe_financiere"
FINANCIAL_TARGETS: frozenset[str] = frozenset({"bordereau_prix", "detail_quantitatif_estimatif"})

SPLIT_NAMES: tuple[str, ...] = ("train", "val", "calib", "test")
SPLIT_FRACS: dict[str, float] = {"train": 0.60, "val": 0.10, "calib": 0.15, "test": 0.15}

DEFAULT_OUTPUT_DIR = Path("data/classify_v2")

CLASSIFIER_ARTIFACT_NAME = "classify_v2_pipeline.joblib"
THRESHOLD_ARTIFACT_NAME = "classify_v2_thresholds.json"