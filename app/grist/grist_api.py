import requests
import json
import pandas as pd
from tqdm import tqdm
from urllib.parse import quote

from app.utils import json_print
from django.conf import settings  # noqa: E402


def check_connexion():
    # Vérifie la connexion à l'API Grist en effectuant une requête GET sur l'URL du document
    r = requests.get(settings.GRIST_DOCS_URL, headers={"Authorization": settings.GRIST_API_KEY})
    json_print(r.text)

def get_tables():
    # Vérifie la connexion à l'API Grist en effectuant une requête GET sur l'URL du document
    r = requests.get(settings.GRIST_DOCS_URL + "/tables", headers={"Authorization": settings.GRIST_API_KEY})
    json_print(r.text)

def get_data_from_grist(table: str, api_key: str = None) -> pd.DataFrame:
    """
    Récupère les données d'une table depuis l'API Grist.
    Récupère toutes les données de la table (toutes les colonnes).
    Args:
        table (str): Nom de la table (ex: Attachments)
        api_key (str): Clé API Grist
    Returns:
        pd.DataFrame: DataFrame contenant les données de la table
    """
    if api_key is None:
        api_key = settings.GRIST_API_KEY
    records_url = settings.GRIST_DOCS_URL + f"/tables/{table}/records"
    headers = {"Authorization": api_key}
    r = requests.get(records_url, headers=headers)
    r.raise_for_status()
    data = r.json()
    # Extraction des champs utiles : fusionne les champs et l'id pour chaque record
    records = [
        {**rec["fields"], "id": rec["id"]}
        for rec in data.get("records", [])
    ]
    return pd.DataFrame(records)


def post_new_data_to_grist(dfToSend, key_column, table_url, api_key, columns_to_send=[], batch_size=100):
    """
    Envoie les données d'un DataFrame à la base de données Grist via l'API,
    uniquement si la ligne à une combinaison de clés qui n'est pas déjà présente.

    Args:
        dfToSend (pd.DataFrame): DataFrame à envoyer
        list_keys (list): Liste des colonnes à utiliser comme clés pour éviter les doublons
        table_url (str): URL de la table à alimenter
        api_key (str): Clé API Grist
        columns_to_send (list): Liste des colonnes à envoyer
        batch_size (int): Taille des lots pour l'envoi
    """
    records_url = table_url+"/records"

    if key_column not in columns_to_send:
        columns_to_send.append(key_column)

    # Récupérer les records uniques du DataFrame (suppression des doublons et des valeurs manquantes)
    records_uniques = dfToSend.drop_duplicates(key_column).astype(str)

    # Télécharger les données existantes de Grist pour éviter les doublons de clés uniques
    dfDataOnline = select_records_by_key(records_uniques[key_column].tolist(), key_column, table_url, api_key)
    try:
        existing_records = set(dfDataOnline[key_column].dropna().unique())
    except:
        existing_records = set()

    headers = {"Authorization": api_key}

    records = []
    ignored_records = []
    # Parcourt chaque ligne unique à envoyer
    for _, row in records_uniques.iterrows():
        if row[key_column] not in existing_records:
            # Prépare le record à envoyer avec les colonnes spécifiées
            record = {
                "fields":{
                    key: row.get(key, "") for key in row.index if key in columns_to_send
                }
            }
            records.append(record)
        else:
            # Ignore les doublons déjà présents dans Grist
            ignored_records.append(row[key_column])

    print(f"\nPost de nouvelles lignes dans Grist - records déjà présents dans la table : {len(ignored_records)}, {ignored_records[:10]}")

    # Envoi par lots pour éviter les requêtes trop volumineuses
    for i in tqdm(range(0, len(records), batch_size), desc="Envoi des fichiers par batch"):
        batch = records[i:i+batch_size]
        body = {"records": batch}
        r = requests.post(records_url, headers=headers, json=body)
        try:
            if(r.status_code != 200):
               print("Erreur lors de l'envoi des données :", json.dumps(r.json(), indent=2))
        except Exception:
            print(r.text)

