"""
Synthèse engagements / pièces jointes : chargement ORM, sélection de PJ par scope,
extraction de champs avec sources.

Requiert Django configuré (django.setup() ou exécution via manage.py).

Pour chaque ligne CSV (num_ej; contrat), les PJ sont chargées séparément sur l'EJ et le
marché (contrat). La meilleure PJ par classification est retenue (plus de champs remplis).
L'extraction parcourt d'abord toutes les sources scope ``ej``, puis le repli ``contrat``.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from docia.models import Document, Engagement

Scope = Literal["ej", "contrat"]
SourceSpec = tuple[Scope, str, str]

__all__ = [
    "SYNTHESIS_OUTPUT_COLUMNS",
    "SYNTHESIS_TO_ENGAGEMENT_FIELDS",
    "SYNTHESIS_FIELD_SOURCES",
    "EjContratRow",
    "PieceJointe",
    "AttachmentsByScope",
    "SynthesisRow",
    "read_ej_contrat_csv",
    "load_attachments",
    "best_pj_per_classification",
    "synthesize_row",
    "run_synthesis_pipeline",
    "sync_synthesis_to_engagements",
]

SYNTHESIS_TO_ENGAGEMENT_FIELDS: dict[str, str] = {
    "objet": "designation",
    "description_prestations": "descriptif_prestations",
    "date": "date",
    "societe_principale": "prestataire",
    "siret": "siret",
    "administration_beneficiaire": "administration",
    "source_et_conflits": "sources_et_conflits",
}

# (scope, classification, clé_json) — ordre = priorité ; ej puis contrat (repli marché).
SYNTHESIS_FIELD_SOURCES: dict[str, list[SourceSpec]] = {
    "objet": [
        ("ej", "devis", "objet"),
        ("ej", "bon_de_commande", "objet"),
        ("ej", "acte_engagement", "objet_marche"),
        ("ej", "ccp_vae", "objet_marche"),
        ("ej", "ccap", "objet_marche"),
        ("ej", "ccp_simple", "objet_marche"),
        ("ej", "fiche_navette", "objet"),
        ("ej", "avenant", "objet"),
        ("ej", "sous_traitance", "objet_marche"),
        ("ej", "conv_financement", "objet"),
        ("ej", "facture", "objet"),
        ("contrat", "acte_engagement", "objet_marche"),
        ("contrat", "ccp_vae", "objet_marche"),
        ("contrat", "ccap", "objet_marche"),
        ("contrat", "ccp_simple", "objet_marche"),
        ("contrat", "fiche_navette", "objet"),
        ("contrat", "avenant", "objet"),
        ("contrat", "sous_traitance", "objet_marche"),
        ("contrat", "conv_financement", "objet"),
    ],
    "description_prestations": [
        ("ej", "devis", "description_prestations"),
        ("ej", "bon_de_commande", "description_prestations"),
        ("ej", "acte_engagement", "description_prestations"),
        ("ej", "ccp_vae", "description_prestations"),
        ("ej", "ccap", "description_prestations"),
        ("ej", "ccp_simple", "description_prestations"),
        ("ej", "fiche_navette", "description_prestations"),
        ("ej", "avenant", "description_prestations"),
        ("ej", "sous_traitance", "description_prestations"),
        ("ej", "conv_financement", "description_prestations"),
        ("ej", "facture", "description_prestations"),
        ("contrat", "acte_engagement", "description_prestations"),
        ("contrat", "ccp_vae", "description_prestations"),
        ("contrat", "ccap", "description_prestations"),
        ("contrat", "ccp_simple", "description_prestations"),
        ("contrat", "fiche_navette", "description_prestations"),
        ("contrat", "avenant", "description_prestations"),
        ("contrat", "sous_traitance", "description_prestations"),
        ("contrat", "conv_financement", "description_prestations"),
    ],
    "date": [
        ("ej", "devis", "date_creation"),
        ("ej", "bon_de_commande", "date_signature"),
        ("ej", "facture", "date_emission"),
        ("ej", "acte_engagement", "date_signature_mandataire"),
        ("ej", "ccp_vae", "date_signature_mandataire"),
        ("ej", "avenant", "date_signature"),
        ("ej", "sous_traitance", "date_signature"),
        ("contrat", "acte_engagement", "date_signature_mandataire"),
        ("contrat", "ccp_vae", "date_signature_mandataire"),
        ("contrat", "avenant", "date_signature"),
        ("contrat", "sous_traitance", "date_signature"),
    ],
    "societe_principale": [
        ("ej", "devis", "societe_principale"),
        ("ej", "bon_de_commande", "societe_principale"),
        ("ej", "facture", "societe_facturante"),
        ("ej", "acte_engagement", "societe_principale"),
        ("ej", "ccp_vae", "societe_principale"),
        ("ej", "ccap", "societe_principale"),
        ("ej", "ccp_simple", "societe_principale"),
        ("ej", "fiche_navette", "societe_principale"),
        ("ej", "avenant", "societe_principale"),
        ("ej", "sous_traitance", "societe_principale"),
        ("ej", "rib", "titulaire_compte"),
        ("ej", "conv_financement", "societe_principale"),
        ("contrat", "acte_engagement", "societe_principale"),
        ("contrat", "ccp_vae", "societe_principale"),
        ("contrat", "ccap", "societe_principale"),
        ("contrat", "ccp_simple", "societe_principale"),
        ("contrat", "fiche_navette", "societe_principale"),
        ("contrat", "avenant", "societe_principale"),
        ("contrat", "sous_traitance", "societe_principale"),
        ("contrat", "rib", "titulaire_compte"),
        ("contrat", "conv_financement", "societe_principale"),
    ],
    "siret": [
        ("ej", "devis", "siret"),
        ("ej", "bon_de_commande", "siret"),
        ("ej", "facture", "siret"),
        ("ej", "acte_engagement", "siret_mandataire"),
        ("ej", "ccp_vae", "siret_mandataire"),
        ("ej", "avenant", "siret"),
        ("ej", "sous_traitance", "siret_titulaire"),
        ("contrat", "acte_engagement", "siret_mandataire"),
        ("contrat", "ccp_vae", "siret_mandataire"),
        ("contrat", "avenant", "siret"),
        ("contrat", "sous_traitance", "siret_titulaire"),
    ],
    "administration_beneficiaire": [
        ("ej", "acte_engagement", "administration_beneficiaire"),
        ("ej", "ccp_vae", "administration_beneficiaire"),
        ("ej", "conv_financement", "administration"),
        ("ej", "facture", "administration"),
        ("contrat", "acte_engagement", "administration_beneficiaire"),
        ("contrat", "ccp_vae", "administration_beneficiaire"),
        ("contrat", "conv_financement", "administration"),
    ],
}

SYNTHESIS_OUTPUT_COLUMNS: tuple[str, ...] = (
    "num_ej",
    "contrat",
    "objet",
    "description_prestations",
    "date",
    "societe_principale",
    "siret",
    "administration_beneficiaire",
    "source_et_conflits",
)


@dataclass
class EjContratRow:
    num_ej: str
    contrat: str | None = None


@dataclass
class PieceJointe:
    filename: str
    classification: str
    structured_data: dict[str, Any]
    hash: str = ""


@dataclass
class AttachmentsByScope:
    ej: list[PieceJointe] = field(default_factory=list)
    contrat: list[PieceJointe] = field(default_factory=list)


@dataclass
class SynthesisRow:
    num_ej: str
    contrat: str | None = None
    objet: str | None = None
    description_prestations: str | None = None
    date: str | None = None
    societe_principale: str | None = None
    siret: str | None = None
    administration_beneficiaire: str | None = None
    source_et_conflits: dict[str, list[dict[str, Any]]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_key(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip().replace("\xa0", "")
    if not s or s.lower() == "nan":
        return None
    return s


def _parse_structured_data(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        data = value
    elif isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        data = parsed
    else:
        return None
    if not _count_filled_keys(data):
        return None
    return data


def _count_filled_keys(data: dict[str, Any]) -> int:
    count = 0
    for value in data.values():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        count += 1
    return count


def _row_from_raw(raw: dict[str, Any]) -> PieceJointe | None:
    classification = raw.get("classification")
    if not classification:
        return None
    structured = _parse_structured_data(raw.get("structured_data"))
    if structured is None:
        return None
    filename = raw.get("filename") or ""
    return PieceJointe(
        filename=str(filename),
        classification=str(classification),
        structured_data=structured,
        hash=str(raw.get("hash") or ""),
    )


def read_ej_contrat_csv(path: str) -> list[EjContratRow]:
    """Lit un CSV ``num_ej;contrat`` et retourne les lignes normalisées."""
    rows: list[EjContratRow] = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for record in reader:
            num_ej = _normalize_key(record.get("num_ej"))
            if not num_ej:
                continue
            rows.append(EjContratRow(num_ej=num_ej, contrat=_normalize_key(record.get("contrat"))))
    return rows


def _fetch_pieces_for_key(num_key: str) -> list[PieceJointe]:
    qs = (
        Document.objects.filter(
            engagements__num_ej=num_key,
            structured_data__isnull=False,
        )
        .values("filename", "classification", "structured_data", "hash")
        .distinct()
    )
    pieces: list[PieceJointe] = []
    for raw in qs:
        pj = _row_from_raw(raw)
        if pj is not None:
            pieces.append(pj)
    return pieces


def load_attachments(num_ej: str, contrat: str | None) -> AttachmentsByScope:
    """
    Charge les PJ avec ``structured_data`` non vide pour l'EJ et, si renseigné, le contrat.
    """
    ej = _fetch_pieces_for_key(num_ej)
    contrat_pieces: list[PieceJointe] = []
    if contrat and contrat != num_ej:
        contrat_pieces = _fetch_pieces_for_key(contrat)
    return AttachmentsByScope(ej=ej, contrat=contrat_pieces)


def best_pj_per_classification(pjs: list[PieceJointe]) -> dict[str, PieceJointe]:
    """
    Une PJ par ``classification`` : celle avec le plus de champs remplis dans
    ``structured_data`` (égalité : filename puis hash).
    """
    best: dict[str, PieceJointe] = {}
    for pj in pjs:
        cls = pj.classification
        current = best.get(cls)
        if current is None:
            best[cls] = pj
            continue
        pj_score = _count_filled_keys(pj.structured_data)
        cur_score = _count_filled_keys(current.structured_data)
        if pj_score > cur_score:
            best[cls] = pj
        elif pj_score == cur_score and (pj.filename, pj.hash) < (current.filename, current.hash):
            best[cls] = pj
    return best


def _collect_candidates(
    specs: list[SourceSpec],
    best_by_scope: dict[Scope, dict[str, PieceJointe]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for scope, classification, json_key in specs:
        pj = best_by_scope.get(scope, {}).get(classification)
        if pj is None:
            continue
        value = pj.structured_data.get(json_key)
        if value is None or value == "":
            continue
        source = pj.filename.strip() if pj.filename.strip() else classification
        result.append({"valeur": value, "source": source})
    return result


def _canonical_value(candidates: list[dict[str, Any]]) -> Any:
    if not candidates:
        return None
    return candidates[0]["valeur"]


def synthesize_row(row: EjContratRow, attachments: AttachmentsByScope) -> SynthesisRow:
    """
    Extrait les champs canoniques et ``source_et_conflits`` pour une ligne EJ/contrat.

    Par champ : toutes les sources ``ej`` sont essayées (ordre de priorité), puis le
    repli ``contrat`` uniquement si aucune valeur n'a été trouvée sur l'EJ.
    """
    best_by_scope: dict[Scope, dict[str, PieceJointe]] = {
        "ej": best_pj_per_classification(attachments.ej),
        "contrat": best_pj_per_classification(attachments.contrat),
    }

    field_values: dict[str, Any] = {}
    conflicts: dict[str, list[dict[str, Any]]] = {}

    for field_name, all_specs in SYNTHESIS_FIELD_SOURCES.items():
        ej_specs = [s for s in all_specs if s[0] == "ej"]
        contrat_specs = [s for s in all_specs if s[0] == "contrat"]

        ej_candidates = _collect_candidates(ej_specs, best_by_scope)
        if ej_candidates:
            candidates = ej_candidates
        else:
            candidates = _collect_candidates(contrat_specs, best_by_scope)

        conflicts[field_name] = candidates
        field_values[field_name] = _canonical_value(candidates)

    source_et_conflits: dict[str, list[dict[str, Any]]] | None
    if not any(conflicts[k] for k in conflicts):
        source_et_conflits = None
    else:
        source_et_conflits = conflicts

    return SynthesisRow(
        num_ej=row.num_ej,
        contrat=row.contrat,
        objet=field_values.get("objet"),
        description_prestations=field_values.get("description_prestations"),
        date=field_values.get("date"),
        societe_principale=field_values.get("societe_principale"),
        siret=field_values.get("siret"),
        administration_beneficiaire=field_values.get("administration_beneficiaire"),
        source_et_conflits=source_et_conflits,
    )


def run_synthesis_pipeline(csv_path: str) -> list[SynthesisRow]:
    """Lit le CSV EJ/contrat et produit une synthèse par ligne."""
    results: list[SynthesisRow] = []
    for row in read_ej_contrat_csv(csv_path):
        attachments = load_attachments(row.num_ej, row.contrat)
        results.append(synthesize_row(row, attachments))
    return results


def _value_for_engagement_attr(attr: str, raw: Any) -> Any:
    """Convertit une valeur de synthèse vers le type attendu par ``Engagement``."""
    if raw is None:
        return None
    if attr == "sources_et_conflits":
        return raw
    if attr == "siret":
        s = str(raw).strip()
        if not s or s.lower() == "nan":
            return None
        return s[: Engagement._meta.get_field("siret").max_length]
    s = str(raw).strip()
    if not s or s.lower() == "nan":
        return None
    return s


def _row_to_mapping(row: SynthesisRow | dict[str, Any]) -> dict[str, Any]:
    if isinstance(row, SynthesisRow):
        return row.to_dict()
    return row


def sync_synthesis_to_engagements(
    rows: list[SynthesisRow] | list[dict[str, Any]],
    *,
    batch_size: int = 500,
    duplicate_num_ej: str = "last",
) -> tuple[int, int]:
    """
    Met à jour les engagements existants à partir des lignes de synthèse.

    Ne crée pas d'engagement manquant. Si plusieurs lignes partagent le même ``num_ej``,
    une seule est retenue (``duplicate_num_ej`` : ``\"first\"`` ou ``\"last\"``).

    Returns:
        ``(nombre_de_mises_à_jour, nombre_de_num_ej_non_trouvés_en_base)``
    """
    if not rows:
        return 0, 0

    mappings = [_row_to_mapping(r) for r in rows]
    deduped: dict[str, dict[str, Any]] = {}
    for m in mappings:
        nej = _normalize_key(m.get("num_ej"))
        if not nej:
            continue
        if duplicate_num_ej == "last" or nej not in deduped:
            deduped[nej] = m

    keys = list(deduped.keys())
    if not keys:
        return 0, 0

    existing = Engagement.objects.filter(num_ej__in=keys).in_bulk(field_name="num_ej")
    to_update: list[Engagement] = []
    missing = 0

    for nej, data in deduped.items():
        if nej not in existing:
            missing += 1
            continue
        obj = existing[nej]
        for synth_col, model_attr in SYNTHESIS_TO_ENGAGEMENT_FIELDS.items():
            if synth_col not in data:
                continue
            setattr(obj, model_attr, _value_for_engagement_attr(model_attr, data[synth_col]))
        to_update.append(obj)

    if to_update:
        Engagement.objects.bulk_update(
            to_update,
            fields=list(SYNTHESIS_TO_ENGAGEMENT_FIELDS.values()),
            batch_size=batch_size,
        )

    return len(to_update), missing
