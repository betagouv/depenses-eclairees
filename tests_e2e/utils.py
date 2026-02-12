import ast
import json
import logging
import os
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from tqdm import tqdm

from docia.file_processing.processor.analyze_content import analyze_file_text
from docia.file_processing.processor.attributes_query import ATTRIBUTES

logger = logging.getLogger(__name__)


def compare_exact_string(llm_value, ref_value):
    # Gestion des valeurs vides ou None
    if not llm_value and not ref_value:
        return True

    if not llm_value or not ref_value:
        return False

    return llm_value == ref_value


def remove_accents(text: str) -> str:
    """Remove accents and diacritical marks from a string.

    à -> a, é -> e, ...
    """
    # Normalize the text to decompose accented characters
    normalized_text = unicodedata.normalize("NFD", text)
    # Remove combining characters (diacritical marks)
    return "".join(char for char in normalized_text if not unicodedata.combining(char))


def normalize_string(s):
    """Normalise une chaîne de caractères : minuscule et sans caractères spéciaux."""
    if pd.isna(s) or s == "":
        return ""
    s = str(s).lower()
    # Retirer les accents
    s = remove_accents(s)
    # Supprime les caractères spéciaux (garde seulement les lettres, chiffres et espaces)
    s = re.sub(r"[^a-z0-9\s]", "", s)
    # Supprime les espaces multiples
    s = re.sub(r"\s+", " ", s).strip()
    return s


def compare_normalized_string(actual, expected):
    """Compare deux chaînes normalisées."""

    if not actual and not expected:
        return True

    if not actual or not expected:
        return False

    return normalize_string(actual.replace(" ", "")) == normalize_string(expected.replace(" ", ""))


def df_analyze_content(
    df: pd.DataFrame,
    df_attributes: pd.DataFrame,
    llm_model: str | None = None,
    temperature: float = 0.0,
    max_workers: int = 4,
    debug_mode: bool = False,
) -> pd.DataFrame:
    """
    Analyse le contenu d'un DataFrame en parallèle en utilisant l'API LLM.

    Args:
        debug_mode: Si True, log le nom du fichier avec l'heure de début et le temps
            de réponse LLM pour chaque ligne.

    Returns:
        DataFrame avec les réponses du LLM ajoutées
    """
    dfResult = df.copy()
    dfResult["llm_response"] = None
    dfResult["structured_data"] = None
    dfResult["error"] = None

    def process_row(idx):
        row = df.loc[idx]
        filename = row["filename"]
        t0 = time.perf_counter() if debug_mode else None
        if debug_mode:
            logger.warning(f"{filename} - début à {time.strftime('%H:%M:%S', time.localtime())}")

        kwargs = {
            "text": row["text"],
            "document_type": row["classification"],
            "temperature": temperature,
        }
        if llm_model:
            kwargs["llm_model"] = llm_model

        try:
            out = analyze_file_text(**kwargs)
            result = {"llm_response": out["llm_response"], "structured_data": out["structured_data"], "error": None}
        except Exception as e:
            logger.exception(f"Erreur lors de l'analyse du fichier {filename}: {e}")
            result = {"llm_response": None, "structured_data": None, "error": f"Erreur lors de l'analyse: {str(e)}"}

        if debug_mode:
            logger.warning(f"{filename} - réponse LLM reçue en {time.perf_counter() - t0:.2f}s")
        return idx, result

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_row, i) for i in df.index]

        for future in tqdm(as_completed(futures), total=len(futures), desc="Traitement des PJ"):
            idx, result = future.result()
            for key, value in result.items():
                dfResult.at[idx, key] = value

    return dfResult


