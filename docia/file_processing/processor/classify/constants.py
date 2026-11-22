from pathlib import Path

# Partagé avec l'UI Django (éviter constants → views → classifier → Django au import)
# Périmètre étape pipeline CONTENT_ANALYSIS (source unique).
CONTENT_ANALYSIS_CLASSIFICATIONS: frozenset[str] = frozenset(
    {
        "devis",
        "facture",
        "fiche_navette",
        "acte_engagement",
        "ccp_vae",
        "bon_de_commande",
        "avenant",
        "conv_financement",
        "sous_traitance",
        "rib",
        "att_sirene",
        "kbis",
        "ccap",
        "ccp_simple",
    }
)

# Démo P1 après logreg : mistral OCR doc entier (AE, sous-traitance).
PIPELINE1_MISTRAL_OCR_LABELS: frozenset[str] = frozenset({"acte_engagement", "sous_traitance"})

# Autres classes à analyser : Tesseract / PyMuPDF4LLM sur tout le PDF.
PIPELINE1_TESSERACT_FULL_OCR_LABELS: frozenset[str] = (
    CONTENT_ANALYSIS_CLASSIFICATIONS - PIPELINE1_MISTRAL_OCR_LABELS
)

CLASSIFICATIONS_AFFICHEES: frozenset[str] = frozenset(
    {
        "acte_engagement",
        "ccp_vae",
        "ccap",
        "ccp_simple",
        "rib",
        "fiche_navette",
        "sous_traitance",
        "avenant",
    }
)

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

# Plafond sur le rejet logreg : fraction max de docs renvoyés au LLM (choix seuils calib).
DEFAULT_MAX_LLM_FALLBACK_RATE = 0.40

# Plancher F1 routage minimal par classe (toutes classes au calib, rejet compte dans le F1).
DEFAULT_MIN_ROUTING_F1 = 0.25