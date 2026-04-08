"""
Synthèse engagements / pièces jointes : chargement ORM, fusion par type de document,
extraction de champs avec sources.

Requiert Django configuré (django.setup() ou exécution via manage.py).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from django.db import connection
from django.db.models import F, Func, IntegerField, Window
from django.db.models.functions import RowNumber

from docia.models import DataEngagement, Document


class _JsonFilledKeyCount(Func):
    """
    Compte les clés de premier niveau dont la valeur n'est ni null JSON ni chaîne vide (comme ``_count_filled_keys``).
    PostgreSQL / jsonb uniquement.
    """

    arity = 1
    function = ""
    # Pas de to_jsonb(''::text) : les quotes cassent le SQL généré ; ``#>> '{}'`` suffit pour les scalaires chaîne.
    template = (
        "(SELECT count(*)::integer FROM jsonb_each(COALESCE((%(expressions)s)::jsonb, '{}'::jsonb)) AS kv "
        "WHERE kv.value IS DISTINCT FROM 'null'::jsonb "
        "AND (jsonb_typeof(kv.value) != 'string' OR (kv.value #>> '{}') IS DISTINCT FROM ''))"
    )
    output_field = IntegerField()


def _queryset_best_pj_per_engagement_postgresql(base_qs):
    """
    Une ligne par (num_ej lié, classification) : document avec le score ``nb_filled`` maximal.
    """
    return (
        base_qs.annotate(nb_filled=_JsonFilledKeyCount(F("structured_data")))
        .filter(nb_filled__gt=0)
        .annotate(
            row_number=Window(
                expression=RowNumber(),
                partition_by=[F("engagements__num_ej"), F("classification")],
                order_by=[F("nb_filled").desc(), F("filename"), F("hash")],
            )
        )
        .filter(row_number=1)
    )

__all__ = [
    "SYNTHESIS_OUTPUT_COLUMNS",
    "SYNTHESIS_TO_ENGAGEMENT_FIELDS",
    "sync_synthesis_to_engagements",
    "MERGE_CONFIG",
    "SOURCE_BY_DATA_COLUMN",
    "OBJET_SOURCES",
    "DESCRIPTION_PRESTATIONS_SOURCES",
    "DATE_SOURCES",
    "SOCIETE_PRINCIPALE_SOURCES",
    "SIRET_SOURCES",
    "ADMINISTRATION_BENEFICIAIRE_SOURCES",
    "get_documents_from_engagements",
    "get_documents_for_synthesis",
    "get_pj_with_max_structured_data",
    "merge_documents_and_engagements",
    "build_merged_documents_table",
    "get_field_with_sources",
    "apply_synthesis_fields",
]

# Colonnes ``apply_synthesis_fields`` → attributs ``DataEngagement`` (table ``engagements``).
SYNTHESIS_TO_ENGAGEMENT_FIELDS: dict[str, str] = {
    "objet": "designation",
    "description_prestations": "descriptif_prestations",
    "date": "date",
    "societe_principale": "prestataire",
    "siret": "siret",
    "administration_beneficiaire": "administration",
    "source_et_conflits": "sources_et_conflits",
}

_DOCUMENT_COLUMNS = [
    "hash",
    "filename",
    "engagements__num_ej",
    "classification",
    "structured_data",
]

_EMPTY_DF_COLUMNS = [c.replace("engagements__num_ej", "engagements") for c in _DOCUMENT_COLUMNS]


def _normalize_num_ej_list(engagements_list: list[Any]) -> list[str]:
    return [
        str(x).strip().replace("\xa0", "")
        for x in engagements_list
        if x is not None and pd.notna(x) and str(x).strip()
    ]


def _parse_structured_data(value: Any) -> dict | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _count_filled_keys(structured_data: dict | None) -> int:
    if not structured_data:
        return 0
    return sum(1 for _k, v in structured_data.items() if v is not None and v != "")


def get_documents_from_engagements(num_ej_list: list[Any]) -> pd.DataFrame:
    """
    Filtre les documents liés aux num_ej donnés (M2M via DataEngagement.num_ej).
    Retourne un DataFrame avec une colonne ``engagements`` (ex-``engagements__num_ej``).

    Sous PostgreSQL, ne retourne qu’**une PJ par couple** (engagement, classification) :
    celle avec le plus de champs remplis dans ``structured_data`` (calcul en base).
    """
    normalized = _normalize_num_ej_list(num_ej_list)
    if not normalized:
        return pd.DataFrame(columns=_EMPTY_DF_COLUMNS)

    base = Document.objects.filter(
        engagements__num_ej__in=normalized,
        structured_data__isnull=False,
    )

    qs = _queryset_best_pj_per_engagement_postgresql(base).order_by("filename", "classification", "hash")

    df = pd.DataFrame(qs.values(*_DOCUMENT_COLUMNS))
    if df.empty:
        return df.rename(columns={"engagements__num_ej": "engagements"})
    df = df.rename(columns={"engagements__num_ej": "engagements"})
    df["structured_data"] = df["structured_data"].apply(_parse_structured_data)
    return df


def get_documents_for_synthesis(ej_db_path: str = "../data/test/ej_db_2025.csv") -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Lit le CSV de lien EJ/contrats et charge les PJ correspondantes depuis la base.
    """
    df_link = pd.read_csv(
        ej_db_path,
        sep=";",
        encoding="utf-8",
        dtype={"num_ej": str, "contrat": str},
    )
    keys = df_link["num_ej"].tolist() + df_link.loc[~pd.isna(df_link["contrat"]), "contrat"].tolist()
    df_pj = get_documents_from_engagements(keys)
    return df_link, df_pj