def analyze_content_quality_test(df_test: pd.DataFrame, document_type: str, multi_line_coef=1, use_cache=False, max_workers=10, llm_model="openweight-medium"):
    """Test de qualité des informations extraites par le LLM.

    Args:
        df_test: DataFrame contenant les données de test.
        document_type: Type de document à analyser.
        multi_line_coef: Coefficient de multiplication des lignes.
        use_cache: Si True, utilise le cache pour éviter de relancer l'analyse.
        debug_mode: Si True, log le nom du fichier et les temps (début / durée LLM) pour chaque ligne.
    """

    if multi_line_coef > 1:
        df_test = pd.concat([df_test for x in range(multi_line_coef)]).reset_index(drop=True)

    # Création du DataFrame pour l'analyse
    df_analyze = pd.DataFrame()
    df_analyze["filename"] = df_test["filename"]
    df_analyze["classification"] = document_type
    df_analyze["text"] = df_test["text"]

    # Vérification du cache
    cache_file = f"/tmp/cache_results_{document_type}.json"
    if use_cache and os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            cached_data = json.load(f)
        df_result = pd.DataFrame(cached_data)
    else:
        # Analyse du contenu avec df_analyze_content
        df_result = df_analyze_content(
            df=df_analyze,
            df_attributes=ATTRIBUTES,
            max_workers=max_workers,
            temperature=0.1,
            llm_model=llm_model,
            debug_mode=debug_mode,
        )

    # Sauvegarde des résultats dans le cache
    if use_cache:
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "w") as f:
            json.dump(df_result.to_dict(orient="records"), f)

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


def _get_value_by_dotted_key(data, key):
    """Retrieve a value from a nested dictionary using a dotted key notation.

    Args:
        data: The dictionary to extract the value from.
        key: The key to retrieve the value. Can be a simple key (e.g., 'title'),
             a nested key (e.g., 'marche.struct'), or a wildcard key for lists
             (e.g., 'lots.*.title').

    Returns:
        The value corresponding to the key in the nested dictionary.

    Examples:
        >>> data = {'title': 'Test', 'marche': {'struct': 'Value'}, 'lots': [{'title': 'Lot1'}, {'title': 'Lot2'}]}
        >>> _get_value_by_dotted_key(data, 'title')
        'Test'
        >>> _get_value_by_dotted_key(data, 'marche.struct')
        'Value'
        >>> _get_value_by_dotted_key(data, 'lots.*.title')
        ['Lot1', 'Lot2']
    """
    if data is None:
        return None
    if "." not in key:
        return data.get(key)
    else:
        key, key_suffix = key.split(".", 1)
        if key == "*":
            if not isinstance(data, list):
                return None
            return [_get_value_by_dotted_key(item, key_suffix) for item in data]
        else:
            return _get_value_by_dotted_key(data.get(key), key_suffix)


def check_quality_one_field(df_merged, col_to_test, comparison_functions, only_errors=False):
    # ============================================================================
    # COMPARAISON POUR UNE COLONNE SPÉCIFIQUE
    # ============================================================================

    comparison_func = comparison_functions[col_to_test]

    print(f"\n{'=' * 80}")
    print(f"Comparaison pour la colonne: {col_to_test}")
    print(f"{'=' * 80}\n")

    # Boucle de comparaison simple
    for idx, row in df_merged.iterrows():
        filename = row.get("filename", "unknown")

        llm_data = row.get("structured_data", None)

        # Extraire les valeurs
        ref_val = _get_value_by_dotted_key(row, col_to_test)
        llm_val = _get_value_by_dotted_key(llm_data, col_to_test)

        # Extraction des pbm OCR
        pbm_ocr = col_to_test in row["pbm_ocr"]

        # Comparer les valeurs
        try:
            match_result = comparison_func(llm_val, ref_val)
            if only_errors and match_result:
                continue
            status = "✅ MATCH" if match_result else "❌ NO MATCH"
            print(f"{status} | {filename} | OCR {'❌' if pbm_ocr else '✅'}")
            print(f"  LLM: {llm_val!r}")
            print(f"  REF: {ref_val!r}")
            print()
        except Exception as e:
            print(f"❌ ERREUR | {filename}: {str(e)} | OCR {'❌' if pbm_ocr else '✅'}")
            print(f"  LLM: {llm_val!r}")
            print(f"  REF: {ref_val!r}")
            print()


