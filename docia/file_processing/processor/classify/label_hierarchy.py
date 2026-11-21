"""
Taxonomie coarse pour l'entraînement classify (évolue avec le métier).

Ce module est volontairement **découplé** du pipeline sklearn : on y maintient
le mapping libellé LLM (fin) → classe coarse trainable, sans toucher au modèle
tant que la taxonomie bouge.

Pour faire évoluer :
1. Ajuster les blocs ``_LLM_*`` (ou une ligne dans ``_LLM_EXPLICIT``).
2. Bumper ``HIERARCHY_REVISION`` (date + note courte en commentaire).
3. Relancer un audit ``list_unmapped_llm_labels(prod_counts)`` si besoin.
4. Brancher ``map_llm_to_coarse`` dans ``label_corrections`` / prochain train.

Les libellés absent du mapping → ``None`` (hors train / pool rejet).
"""

from __future__ import annotations

# Revision lisible dans les logs / rapports (pas un semver produit)
HIERARCHY_REVISION = "2026-11-21e-split_ccp_ratio"

# --- Coarse labels (ordre = doc / stabilité affichage) ---

COARSE_ACTE_ENGAGEMENT = "acte_engagement"
COARSE_ANNEXE = "annexe"
COARSE_CATALOGUE_PRIX = "catalogue_prix"
# Anciens noms (revues / rapports) → même coarse
COARSE_ANNEXE_FINANCIERE = COARSE_CATALOGUE_PRIX
COARSE_OFFRE_COMMERCIALE = COARSE_CATALOGUE_PRIX
COARSE_DEVIS = "devis"
COARSE_CCAP = "ccap"
COARSE_CCTP = "cctp"
COARSE_CCP_SIMPLE = "ccp_simple"
COARSE_CCP_VAE = "ccp_vae"
COARSE_AVENANT = "avenant"
COARSE_SOUS_TRAITANCE = "sous_traitance"
COARSE_RIB = "rib"
COARSE_CONTRATS_MIXTE = "contrats_mixte"
COARSE_MESSAGERIE = "messagerie"
COARSE_FICHE_NAVETTE = "fiche_navette"
COARSE_OUTIL_GESTION = "outil_gestion"
COARSE_EXECUTION_COMMANDE = "execution_commande"
COARSE_CERTIFICATS_ADMINISTRATIFS = "certificats_administratifs"
COARSE_DOSSIER_CANDIDATURE = "dossier_candidature"
COARSE_CONSULTATION_MARCHE = "consultation_marche"

COARSE_LABELS: tuple[str, ...] = (
    COARSE_ACTE_ENGAGEMENT,
    COARSE_ANNEXE,
    COARSE_CATALOGUE_PRIX,
    COARSE_DEVIS,
    COARSE_CCAP,
    COARSE_CCTP,
    COARSE_CCP_SIMPLE,
    COARSE_CCP_VAE,
    COARSE_AVENANT,
    COARSE_SOUS_TRAITANCE,
    COARSE_RIB,
    COARSE_CONTRATS_MIXTE,
    COARSE_MESSAGERIE,
    COARSE_FICHE_NAVETTE,
    COARSE_OUTIL_GESTION,
    COARSE_EXECUTION_COMMANDE,
    COARSE_CERTIFICATS_ADMINISTRATIFS,
    COARSE_DOSSIER_CANDIDATURE,
    COARSE_CONSULTATION_MARCHE,
)

TRAINABLE_COARSE: frozenset[str] = frozenset(COARSE_LABELS)

# KPI entraînement / seuils : ne pas rater le cœur métier (9 coarse, CCP scindé)
PRIORITY_COARSE_LABELS: frozenset[str] = frozenset(
    {
        COARSE_ACTE_ENGAGEMENT,
        COARSE_CCAP,
        COARSE_SOUS_TRAITANCE,
        COARSE_RIB,
        COARSE_CCP_SIMPLE,
        COARSE_CCP_VAE,
        COARSE_AVENANT,
        COARSE_DEVIS,
    }
)