# (classification, colonne de jointure dans df_engagements, suffixe data, suffixe filename)
MERGE_CONFIG = [
    ("devis", "num_ej", "_devis", "_devis"),
    ("bon_de_commande", "num_ej", "_bdc", "_bdc"),
    ("acte_engagement", "num_ej", "", "_ae"),
    ("acte_engagement", "contrat", "_ae_contrat", "_ae_contrat"),
    ("ccap", "num_ej", "_ccap", "_ccap"),
    ("ccap", "contrat", "_ccap_contrat", "_ccap_contrat"),
    ("fiche_navette", "num_ej", "_nav", "_nav"),
    ("fiche_navette", "contrat", "_nav_contrat", "_nav_contrat"),
    ("avenant", "num_ej", "_avenant", "_avenant"),
    ("avenant", "contrat", "_avenant_contrat", "_avenant_contrat"),
    ("sous_traitance", "num_ej", "_sstraitance", "_sstraitance"),
    ("sous_traitance", "contrat", "_sstraitance_contrat", "_sstraitance_contrat"),
    ("rib", "num_ej", "_rib", "_rib"),
    ("rib", "contrat", "_rib_contrat", "_rib_contrat"),
    ("conv_financement", "num_ej", "_conv_financement", "_conv_financement"),
    ("conv_financement", "contrat", "_conv_financement_contrat", "_conv_financement_contrat"),
    ("facture", "num_ej", "_facture", "_facture"),
]


def merge_documents_and_engagements(df_engagements: pd.DataFrame, df_pj: pd.DataFrame) -> pd.DataFrame:
    """
    Une ligne par ligne du CSV engagements avec structured_data + filename par type de PJ.

    ``df_pj`` doit être déjà dédoublonné (une PJ max par engagement × classification),
    comme le retour de ``get_documents_from_engagements``.
    """
    df_out = df_engagements.copy(deep=True)
    df_out["num_ej"] = df_out["num_ej"].astype(str)

    for classification, left_on, data_suffix, filename_suffix in MERGE_CONFIG:
        sub = df_pj[df_pj["classification"] == classification][
            ["engagements", "structured_data", "filename"]
        ].copy()
        data_col = "structured_data" if data_suffix == "" else "structured_data" + data_suffix
        filename_col = "filename" + filename_suffix
        sub = sub.rename(columns={"structured_data": data_col, "filename": filename_col})
        df_out = df_out.merge(sub, left_on=left_on, right_on="engagements", how="left")
        df_out = df_out.drop(columns=["engagements"], errors="ignore")

    return df_out.reset_index(drop=True)


def build_merged_documents_table(ej_db_path: str = "../data/test/ej_db_2025.csv") -> pd.DataFrame:
    """Charge ``ej_db_path`` et retourne la table large fusionnée (une ligne par EJ du CSV)."""
    df_engagements, df_pj = get_documents_for_synthesis(ej_db_path)
    return merge_documents_and_engagements(df_engagements, df_pj)