def check_quality_one_row(df_merged, row_idx_to_test, comparison_functions, excluded_columns=None, only_errors=False):
    # ============================================================================
    # COMPARAISON POUR UNE LIGNE SPÉCIFIQUE
    # ============================================================================
    excluded_columns = excluded_columns or []

    if row_idx_to_test >= len(df_merged):
        print(f"\n❌ Index {row_idx_to_test} invalide. Le DataFrame contient {len(df_merged)} lignes.\n")
    else:
        row = df_merged.iloc[row_idx_to_test]
        filename = row.get("filename", "unknown")

        print(f"\n{'=' * 80}")
        print(f"Comparaison pour la ligne {row_idx_to_test} (fichier: {filename})")
        print(f"{'=' * 80}\n")

        llm_data = row.get("structured_data", None)

        # Comparer toutes les colonnes (sauf exclues)
        for col, comparison_func in comparison_functions.items():
            if col in excluded_columns:
                continue

            # Extraire les valeurs
            ref_val = _get_value_by_dotted_key(row, col)
            llm_val = _get_value_by_dotted_key(llm_data, col)

            # Extraction des pbm OCR
            pbm_ocr = col in row["pbm_ocr"]

            # Comparer les valeurs
            try:
                match_result = comparison_func(llm_val, ref_val)
                match_result = bool(match_result) if not isinstance(match_result, bool) else match_result
                if only_errors and match_result:
                    continue
                status = "✅ MATCH" if match_result else "❌ NO MATCH"
                print(f"{status} | {col} | OCR {'❌' if pbm_ocr else '✅'}")
                print(f"  LLM: {llm_val!r}")
                print(f"  REF: {ref_val!r}")
                print()
            except Exception as e:
                print(f"❌ ERREUR | {col}: {str(e)} | OCR {'❌' if pbm_ocr else '✅'}")
                print(f"  LLM: {llm_val!r}")
                print(f"  REF: {ref_val!r}")
                print()


def get_fields_with_comparison_errors(df_merged, comparison_functions, excluded_columns=None):
    """
    Pour chaque fichier (ligne) de df_merged, retourne la liste des champs pour lesquels
    la comparaison entre la valeur LLM et la valeur par défaut (référence) échoue.

    Args:
        df_merged: DataFrame fusionné (résultats LLM + valeurs de référence).
        comparison_functions: Dictionnaire colonne -> fonction de comparaison.
        excluded_columns: Liste de colonnes à exclure de la vérification.

    Returns:
        dict: {filename: [champ1, champ2, ...]} pour chaque fichier. Les clés sont les
        noms de fichiers, les valeurs sont les listes de champs en erreur de comparaison.
    """
    excluded_columns = excluded_columns or []

    result = {}
    for idx, row in df_merged.iterrows():
        filename = row.get("filename", "unknown")
        llm_data = row.get("structured_data", None)
        errors = []

        for col, comparison_func in comparison_functions.items():
            if col in excluded_columns:
                continue

            ref_val = _get_value_by_dotted_key(row, col)
            llm_val = _get_value_by_dotted_key(llm_data, col) if llm_data is not None else None

            try:
                match_result = comparison_func(llm_val, ref_val)
                if not (bool(match_result) if not isinstance(match_result, bool) else match_result):
                    errors.append(col)
            except Exception:
                errors.append(col)

        result[filename] = errors

    return result


def _parse_best_test_errors(row):
    """Retourne la liste des champs en erreur du meilleur test pour cette ligne (colonne optionnelle)."""
    val = row.get("best_test_comparison_errors")
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        val = val.strip()
        if not val or val in ("[]", "nan"):
            return []
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            parsed = ast.literal_eval(val)
            return list(parsed) if isinstance(parsed, (list, tuple)) else []
        except (ValueError, SyntaxError, TypeError):
            return []
    return []