def post_data_to_grist_multiple_keys(dfToSend, list_keys, table_url, api_key, columns_to_send=[], batch_size=100):
    """
    Envoie les données d'un DataFrame à la base de données Grist via l'API,
    uniquement si la ligne à une liste de clés qui ne sont pas déjà présentes.

    Args:
        dfToSend (pd.DataFrame): DataFrame à envoyer
        list_keys (list): Liste des colonnes sur lesquelles se fonder pour trouver les doublons au sein de dfToSend et en ligne
        table_url (str): URL de la table à alimenter
        api_key (str): Clé API Grist
        columns_to_send (list): Liste des colonnes à envoyer
        batch_size (int): Taille des lots pour l'envoi
    """
    records_url = table_url+"/records"

    for key_column in list_keys:
        if key_column not in columns_to_send:
            columns_to_send.append(key_column)

    # Récupérer les records uniques du DataFrame (suppression des doublons et des valeurs manquantes)
    records_uniques = dfToSend.drop_duplicates(list_keys).astype(str)

    # Télécharger les données existantes de Grist pour éviter les doublons de ligne
    dfDataOnline = select_records_by_key(records_uniques[key_column].tolist(), key_column, table_url, api_key)
    try:
        df_existing_records = dfDataOnline.drop_duplicates(list_keys)
    except:
        df_existing_records = pd.DataFrame(columns=list_keys)

    headers = {"Authorization": api_key}

    records = []
    ignored_records = []
    
    # Parcourt chaque ligne unique à envoyer
    for _, row in records_uniques.iterrows():
        # Vérifie si la ligne (pour les colonnes à envoyer) existe déjà dans df_existing_records
        is_duplicate = False
        if not df_existing_records.empty:
            # On compare les valeurs des colonnes à envoyer
            mask = (df_existing_records[columns_to_send] == row[columns_to_send]).all(axis=1)
            if mask.any():
                is_duplicate = True

        if not is_duplicate:
            # Prépare le record à envoyer avec les colonnes spécifiées
            record = {
                "fields": {
                    key: row.get(key, "") for key in row.index if key in columns_to_send
                }
            }
            records.append(record)

        else:
            ignored_records.append({key: row[key] for key in row.index if key in list_keys})

    print(f"\nPost de nouvelles lignes dans Grist - Envoi de nouvelles lignes à la table : {len(records)}; records ignorés (déjà présents) : {len(ignored_records)}, exemples : {ignored_records[:5]}")

    # Envoi par lots pour éviter les requêtes trop volumineuses
    for i in tqdm(range(0, len(records), batch_size), desc="Envoi des fichiers par batch"):
        batch = records[i:i+batch_size]
        body = {"records": batch}
        r = requests.post(records_url, headers=headers, json=body)
        try:
            if(r.status_code != 200):
               print("Erreur lors de l'envoi des données :", json.dumps(r.json(), indent=2))
        except Exception:
            print(r.text)


def get_grist_id_from_key(df_correspondance, key_column, key_value):
    """
    Retourne l'identifiant Grist associé à une clé.
    Args:
        df_correspondance (pd.DataFrame): DataFrame avec colonnes 'filename' et 'id'
        key_column (str): Nom de la colonne à utiliser pour la recherche
        key_value (str): Valeur de la clé à chercher
    Returns:
        int or None: id Grist correspondant, ou None si non trouvé
    """
    # Recherche la ligne correspondant à la clé
    try:
        match = df_correspondance.loc[df_correspondance[key_column] == key_value]
        if not match.empty:
            return int(match.iloc[0]["id"])
        return None
    except Exception as e:
        print("Erreur lors de la récupération de l'identifiant du record dans les données :", e)
        return None

def select_records_by_key(list_key, key_column, table_url, api_key, batch_size=100):
    """
    Récupère tous les records attachés à une liste de clés données dans Grist, par batch pour éviter les requêtes trop volumineuses.

    Args:
        list_key (list): Liste des clés à rechercher
        key_column (str): Nom de la colonne à utiliser pour la recherche
        table_url (str): URL de la table Attachments (ex: .../tables/Attachments)
        api_key (str): Clé API Grist
        batch_size (int): Taille des lots pour les requêtes
    Returns:
        pd.DataFrame: DataFrame des documents correspondant à chaque clé fournie dans list_key
    """
    records_url = table_url + "/records"
    headers = {"Authorization": api_key}
    all_records = []

    for i in range(0, len(list_key), batch_size):
        batch_keys = list_key[i:i+batch_size]
        str_keys = ",".join([f'"{key}"' for key in batch_keys])
        params = {"filter": f'{{"{key_column}": [{str_keys}]}}'}
        try:
            r = requests.get(records_url, headers=headers, params=params)
            if r.status_code != 200:
                print(f"Erreur lors de la récupération des données (batch {i//batch_size+1}):", r.text)
                continue
            data = r.json()
            batch_records = [
                {**rec["fields"], "id": rec["id"]}
                for rec in data.get("records", [])
            ]
            all_records.extend(batch_records)
        except Exception as e:
            print(f"Exception lors de la récupération du batch {i//batch_size+1}: {e}")

    return pd.DataFrame(all_records)

