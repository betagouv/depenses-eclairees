#!/usr/bin/env python3
"""Lance synthesis sur ``data/test/ej_db_2025.csv`` (Django déjà configuré)."""

import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "docia.settings")

import django

django.setup()

from django.conf import settings

from docia.file_processing.processor.synthesis import (
    SYNTHESIS_OUTPUT_COLUMNS,
    apply_synthesis_fields,
    build_merged_documents_table,
)

PROJECT_PATH = settings.BASE_DIR
CSV_DIR_PATH = (PROJECT_PATH / ".." / "data" / "test").resolve()
EJ_DB = CSV_DIR_PATH / "ej_db_2025.csv"

_CHAMPS_SYNTHESE = tuple(
    c for c in SYNTHESIS_OUTPUT_COLUMNS if c not in ("num_ej", "contrat", "source_et_conflits")
)


def _cellule_remplie(x) -> bool:
    if x is None:
        return False
    try:
        if pd.isna(x):
            return False
    except TypeError:
        pass
    if isinstance(x, str) and not x.strip():
        return False
    return True


def afficher_resume_resultats(df: pd.DataFrame) -> None:
    """
    Affiche uniquement en console : volumétrie EJ / contrats et décompte des champs
    métier renseignés (hors usage dans le module synthesis).
    """
    n_lignes = len(df)
    n_ej_distincts = int(df["num_ej"].nunique()) if "num_ej" in df.columns else 0

    if "contrat" in df.columns:
        s = df["contrat"]
        masque = s.notna()
        masque &= s.astype(str).str.strip().ne("")
        masque &= s.astype(str).str.lower().ne("nan")
        n_lignes_avec_contrat = int(masque.sum())
        contrats_non_vides = s.loc[masque].astype(str).str.strip()
        n_contrats_distincts = int(contrats_non_vides.nunique()) if len(contrats_non_vides) else 0
    else:
        n_lignes_avec_contrat = 0
        n_contrats_distincts = 0

    print("--- Résumé synthèse ---")
    print(f"Lignes (une par entrée du CSV lié EJ): {n_lignes}")
    print(f"Numéros d'EJ distincts: {n_ej_distincts}")
    print(f"Lignes avec colonne « contrat » renseignée: {n_lignes_avec_contrat}")
    print(f"Valeurs distinctes de contrat (non vides): {n_contrats_distincts}")

    if "source_et_conflits" in df.columns:
        n_avec_sources = int(df["source_et_conflits"].apply(lambda x: x is not None).sum())
        print(f"Lignes avec source_et_conflits (non None): {n_avec_sources}")

    print("Champs métier renseignés (nombre de lignes avec valeur):")
    total_champs = 0
    for col in _CHAMPS_SYNTHESE:
        if col not in df.columns:
            continue
        n = int(df[col].apply(_cellule_remplie).sum())
        total_champs += n
        print(f"  · {col}: {n}")
    print(f"Somme des remplissages (toutes colonnes métier): {total_champs}")

    champs_dispo = [c for c in _CHAMPS_SYNTHESE if c in df.columns]
    if champs_dispo:
        au_moins_un = df[champs_dispo].apply(lambda row: any(_cellule_remplie(v) for v in row), axis=1)
        print(f"Lignes avec au moins un champ métier renseigné: {int(au_moins_un.sum())}")


if __name__ == "__main__":
    if not EJ_DB.is_file():
        print(f"Fichier introuvable: {EJ_DB}", file=sys.stderr)
        sys.exit(1)

    df = apply_synthesis_fields(build_merged_documents_table(str(EJ_DB)))
    afficher_resume_resultats(df)
    print()
    print(f"{len(df)} lignes, {len(df.columns)} colonnes")
    preview = [c for c in ("num_ej", "objet", "date", "siret") if c in df.columns]
    if preview:
        print(df[preview].head(10).to_string())