SOURCE_BY_DATA_COLUMN = {
    "structured_data": "acte_engagement",
    "structured_data_ae_contrat": "acte_engagement_contrat",
    "structured_data_ccap": "ccap",
    "structured_data_ccap_contrat": "ccap_contrat",
    "structured_data_devis": "devis",
    "structured_data_bdc": "bon_de_commande",
    "structured_data_nav": "fiche_navette",
    "structured_data_nav_contrat": "fiche_navette_contrat",
    "structured_data_avenant": "avenant",
    "structured_data_avenant_contrat": "avenant_contrat",
    "structured_data_sstraitance": "sous_traitance",
    "structured_data_sstraitance_contrat": "sous_traitance_contrat",
    "structured_data_rib": "rib",
    "structured_data_rib_contrat": "rib_contrat",
    "structured_data_conv_financement": "conv_financement",
    "structured_data_conv_financement_contrat": "conv_financement_contrat",
    "structured_data_facture": "facture",
}


def get_field_with_sources(
    row: pd.Series,
    sources_config: list[tuple[str, str, str | None]],
) -> list[dict[str, Any]]:
    """
    Pour un champ métier, liste les ``{"valeur", "source"}`` selon l'ordre de priorité.
    ``sources_config`` : liste de (colonne structured_data_*, clé JSON, colonne filename ou None).
    """
    result = []
    for data_col, key, filename_col in sources_config:
        if data_col not in row.index or pd.isna(row[data_col]):
            continue
        raw = row[data_col]
        data = raw if isinstance(raw, dict) else {}
        value = data.get(key, None) if data else None
        if value is not None and value != "":
            if (
                filename_col
                and filename_col in row.index
                and pd.notna(row.get(filename_col))
                and str(row[filename_col]).strip()
            ):
                source = str(row[filename_col]).strip()
            else:
                source = SOURCE_BY_DATA_COLUMN.get(
                    data_col,
                    data_col.replace("structured_data_", "").replace("structured_data", "acte_engagement"),
                )
            result.append({"valeur": value, "source": source})
    return result


OBJET_SOURCES = [
    ("structured_data_devis", "objet", "filename_devis"),
    ("structured_data_bdc", "objet", "filename_bdc"),
    ("structured_data", "objet_marche", "filename_ae"),
    ("structured_data_ae_contrat", "objet_marche", "filename_ae_contrat"),
    ("structured_data_ccap", "objet_marche", "filename_ccap"),
    ("structured_data_ccap_contrat", "objet_marche", "filename_ccap_contrat"),
    ("structured_data_nav", "objet", "filename_nav"),
    ("structured_data_nav_contrat", "objet", "filename_nav_contrat"),
    ("structured_data_avenant", "objet", "filename_avenant"),
    ("structured_data_avenant_contrat", "objet", "filename_avenant_contrat"),
    ("structured_data_sstraitance", "objet_marche", "filename_sstraitance"),
    ("structured_data_sstraitance_contrat", "objet_marche", "filename_sstraitance_contrat"),
    ("structured_data_conv_financement", "objet", "filename_conv_financement"),
    ("structured_data_conv_financement_contrat", "objet", "filename_conv_financement_contrat"),
    ("structured_data_facture", "objet", "filename_facture"),
]

DESCRIPTION_PRESTATIONS_SOURCES = [
    ("structured_data_devis", "description_prestations", "filename_devis"),
    ("structured_data_bdc", "description_prestations", "filename_bdc"),
    ("structured_data", "description_prestations", "filename_ae"),
    ("structured_data_ae_contrat", "description_prestations", "filename_ae_contrat"),
    ("structured_data_ccap", "description_prestations", "filename_ccap"),
    ("structured_data_ccap_contrat", "description_prestations", "filename_ccap_contrat"),
    ("structured_data_nav", "description_prestations", "filename_nav"),
    ("structured_data_nav_contrat", "description_prestations", "filename_nav_contrat"),
    ("structured_data_avenant", "description_prestations", "filename_avenant"),
    ("structured_data_avenant_contrat", "description_prestations", "filename_avenant_contrat"),
    ("structured_data_sstraitance", "description_prestations", "filename_sstraitance"),
    ("structured_data_sstraitance_contrat", "description_prestations", "filename_sstraitance_contrat"),
    ("structured_data_conv_financement", "description_prestations", "filename_conv_financement"),
    ("structured_data_conv_financement_contrat", "description_prestations", "filename_conv_financement_contrat"),
    ("structured_data_facture", "description_prestations", "filename_facture"),
]