def update_records_in_grist(dfFiles, key_column, table_url, api_key, columns_to_update, batch_size = 100):
    """
    Met à jour les champs spécifiés dans columns_to_patch dans Grist pour chaque fichier du DataFrame,
    en envoyant les modifications par batch de 100 via une requête PATCH au format attendu par l'API Grist.

    Args:
        dfFiles (pd.DataFrame): DataFrame contenant au moins 'filename' et les colonnes à patcher
        dfIdInGrist (pd.DataFrame): DataFrame de correspondance avec colonnes 'filename' et 'id'
        api_url (str): URL de la table Attachments (ex: .../tables/Attachments/records)
        api_key (str): Clé API Grist
        columns_to_patch (list): Liste des noms de colonnes à modifier dans Grist
    """
    # Prépare les headers pour l'authentification
    headers = {"Authorization": api_key}
    records = []           # Liste des records à patcher
    missing_records = []   # Liste des clés non trouvées dans Grist
    records_url = table_url + "/records"

    # Récupère les IDs Grist correspondant aux clés du DataFrame
    dfIdInGrist = select_records_by_key(dfFiles[key_column].tolist(), key_column, table_url, api_key)

    # Parcourt chaque ligne du DataFrame à mettre à jour
    for _, row in dfFiles.iterrows():
        key_value = row[key_column]
        # Cherche l'id Grist correspondant à la clé
        record_id = get_grist_id_from_key(dfIdInGrist, key_column, key_value)
        if record_id is not None:
            fields = {}
            # Prépare les champs à mettre à jour
            for col in columns_to_update:
                val = row.get(col, "")
                if isinstance(val, list):
                    val = str(val)
                # Remplace les NaN par une chaîne vide
                if pd.isna(val):
                    val = ""
                # Convertit les types numpy en types natifs Python
                if hasattr(val, "item"):
                    val = val.item()
                fields[col] = val
            # Ajoute le record à la liste des records à patcher
            record = {
                "id": int(record_id),
                "fields": fields
            }
            records.append(record)
            
        else:
            # Ajoute la clé à la liste des enregistrements manquants
            missing_records.append(key_value)

    print("\nUpdate dans Grist - Nbr de records non présents dans la table :", len(missing_records), missing_records[:10])

    # Envoie les modifications par lots (batch) pour éviter les requêtes trop volumineuses
    for i in tqdm(range(0, len(records), batch_size), desc="Envoi des mises à jour à Grist par paquet"):
        batch = records[i:i+batch_size]
        body = {"records": batch}
        # Requête PATCH à l'API Grist
        r = requests.patch(records_url, headers=headers, json=body)
        try:
            if(r.status_code != 200):
                print("Erreur lors de la mise à jour :", json.dumps(r.json(), indent=2))
        except Exception:
            print("Erreur dans la réponse : ", r.text)

def get_table_list_ids(docs_url, api_key, table_name):
    records_url = docs_url + "sql"
    headers = {"Authorization": api_key}
    parameters = {"q": f"SELECT id FROM {table_name} LIMIT 100000"}
    r = requests.get(records_url, headers=headers, params=parameters)
    
    if(r.status_code == 200):
        list_ids = [x["fields"]["id"] for x in r.json()['records']]
    else:
        print(f"Erreur lors de la récupération des IDs : {r.text}")
        list_ids = []
    return list_ids

def delete_table_records(table_url, api_key):
    delete_url = table_url + "/data/delete"
    docs_url = table_url.split("tables")[0]
    table_name = table_url.split("tables/")[1]
    
    ids = get_table_list_ids(docs_url, api_key, table_name)
    headers = {"Authorization": api_key}
    batch_size = 10000
    success_count = 0
    for i in tqdm(range(0, len(ids), batch_size), desc="Suppression des données par batch"):
        batch_ids = ids[i:i+batch_size]
        r = requests.post(delete_url, headers=headers, json=batch_ids)
        try:
            if(r.status_code != 200):
               print("Erreur lors de la suppression des données pour le batch {i//batch_size+1} :", json.dumps(r.json(), indent=2))
        except Exception:
            print(r.text)
        else:
            success_count += len(batch_ids)
    print(f"Données supprimées avec succès : {success_count} enregistrements supprimés")
