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

def create_batch_test(true_classification: list[str] = None, multi_line_coef=1):
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
    if true_classification is not None:
        df_test = df_test[df_test["classification"].apply(lambda x: true_classification == x)]
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


def compare_classification(df_result: pd.DataFrame):
    """Comparaison des classifications."""
    def lists_equal_ignore_order(list1, list2):
        """Compare deux listes en ignorant l'ordre."""
        if not isinstance(list1, list) or not isinstance(list2, list):
            return list1 == list2
        # return sorted(list1) == sorted(list2)
        return list1[0] == list2[0]
    
    df_result["is_correct"] = df_result.apply(
        lambda row: lists_equal_ignore_order(row["true_classification"], row["classification"]),
        axis=1
    )
    print(df_result[["filename", "true_classification", "classification", "is_correct"]].rename(columns={"true_classification": "true", "classification": "predicted", "is_correct": "ok"}))
    return df_result

def display_results(df_result: pd.DataFrame):
    """Affiche les résultats de classification par classe (basé sur le premier élément)."""
    # Fonction helper pour extraire le premier élément d'une liste
    def get_first_element(x):
        if isinstance(x, list) and len(x) > 0:
            return x[0]
        return 'Non classifié'
    
    # Créer des colonnes avec le premier élément
    df_result['true_class_first'] = df_result['true_classification'].apply(get_first_element)
    df_result['pred_class_first'] = df_result['classification'].apply(get_first_element)
    
    # Statistiques globales
    total_files = len(df_result)
    correct_files = df_result['is_correct'].sum()
    incorrect_files = total_files - correct_files
    
    # Compter les fichiers non classifiés (premier élément est 'Non classifié')
    unclassified_files = (df_result['pred_class_first'] == 'Non classifié').sum()
    
    print("=" * 60)
    print("STATISTIQUES GLOBALES")
    print("=" * 60)
    print(f"Nombre total de fichiers : {total_files}")
    print(f"Nombre de fichiers correctement classifiés : {correct_files} ({100*correct_files/total_files:.1f}%)")
    print(f"Nombre de fichiers incorrectement classifiés : {incorrect_files} ({100*incorrect_files/total_files:.1f}%)")
    print(f"Nombre de fichiers non classifiés : {unclassified_files} ({100*unclassified_files/total_files:.1f}%)")
    print()
    
    # Extraire toutes les classes uniques du premier élément de true_classification
    all_classes = df_result['true_class_first'].unique()
    
    if len(all_classes) == 0:
        print("Aucune classe trouvée dans true_classification")
        return
    
    print("=" * 60)
    print("STATISTIQUES PAR CLASSE (basé sur le premier élément)")
    print("=" * 60)
    
    # Statistiques par classe
    stats_by_class = []
    for class_name in sorted(all_classes):
        # Fichiers avec cette classe comme premier élément dans true_classification
        mask_has_class = df_result['true_class_first'] == class_name
        total_class = mask_has_class.sum()
        
        if total_class == 0:
            continue
        
        # Fichiers correctement classifiés pour cette classe
        correct_class = df_result[mask_has_class & (df_result['is_correct'] == 1)].shape[0]
        
        # Fichiers incorrectement classifiés pour cette classe
        incorrect_class = total_class - correct_class
        
        # Taux de précision
        precision = (correct_class / total_class * 100) if total_class > 0 else 0
        
        # Compter les catégories prédites (premier élément) pour cette classe réelle
        predicted_categories = df_result[mask_has_class]['pred_class_first'].value_counts().to_dict()
        
        # Formater les catégories prédites
        pred_details = []
        for pred_class, count in sorted(predicted_categories.items(), key=lambda x: x[1], reverse=True):
            pred_details.append(f"{pred_class} ({count})")
        pred_details_str = '; '.join(pred_details)
        
        stats_by_class.append({
            'Classe': class_name,
            'Total': total_class,
            'Corrects': correct_class,
            'Incorrects': incorrect_class,
            'Précision (%)': f"{precision:.1f}%",
            'Catégories prédites': pred_details_str
        })
    
    # Afficher le tableau
    df_stats = pd.DataFrame(stats_by_class)
    print(df_stats.to_string(index=False))
    print()
    
    # Distribution des classifications prédites (premier élément)
    print("=" * 60)
    print("DISTRIBUTION DES CLASSIFICATIONS PRÉDITES (premier élément)")
    print("=" * 60)
    classification_counts = df_result['pred_class_first'].value_counts()
    
    for cls, count in classification_counts.items():
        print(f"  {cls}: {count}")

df_result = create_batch_test(true_classification=["ccap"])
# df_result = create_batch_test()


df_comparison = compare_classification(df_result)

display_results(df_comparison)