# Poids relatif des classes prioritaires vs ``class_weight=balanced`` (mode coarse)
PRIORITY_CLASS_WEIGHT_FACTOR = 2.0

# Marginal / hors scope train : pas de mapping coarse (restent « autres » côté rejet)
MARGINAL_LLM_LABELS: frozenset[str] = frozenset({"facture"})

_LLM_ANNEXE: frozenset[str] = frozenset(
    {
        "ccap_annexe",
        "cctp_annexe",
        "ccap_annexe_beneficiaires",
    }
)

_LLM_CATALOGUE_PRIX: frozenset[str] = frozenset(
    {
        "ae_annexe",
        "bordereau_prix",
        "detail_quantitatif_estimatif",
        "decomposition_prix",
    }
)

_LLM_CONTRATS_MIXTE: frozenset[str] = frozenset(
    {
        "ccc",
        "ccag",
        "cga",
        "cge",
        "conv_financement",
        "ej_complexe",
        "gapd",
    }
)

_LLM_MESSAGERIE: frozenset[str] = frozenset(
    {
        "att_echanges",
        "mail",
        "notification",
        "suivi_messages",
    }
)

_LLM_OUTIL_GESTION: frozenset[str] = frozenset(
    {
        "commentaire",
        "fiche_communication",
        "fiche_engagement",
        "fiche_modificative",
        "mise_au_point",
        "rapport_signature",
    }
)

_LLM_EXECUTION_COMMANDE: frozenset[str] = frozenset(
    {
        "abondement",
        "application_revision_prix",
        "bon_de_commande",
        "fiche_achat",
        "ordre_service",
        "rapport_affermissement_tranche",
        "reconduction",
        "service_fait",
    }
)

_LLM_CERTIFICATS_ADMINISTRATIFS: frozenset[str] = frozenset(
    {
        "ca_chgt_autre",
        "ca_chgt_denomination",
        "ca_chgt_ej",
        "ca_chgt_revision_prix",
        "ca_chgt_siret",
        "delegation_pouvoir",
    }
)

_LLM_DOSSIER_CANDIDATURE: frozenset[str] = frozenset(
    {
        "att_etrangers",
        "att_fiscale",
        "att_handicap",
        "att_honneur",
        "att_resp_civile",
        "att_sirene",
        "att_sociale",
        "cv",
        "kbis",
        "lettre_candidature_dc1",
        "lettre_candidature_dc2",
        "memoire_technique",
    }
)

_LLM_CONSULTATION_MARCHE: frozenset[str] = frozenset(
    {
        "avis_boamp",
        "avis_rma",
        "lettre_consultation",
        "pv_cao",
        "question_reponse",
        "rapport_analyse_offre",
        "reglement_consultation",
    }
)

LLM_EXTRA_TEXT_STREAM: frozenset[str] = frozenset().union(
    _LLM_ANNEXE,
    _LLM_CATALOGUE_PRIX,
    _LLM_CONTRATS_MIXTE,
    _LLM_MESSAGERIE,
    _LLM_OUTIL_GESTION,
    _LLM_EXECUTION_COMMANDE,
    _LLM_CERTIFICATS_ADMINISTRATIFS,
    _LLM_DOSSIER_CANDIDATURE,
    _LLM_CONSULTATION_MARCHE,
)

_LLM_IDENTITY_COARSE: frozenset[str] = frozenset(
    {
        COARSE_ACTE_ENGAGEMENT,
        COARSE_DEVIS,
        COARSE_CCAP,
        COARSE_CCTP,
        COARSE_CCP_SIMPLE,
        COARSE_CCP_VAE,
        COARSE_AVENANT,
        COARSE_SOUS_TRAITANCE,
        COARSE_RIB,
        COARSE_FICHE_NAVETTE,
    }
)

_LLM_EXPLICIT: dict[str, str] = {
    "ca_chgt_rib": COARSE_RIB,
    # Erreur de saisie fréquente en revue (CCAP vs CCP)
    "ccap_vae": COARSE_CCP_VAE,
}

# Rétrocompat rapports / alias prod
COARSE_EXECUTION_MARCHE = COARSE_EXECUTION_COMMANDE
COARSE_CONTRATS_DIVERS = COARSE_CONTRATS_MIXTE


