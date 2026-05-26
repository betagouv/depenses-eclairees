import json
import logging
import os
import sys
import time

import django
from django.conf import settings

import pandas as pd

sys.path.append(".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "docia.settings")
django.setup()

from docia.file_processing.processor.synthesis import (  # noqa: E402
    SYNTHESIS_OUTPUT_COLUMNS,
    run_synthesis_pipeline,
)

logger = logging.getLogger("docia." + __name__)

PROJECT_PATH = settings.BASE_DIR
CSV_DIR_PATH = (PROJECT_PATH / ".." / "data" / "test").resolve()
EJ_DB = CSV_DIR_PATH / "test.csv"
EJ_DB_ANALYSE = CSV_DIR_PATH / "test_analyse.csv"

_CHAMPS_SYNTHESE = tuple(c for c in SYNTHESIS_OUTPUT_COLUMNS if c not in ("num_ej", "contrat", "source_et_conflits"))


def _cellule_remplie(x) -> bool:
    if x is None:
        return False
    if isinstance(x, str) and not x.strip():
        return False
    return True


def _rows_to_dataframe(rows: list) -> pd.DataFrame:
    records = []
    for row in rows:
        data = row.to_dict()
        conflicts = data.get("source_et_conflits")
        if conflicts is not None:
            data["source_et_conflits"] = json.dumps(conflicts, ensure_ascii=False)
        records.append(data)
    return pd.DataFrame(records, columns=list(SYNTHESIS_OUTPUT_COLUMNS))


def _prepare_dataframe_for_csv(df: pd.DataFrame) -> pd.DataFrame:
    """Nettoie les cellules avant export CSV (sauts de ligne, retours chariot)."""
    return df.apply(lambda col: col.astype(str).str.replace("\n", " ", regex=False).str.replace("\r", "r", regex=False))


def afficher_resume_resultats(rows: list, *, elapsed_s: float) -> None:
    """Affiche en console volumétrie EJ / contrats et décompte des champs métier renseignés."""
    n_lignes = len(rows)
    num_ejs = {r.num_ej for r in rows}
    n_ej_distincts = len(num_ejs)

    contrats_non_vides = [r.contrat for r in rows if r.contrat]
    n_lignes_avec_contrat = len(contrats_non_vides)
    n_contrats_distincts = len(set(contrats_non_vides))

    print("--- Résumé synthèse ---")
    print(f"Temps de traitement: {elapsed_s:.2f} s ({n_lignes} lignes)")
    if n_lignes:
        print(f"  · {elapsed_s / n_lignes:.3f} s par ligne")
    print(f"Lignes (une par entrée du CSV lié EJ): {n_lignes}")
    print(f"Numéros d'EJ distincts: {n_ej_distincts}")
    print(f"Lignes avec colonne « contrat » renseignée: {n_lignes_avec_contrat}")
    print(f"Valeurs distinctes de contrat (non vides): {n_contrats_distincts}")

    n_avec_sources = sum(1 for r in rows if r.source_et_conflits is not None)
    print(f"Lignes avec source_et_conflits (non None): {n_avec_sources}")

    print("Champs métier renseignés (nombre de lignes avec valeur):")
    total_champs = 0
    for col in _CHAMPS_SYNTHESE:
        n = sum(1 for r in rows if _cellule_remplie(getattr(r, col, None)))
        total_champs += n
        print(f"  · {col}: {n}")
    print(f"Somme des remplissages (toutes colonnes métier): {total_champs}")

    au_moins_un = sum(1 for r in rows if any(_cellule_remplie(getattr(r, col, None)) for col in _CHAMPS_SYNTHESE))
    print(f"Lignes avec au moins un champ métier renseigné: {au_moins_un}")


if __name__ == "__main__":
    if not EJ_DB.is_file():
        logger.error(f"Fichier introuvable: {EJ_DB}")
        sys.exit(1)

    t0 = time.perf_counter()
    rows = run_synthesis_pipeline(str(EJ_DB))
    elapsed = time.perf_counter() - t0

    EJ_DB_ANALYSE.parent.mkdir(parents=True, exist_ok=True)
    df = _prepare_dataframe_for_csv(_rows_to_dataframe(rows))
    df.to_csv(
        EJ_DB_ANALYSE,
        sep=";",
        encoding="utf-8",
        quotechar='"',
        index=False,
        quoting=1,
    )
    logger.info(f"Export CSV : {EJ_DB_ANALYSE} ({elapsed:.2f} s)")

    afficher_resume_resultats(rows, elapsed_s=elapsed)