DATE_SOURCES = [
    ("structured_data_devis", "date_creation", "filename_devis"),
    ("structured_data_bdc", "date_signature", "filename_bdc"),
    ("structured_data_facture", "date_emission", "filename_facture"),
    ("structured_data", "date_signature_mandataire", "filename_ae"),
    ("structured_data_ae_contrat", "date_signature_mandataire", "filename_ae_contrat"),
    ("structured_data_avenant", "date_signature", "filename_avenant"),
    ("structured_data_avenant_contrat", "date_signature", "filename_avenant_contrat"),
    ("structured_data_sstraitance", "date_signature", "filename_sstraitance"),
    ("structured_data_sstraitance_contrat", "date_signature", "filename_sstraitance_contrat"),
]

SOCIETE_PRINCIPALE_SOURCES = [
    ("structured_data_devis", "societe_principale", "filename_devis"),
    ("structured_data_bdc", "societe_principale", "filename_bdc"),
    ("structured_data_facture", "societe_facturante", "filename_facture"),
    ("structured_data", "societe_principale", "filename_ae"),
    ("structured_data_ae_contrat", "societe_principale", "filename_ae_contrat"),
    ("structured_data_ccap", "societe_principale", "filename_ccap"),
    ("structured_data_ccap_contrat", "societe_principale", "filename_ccap_contrat"),
    ("structured_data_nav", "societe_principale", "filename_nav"),
    ("structured_data_nav_contrat", "societe_principale", "filename_nav_contrat"),
    ("structured_data_avenant", "societe_principale", "filename_avenant"),
    ("structured_data_avenant_contrat", "societe_principale", "filename_avenant_contrat"),
    ("structured_data_sstraitance", "societe_principale", "filename_sstraitance"),
    ("structured_data_sstraitance_contrat", "societe_principale", "filename_sstraitance_contrat"),
    ("structured_data_rib", "titulaire_compte", "filename_rib"),
    ("structured_data_rib_contrat", "titulaire_compte", "filename_rib_contrat"),
    ("structured_data_conv_financement", "societe_principale", "filename_conv_financement"),
    ("structured_data_conv_financement_contrat", "societe_principale", "filename_conv_financement_contrat"),
]

SIRET_SOURCES = [
    ("structured_data_devis", "siret", "filename_devis"),
    ("structured_data_bdc", "siret", "filename_bdc"),
    ("structured_data_facture", "siret", "filename_facture"),
    ("structured_data", "siret_mandataire", "filename_ae"),
    ("structured_data_ae_contrat", "siret_mandataire", "filename_ae_contrat"),
    ("structured_data_avenant", "siret", "filename_avenant"),
    ("structured_data_avenant_contrat", "siret", "filename_avenant_contrat"),
    ("structured_data_sstraitance", "siret_titulaire", "filename_sstraitance"),
    ("structured_data_sstraitance_contrat", "siret_titulaire", "filename_sstraitance_contrat"),
]

ADMINISTRATION_BENEFICIAIRE_SOURCES = [
    ("structured_data", "administration_beneficiaire", "filename_ae"),
    ("structured_data_ae_contrat", "administration_beneficiaire", "filename_ae_contrat"),
    ("structured_data_conv_financement", "administration", "filename_conv_financement"),
    ("structured_data_conv_financement_contrat", "administration", "filename_conv_financement_contrat"),
    ("structured_data_facture", "administration", "filename_facture"),
]

_SYNTHESIS_FIELD_CONFIG: list[tuple[str, list[tuple[str, str, str | None]]]] = [
    ("objet", OBJET_SOURCES),
    ("description_prestations", DESCRIPTION_PRESTATIONS_SOURCES),
    ("date", DATE_SOURCES),
    ("societe_principale", SOCIETE_PRINCIPALE_SOURCES),
    ("siret", SIRET_SOURCES),
    ("administration_beneficiaire", ADMINISTRATION_BENEFICIAIRE_SOURCES),
]

# Ordre des colonnes renvoyées par ``apply_synthesis_fields`` (les clés absentes du DataFrame sont ignorées).
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


def _canonical_value(candidates: list[dict[str, Any]]) -> Any:
    """Valeur retenue (priorité métier) ; les sources sont dans ``source_et_conflits``."""
    if not candidates:
        return None
    return candidates[0]["valeur"]


