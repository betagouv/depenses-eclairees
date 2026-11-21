"""
Registre des tables Grist utilisées pour le golden test set (classification + e2e qualité).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FilterKind = Literal["classif_traitement", "commentaire_traite"]


@dataclass(frozen=True, slots=True)
class GristTestSource:
    table: str
    label_fine: str
    filter_kind: FilterKind
    e2e_module: str


CLASSIF_GT_SOURCE = GristTestSource(
    table="Classif_gt",
    label_fine="",  # issu de classification[0]
    filter_kind="classif_traitement",
    e2e_module="test_quality_classification",
)

GRIST_PRIORITY_QUALITY_SOURCES: tuple[GristTestSource, ...] = (
    GristTestSource(
        table="Acte_engagement_gt",
        label_fine="acte_engagement",
        filter_kind="commentaire_traite",
        e2e_module="test_quality_acte_engagement",
    ),
    GristTestSource(
        table="Ccap_gt",
        label_fine="ccap",
        filter_kind="commentaire_traite",
        e2e_module="test_quality_ccap",
    ),
    GristTestSource(
        table="Devis_gt",
        label_fine="devis",
        filter_kind="commentaire_traite",
        e2e_module="test_quality_devis",
    ),
    GristTestSource(
        table="Rib_gt",
        label_fine="rib",
        filter_kind="commentaire_traite",
        e2e_module="test_quality_rib",
    ),
    GristTestSource(
        table="Avenant_gt",
        label_fine="avenant",
        filter_kind="commentaire_traite",
        e2e_module="test_quality_avenant",
    ),
    GristTestSource(
        table="Dc4_gt",
        label_fine="sous_traitance",
        filter_kind="commentaire_traite",
        e2e_module="test_quality_dc4",
    ),
)

FICHE_NAVETTE_SOURCE = GristTestSource(
    table="Fiche_navette_gt",
    label_fine="fiche_navette",
    filter_kind="commentaire_traite",
    e2e_module="test_quality_fiche_navette",
)


def priority_sources(*, include_fiche_navette: bool = False) -> tuple[GristTestSource, ...]:
    out = GRIST_PRIORITY_QUALITY_SOURCES
    if include_fiche_navette:
        return out + (FICHE_NAVETTE_SOURCE,)
    return out