import json
import logging
import os
import sys

import django

sys.path.append(".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "docia.settings")
django.setup()

from app.grist.grist_api import get_data_from_grist  # noqa: E402
from docia.file_processing.processor.analyze_content import LLMClient  # noqa: E402
from tests_e2e.utils import (  # noqa: E402
    analyze_content_quality_test,
    check_global_statistics,
    check_quality_one_field,
    check_quality_one_row,
    compare_address,
    compare_duration,
    compare_mandatee_bank_account,
    compare_normalized_string,
)

logger = logging.getLogger("docia." + __name__)


def compare_object(llm_value, ref_value, llm_model="openweight-medium"):
    """
    Compare deux objets en utilisant un LLM comme juge pour évaluer la proximité de sens.

    Args:
        llm_value: Valeur extraite par le LLM
        ref_value: Valeur de référence
        temperature: Température pour la génération (0.0 = déterministe, 0.2-0.3 = nuance avec cohérence)
                    Par défaut 0.2 pour permettre de la nuance tout en gardant de la reproductibilité.

    Returns:
        bool: True si les objets sont sémantiquement proches, False sinon
    """
    # Gestion des valeurs vides ou None
    if not llm_value and not ref_value:
        return True

    if not llm_value or not ref_value:
        return False

    try:
        # Création d'une instance LLMClient
        llm_env = LLMClient()

        # Construction du prompt pour demander l'avis du LLM
        system_prompt = (
            "Vous êtes un expert en analyse sémantique de documents juridiques. "
            "Votre rôle est d'évaluer la proximité de sens entre deux descriptions d'objets."
        )

        user_prompt = f"""
            Compare les deux descriptions d'objet suivantes et détermine si elles décrivent 
            la même chose ou des choses sémantiquement proches.

            Valeur extraite par le LLM: {llm_value}

            Valeur de référence: {ref_value}

            Analyse si ces deux descriptions ont le même sens ou un sens proche. Prends en compte :
            - Les synonymes et formulations équivalentes
            - Les variations de style ou de formulation
            - L'essence et le contenu principal, pas seulement la forme exacte

            Tu dois IMPÉRATIVEMENT répondre UNIQUEMENT avec un JSON valide, sans aucun autre texte, avec 
            cette structure exacte:
            {{
                "sont_proches": true ou false,
                "explication": "brève explication de votre analyse"
            }}
        """
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

        # Format de réponse JSON forcé
        response_format = {"type": "json_object"}

        # Appel au LLM avec format JSON forcé
        # Température 0.2 : permet de la nuance dans l'évaluation sémantique tout en gardant de la cohérence
        result = llm_env.ask_llm(messages=messages, model=llm_model, response_format=response_format, temperature=0)

        # print("Réponse LLM : ", result.get("explication", ""))

        return bool(result.get("sont_proches", False))

    except Exception as e:
        logger.error(f"Error calling LLM for compare_object: {e}")
        return False


def compare_beneficiary_administration(llm_value, ref_value, llm_model="openweight-medium"):
    """
    Compare deux administrations bénéficiaires en utilisant un LLM comme juge pour évaluer s'il s'agit du même
    organisme ou d'une entité publique équivalente.

    Args:
        llm_value: Valeur extraite par le LLM pour l'administration bénéficiaire
        ref_value: Valeur de référence pour l'administration bénéficiaire

    Returns:
        bool: True si les administrations bénéficiaires sont identiques ou équivalentes, False sinon
    """
    # Gestion des valeurs vides ou None
    if not llm_value and not ref_value:
        return True

    if not llm_value or not ref_value:
        return False

    try:
        # Création d'une instance LLMClient
        llm_env = LLMClient()

        # Construction du prompt pour demander l'avis du LLM
        system_prompt = (
            "Vous êtes un expert en analyse de documents administratifs publics. "
            "Votre rôle est d'évaluer si deux chaînes désignent la même administration bénéficiaire (structure "
            "administrative ou publique bénéficiaire d'une commande) "
            "ou deux entités publiques équivalentes."
        )

        user_prompt = f"""
            Compare les deux mentions suivantes concernant l'administration bénéficiaire d'un 
            contrat ou acte administratif, et détermine si elles désignent la même structure, 
            entité ou administration bénéficiaire, ou des administrations équivalentes (avec 
            ou sans variation d'intitulé ou de formulation). Par exemple, si la valeur extraite 
            par le LLM est plus précise que la valeur de référence, alors on considère que les 
            deux administrations sont équivalentes.

            Valeur extraite par le LLM :
            {llm_value}

            Valeur de référence :
            {ref_value}

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
        """

        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

        # Format de réponse JSON forcé
        response_format = {"type": "json_object"}

        # Appel au LLM avec format JSON forcé, température basse pour fiabilité
        result = llm_env.ask_llm(messages=messages, model=llm_model, response_format=response_format, temperature=0)

        # print("LLM explanation for administration_beneficiaire: ", result.get("explication", ""))

        return bool(result.get("sont_equivalentes", False))

    except Exception as e:
        logger.error(f"Error calling LLM for compare_beneficiary_administration: {e}")
        return False


def get_comparison_functions():
    """Mapping des colonnes vers leurs fonctions de comparaison

    Retourne le dictionnaire des fonctions de comparaison.
    Cette fonction garantit que les références pointent toujours vers les dernières versions des fonctions,
    même après un rechargement de module.

    Returns:
        dict: Dictionnaire associant les noms de colonnes à leurs fonctions de comparaison
    """
    return {
        "administration_beneficiaire": compare_beneficiary_administration,
        "objet_marche": compare_object,
        "societe_principale": compare_normalized_string,
        "adresse_postale_titulaire": compare_address,
        "siret_titulaire": compare_normalized_string,
        "societe_sous_traitant": compare_normalized_string,
        "adresse_postale_sous_traitant": compare_address,
        "siret_sous_traitant": compare_normalized_string,
        "montant_sous_traitance_ht": compare_normalized_string,
        "montant_sous_traitance_ttc": compare_normalized_string,
        "description_prestations": compare_normalized_string,
        "date_signature": compare_normalized_string,
        "montant_tva": compare_normalized_string,
        "paiement_direct": compare_normalized_string,
        "rib_sous_traitant": compare_mandatee_bank_account,
        "conserve_avance": compare_normalized_string,
        "duree_sous_traitance": compare_duration,
    }


def create_batch_test(multi_line_coef=1):
    """Test de qualité des informations extraites par le LLM."""
    df_test = get_data_from_grist(table="Dc4_gt").query("commentaire == 'traité'")

    df_test.fillna("", inplace=True)
    for col in (
        "adresse_postale_titulaire",
        "adresse_postale_sous_traitant",
        "rib_sous_traitant",
        "duree_sous_traitance",
    ):
        df_test[col] = df_test[col].apply(lambda x: json.loads(x) if isinstance(x, str) else x)

    # Lancement du test
    return analyze_content_quality_test(df_test, "sous_traitance", multi_line_coef=multi_line_coef)


if __name__ == "__main__":
    df_test, df_result, df_merged = create_batch_test()

    EXCLUDED_COLUMNS = ["objet_marche", "administration_beneficiaire"]

    comparison_functions = get_comparison_functions()

    check_quality_one_field(df_merged, "rib_sous_traitant", comparison_functions)

    check_quality_one_row(df_merged, 0, comparison_functions, excluded_columns=EXCLUDED_COLUMNS)

    check_global_statistics(df_merged, comparison_functions, excluded_columns=EXCLUDED_COLUMNS)
