import ast
import json
import logging
import os
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

import pandas as pd

from docia.file_processing.processor.analyze_content import LLMClient, analyze_file_text

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


def compare_duration(actual, expected):
    """Compare duree : nombre de mois, comparaison exacte."""

    # Gestion des valeurs vides ou None
    if not actual and not expected:
        return True

    if not actual or not expected:
        return False
    try:
        if actual.get("duree_initiale") != expected.get("duree_initiale"):
            return False
        if actual.get("duree_reconduction") != expected.get("duree_reconduction"):
            return False
        if actual.get("nb_reconductions") != expected.get("nb_reconductions"):
            return False
        if actual.get("delai_tranche_optionnelle") != expected.get("delai_tranche_optionnelle"):
            return False
        return True
    except (ValueError, TypeError):
        return False


def compare_address(actual, expected):
    """Compare l'adresse : comparaison des valeurs selon la structure JSON.

    Structure attendue : {
        'numero_voie': 'le numéro de voie',
        'nom_voie': 'le nom de la voie',
        'complement_adresse': 'le complément d'adresse éventuel',
        'code_postal': 'le code postal',
        'ville': 'la ville',
        'pays': 'le pays'
    }
    """
    # Gestion des valeurs vides ou None
    if not actual and not expected:
        return True

    if not actual or not expected:
        return False

    # Liste des champs à comparer
    fields = ["numero_voie", "nom_voie", "complement_adresse", "code_postal", "ville", "pays"]

    # Comparer chaque champ
    for field in fields:
        llm_field_val = actual.get(field, "")
        ref_field_val = expected.get(field, "")

        # Normaliser les valeurs vides
        def _normalize(s):
            s = s.strip().upper()
            s = remove_accents(s)
            s = re.sub(r"[-']", " ", s)
            s = re.sub(r"\s\s", " ", s)
            return s

        llm_field_val = _normalize(llm_field_val)
        ref_field_val = _normalize(ref_field_val)

        # Comparer les valeurs du champ
        if llm_field_val != ref_field_val:
            return False

    return True


def compare_mandatee_bank_account(actual, expected):
    """Compare rib_mandataire : format JSON, comparaison des champs IBAN et banque.

    - Si les deux IBAN sont non vides, on valide si compare_normalized_string(iban, iban) renvoie True.
    - Si les deux IBAN sont vides ou None, on valide si les banques sont équivalentes.
    - Si un seul IBAN est non vide, on renvoie False.
    """
    if not actual and not expected:
        return True

    if not actual or not expected:
        return False

    llm_iban = actual.get("iban")
    ref_iban = expected.get("iban")
    llm_banque = normalize_string(actual.get("banque", ""))
    ref_banque = normalize_string(expected.get("banque", ""))

    if llm_iban and ref_iban:
        return compare_normalized_string(llm_iban, ref_iban)
    if not llm_iban and not ref_iban:
        return llm_banque == ref_banque
    return False


# Prompts pour compare_with_llm : chaînes à compléter avec {actual} et {expected}
DEFAULT_PROMPT_COMPARE_WITH_LLM = {
    "system": "Vous êtes un expert en analyse sémantique de documents juridiques. "
    "Votre rôle est d'évaluer la proximité de sens entre deux descriptions d'objets.",
    "user": """
            Compare les deux descriptions d'objet suivantes et détermine si elles décrivent 
            la même chose ou des choses sémantiquement équivalentes.

            Valeur extraite par le LLM: {actual}
            Valeur de référence: {expected}

            Tu dois IMPÉRATIVEMENT répondre UNIQUEMENT avec un JSON valide, sans aucun autre texte, avec cette 
            structure exacte :
            {{
                "sont_equivalentes": true ou false,
                "explication": "brève explication de votre analyse"
            }}
        """,
}