def apply_synthesis_fields(df_merged: pd.DataFrame) -> pd.DataFrame:
    """
    Ajoute les colonnes canoniques ``objet``, ``description_prestations``, etc. :
    chaque cellule contient uniquement la **valeur** retenue (première selon la
    priorité), ou ``None`` si aucune valeur.

    Les couples ``{"valeur", "source"}`` par champ (toutes les sources candidates)
    sont regroupés dans ``source_et_conflits``. Si **aucun** champ n’a de source sur
    la ligne, ``source_et_conflits`` vaut ``None``.

    Retourne uniquement ``num_ej``, ``contrat``, les champs canoniques et
    ``source_et_conflits`` (dans cet ordre ; colonnes absentes ignorées).
    """
    df = df_merged.copy(deep=True)
    for col_name, _cfg in _SYNTHESIS_FIELD_CONFIG:
        df[col_name] = None
    df["source_et_conflits"] = None

    for idx in df.index:
        row = df.loc[idx]
        conflicts: dict[str, list[dict[str, Any]]] = {}
        for col_name, cfg in _SYNTHESIS_FIELD_CONFIG:
            candidates = get_field_with_sources(row, cfg)
            conflicts[col_name] = candidates
            df.at[idx, col_name] = _canonical_value(candidates)
        if not any(conflicts[k] for k in conflicts):
            df.at[idx, "source_et_conflits"] = None
        else:
            df.at[idx, "source_et_conflits"] = conflicts

    present = [c for c in SYNTHESIS_OUTPUT_COLUMNS if c in df.columns]
    return df[present].copy()


_ENGAGEMENT_FIELDS_TO_UPDATE: tuple[str, ...] = tuple(SYNTHESIS_TO_ENGAGEMENT_FIELDS.values())


def _value_for_engagement_attr(attr: str, raw: Any) -> Any:
    """Convertit une valeur issue du DataFrame vers le type attendu par ``DataEngagement``."""
    if raw is None:
        return None
    if isinstance(raw, float) and pd.isna(raw):
        return None
    if attr == "sources_et_conflits":
        return raw
    if attr == "siret":
        s = str(raw).strip()
        if not s or s.lower() == "nan":
            return None
        return s[: DataEngagement._meta.get_field("siret").max_length]
    s = str(raw).strip()
    if not s or s.lower() == "nan":
        return None
    return s


def sync_synthesis_to_engagements(
    df: pd.DataFrame,
    *,
    batch_size: int = 500,
    duplicate_num_ej: str = "last",
) -> tuple[int, int]:
    """
    Met à jour les lignes existantes de la table ``engagements`` (modèle ``DataEngagement``)
    à partir d'un DataFrame produit par ``apply_synthesis_fields``.

    Remplit ``designation``, ``descriptif_prestations``, ``date``, ``prestataire``,
    ``siret``, ``administration`` et ``sources_et_conflits`` (voir
    ``SYNTHESIS_TO_ENGAGEMENT_FIELDS``). Ne crée pas d'engagement manquant : les
    ``num_ej`` absents de la base sont comptés et ignorés.

    Si plusieurs lignes ont le même ``num_ej``, une seule est retenue (``duplicate_num_ej`` :
    ``\"first\"`` ou ``\"last\"``).

    Returns:
        ``(nombre_de_mises_à_jour, nombre_de_num_ej_non_trouvés_en_base)``
    """
    if df.empty or "num_ej" not in df.columns:
        return 0, 0

    dedup = df.drop_duplicates(subset=["num_ej"], keep=duplicate_num_ej)

    keys = []
    for x in dedup["num_ej"].tolist():
        if x is None or (isinstance(x, float) and pd.isna(x)):
            continue
        nej = str(x).strip().replace("\xa0", "")
        if nej:
            keys.append(nej)

    if not keys:
        return 0, 0

    existing = DataEngagement.objects.filter(num_ej__in=keys).in_bulk(field_name="num_ej")
    to_update: list[DataEngagement] = []
    missing = 0

    for _, row in dedup.iterrows():
        raw_ej = row["num_ej"]
        if raw_ej is None or (isinstance(raw_ej, float) and pd.isna(raw_ej)):
            continue
        nej = str(raw_ej).strip().replace("\xa0", "")
        if not nej:
            continue
        if nej not in existing:
            missing += 1
            continue
        obj = existing[nej]
        for synth_col, model_attr in SYNTHESIS_TO_ENGAGEMENT_FIELDS.items():
            if synth_col not in dedup.columns:
                continue
            setattr(obj, model_attr, _value_for_engagement_attr(model_attr, row[synth_col]))
        to_update.append(obj)

    if to_update:
        DataEngagement.objects.bulk_update(
            to_update,
            fields=list(_ENGAGEMENT_FIELDS_TO_UPDATE),
            batch_size=batch_size,
        )

    return len(to_update), missing
