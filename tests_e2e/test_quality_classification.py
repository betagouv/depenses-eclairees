import json
import logging
import os
import sys

import django
from django.conf import settings

import pandas as pd

sys.path.append(".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "docia.settings")
django.setup()

from docia.file_processing.processor.analyze_content import LLMClient  # noqa: E402
from docia.file_processing.processor.classifier import classify_files, DIC_CLASS_FILE_BY_NAME  # noqa: E402
from app.ai_models.config_albert import ALBERT_API_KEY, ALBERT_BASE_URL  # noqa: E402
logger = logging.getLogger("docia." + __name__)

PROJECT_PATH = settings.BASE_DIR
CSV_DIR_PATH = (PROJECT_PATH / ".." / "data" / "test").resolve()

# create_batch_test 
# Trouve le csv (pareil que dans les autres tests)
# Crée le dataframe
# Récupère uniquement les lignes avec une certaine classification dans le GT
# Passe les tests dans la classification et récupère un tableau des résultats
# Renvoier les df : df_test, df_result, df_merged

# Ajoute une focntion de comparaison pour la classification

# Ajouter une fonction montrant les résultats pour globaux et lignes par ligne

def create_batch_test(multi_line_coef=1):
    """Création du batch de test pour la classification."""
    # Chemin vers le fichier CSV de test
    csv_path = CSV_DIR_PATH / "test_classification.csv"

    # Lecture du fichier CSV et remplissage des valeurs manquantes
    df_test = pd.read_csv(csv_path)
    for idx, row in df_test.iterrows():
        try:
            df_test.at[idx, "classification"] = json.loads(row["classification"])
        except:
            df_test.at[idx, "classification"] = None
    df_test.dropna(subset=["classification"], inplace=True)
    if multi_line_coef > 1:
        df_test = pd.concat([df_test for x in range(multi_line_coef)]).reset_index(drop=True)

    # Création du DataFrame pour l'analyse
    df_classified = pd.DataFrame()
    df_classified["filename"] = df_test["filename"]
    df_classified["text"] = df_test["text"]
    df_classified["true_classification"] = df_test["classification"]

    # Analyse du contenu avec df_analyze_content
    df_result = classify_files(
        dfFiles=df_classified,
        list_classification=DIC_CLASS_FILE_BY_NAME
    )

    return df_result

df_result = create_batch_test()