PROMPT_OBJECT = {
    "system": "Vous êtes un expert en analyse sémantique de documents juridiques. "
    "Votre rôle est d'évaluer si deux descriptions d'objets décrivent la même chose "
    "ou des choses sémantiquement équivalentes.",
    "user": """
        Compare les deux descriptions d'objets suivantes et détermine si elles décrivent 
        la même chose ou des choses sémantiquement équivalentes.

        Valeur extraite par le LLM: {actual}
        Valeur de référence: {expected}

        Analyse si ces deux descriptions ont le même sens ou un sens proche. Prends en compte :
        - Les synonymes et formulations équivalentes
        - Les variations de style ou de formulation
        - L'essence et le contenu principal, pas seulement la forme exacte

        Tu dois IMPÉRATIVEMENT répondre UNIQUEMENT avec un JSON valide, sans aucun autre texte, avec cette 
        structure exacte:
        {{
            "sont_equivalentes": true ou false,
            "explication": "brève explication de votre analyse"
        }}
    """,
}

PROMPT_BENEFICIARY_ADMINISTRATION = {
    "system": "Vous êtes un expert en analyse de documents administratifs publics. "
    "Votre rôle est d'évaluer si deux chaînes désignent la même administration bénéficiaire (structure "
    "administrative ou publique bénéficiaire d'une commande) "
    "ou deux entités publiques équivalentes.",
    "user": """
            Compare les deux mentions suivantes concernant l'administration bénéficiaire d'un 
            contrat ou acte administratif, et détermine si elles désignent la même structure, 
            entité ou administration bénéficiaire, ou des administrations équivalentes (avec 
            ou sans variation d'intitulé ou de formulation). Par exemple, si la valeur extraite 
            par le LLM est plus précise que la valeur de référence, alors on considère que les 
            deux administrations sont équivalentes.

            Valeur extraite par le LLM: {actual}
            Valeur de référence: {expected}

            Analyse si ces deux valeurs réfèrent à la même administration ou à une entité équivalente. 
            Prends en compte :
            - Les synonymes, reformulations, différences d'intitulé ou d'abréviation (par exemple, 
              'Préfecture de la région Île-de-France' vs 'Préfecture régionale Île-de-France')
            - Le contexte administratif ou territorial, les rôles correspondant aux structures (par exemple, 
              un intitulé de direction qui désigne l'administration bénéficiaire)
            - Le fait que certaines valeurs peuvent préciser un service ou une direction interne d'une administration 
              (cela compte pour la même administration si l'essentiel concorde)
            - Le format doit être le nom complet, sans acronymes sauf s'ils sont officiels et connus

            Tu dois IMPÉRATIVEMENT répondre UNIQUEMENT avec un JSON valide, sans aucun autre texte, avec cette 
            structure exacte :
            {{
                "sont_equivalentes": true ou false,
                "explication": "brève explication de votre analyse"
            }}
        """,
}


def compare_with_llm(
    actual,
    expected,
    prompt=None,
    llm_model="openweight-medium",
):
    """Compare deux valeurs en utilisant un LLM comme juge pour évaluer la proximité de sens.

    Args:
        actual: Valeur extraite par le LLM.
        expected: Valeur de référence.
        prompt: Dict avec clés "system" et "user" (chaîne template avec {actual} et {expected}).
                Par défaut: DEFAULT_PROMPT_COMPARE_WITH_LLM.
        llm_model: Modèle LLM à utiliser.
    """
    if prompt is None:
        prompt = DEFAULT_PROMPT_COMPARE_WITH_LLM
    # Gestion des valeurs vides ou None
    if not actual and not expected:
        return True

    if not actual or not expected:
        return False

    user_content = prompt["user"].format(actual=actual, expected=expected)

    try:
        llm_env = LLMClient()
        system_prompt = prompt.get("system", "")
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}]
        result = llm_env.ask_llm(
            messages=messages, model=llm_model, response_format={"type": "json_object"}, temperature=0
        )
        return bool(result.content.get("sont_equivalentes", False))
    except Exception as e:
        logger.error(f"Error calling LLM for compare_with_llm: {e}")
        return False


