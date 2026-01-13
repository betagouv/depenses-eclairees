import re

import pandas as pd

from docia.file_processing.processor import ATTRIBUTES
from docia.file_processing.processor.analyze_content import df_analyze_content
from docia.file_processing.processor.post_processing_llm import clean_llm_response


def normalize_string(s):
    """Normalise une chaîne de caractères : minuscule et sans caractères spéciaux."""
    if pd.isna(s) or s == "":
        return ""
    s = str(s).lower()
    # Supprime les caractères spéciaux (garde seulement les lettres, chiffres et espaces)
    s = re.sub(r"[^a-z0-9\s]", "", s)
    # Supprime les espaces multiples
    s = re.sub(r"\s+", " ", s).strip()
    return s


def analyze_content_quality_test(df_test: pd.DataFrame, document_type: str, multi_line_coef=1):
    """Test de qualité des informations extraites par le LLM."""

    # Nettoyage des colonnes du DataFrame de test (après lecture du CSV)
    for idx, row in df_test.iterrows():
        cleaned_data = clean_llm_response(document_type, row.to_dict())
        for key, value in cleaned_data.items():
            df_test.at[idx, key] = value

    if multi_line_coef > 1:
        df_test = pd.concat([df_test for x in range(multi_line_coef)]).reset_index(drop=True)

    # Création du DataFrame pour l'analyse
    df_analyze = pd.DataFrame()
    df_analyze["filename"] = df_test["filename"]
    df_analyze["classification"] = document_type
    df_analyze["relevant_content"] = df_test["text"]

    # Analyse du contenu avec df_analyze_content
    df_result = df_analyze_content(
        df=df_analyze,
        df_attributes=ATTRIBUTES,
        max_workers=10,
        temperature=0.1,
    )

    # Fusion des résultats avec les valeurs de référence
    # Pour éviter le produit cartésien lorsque filename est dupliqué, on utilise l'index
    # Les deux dataframes ont le même nombre de lignes et le même ordre
    df_result_reset = df_result[["filename", "llm_response", "structured_data"]].reset_index(drop=True)
    df_test_reset = df_test.reset_index(drop=True)

    # Ajout d'un identifiant unique basé sur l'index pour le merge
    df_result_reset["_merge_key"] = df_result_reset.index
    df_test_reset["_merge_key"] = df_test_reset.index

    # Merge sur l'identifiant unique plutôt que sur filename
    df_merged = df_result_reset.merge(df_test_reset, on="_merge_key", how="inner")

    # Suppression de la colonne temporaire et de la colonne filename dupliquée
    df_merged = df_merged.drop(columns=["_merge_key", "filename_x"])
    df_merged = df_merged.rename(columns={"filename_y": "filename"})

    return df_test, df_result, df_merged


def check_quality_one_field(df_merged, col_to_test, comparison_func):
    # ============================================================================
    # COMPARAISON POUR UNE COLONNE SPÉCIFIQUE
    # ============================================================================

    print(f"\n{'=' * 80}")
    print(f"Comparaison pour la colonne: {col_to_test}")
    print(f"{'=' * 80}\n")

    # Boucle de comparaison simple
    for idx, row in df_merged.iterrows():
        filename = row.get("filename", "unknown")

        llm_data = row.get("structured_data", None)

        # Extraire les valeurs
        ref_val = row.get(col_to_test, None)
        llm_val = llm_data.get(col_to_test, None) if llm_data else None

        # Extraction des pbm OCR
        list_pbm_ocr = eval(row["pbm_ocr"]) or []
        pbm_ocr = col_to_test in list_pbm_ocr

        # Comparer les valeurs
        try:
            match_result = comparison_func(llm_val, ref_val)
            status = "✅ MATCH" if match_result else "❌ NO MATCH"
            print(f"{status} | {filename} | OCR {'❌' if pbm_ocr else '✅'}")
            print(f"  LLM: {llm_val}")
            print(f"  REF: {ref_val}")
            print()
        except Exception as e:
            print(f"❌ ERREUR | {filename}: {str(e)} | OCR {'❌' if pbm_ocr else '✅'}")
            print(f"  LLM: {llm_val}")
            print(f"  REF: {ref_val}")
            print()


def check_quality_one_row(df_merged, row_idx_to_test, comparison_functions, excluded_columns=None):
    # ============================================================================
    # COMPARAISON POUR UNE LIGNE SPÉCIFIQUE
    # ============================================================================
    excluded_columns = excluded_columns or []

    if row_idx_to_test < len(df_merged):
        row = df_merged.iloc[row_idx_to_test]
        filename = row.get("filename", "unknown")

        print(f"\n{'=' * 80}")
        print(f"Comparaison pour la ligne {row_idx_to_test} (fichier: {filename})")
        print(f"{'=' * 80}\n")

        llm_data = row.get("structured_data", None)

        # Comparer toutes les colonnes (sauf exclues)
        for col in comparison_functions.keys():
            if col in excluded_columns:
                continue
            if col not in df_merged.columns:
                continue

            comparison_func = comparison_functions[col]

            # Extraire les valeurs
            ref_val = row.get(col, None)
            llm_val = llm_data.get(col, None)

            # Extraction des pbm OCR
            list_pbm_ocr = eval(row["pbm_ocr"]) or []
            pbm_ocr = col in list_pbm_ocr

            # Comparer les valeurs
            try:
                match_result = comparison_func(llm_val, ref_val)
                match_result = bool(match_result) if not isinstance(match_result, bool) else match_result
                status = "✅ MATCH" if match_result else "❌ NO MATCH"
                print(f"{status} | {col} | OCR {'❌' if pbm_ocr else '✅'}")
                print(f"  LLM: {llm_val}")
                print(f"  REF: {ref_val}")
                print()
            except Exception as e:
                print(f"❌ ERREUR | {col}: {str(e)} | OCR {'❌' if pbm_ocr else '✅'}")
                print(f"  LLM: {llm_val}")
                print(f"  REF: {ref_val}")
                print()
    else:
        print(f"\n❌ Index {row_idx_to_test} invalide. Le DataFrame contient {len(df_merged)} lignes.\n")


