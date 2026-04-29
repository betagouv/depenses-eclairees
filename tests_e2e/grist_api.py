import json

from django.conf import settings

import requests

import pandas as pd


def auth_headers():
    return {
        "Authorization": f"Bearer {settings.GRIST_API_KEY}",
    }


def get_tables():
    # Vérifie la connexion à l'API Grist en effectuant une requête GET sur l'URL du document
    r = requests.get(settings.GRIST_DOCS_URL + "/tables", headers=auth_headers())
    print(json.dumps(r.json, indent=4))


def get_data_from_grist(table: str) -> pd.DataFrame:
    """
    Récupère les données d'une table depuis l'API Grist.
    Récupère toutes les données de la table (toutes les colonnes).
    Args:
        table (str): Nom de la table (ex: Attachments)
    Returns:
        pd.DataFrame: DataFrame contenant les données de la table
    """
    records_url = settings.GRIST_DOCS_URL + f"/tables/{table}/records"
    r = requests.get(records_url, headers=auth_headers())
    r.raise_for_status()
    data = r.json()
    # Extraction des champs utiles : fusionne les champs et l'id pour chaque record
    records = [{**rec["fields"], "id": rec["id"]} for rec in data.get("records", [])]
    return pd.DataFrame(records)
