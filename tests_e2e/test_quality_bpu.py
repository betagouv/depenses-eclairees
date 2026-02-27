"""
Test e2e qualité BPU : structure plate (prestations_flat) + arbre reconstitué (prestations).

- prestations_flat : liste plate avec id, parent, label, pricing (sans guid, retiré après fusion).
- prestations : arborescence récursive reconstituée par postprocessing (sans LLM).
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

import django
import pandas as pd

sys.path.append(".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "docia.settings")
django.setup()

from app.grist.grist_api import get_data_from_grist  # noqa: E402
from docia.file_processing.processor.text_extraction import (  # noqa: E402
    extract_text_from_ods,
    extract_text_from_xls,
    extract_text_from_xlsx,
)
from tests_e2e.utils import (  # noqa: E402
    analyze_content_quality_test,
)

logger = logging.getLogger("docia." + __name__)

FLAT_FIELDS = ("id", "parent", "label", "pricing")


def assert_bpu_flat_structure(structured_data: dict) -> None:
    """
    Vérifie que structured_data contient la structure BPU attendue :
    - prestations_flat : liste plate avec id, parent, label, pricing (guid retiré après fusion).
    - prestations : arbre récursif reconstitué par postprocessing.
    """
    assert structured_data is not None, "structured_data should not be None"
    prestations_flat = structured_data.get("prestations_flat")
    if prestations_flat is None:
        return
    assert isinstance(prestations_flat, list), "prestations_flat must be a list"
    for i, item in enumerate(prestations_flat):
        assert isinstance(item, dict), f"prestations_flat[{i}] must be a dict"
        for key in FLAT_FIELDS:
            assert key in item, f"prestations_flat[{i}] must have key {key!r}"
        if item.get("pricing") is not None:
            assert isinstance(item["pricing"], dict), f"prestations_flat[{i}].pricing must be dict or null"
    # Postprocessing doit avoir ajouté l'arbre en "prestations"
    tree = structured_data.get("prestations")
    assert tree is None or isinstance(tree, list), "prestations must be a list or null"


def _default_bpu_raw_dir() -> Path:
    """Répertoire par défaut des BPU bruts : data/test/bpu/raw/ à la racine du projet."""
    return Path("../data/test/bpu/raw/")


def get_markdown_from_bpu(filename: str, directory: Path | None = None) -> str:
    """
    Récupère le markdown concaténé de tous les onglets d'un fichier BPU (XLS, XLSX ou ODS).
    Utilise les extracteurs du module text_extraction (main).

    Args:
        filename: Nom du fichier (ex: "1300178703_2.1.BPU.xlsx", "fichier.xls", "fichier.ods").
        directory: Dossier contenant le fichier. Par défaut : data/test/bpu/raw/.

    Returns:
        Chaîne markdown (## NomOnglet + table avec |) concaténée pour tous les onglets.
    """
    directory = directory or _default_bpu_raw_dir()
    path = Path(directory) / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Fichier introuvable: {path}. Placez le fichier dans {directory} ou passez directory=..."
        )
    file_content = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".xls":
        text, _ = extract_text_from_xls(file_content, str(path))
        return text
    if suffix == ".ods":
        text, _ = extract_text_from_ods(file_content, str(path))
        return text
    text, _ = extract_text_from_xlsx(file_content, str(path))
    return text


def create_batch_test(num_ej: str, multi_line_coef=1, columns: list[str] = None, llm_model: str = "openweight-small"):
    """Test de qualité des informations extraites par le LLM pour les BPU.

    Les données de référence sont chargées depuis la table Grist Bpu_gt.
    """
    # Import des données depuis Grist (table Bpu_gt)
    columns = ["filename", "num_ej", "extension", "text"]
    df_test = get_data_from_grist(table="Bpu_gt")[columns].query("extension in ['pdf', 'PDF']")
    df_test.fillna("", inplace=True)

    # Lancement du test

    return analyze_content_quality_test(
        df_test.query(f"num_ej == '{num_ej}'"), "bordereau_prix", multi_line_coef=multi_line_coef, llm_model=llm_model
    )


if __name__ == "__main__":
    t0 = time.perf_counter()
    filename = None
    num_ej = None
    filename = "1300178703_2.1.BPU.xlsx" # OK 8min
    # filename = "1406856692_BPU_LOT_1_CITRONMER___2_.xlsx" # OK
    # filename = "1300189810_AMNYOS_BPU_DQE_lo1.xls"
    # filename = "1300143903_BPU revision des prix.ods"
    # filename = "1406856692_Devis_RP_FIVP_signe__769_.pdf"
    # num_ej = '1405526863' # OK
    # num_ej = "1200077900"  # OK
    # num_ej = '1405420568' # OK
    # num_ej = '1300196879'
    # num_ej = '1000188909' # OK
    # num_ej = '1200057300' # OK
    if filename:
        num_ej = filename.split("_")[0]
        extension = filename.split(".")[-1]
    else:
        extension = "pdf"
    if extension in ["xlsx", "xls", "ods"]: # BPU XLSX
        text = get_markdown_from_bpu(filename, directory=_default_bpu_raw_dir())
        # print(text)
        import tiktoken
        encoding = tiktoken.encoding_for_model("gpt-4o-mini")
        tokens = encoding.encode(text)
        print(len(tokens))
        df_test = pd.DataFrame(
        {"filename": [filename],
         "text": [text],
         "num_ej": [num_ej],
         "extension": [extension]})
        df_test, df_result, df_merged = analyze_content_quality_test(
            df_test, "bordereau_prix", llm_model="openweight-small"
        )
    elif extension.lower() == "pdf":  # BPU PDF
        df_test, df_result, df_merged = create_batch_test(num_ej)
        filename = df_test.filename.iloc[0]

    # Vérifier la structure plate + arbre reconstitué
    sd = df_merged.structured_data.iloc[0]
    err = df_merged.error.iloc[0] if "error" in df_merged.columns else None
    if sd is None or pd.isna(sd):
        msg = "structured_data should not be None"
        if err:
            msg += f". Analysis error: {err}"
        assert False, msg
    assert_bpu_flat_structure(sd)

    # Sauvegarder la sortie (prestations_flat + prestations)
    out_path = Path("../data/test/bpu/bpu_analyze/") / f"output_{filename}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    output = json.dumps(sd, indent=4, ensure_ascii=False)
    with open(out_path, "w") as f:
        f.write(output)
    print("Prestations_flat:", len(sd.get("prestations_flat") or []))
    print("Prestations (racines):", len(sd.get("prestations") or []))
    print("Output:", out_path)
    print(output[:1000] + "..." if len(output) > 1000 else output)
    elapsed = time.perf_counter() - t0
    print(f"Timer: {elapsed:.2f}s")