def check_global_statistics(df_merged, comparison_functions, excluded_columns=None):
    # ============================================================================
    # STATISTIQUES GLOBALES DE COMPARAISON
    # ============================================================================
    excluded_columns = excluded_columns or []

    print(f"\n{'=' * 80}")
    print("STATISTIQUES GLOBALES DE COMPARAISON")
    print(f"{'=' * 80}\n")

    results = {}

    # Comparaison pour chaque colonne (sauf exclues)
    for col in comparison_functions.keys():
        # Ignorer les colonnes exclues
        if col in excluded_columns:
            continue

        # Vérifier si la colonne existe dans le CSV de référence
        if col not in df_merged.columns:
            continue

        comparison_func = comparison_functions[col]
        matches = []
        errors = []
        ocr_errors_count = 0
        matches_no_ocr = []

        # Comparer toutes les lignes pour cette colonne
        for idx, row in df_merged.iterrows():
            filename = row.get("filename", "unknown")

            # Vérifier les erreurs OCR pour cette colonne
            pbm_ocr = False
            list_pbm_ocr = eval(row["pbm_ocr"]) or []
            if col in list_pbm_ocr:
                ocr_errors_count += 1
                pbm_ocr = True

            structured_data = row.get("structured_data", None)
            if structured_data is None or pd.isna(structured_data):
                errors.append(f"{filename}: structured_data is None or NaN")
                matches.append(False)
                # Si pas de problème OCR, on compte aussi dans matches_no_ocr
                if not pbm_ocr:
                    matches_no_ocr.append(False)
                continue

            # Extraire les valeurs
            ref_val = row.get(col, None)
            llm_val = structured_data.get(col, None)

            # Comparer les valeurs
            try:
                match_result = comparison_func(llm_val, ref_val)
                match_result = bool(match_result) if not isinstance(match_result, bool) else match_result
                matches.append(match_result)
                # Si pas de problème OCR, on ajoute aussi à matches_no_ocr
                if not pbm_ocr:
                    matches_no_ocr.append(match_result)
            except Exception as e:
                errors.append(f"{filename}: Error in comparison_func: {str(e)}")
                matches.append(False)
                # Si pas de problème OCR, on ajoute aussi à matches_no_ocr
                if not pbm_ocr:
                    matches_no_ocr.append(False)

        # Calculer les statistiques pour cette colonne
        total = len(matches)
        matches_count = sum(matches)
        errors_count = len(errors)
        accuracy = matches_count / total if total > 0 else 0.0

        # Calculer l'accuracy sans OCR (seulement sur les comparaisons sans problème OCR)
        total_no_ocr = len(matches_no_ocr)
        matches_no_ocr_count = sum(matches_no_ocr)
        accuracy_no_ocr = matches_no_ocr_count / total_no_ocr if total_no_ocr > 0 else 0.0

        results[col] = {
            "total": total,
            "matches": matches_count,
            "errors": errors_count,
            "ocr_errors": ocr_errors_count,
            "accuracy": accuracy,
            "accuracy_no_ocr": accuracy_no_ocr,
            "total_no_ocr": total_no_ocr,
            "matches_no_ocr": matches_no_ocr_count,
        }

    # Affichage des statistiques
    print(
        " | ".join(
            [
                f"{'Colonne':<35}",
                f"{'Total':<6}",
                f"{'Matches':<8}",
                f"{'Erreurs':<8}",
                f"{'OCR Errors':<10}",
                f"{'Accuracy':<10}",
                f"{'Accuracy (no OCR)':<18}",
            ]
        )
    )
    print("-" * 120)

    for col, result in results.items():
        print(
            " | ".join(
                [
                    f"{col:<35}",
                    f"{result['total']:<6}",
                    f"{result['matches']:<8}",
                    f"{result['errors']:<8}",
                    f"{result['ocr_errors']:<10}",
                    f"{result['accuracy'] * 100:>6.2f}%",
                    f"{result['accuracy_no_ocr'] * 100:>14.2f}%",
                ]
            )
        )

    print(f"\n{'=' * 120}")
    print("Résumé global:")
    total_comparisons = sum(r["total"] for r in results.values())
    total_matches = sum(r["matches"] for r in results.values())
    total_errors = sum(r["errors"] for r in results.values())
    total_ocr_errors = sum(r["ocr_errors"] for r in results.values())
    global_accuracy = total_matches / total_comparisons if total_comparisons > 0 else 0.0

    # Calculer l'accuracy globale sans OCR
    total_no_ocr = sum(r["total_no_ocr"] for r in results.values())
    total_matches_no_ocr = sum(r["matches_no_ocr"] for r in results.values())
    global_accuracy_no_ocr = total_matches_no_ocr / total_no_ocr if total_no_ocr > 0 else 0.0

    print(f"Total de comparaisons: {total_comparisons}")
    print(f"Total de matches: {total_matches}")
    print(f"Total d'erreurs: {total_errors}")
    print(f"Total d'erreurs OCR: {total_ocr_errors}")
    print(f"Accuracy globale: {global_accuracy * 100:.2f}%")
    print(f"Accuracy globale (sans OCR): {global_accuracy_no_ocr * 100:.2f}% ({total_matches_no_ocr}/{total_no_ocr})")
    print(f"{'=' * 120}\n")
