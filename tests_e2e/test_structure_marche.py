import json
import re
import pandas as pd
import pytest
import logging
from datetime import datetime
import copy
import os
import django
import sys
sys.path.append(".")

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'docia.settings')
django.setup()


from django.conf import settings

from app.processor.analyze_content import df_analyze_content, LLMClient, parse_json_response
from app.processor.attributes_query import ATTRIBUTES
from app.ai_models.config_albert import ALBERT_API_KEY, ALBERT_BASE_URL
from app.processor.post_processing_llm import *

from app.data.sql import sql


logger = logging.getLogger("docia." + __name__)

PROJECT_PATH = settings.BASE_DIR
CSV_DIR_PATH = (PROJECT_PATH / ".." / "data" / "test").resolve()

def get_files(classification):
    df = sql.select_attachments(
        columns=["filename", "extension", "dossier", "num_EJ", "date_creation", "taille", "hash", "is_ocr", "nb_mot", "llm_response", "json_error", "classification"],
        where=f"classification = '{classification}'",
        order_by=["filename", "extension", "hash"],
        offset=0,
        limit=10000,
    )
    return df


def get_lots_from_ccap(df_ccap, mode="marche"):
    columns=["id_marche", "objet", "structure","lot","parent","num_ej", "source",]
    df_marche = pd.DataFrame(columns=columns)
    for idx, row in df_ccap.iterrows(): 
        # Récupérer le dict llm_response
        llm_response = row.get('llm_response', None)
        if llm_response is not None:
            id_marche = llm_response.get('id_marche', None)
            lots = llm_response.get('lots', None)
            objet = llm_response.get('objet_marche', None)
            if lots is not None:
                forme_marche = llm_response.get('forme_marche', None)
                new_row = pd.DataFrame([{"id_marche": id_marche, "objet": objet, "structure": forme_marche.get('structure') if forme_marche else None, "lot":[], "parent":None, "source": row["filename"]}])
                df_marche = pd.concat([df_marche, new_row], ignore_index=True)
                forme_marche_lots = llm_response.get('forme_marche_lots', None)
                if mode != "marche":
                    for lot, forme_marche_lot in zip(lots, forme_marche_lots):
                        new_row = pd.DataFrame([{"id_marche": id_marche, "objet": objet, "structure": forme_marche_lot.get('structure') if forme_marche_lot else None, "lot":f"lot {lot.get('numero_lot')}: {lot.get('titre_lot')}", "parent":id_marche, "source": row["filename"]}])
                        df_marche = pd.concat([df_marche, new_row], ignore_index=True)
    # return df_marche.groupby(["id_marche","lot"]).first().reset_index()[columns]
    return df_marche

def get_lot_from_ae(df_ae):
    columns=["id_marche", "objet", "structure","lot","parent","num_ej", "source",]
    df_lot = pd.DataFrame(columns=columns)
    for idx, row in df_ae.iterrows():
        # Récupérer le dict llm_response
        llm_response = row.get('llm_response', None)
        if llm_response is not None:
            objet = llm_response.get('objet_marche', None)
            lot_concerne = llm_response.get('lot_concerne', None)
            if lot_concerne is not None:
                new_row = pd.DataFrame([{"id_marche": None, "objet": objet, "structure": "simple", "lot":lot_concerne, "parent":None, "num_ej": row["num_EJ"], "source": row["filename"]}])
                df_lot = pd.concat([df_lot, new_row], ignore_index=True)
    return df_lot.groupby("num_ej").first().reset_index()[columns]

df_ccap = get_files(classification="ccap")
df_ae = get_files(classification="acte_engagement")
df_marche = get_lots_from_ccap(df_ccap.query("num_EJ in ('1000157271', '1000168082', '1300192010', '1300191983')"), mode="marche")
df_lot = get_lot_from_ae(df_ae.query("num_EJ in ('1000157271', '1000168082', '1300192010', '1300191983')"))
print(df_lot)