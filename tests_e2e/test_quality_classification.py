import json
import logging
import os
import sys

import django

import pandas as pd

sys.path.append(".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "docia.settings")
django.setup()


from app.grist.grist_api import get_data_from_grist  # noqa: E402
from docia.file_processing.processor.classifier import DIC_CLASS_FILE_BY_NAME, classify_files  # noqa: E402

logger = logging.getLogger("docia." + __name__)


def create_batch_test(true_classification: list[str] = None, multi_line_coef=1):
    """Création du batch de test pour la classification."""
    columns_to_keep = ["filename", "num_ej", "classification", "is_ocr", "commentaire", "traitement", "text"]
    df_test = get_data_from_grist(table="Classif_gt")[columns_to_keep]

    df_test = df_test.query("traitement != 'Alexandre'")

    for idx, row in df_test.iterrows():
        df_test.at[idx, "classification"] = json.loads(row["classification"])
    df_test.dropna(subset=["classification"], inplace=True)

    if true_classification:
        df_test = df_test[df_test["classification"].str[0].isin(true_classification)]

    if multi_line_coef > 1:
        df_test = pd.concat([df_test for x in range(multi_line_coef)]).reset_index(drop=True)

    # Création du DataFrame pour l'analyse
    df_classified = pd.DataFrame()
    df_classified["filename"] = df_test["filename"]
    df_classified["text"] = df_test["text"]
    df_classified["true_classification"] = df_test["classification"]

    # Analyse du contenu avec df_analyze_content
    df_result = classify_files(dfFiles=df_classified, list_classification=DIC_CLASS_FILE_BY_NAME, max_workers=10)

    return df_test, df_classified, df_result


def compare_classification(df_result: pd.DataFrame, errors_only: bool = False):
    """Comparaison des classifications avec affichage amélioré.

    Args:
        df_result: DataFrame contenant les résultats de classification
        errors_only: Si True, n'affiche que les erreurs. Si False, affiche toutes les lignes.
    """

    df_result["is_correct"] = df_result["true_classification"].str[0] == df_result["classification"]

    # Préparer l'affichage avec symboles visuels
    def format_status(is_correct):
        """Retourne un symbole selon le statut."""
        return "✅" if is_correct else "❌"

    def format_classification(classif):
        """Formate une classification pour l'affichage."""
        if isinstance(classif, list):
            return ", ".join(str(c) for c in classif)
        return str(classif) if classif is not None else "None"

    def format_filename(filename):
        """Tronque le nom de fichier à 30 caractères max."""
        if len(filename) > 30:
            return filename[:40] + "..."
        return filename

    # Créer un DataFrame pour l'affichage
    df_display = pd.DataFrame()
    df_display["Statut"] = df_result["is_correct"].apply(format_status)
    df_display["Fichier"] = df_result["filename"].apply(format_filename)

    # Afficher les deux classifications seulement quand elles ne matchent pas
    df_display["Attendu"] = df_result["true_classification"].apply(format_classification)
    df_display["Prédit"] = df_result["classification"].apply(format_classification)

    # Masquer les colonnes "Attendu" et "Prédit" pour les lignes correctes
    mask_correct = df_result["is_correct"]
    df_display.loc[mask_correct, "Attendu"] = ""
    df_display.loc[mask_correct, "Prédit"] = ""

    # Filtrer pour n'afficher que les erreurs si demandé
    if errors_only:
        df_display = df_display[~mask_correct]

    # Afficher avec un formatage adapté pour ~50 lignes
    print("\n" + "=" * 100)
    print("COMPARAISON DES CLASSIFICATIONS")
    print("=" * 100)

    # Afficher les statistiques rapides
    total = len(df_result)
    correct = df_result["is_correct"].sum()
    incorrect = total - correct
    print(f"\nTotal: {total} | ✅ Corrects: {correct} | ❌ Incorrects: {incorrect}\n")

    # Afficher un message si on filtre les erreurs
    if errors_only:
        print(f"Affichage des erreurs uniquement ({len(df_display)} ligne(s))\n")

    # Configurer pandas pour un affichage optimal
    pd.set_option("display.max_rows", None)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", None)
    pd.set_option("display.max_colwidth", 50)

    # Afficher le tableau
    print(df_display.to_string(index=False))

    # Réinitialiser les options pandas
    pd.reset_option("display.max_rows")
    pd.reset_option("display.max_columns")
    pd.reset_option("display.width")
    pd.reset_option("display.max_colwidth")

    print("\n" + "=" * 100 + "\n")

    return df_result


def display_results(df_result: pd.DataFrame):
    """Affiche les résultats de classification par classe (basé sur le premier élément)."""

    # Créer des colonnes avec le premier élément
    df_result["true_class_first"] = df_result["true_classification"].str[0]
    df_result["pred_class_first"] = df_result["classification"]

    # Statistiques globales
    total_files = len(df_result)
    correct_files = df_result["is_correct"].sum()
    incorrect_files = total_files - correct_files

    # Compter les fichiers non classifiés (premier élément est 'Non classifié')
    unclassified_files = (df_result["pred_class_first"] == "Non classifié").sum()

    print("=" * 60)
    print("STATISTIQUES GLOBALES")
    print("=" * 60)
    print(f"Nombre total de fichiers : {total_files}")
    print(f"Nombre de fichiers correctement classifiés : {correct_files} ({100 * correct_files / total_files:.1f}%)")
    print(
        f"Nombre de fichiers incorrectement classifiés : {incorrect_files} ({100 * incorrect_files / total_files:.1f}%)"
    )
    print(f"Nombre de fichiers non classifiés : {unclassified_files} ({100 * unclassified_files / total_files:.1f}%)")
    print()

    # Extraire toutes les classes uniques du premier élément de true_classification
    all_classes = df_result["true_class_first"].unique()

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
        mask_has_class = df_result["true_class_first"] == class_name
        total_class = mask_has_class.sum()

        if total_class == 0:
            continue

        # Fichiers correctement classifiés pour cette classe
        correct_class = df_result[mask_has_class & (df_result["is_correct"] == 1)].shape[0]

        # Fichiers incorrectement classifiés pour cette classe
        incorrect_class = total_class - correct_class

        # Taux de précision
        precision = (correct_class / total_class * 100) if total_class > 0 else 0

        # Compter les catégories prédites (premier élément) pour cette classe réelle
        predicted_categories = df_result[mask_has_class]["pred_class_first"].value_counts().to_dict()

        # Formater les catégories prédites
        pred_details = []
        for pred_class, count in sorted(predicted_categories.items(), key=lambda x: x[1], reverse=True):
            pred_details.append(f"{pred_class} ({count})")
        pred_details_str = "; ".join(pred_details)

        stats_by_class.append(
            {
                "Classe": class_name,
                "Total": total_class,
                "Corrects": correct_class,
                "Incorrects": incorrect_class,
                "Précision (%)": f"{precision:.1f}%",
                "Catégories prédites": pred_details_str,
            }
        )

    # Afficher le tableau
    df_stats = pd.DataFrame(stats_by_class)
    print(df_stats.to_string(index=False))
    print()

    # Distribution des classifications prédites (premier élément)
    print("=" * 60)
    print("DISTRIBUTION DES CLASSIFICATIONS PRÉDITES (premier élément)")
    print("=" * 60)
    classification_counts = df_result["pred_class_first"].value_counts()

    for cls, count in classification_counts.items():
        print(f"  {cls}: {count}")


df_test, df_classified, df_result = create_batch_test()


df_comparison = compare_classification(df_result, errors_only=True)


display_results(df_comparison)
df_comparison.query("is_correct == 0")[["filename", "true_class_first", "pred_class_first"]]
