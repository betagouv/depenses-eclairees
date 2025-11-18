import json
import re
from datetime import datetime
import pandas as pd
import pytest

# import sys
# sys.path.append(".")

from app.processor.analyze_content import df_analyze_content
from app.processor.attributes_query import ATTRIBUTES
from app.ai_models.config_albert import API_KEY_ALBERT, BASE_URL_PROD
from app.utils import json_print
from app.processor import post_traitement_llm


def normalize_string(s):
    """Normalise une chaîne de caractères : minuscule et sans caractères spéciaux."""
    if pd.isna(s) or s == "":
        return ""
    s = str(s).lower()
    # Supprime les caractères spéciaux (garde seulement les lettres, chiffres et espaces)
    s = re.sub(r'[^a-z0-9\s]', '', s)
    # Supprime les espaces multiples
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def compare_objet(llm_value, ref_value):
    """Compare objet : renvoie True."""
    return True


def compare_administration_beneficiaire(llm_value, ref_value):
    """Compare administration_beneficiaire : renvoie True."""
    return True


def compare_societe_principale(llm_value, ref_value):
    """Compare societe_principale : comparaison de chaînes normalisées."""
    llm_norm = normalize_string(llm_value)
    ref_norm = normalize_string(ref_value)
    return llm_norm == ref_norm


def compare_siret_mandataire(llm_value, ref_value):
    """Compare siret_mandataire : comparaison exaSupercte."""
    llm_str = str(llm_value) if not pd.isna(llm_value) else ""
    ref_str = str(ref_value) if not pd.isna(ref_value) else ""
    return llm_str == ref_str


def compare_siren_mandataire(llm_value, ref_value):
    """Compare siren_mandataire : comparaison exacte."""
    llm_str = str(llm_value) if not pd.isna(llm_value) else ""
    ref_str = str(ref_value) if not pd.isna(ref_value) else ""
    return llm_str == ref_str


def compare_rib_mandataire(llm_val, ref_val):
    """Compare rib_mandataire : format JSON, comparaison des 5 champs."""
    llm_dict = post_traitement_llm.post_traitement_rib(llm_val)
    ref_dict = post_traitement_llm.post_traitement_rib(ref_val)

    if llm_dict == '' and ref_dict == '':
        return True
    
    # Si 'iban' est dans ref_dict et non vide, alors on compare les ibans (exact).
    if ref_dict.get('iban', '') != '':
        if llm_dict.get('iban', '') == ref_dict.get('iban', ''):
            return True
        else:
            return False
    else:
        # Si 'iban' absent ou vide dans ref_dict, alors on vérifie qu'il est aussi absent ou vide dans llm_dict, ET que les banques sont les mêmes (normalisées)
        if llm_dict.get('iban', '') != '':
            return False
        # S'il n'y a pas d'iban, on compare les banques (normalisées)
        llm_banque = normalize_string(llm_dict.get('banque', ''))
        ref_banque = normalize_string(ref_dict.get('banque', ''))
        if llm_banque != ref_banque and (not llm_banque in ref_banque and llm_banque != ''):
            return False
        return True


def compare_avance(llm_value, ref_value):
    """Compare avance : renvoie True."""
    return True


def compare_cotraitants(llm_value, ref_value):
    """Compare cotraitants : liste de json, renvoie True pour l'instant."""
    return True


def compare_sous_traitants(llm_value, ref_value):
    """Compare sous_traitants : liste de json, renvoie True pour l'instant."""
    return True


def compare_rib_autres(llm_value, ref_value):
    """Compare rib_autres : liste de json, renvoie True pour l'instant."""
    return True


def compare_montant(llm_value, ref_value):
    """Compare montant : comparaison des valeurs."""
    llm_val = post_traitement_llm.post_traitement_montant(llm_value)
    ref_val = post_traitement_llm.post_traitement_montant(ref_value)
    return llm_val == ref_val


def parse_date(date_str):
    """Parse une date au format DD/MM/YYYY ou autres formats courants."""
    if pd.isna(date_str) or date_str == "":
        return None
    date_str = str(date_str).strip()
    formats = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d']
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None

def compare_date(llm_value, ref_value):
    """Compare date : comparaison de dates."""
    llm_date = parse_date(llm_value)
    ref_date = parse_date(ref_value)
    if llm_date is None and ref_date is None:
        return True
    if llm_date is None or ref_date is None:
        return False
    return llm_date == ref_date

def compare_duree(llm_value, ref_value):
    """Compare duree : nombre de mois, comparaison exacte."""
    try:
        llm_val = int(float(llm_value)) if not pd.isna(llm_value) and llm_value != "" else None
        ref_val = int(float(ref_value)) if not pd.isna(ref_value) and ref_value != "" else None
        if llm_val is None and ref_val is None:
            return True
        if llm_val is None or ref_val is None:
            return False
        return llm_val == ref_val
    except (ValueError, TypeError):
        return False