def _build_llm_to_coarse() -> dict[str, str]:
    out: dict[str, str] = dict(_LLM_EXPLICIT)
    for lbl in _LLM_IDENTITY_COARSE:
        out[lbl] = lbl
    for lbl in _LLM_ANNEXE:
        out[lbl] = COARSE_ANNEXE
    for lbl in _LLM_CATALOGUE_PRIX:
        out[lbl] = COARSE_CATALOGUE_PRIX
    for lbl in _LLM_CONTRATS_MIXTE:
        out[lbl] = COARSE_CONTRATS_MIXTE
    for lbl in _LLM_MESSAGERIE:
        out[lbl] = COARSE_MESSAGERIE
    for lbl in _LLM_OUTIL_GESTION:
        out[lbl] = COARSE_OUTIL_GESTION
    for lbl in _LLM_EXECUTION_COMMANDE:
        out[lbl] = COARSE_EXECUTION_COMMANDE
    for lbl in _LLM_CERTIFICATS_ADMINISTRATIFS:
        out[lbl] = COARSE_CERTIFICATS_ADMINISTRATIFS
    for lbl in _LLM_DOSSIER_CANDIDATURE:
        out[lbl] = COARSE_DOSSIER_CANDIDATURE
    for lbl in _LLM_CONSULTATION_MARCHE:
        out[lbl] = COARSE_CONSULTATION_MARCHE
    return out


LLM_TO_COARSE: dict[str, str] = _build_llm_to_coarse()


def all_trainable_llm_labels() -> frozenset[str]:
    """Libellés LLM (fin) qui alimentent au moins une classe coarse."""
    return frozenset(LLM_TO_COARSE.keys()) | _LLM_IDENTITY_COARSE


def map_llm_to_coarse(label: str | None) -> str | None:
    """Libellé silver LLM → coarse trainable, ou ``None`` si hors périmètre."""
    if label is None:
        return None
    text = str(label).strip()
    if not text or text.lower() in ("nan", "none"):
        return None
    if text in MARGINAL_LLM_LABELS:
        return None
    if text in (COARSE_CATALOGUE_PRIX, "annexe_financiere", "offre_commerciale"):
        return COARSE_CATALOGUE_PRIX
    if text in TRAINABLE_COARSE:
        return text
    return LLM_TO_COARSE.get(text)


def is_trainable_coarse(label: str | None) -> bool:
    coarse = map_llm_to_coarse(label)
    return coarse is not None and coarse in TRAINABLE_COARSE


def list_unmapped_llm_labels(classification_counts: dict[str, int], *, min_count: int = 50) -> list[tuple[str, int]]:
    """Libellés prod fréquents sans mapping coarse (candidats à ajouter au hiérarchique)."""
    rows: list[tuple[str, int]] = []
    for lbl, n in classification_counts.items():
        if n < min_count:
            continue
        if lbl in MARGINAL_LLM_LABELS:
            continue
        if map_llm_to_coarse(lbl) is not None:
            continue
        rows.append((lbl, int(n)))
    rows.sort(key=lambda x: -x[1])
    return rows


def coarse_memberships() -> dict[str, list[str]]:
    """Vue inverse pour docs / revue humaine."""
    inv: dict[str, list[str]] = {c: [] for c in COARSE_LABELS}
    for llm, coarse in LLM_TO_COARSE.items():
        inv.setdefault(coarse, []).append(llm)
    for c in _LLM_IDENTITY_COARSE:
        if c not in inv.get(c, []):
            inv.setdefault(c, []).append(c)
    for coarse in inv:
        inv[coarse] = sorted(set(inv[coarse]))
    return inv


def extend_mapping(llm_label: str, coarse: str) -> None:
    """
    Extension locale en tests / notebooks uniquement.
    En prod, modifier les constantes du module et bumper HIERARCHY_REVISION.
    """
    if coarse not in TRAINABLE_COARSE:
        raise ValueError(f"Unknown coarse label: {coarse}")
    LLM_TO_COARSE[llm_label] = coarse