def df_analyze_content(
    df: pd.DataFrame,
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
            result = {"llm_response": out.llm_response, "structured_data": out.structured_data, "error": None}
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


def analyze_content_quality_test(
    df_test: pd.DataFrame,
    document_type: str,
    multi_line_coef=1,
    use_cache=False,
    max_workers=10,
    llm_model="mistral-medium-2508",
    debug_mode=False,
):
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
            max_workers=max_workers,
            temperature=0,
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


def _format_leaf(val) -> str:
    """Format une valeur feuille pour l'affichage (traitée comme string)."""
    return str(val)


def print_json_diff(ref_data, llm_data, path_prefix: str = ""):
    """
    Affiche les différences entre deux JSON (ref vs llm) en parcourant les clés de la référence.

    Pour chaque feuille : affiche le chemin et côte à côte REF | LLM.
    Les feuilles avec la même valeur sont affichées telles quelles ; celles qui diffèrent
    sont préfixées par ❌.
    Les clés présentes seulement dans REF ou seulement dans LLM sont aussi marquées ❌.
    """
    # Au moins l'un des deux n'est pas un dict -> feuille
    if not isinstance(ref_data, dict) or not isinstance(llm_data, dict):
        ref_str = _format_leaf(ref_data)
        llm_str = _format_leaf(llm_data)
        path = path_prefix or "(racine)"
        diff = ref_str != llm_str
        prefix = "    ❌ " if diff else "      "
        print(f"{prefix}{path}:  REF={ref_str!s}  |  LLM={llm_str!s}")
        return

    if ref_data is None and llm_data is None:
        return

    ref_keys = set(ref_data.keys())
    llm_keys = set(llm_data.keys())

    only_ref = ref_keys - llm_keys
    only_llm = llm_keys - ref_keys
    common = ref_keys & llm_keys

    for k in sorted(only_ref):
        print(f"    ❌ [REF seulement] {path_prefix + '.' + k if path_prefix else k}")
    for k in sorted(only_llm):
        print(f"    ❌ [LLM seulement] {path_prefix + '.' + k if path_prefix else k}")

    for k in sorted(common):
        path = f"{path_prefix}.{k}" if path_prefix else k
        ref_v = ref_data[k]
        llm_v = llm_data[k]

        if isinstance(ref_v, dict) and isinstance(llm_v, dict):
            print_json_diff(ref_v, llm_v, path_prefix=path)
        elif isinstance(ref_v, dict) or isinstance(llm_v, dict):
            # L'un est dict, l'autre non : afficher comme feuille
            ref_str = _format_leaf(ref_v)
            llm_str = _format_leaf(llm_v)
            diff = ref_str != llm_str
            prefix = "    ❌ " if diff else "      "
            print(f"{prefix}{path}:  REF={ref_str!s}  |  LLM={llm_str!s}")
        else:
            ref_str = _format_leaf(ref_v)
            llm_str = _format_leaf(llm_v)
            diff = ref_str != llm_str
            prefix = "    ❌ " if diff else "      "
            print(f"{prefix}{path}:  REF={ref_str!s}  |  LLM={llm_str!s}")


def check_quality_one_field(df_merged, col_to_test, comparison_functions, only_errors=False):
    # ============================================================================
    # COMPARAISON POUR UNE COLONNE SPÉCIFIQUE
    # ============================================================================

    comparison_func = _get_comparison_function_for_column(col_to_test, comparison_functions)

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

        # Comparer les valeurs
        try:
            match_result = comparison_func(llm_val, ref_val)
            if only_errors and match_result:
                continue
            status = "✅ MATCH" if match_result else "❌ NO MATCH"
            print(f"{status} | {filename}")
            print(f"  LLM: {llm_val!r}")
            print(f"  REF: {ref_val!r}")
            if not match_result and isinstance(ref_val, dict) and isinstance(llm_val, dict):
                print("  Diff détaillée (feuilles REF | LLM):")
                print_json_diff(ref_val, llm_val)
            elif not match_result and isinstance(ref_val, list) and isinstance(llm_val, list):
                print("  Diff détaillée (listes REF | LLM):")
                for i in range(min(len(ref_val), len(llm_val))):
                    print(f"  {i}:")
                    print_json_diff(ref_val[i], llm_val[i])
                if len(ref_val) != len(llm_val):
                    print(f"  Listes de taille différente: REF={len(ref_val)}, LLM={len(llm_val)}")
            print()
        except Exception as e:
            print(f"❌ ERREUR | {filename}: {str(e)}")
            print(f"  LLM: {llm_val!r}")
            print(f"  REF: {ref_val!r}")
            print()


def check_quality_by_error_type(
    df_merged,
    comparison_functions,
    mode: str = "FN",
    excluded_columns=None,
    included_columns=None,
):
    """
    Affiche les comparaisons qui tombent dans une cellule d'erreur de la matrice de confusion
    (comme ``check_global_statistics``) : omissions FN, incompréhensions FP2, hallucinations FP.

    Même présentation que ``check_quality_one_field`` pour chaque cas (valeurs LLM/REF, diff
    dict/listes si pertinent).

    Args:
        df_merged: jeu fusionné (référence + ``structured_data`` LLM).
        comparison_functions: dict colonne -> fonction de comparaison.
        mode: ``\"FN\"``, ``\"FP2\"`` ou ``\"FP\"``.
        excluded_columns / included_columns: filtre des colonnes (voir ``_get_columns_to_compare``).
    """
    allowed_modes = frozenset({"FN", "FP2", "FP"})
    if mode not in allowed_modes:
        raise ValueError(f"mode doit être l'un de {sorted(allowed_modes)}, reçu: {mode!r}")

    columns_to_compare = _get_columns_to_compare(
        comparison_functions,
        excluded_columns=excluded_columns,
        included_columns=included_columns,
    )

    mode_titles = {
        "FN": "omissions (FN)",
        "FP2": "incompréhensions (FP2)",
        "FP": "hallucinations (FP)",
    }

    print(f"\n{'=' * 80}")
    print(f"Comparaisons en erreur — {mode_titles[mode]}")
    print(f"{'=' * 80}\n")

    total_shown = 0
    for col in columns_to_compare:
        comparison_func = _get_comparison_function_for_column(col, comparison_functions)
        for _idx, row in df_merged.iterrows():
            filename = row.get("filename", "unknown")
            ref_val = _get_value_by_dotted_key(row, col)
            ref_non_null = _field_value_is_non_null_non_empty(ref_val)
            structured_data = row.get("structured_data", None)
            compare_error = None

            if structured_data is None or pd.isna(structured_data):
                llm_val = None
                llm_non_null = False
                match_result = False
            else:
                llm_val = _get_value_by_dotted_key(structured_data, col)
                llm_non_null = _field_value_is_non_null_non_empty(llm_val)
                try:
                    match_result = comparison_func(llm_val, ref_val)
                    match_result = bool(match_result) if not isinstance(match_result, bool) else match_result
                except Exception as e:
                    match_result = False
                    compare_error = str(e)

            _dvp, dfp2, dfn, _dvn, dfp = _classify_confusion_cell(ref_non_null, match_result, llm_non_null)
            if mode == "FN" and dfn != 1:
                continue
            if mode == "FP2" and dfp2 != 1:
                continue
            if mode == "FP" and dfp != 1:
                continue

            total_shown += 1
            if compare_error is not None:
                print(f"❌ ERREUR | {filename} | {col}: {compare_error}")
            else:
                print(f"❌ NO MATCH | {filename} | {col}")
            print(f"  LLM: {llm_val!r}")
            print(f"  REF: {ref_val!r}")
            if compare_error is None and not match_result and isinstance(ref_val, dict) and isinstance(llm_val, dict):
                print("  Diff détaillée (feuilles REF | LLM):")
                print_json_diff(ref_val, llm_val)
            elif compare_error is None and not match_result and isinstance(ref_val, list) and isinstance(llm_val, list):
                print("  Diff détaillée (listes REF | LLM):")
                for i in range(min(len(ref_val), len(llm_val))):
                    print(f"  {i}:")
                    print_json_diff(ref_val[i], llm_val[i])
                if len(ref_val) != len(llm_val):
                    print(f"  Listes de taille différente: REF={len(ref_val)}, LLM={len(llm_val)}")
            print()

    print(f"Total : {total_shown} occurrence(s) de type {mode}\n")


def _get_columns_to_compare(comparison_functions, excluded_columns=None, included_columns=None):
    """Construit la liste ordonnée des colonnes a comparer.

    Par defaut, toutes les colonnes definies dans comparison_functions sont comparees.
    Si included_columns est fourni, seules ces colonnes sont conservees dans cet ordre.
    Les clés imbriquées (ex: ``forme_marche.lot_concerne.numero_lot``) sont acceptées
    si leur racine est présente dans ``comparison_functions``.
    excluded_columns est applique en dernier.
    """
    excluded_columns = set(excluded_columns or [])
    available_columns = set(comparison_functions.keys())

    if included_columns is None:
        selected_columns = list(comparison_functions.keys())
    else:
        selected_columns = []
        invalid_columns = []
        for col in included_columns:
            root_col = col.split(".", 1)[0]
            if col == "duree" or col in available_columns:
                selected_columns.append(col)
                continue
            if "." in col and root_col in available_columns:
                selected_columns.append(col)
                continue
            invalid_columns.append(col)
        assert not invalid_columns, f"Columns {invalid_columns} not in {sorted(available_columns)}"

    return [col for col in selected_columns if col not in excluded_columns]


def _get_comparison_function_for_column(col, comparison_functions):
    """
    Retourne la fonction de comparaison pour une colonne, y compris clé imbriquée.

    - Colonne explicite (ex: 'forme_marche'): fonction dédiée dans comparison_functions.
    - Clé imbriquée (ex: 'forme_marche.lot_concerne.numero_lot'):
      comparaison feuille avec compare_exact_string.
    - 'duree' garde sa comparaison dédiée quand utilisé tel quel.
    - Les sous-clés (dont ``duree.*``) sont comparées comme des feuilles.
    """
    if col in comparison_functions:
        return comparison_functions[col]

    if "." in col:
        root_col = col.split(".", 1)[0]
        if root_col in comparison_functions:
            return compare_exact_string

    raise KeyError(f"No comparison function found for column '{col}'")


def check_quality_one_row(
    df_merged,
    row_idx_to_test,
    comparison_functions,
    excluded_columns=None,
    included_columns=None,
    only_errors=False,
):
    # ============================================================================
    # COMPARAISON POUR UNE LIGNE SPÉCIFIQUE
    # ============================================================================
    columns_to_compare = _get_columns_to_compare(
        comparison_functions,
        excluded_columns=excluded_columns,
        included_columns=included_columns,
    )

    if row_idx_to_test >= len(df_merged):
        print(f"\n❌ Index {row_idx_to_test} invalide. Le DataFrame contient {len(df_merged)} lignes.\n")
    else:
        row = df_merged.iloc[row_idx_to_test]
        filename = row.get("filename", "unknown")

        print(f"\n{'=' * 80}")
        print(f"Comparaison pour la ligne {row_idx_to_test} (fichier: {filename})")
        print(f"{'=' * 80}\n")

        llm_data = row.get("structured_data", None)

        # Comparer les colonnes sélectionnées
        for col in columns_to_compare:
            comparison_func = _get_comparison_function_for_column(col, comparison_functions)
            # Extraire les valeurs
            ref_val = _get_value_by_dotted_key(row, col)
            llm_val = _get_value_by_dotted_key(llm_data, col)

            # Comparer les valeurs
            try:
                match_result = comparison_func(llm_val, ref_val)
                match_result = bool(match_result) if not isinstance(match_result, bool) else match_result
                if only_errors and match_result:
                    continue
                status = "✅ MATCH" if match_result else "❌ NO MATCH"
                print(f"{status} | {col}")
                print(f"  LLM: {llm_val!r}")
                print(f"  REF: {ref_val!r}")
                print()
            except Exception as e:
                print(f"❌ ERREUR | {col}: {str(e)}")
                print(f"  LLM: {llm_val!r}")
                print(f"  REF: {ref_val!r}")
                print()


def get_fields_with_comparison_errors(
    df_merged,
    comparison_functions,
    excluded_columns=None,
    included_columns=None,
):
    """
    Pour chaque fichier (ligne) de df_merged, retourne la liste des champs pour lesquels
    la comparaison entre la valeur LLM et la valeur par défaut (référence) échoue.

    Args:
        df_merged: DataFrame fusionné (résultats LLM + valeurs de référence).
        comparison_functions: Dictionnaire colonne -> fonction de comparaison.
        excluded_columns: Liste de colonnes à exclure de la vérification.
        included_columns: Liste de colonnes a inclure dans la verification.

    Returns:
        dict: {filename: [champ1, champ2, ...]} pour chaque fichier. Les clés sont les
        noms de fichiers, les valeurs sont les listes de champs en erreur de comparaison.
    """
    columns_to_compare = _get_columns_to_compare(
        comparison_functions,
        excluded_columns=excluded_columns,
        included_columns=included_columns,
    )

    result = {}
    for idx, row in df_merged.iterrows():
        filename = row.get("filename", "unknown")
        llm_data = row.get("structured_data", None)
        errors = []

        for col in columns_to_compare:
            comparison_func = _get_comparison_function_for_column(col, comparison_functions)

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


def _field_value_is_non_null_non_empty(val) -> bool:
    """True si une valeur de champ (référence ou LLM) est considérée renseignée (non vide / non nulle)."""
    if val is None:
        return False
    if isinstance(val, bool):
        return True
    if isinstance(val, (dict, list, tuple, set)):
        return len(val) > 0
    if isinstance(val, str):
        return bool(val.strip())
    try:
        if pd.isna(val):
            return False
    except (ValueError, TypeError):
        pass
    return True


def _fmt_ratio_pct(num: int, den: int, ratio: float) -> str:
    if den <= 0:
        return "n/d"
    return f"{num}/{den} = {ratio * 100:.1f}%"


def _classify_confusion_cell(
    ref_non_null: bool, match_result: bool, llm_non_null: bool
) -> tuple[int, int, int, int, int]:
    """
    Retourne un incrément (vp, fp2, fn, vn, fp) — une seule cellule vaut 1, les autres 0.
    """
    if ref_non_null:
        if match_result:
            return (1, 0, 0, 0, 0)
        if llm_non_null:
            return (0, 1, 0, 0, 0)
        return (0, 0, 1, 0, 0)
    if match_result:
        return (0, 0, 0, 1, 0)
    if llm_non_null:
        return (0, 0, 0, 0, 1)
    return (0, 0, 0, 1, 0)


def _fmt_quality_metric_columns(
    *,
    vp: int,
    fp2: int,
    fn: int,
    vn: int,
    fp: int,
    w: int,
) -> tuple[str, str, str]:
    """Trois colonnes : Détection, Exactitude, Absence justifiée (taux de réussite)."""
    det_den = vp + fp2 + fn
    ex_den = vp + fp2
    abs_den = fp + vn
    det_num = vp + fp2
    ex_num = vp
    abs_num = vn
    d = _fmt_ratio_pct(det_num, det_den, det_num / det_den) if det_den > 0 else "n/d"
    e = _fmt_ratio_pct(ex_num, ex_den, ex_num / ex_den) if ex_den > 0 else "n/d"
    a = _fmt_ratio_pct(abs_num, abs_den, abs_num / abs_den) if abs_den > 0 else "n/d"
    return (f"{d:<{w}}", f"{e:<{w}}", f"{a:<{w}}")


def _print_confusion_matrix_visual(
    counts: tuple[int, int, int, int, int] | None = None,
) -> None:
    """
    Affiche la matrice de confusion (référence × sortie LLM).
    counts = (vp, fp2, fn, vn, fp) pour afficher les effectifs ; sinon légende seule.
    """
    if counts is None:
        vp_n = fp2_n = fn_n = vn_n = fp_n = None
    else:
        vp_n, fp2_n, fn_n, vn_n, fp_n = counts

    def cell(label: str, n: int | None) -> str:
        if n is None:
            return label.center(14)
        return f"{label} ({n})".center(14)

    dash = "—".center(14)
    row_pres = f"│ {'Présente (1)':<14} │{cell('VP', vp_n)}│{cell('FP2', fp2_n)}│{cell('FN', fn_n)}│"
    row_abs = f"│ {'Absente (0)':<14} │{dash}│{cell('FP', fp_n)}│{cell('VN', vn_n)}│"

    border = "┌────────────────┬──────────────┬──────────────┬──────────────┐"
    sep = "├────────────────┼──────────────┼──────────────┼──────────────┤"
    bot = "└────────────────┴──────────────┴──────────────┴──────────────┘"
    head = "│ Référence      │ LLM correct  │ LLM incorrect│ LLM absent   │"

    print(border)
    print(head)
    print(sep)
    print(row_pres)
    print(row_abs)
    print(bot)


def check_global_statistics(
    df_merged,
    comparison_functions,
    excluded_columns=None,
    included_columns=None,
):
    """
    Affiche d'abord la matrice de confusion et les métriques globales, puis le détail par colonne.

    Métriques (taux de réussite) : Détection = (VP+FP2)/(VP+FP2+FN), Exactitude = VP/(VP+FP2),
    Absence justifiée = VN/(FP+VN).

    Retourne l'accuracy globale ``matches / total`` (comparaisons OK), inchangée pour la compatibilité
    des tests (ex. seuil sur l'acte d'engagement).
    """
    # ============================================================================
    # STATISTIQUES GLOBALES DE COMPARAISON
    # ============================================================================
    columns_to_compare = _get_columns_to_compare(
        comparison_functions,
        excluded_columns=excluded_columns,
        included_columns=included_columns,
    )
    use_best_ref = "best_test_comparison_errors" in df_merged.columns

    print(f"\n{'=' * 80}")
    print("STATISTIQUES GLOBALES DE COMPARAISON")
    print(f"{'=' * 80}")
    n_rows_test = len(df_merged)
    print(f"Nombre de lignes du jeu de test : {n_rows_test}")

    results = {}

    # Comparaison pour chaque colonne sélectionnée
    for col in columns_to_compare:
        comparison_func = _get_comparison_function_for_column(col, comparison_functions)
        matches = []
        errors = []
        total_non_null = 0
        non_null_ok = 0
        total_llm_non_null = 0
        llm_non_null_ok = 0
        regressions_vs_best = 0
        improvements_vs_best = 0
        vp = fp2 = fn = vn = fp = 0

        # Comparer toutes les lignes pour cette colonne
        for idx, row in df_merged.iterrows():
            filename = row.get("filename", "unknown")
            ref_val = _get_value_by_dotted_key(row, col)
            ref_non_null = _field_value_is_non_null_non_empty(ref_val)

            structured_data = row.get("structured_data", None)
            if structured_data is None or pd.isna(structured_data):
                errors.append(f"{filename}: structured_data is None or NaN")
                matches.append(False)
                if ref_non_null:
                    total_non_null += 1
                dvp, dfp2, dfn, dvn, dfp = _classify_confusion_cell(ref_non_null, False, False)
                vp += dvp
                fp2 += dfp2
                fn += dfn
                vn += dvn
                fp += dfp
                continue

            llm_val = _get_value_by_dotted_key(structured_data, col)
            llm_non_null = _field_value_is_non_null_non_empty(llm_val)

            # Comparer les valeurs
            try:
                match_result = comparison_func(llm_val, ref_val)
                match_result = bool(match_result) if not isinstance(match_result, bool) else match_result
                matches.append(match_result)
                if ref_non_null:
                    total_non_null += 1
                    if match_result:
                        non_null_ok += 1
                if llm_non_null:
                    total_llm_non_null += 1
                    if match_result:
                        llm_non_null_ok += 1

                dvp, dfp2, dfn, dvn, dfp = _classify_confusion_cell(ref_non_null, match_result, llm_non_null)
                vp += dvp
                fp2 += dfp2
                fn += dfn
                vn += dvn
                fp += dfp

                # Écart au meilleur test (si colonne optionnelle présente)
                if use_best_ref:
                    best_errors = _parse_best_test_errors(row)
                    best_col = col.split(".", 1)[0] if "." in col else col
                    best_had_error = best_col in best_errors
                    current_has_error = not match_result
                    if not best_had_error and current_has_error:
                        regressions_vs_best += 1
                    elif best_had_error and not current_has_error:
                        improvements_vs_best += 1
            except Exception as e:
                errors.append(f"{filename}: Error in comparison_func: {str(e)}")
                matches.append(False)
                if ref_non_null:
                    total_non_null += 1
                if llm_non_null:
                    total_llm_non_null += 1
                dvp, dfp2, dfn, dvn, dfp = _classify_confusion_cell(ref_non_null, False, llm_non_null)
                vp += dvp
                fp2 += dfp2
                fn += dfn
                vn += dvn
                fp += dfp
                if use_best_ref:
                    best_errors = _parse_best_test_errors(row)
                    best_col = col.split(".", 1)[0] if "." in col else col
                    best_had_error = best_col in best_errors
                    if not best_had_error:
                        regressions_vs_best += 1

        # Calculer les statistiques pour cette colonne
        total = len(matches)
        matches_count = sum(matches)
        errors_count = len(errors)
        accuracy = matches_count / total if total > 0 else 0.0
        recall_non_null = non_null_ok / total_non_null if total_non_null > 0 else 0.0
        precision_llm_non_null = llm_non_null_ok / total_llm_non_null if total_llm_non_null > 0 else 0.0

        results[col] = {
            "total": total,
            "matches": matches_count,
            "errors": errors_count,
            "accuracy": accuracy,
            "total_non_null": total_non_null,
            "non_null_ok": non_null_ok,
            "recall_non_null": recall_non_null,
            "total_llm_non_null": total_llm_non_null,
            "llm_non_null_ok": llm_non_null_ok,
            "precision_llm_non_null": precision_llm_non_null,
            "vp": vp,
            "fp2": fp2,
            "fn": fn,
            "vn": vn,
            "fp": fp,
        }
        if use_best_ref:
            results[col]["delta_vs_best"] = regressions_vs_best - improvements_vs_best
            results[col]["regressions_vs_best"] = regressions_vs_best
            results[col]["improvements_vs_best"] = improvements_vs_best

    w_col, w_metric = 32, 30
    dash_len = w_col + 3 * w_metric + 12 + (14 if use_best_ref else 0)

    total_comparisons = sum(r["total"] for r in results.values())
    total_matches = sum(r["matches"] for r in results.values())
    global_accuracy = total_matches / total_comparisons if total_comparisons > 0 else 0.0

    gvp = sum(r["vp"] for r in results.values())
    gfp2 = sum(r["fp2"] for r in results.values())
    gfn = sum(r["fn"] for r in results.values())
    gvn = sum(r["vn"] for r in results.values())
    gfp = sum(r["fp"] for r in results.values())

    go, gi, gh = _fmt_quality_metric_columns(
        vp=gvp,
        fp2=gfp2,
        fn=gfn,
        vn=gvn,
        fp=gfp,
        w=w_metric,
    )
    match_failures = total_comparisons - total_matches

    print()
    _print_confusion_matrix_visual((gvp, gfp2, gfn, gvn, gfp))
    print("Détection = (VP+FP2)/(VP+FP2+FN)  |  Exactitude = VP/(VP+FP2)  |  Absence justifiée = VN/(FP+VN)")
    print()
    print(
        f"Matches (comparaisons OK) : {total_matches}/{total_comparisons} = {global_accuracy * 100:.1f}%  |  "
        f"échecs : {match_failures}"
    )
    print(f"Détection : {go.strip()} — {gfn} omissions")
    print(f"Exactitude : {gi.strip()} — {gfp2} incompréhensions")
    print(f"Absence justifiée : {gh.strip()} — {gfp} hallucinations")
    if use_best_ref:
        total_imp = sum(r.get("improvements_vs_best", 0) for r in results.values())
        total_reg = sum(r.get("regressions_vs_best", 0) for r in results.values())
        print(f"Écart au meilleur test: Améliorations +{total_imp}, Régressions -{total_reg}")

    print(f"\n{'=' * dash_len}")
    print("Détail par colonne")
    header_parts = [
        f"{'Colonne':<{w_col}}",
        f"{'Détection':<{w_metric}}",
        f"{'Exactitude':<{w_metric}}",
        f"{'Absence justifiée':<{w_metric}}",
    ]
    if use_best_ref:
        header_parts.append(f"{'(+)':<5}")
        header_parts.append(f"{'(-)':<5}")
    print(" | ".join(header_parts))
    print("-" * dash_len)

    for col in columns_to_compare:
        result = results[col]
        vp, fp2, fn, vn, fp = result["vp"], result["fp2"], result["fn"], result["vn"], result["fp"]
        o, i, h = _fmt_quality_metric_columns(
            vp=vp,
            fp2=fp2,
            fn=fn,
            vn=vn,
            fp=fp,
            w=w_metric,
        )
        row_parts = [f"{col:<{w_col}}", o, i, h]
        if use_best_ref:
            imp = result.get("improvements_vs_best", 0)
            reg = result.get("regressions_vs_best", 0)
            row_parts.append(f"{'+' + str(imp) if imp else '0':<5}")
            row_parts.append(f"{'-' + str(reg) if reg else '0':<5}")
        print(" | ".join(row_parts))

    print(f"{'=' * dash_len}\n")

    return global_accuracy