# Mapping des colonnes vers leurs fonctions de comparaison
COMPARISON_FUNCTIONS = {
    'objet': compare_objet,
    'administration_beneficiaire': compare_administration_beneficiaire,
    'societe_principale': compare_societe_principale,
    'siret_mandataire': compare_siret_mandataire,
    'siren_mandataire': compare_siren_mandataire,
    'rib_mandataire': compare_rib_mandataire,
    'avance': compare_avance,
    'cotraitants': compare_cotraitants,
    'sous_traitants': compare_sous_traitants,
    'rib_autres': compare_rib_autres,
    'montant_ttc': compare_montant,
    'montant_ht': compare_montant,
    'date_signature_mandataire': compare_date,
    'date_signature_administration': compare_date,
    'duree': compare_duree,
}


def test_quality_infos():
    """Test de qualité des informations extraites par le LLM."""
    # Chemin vers le fichier CSV de test
    csv_path = "/Users/dinum-284659/dev/data/test/test_acte_engagement.csv"
    
    # Lecture du fichier CSV
    df_test = pd.read_csv(csv_path).astype(str)
    df_test['siret_mandataire'] = df_test['siret_mandataire'].apply(lambda x: x.split('.')[0])
    df_test['siren_mandataire'] = df_test['siren_mandataire'].apply(lambda x: x.split('.')[0])
    df_test.fillna('', inplace=True)
    
    # Création du DataFrame pour l'analyse
    df_analyze = pd.DataFrame()
    df_analyze['filename'] = df_test['filename']
    df_analyze['classification'] = 'acte_engagement'
    df_analyze['relevant_content'] = df_test['text']
    
    # Configuration du LLM
    llm_model = 'albert-large'
    
    # Analyse du contenu avec df_analyze_content
    df_result = df_analyze_content(
        api_key=API_KEY_ALBERT,
        base_url=BASE_URL_PROD,
        llm_model=llm_model,
        df=df_analyze,
        df_attributes=ATTRIBUTES,
        max_workers=20,
        temperature=0.5,
        save_grist=False
    )
    
    # Fusion des résultats avec les valeurs de référence
    df_merged = df_result[['filename', 'llm_response']].merge(
        df_test,
        on='filename',
        how='inner'
    )
    
    # Stockage détaillé de toutes les comparaisons
    detailed_comparisons = []
    results = {}
    
    # Colonnes à exclure des comparaisons
    excluded_columns = {
        'objet',
        'administration_beneficiaire',
        'avance',
        'cotraitants',
        'sous_traitants',
        'rib_autres'
    }
    
    # Comparaison pour chaque colonne
    for col in COMPARISON_FUNCTIONS.keys():
        # Ignorer les colonnes exclues
        if col in excluded_columns:
            continue
        
        # Vérifier si la colonne existe dans le CSV de référence
        if col in df_test.columns:
            comparison_func = COMPARISON_FUNCTIONS[col]
            print(f"Traitement de la colonne: {col}")
            matches = []
            
            for idx, row in df_merged.iterrows():
                filename = row.get('filename', 'unknown')
                llm_val = None
                ref_val = None
                match_result = None
                error = None
                
                # Parser le JSON de llm_response
                llm_response = row.get('llm_response', None)
                if llm_response is None or pd.isna(llm_response):
                    error = "llm_response est None ou NaN"
                    match_result = False
                    detailed_comparisons.append({
                        'filename': filename,
                        'colonne': col,
                        'llm_val': None,
                        'ref_val': None,
                        'match': False,
                        'error': error
                    })
                    matches.append(False)
                    continue
                
                try:
                    llm_data = json.loads(llm_response) if isinstance(llm_response, str) else llm_response
                except (json.JSONDecodeError, TypeError) as e:
                    error = f"Erreur de parsing JSON: {str(e)}"
                    match_result = False
                    detailed_comparisons.append({
                        'filename': filename,
                        'colonne': col,
                        'llm_val': None,
                        'ref_val': None,
                        'match': False,
                        'error': error
                    })
                    matches.append(False)
                    continue
                
                # Extraire la valeur du champ dans le JSON
                llm_val = llm_data.get(col, None)
                
                # Récupérer la valeur de référence du CSV
                ref_val = row.get(col, None)
                
                # Comparer les valeurs avec gestion d'erreur
                try:
                    match_result = comparison_func(llm_val, ref_val)
                    # S'assurer que match_result est un booléen
                    if not isinstance(match_result, bool):
                        match_result = bool(match_result)
                    matches.append(match_result)
                except Exception as e:
                    error = f"Erreur dans comparison_func: {str(e)}"
                    match_result = False
                    matches.append(False)
                
                # Stocker les détails de la comparaison
                detailed_comparisons.append({
                    'filename': filename,
                    'colonne': col,
                    'llm_val': llm_val,
                    'ref_val': ref_val,
                    'match': match_result,
                    'error': error
                })
            
            results[col] = {
                'total': len(matches),
                'matches': sum(matches),
                'accuracy': sum(matches) / len(matches) if len(matches) > 0 else 0.0
            }
    
    # Création d'un DataFrame pour l'affichage détaillé
    df_comparisons = pd.DataFrame(detailed_comparisons)
    
    # Affichage des résultats agrégés
    print("\n=== Résultats de la comparaison (agrégés) ===")
    for col, result in results.items():
        print(f"{col}: {result['matches']}/{result['total']} ({result['accuracy']*100:.2f}%)")
    
    # Affichage détaillé des comparaisons
    print("\n=== Détails des comparaisons ===")
    print(f"Nombre total de comparaisons: {len(df_comparisons)}")
    print("\nTableau complet des comparaisons:")
    print("=" * 120)
    
    # Formatage pour l'affichage
    for filename in df_comparisons['filename'].unique():
        print(f"\n📄 Fichier: {filename}")
        print("-" * 120)
        df_file = df_comparisons[df_comparisons['filename'] == filename]
        
        for _, row in df_file.iterrows():
            colonne = row['colonne']
            # Ignorer les colonnes exclues dans l'affichage détaillé
            if colonne in excluded_columns:
                continue
            llm_val_str = str(row['llm_val']) if row['llm_val'] is not None else "None"
            ref_val_str = str(row['ref_val']) if row['ref_val'] is not None else "None"
            match = row['match']
            error = row['error']
            
            # Tronquer les valeurs trop longues pour l'affichage
            max_len = 40
            if len(llm_val_str) > max_len:
                llm_val_str = llm_val_str[:max_len] + "..."
            if len(ref_val_str) > max_len:
                ref_val_str = ref_val_str[:max_len] + "..."
            
            # Symbole pour le match
            if pd.notna(error):
                status = "❌ ERROR"
                status_info = f" | Erreur: {error}"
            elif match:
                status = "✅ MATCH"
                status_info = ""
            else:
                status = "❌ NO MATCH"
                status_info = ""
            
            print(f"  {colonne:25} | LLM: {llm_val_str:40} | REF: {ref_val_str:40} | {status}{status_info}")
    
    print("\n" + "=" * 120)
    
    # Affichage détaillé par champ (colonne)
    print("\n=== Détails des comparaisons par champ ===")
    print("=" * 120)
    
    # Trier les colonnes pour un affichage cohérent
    colonnes_triees = [col for col in COMPARISON_FUNCTIONS.keys() if col not in excluded_columns]
    
    for colonne in colonnes_triees:
        print(f"\n📋 Champ: {colonne}")
        print("-" * 120)
        df_col = df_comparisons[df_comparisons['colonne'] == colonne]
        
        for _, row in df_col.iterrows():
            filename = row['filename']
            llm_val_str = str(row['llm_val']) if row['llm_val'] is not None else "None"
            ref_val_str = str(row['ref_val']) if row['ref_val'] is not None else "None"
            match = row['match']
            error = row['error']
            
            # Tronquer les valeurs trop longues pour l'affichage
            max_len = 80
            if len(llm_val_str) > max_len:
                llm_val_str = llm_val_str[:max_len] + "..."
            if len(ref_val_str) > max_len:
                ref_val_str = ref_val_str[:max_len] + "..."
            if len(filename) > 30:
                filename = filename[:30] + "..."
            
            # Symbole pour le match
            if pd.notna(error):
                status = "❌ ERROR"
                status_info = f" | Erreur: {error}"
            elif match:
                status = "✅ MATCH"
                status_info = ""
            else:
                status = "❌ NO MATCH"
                status_info = ""
            
            print(f"  📄 {filename:30} | LLM: {llm_val_str:20} | REF: {ref_val_str:20} | {status}{status_info}")
    
    print("\n" + "=" * 120)
    
    # Statistiques par colonne (en excluant les colonnes exclues)
    print("\n=== Statistiques par colonne ===")
    for col in df_comparisons['colonne'].unique():
        # Filtrer explicitement les colonnes exclues (au cas où)
        if col in excluded_columns:
            continue
        df_col = df_comparisons[df_comparisons['colonne'] == col]
        total = len(df_col)
        matches = sum(df_col['match'] == True)
        errors = sum(pd.notna(df_col['error']))
        accuracy = matches/total*100 if total > 0 else 0.0
        print(f"{col:30} | Total: {total:3} | Matches: {matches:3} | Erreurs: {errors:3} | Accuracy: {accuracy:.2f}%")
    
    # Assertions pour vérifier que les tests passent
    # On peut ajuster les seuils selon les besoins
    for col, result in results.items():
        assert result['total'] > 0, f"Aucune donnée trouvée pour {col}"
        # Pour l'instant, on vérifie juste que le test s'exécute sans erreur
        # Les seuils de précision peuvent être ajustés selon les besoins
    
    return df_comparisons

# df_comparisons = test_quality_infos()
    
# row = df_comparisons.query("colonne == 'rib_mandataire' and match == False").iloc[10]
# print(row['llm_val'], '\n', row['ref_val'])
# print(row['match'])

test_quality_infos()