def check_global_statistics(df_merged, comparison_functions, excluded_columns=None):
    # ============================================================================
    # STATISTIQUES GLOBALES DE COMPARAISON
    # ============================================================================
    excluded_columns = excluded_columns or []
    use_best_ref = "best_test_comparison_errors" in df_merged.columns

    print(f"\n{'=' * 80}")
    print("STATISTIQUES GLOBALES DE COMPARAISON")
    print(f"{'=' * 80}\n")

    results = {}

    # Comparaison pour chaque colonne (sauf exclues)
    for col, comparison_func in comparison_functions.items():
        # Ignorer les colonnes exclues
        if col in excluded_columns:
            continue

        matches = []
        errors = []
        ocr_errors_count = 0
        matches_no_ocr = []
        regressions_vs_best = 0
        improvements_vs_best = 0

        # Comparer toutes les lignes pour cette colonne
        for idx, row in df_merged.iterrows():
            filename = row.get("filename", "unknown")

            # Vérifier les erreurs OCR pour cette colonne
            pbm_ocr = False
            if col in row.get("pbm_ocr", []):
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
            ref_val = _get_value_by_dotted_key(row, col)
            llm_val = _get_value_by_dotted_key(structured_data, col)

            # Comparer les valeurs
            try:
                match_result = comparison_func(llm_val, ref_val)
                match_result = bool(match_result) if not isinstance(match_result, bool) else match_result
                matches.append(match_result)
                # Si pas de problème OCR, on compte aussi dans matches_no_ocr
                if not pbm_ocr:
                    matches_no_ocr.append(match_result)

                # Écart au meilleur test (si colonne optionnelle présente)
                if use_best_ref:
                    best_errors = _parse_best_test_errors(row)
                    best_had_error = col in best_errors
                    current_has_error = not match_result
                    if not best_had_error and current_has_error:
                        regressions_vs_best += 1
                    elif best_had_error and not current_has_error:
                        improvements_vs_best += 1
            except Exception as e:
                errors.append(f"{filename}: Error in comparison_func: {str(e)}")
                matches.append(False)
                # Si pas de problème OCR, on ajoute aussi à matches_no_ocr
                if not pbm_ocr:
                    matches_no_ocr.append(False)
                if use_best_ref:
                    best_errors = _parse_best_test_errors(row)
                    best_had_error = col in best_errors
                    if not best_had_error:
                        regressions_vs_best += 1

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
        if use_best_ref:
            results[col]["delta_vs_best"] = regressions_vs_best - improvements_vs_best
            results[col]["regressions_vs_best"] = regressions_vs_best
            results[col]["improvements_vs_best"] = improvements_vs_best

    # Affichage des statistiques
    header_parts = [
        f"{'Colonne':<35}",
        f"{'Total':<6}",
        f"{'Matches':<8}",
        f"{'Erreurs':<8}",
        f"{'OCR Errors':<10}",
        f"{'Accuracy':<10}",
        f"{'Accuracy (no OCR)':<18}",
    ]
    if use_best_ref:
        header_parts.append(f"{'(+)':<14}")
        header_parts.append(f"{'(-)':<14}")
    print(" | ".join(header_parts))
    print("-" * (160 if use_best_ref else 120))

    for col, result in results.items():
        row_parts = [
            f"{col:<35}",
            f"{result['total']:<6}",
            f"{result['matches']:<8}",
            f"{result['errors']:<8}",
            f"{result['ocr_errors']:<10}",
            f"{result['accuracy'] * 100:>6.2f}%",
            f"{result['accuracy_no_ocr'] * 100:>14.2f}%",
        ]
        if use_best_ref:
            imp = result.get("improvements_vs_best", 0)
            reg = result.get("regressions_vs_best", 0)
            row_parts.append(f"{'+' + str(imp) if imp else '0':<14}")
            row_parts.append(f"{'-' + str(reg) if reg else '0':<14}")
        print(" | ".join(row_parts))

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
    if use_best_ref:
        total_imp = sum(r.get("improvements_vs_best", 0) for r in results.values())
        total_reg = sum(r.get("regressions_vs_best", 0) for r in results.values())
        print(f"Écart au meilleur test: Améliorations +{total_imp}, Régressions -{total_reg}")
    print(f"{'=' * (160 if use_best_ref else 120)}\n")

    return global_accuracy
