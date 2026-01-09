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
import tqdm
from concurrent.futures import ThreadPoolExecutor
sys.path.append(".")

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'docia.settings')
django.setup()


from django.conf import settings

from app.processor.analyze_content import df_analyze_content, LLMClient, parse_json_response
from app.processor.attributes_query import ATTRIBUTES
from app.ai_models.config_albert import ALBERT_API_KEY, ALBERT_BASE_URL
from app.processor.post_processing_llm import *
from app.processor.select_relevant_content import RAGEnvironment

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


def drop_duplicates_ccap(df_ccap):
    ccap_length = len(df_ccap)
    # Critère 1 : Drop duplicates based on hash
    df_ccap.drop_duplicates(subset=["hash"], keep="first", inplace=True)
    # Critère 2 : Drop duplicates based on id_marche and nb_lots
    df_ccap['id_marche'] = df_ccap.get('llm_response',None).apply(lambda x:x.get('id_marche',None) if x is not None else None).fillna(df_ccap['hash'])
    df_ccap['nb_lots'] = df_ccap.get('llm_response',None).apply(lambda x:x.get('lots',None) if x is not None else None).str.len().fillna(0).astype(int)
    # df_ccap.loc[(df_ccap['id_marche']=='') | (df_ccap['id_marche']=='non specifié'), 'id_marche'] = df_ccap.loc[(df_ccap['id_marche']=='') | (df_ccap['id_marche']=='non specifié'), 'hash']
    df_ccap.sort_values(by=["id_marche", "nb_lots"], ascending=[True, False], inplace=True)
    df_ccap.drop_duplicates(subset=["id_marche"], keep="first", inplace=True)
    ccap_length_after = len(df_ccap)
    print(f"ccap_length: {ccap_length}, ccap_length_after: {ccap_length_after}")
    return df_ccap

def get_lots_from_ccap(df_ccap):
    columns=["id_marche", "objet", "structure","numero_lot","titre_lot","parent","num_ej", "source"]
    df_ccap = drop_duplicates_ccap(df_ccap)
    df_marche = pd.DataFrame(columns=columns)
    df_lots = pd.DataFrame(columns=columns)
    for idx, row in df_ccap.iterrows(): 
        # Récupérer le dict llm_response
        llm_response = row.get('llm_response', None)
        if llm_response is not None:
            id_marche = llm_response.get('id_marche', None)
            lots = llm_response.get('lots', None)
            objet = llm_response.get('objet_marche', None)
            forme_marche = llm_response.get('forme_marche', None)
            forme_marche_lots = llm_response.get('forme_marche_lots', None)
            if lots is not None and forme_marche_lots is not None:
                new_row = pd.DataFrame([{"id_marche": id_marche, "objet": objet, "structure": forme_marche.get('structure') if forme_marche else None, "numero_lot": [], "titre_lot": [], "parent":None, "source": row["filename"]}])
                df_marche = pd.concat([df_marche, new_row], ignore_index=True)
                for lot, forme_marche_lot in zip(lots, forme_marche_lots):
                    new_row = pd.DataFrame([{"id_marche": id_marche, "objet": objet, "structure": forme_marche_lot.get('structure') if forme_marche_lot else None, "numero_lot": lot.get('numero_lot'), "titre_lot": f"lot {lot.get('numero_lot')}: {lot.get('titre_lot')}", "parent":id_marche, "source": row["filename"]}])
                    df_lots = pd.concat([df_lots, new_row], ignore_index=True)
    return df_marche, df_lots


def drop_duplicates_ae(df_ae):
    ae_length = len(df_ae)
    df_ae.drop_duplicates(subset=["num_EJ"], keep="first", inplace=True)
    return df_ae

def get_lot_from_ae(df_ae):
    columns=["id_marche", "objet", "structure","lot","parent","num_ej", "source"]
    df_ae = drop_duplicates_ae(df_ae)
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
    return df_lot

def get_ae_lot_from_ccap(df_lots, df_lot, semantic_weight=0.5):
    df_lots = df_lots.query("titre_lot != ''")
    if df_lots.empty:
        return pd.DataFrame(columns=["id_marche", "num_ej", "titre_lot_ae", "titre_lot_marche", "score", "source_ccap", "source_ae"])

    df_lot = df_lot.query("lot != ''")
    if df_lot.empty:
        return pd.DataFrame(columns=["id_marche", "num_ej", "titre_lot_ae", "titre_lot_marche", "score", "source_ccap", "source_ae"])

    df_ae_lot = pd.DataFrame(columns=["id_marche", "num_ej", "titre_lot_ae", "titre_lot_marche", "score", "source_ccap", "source_ae"])


    api_key=ALBERT_API_KEY
    base_url=ALBERT_BASE_URL
    embedding_model="BAAI/bge-m3"
    chunk_size=2000
    chunk_overlap=0
    hybrid_search=True
    semantic_weight=semantic_weight
    retrieval_top_k=1
    max_mots=20000

    df_lots["id_marche_lot"] = df_lots["source"].astype(str) + "_" + df_lots["numero_lot"].astype(str)
    
    df_lots["titre_lot_padded"] = (df_lots["titre_lot"].astype(str) + " - " + df_lots["objet"].astype(str)).str.pad(width=chunk_size, side='right', fillchar=' ').str.lower()
    # df_lots["titre_lot_padded"] = df_lots["titre_lot"].str.lower().str.pad(width=chunk_size, side='right', fillchar=' ')
    text = ''.join(df_lots.titre_lot_padded.tolist())
    chunk_id_list = df_lots.id_marche_lot.tolist()
    rag_env = RAGEnvironment(
        api_key=api_key,
        base_url=base_url,
        embedding_model=embedding_model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        hybrid_search=hybrid_search,
        semantic_weight=semantic_weight,
        retrieval_top_k=retrieval_top_k,
        max_car=max_mots
    )

    # Réinitialiser pour chaque document
    rag_env.documents = {}
    rag_env.chunks = []
    rag_env.index = None
    rag_env.tfidf_matrix = None

    rag_env.add_documents(texts=[text], chunk_id_list=chunk_id_list)

    # for idx, row in df_lot.iterrows():
    for idx in tqdm.tqdm(df_lot.index, total=len(df_lot), desc="Processing lots"):
        row = df_lot.loc[idx]
        query = f'{row["lot"].lower()} - {row["objet"].lower()}'
        # query = row["lot"].lower()
        context, results = rag_env.get_relevant_context(query, top_k=retrieval_top_k, hybrid_weight=semantic_weight, return_results=True)
        score = results[0]["score"] if len(results) > 0 else 0
        if len(results) > 0:
            source = '_'.join(results[0]['chunk']['chunk_id'].split('_')[0:-1])
            numero_lot_marche = int(results[0]['chunk']['chunk_id'].split('_')[-1])
            id_marche = df_lots.loc[df_lots["source"] == source,"id_marche"].values[0] if df_lots.loc[df_lots["source"] == source,"id_marche"].values[0] is not None else None
            titre_lot_marche = df_lots.loc[(df_lots["source"] == source) & (df_lots["numero_lot"] == numero_lot_marche),"titre_lot"].values[0] if df_lots.loc[(df_lots["source"] == source) & (df_lots["numero_lot"] == numero_lot_marche),"titre_lot"].values[0] is not None else None
            df_ae_lot = pd.concat([df_ae_lot, pd.DataFrame([{"id_marche": id_marche, "num_ej": row["num_ej"], "titre_lot_ae": row["lot"], "titre_lot_marche": titre_lot_marche,"score": results[0]["score"], "source_ccap": source, "source_ae": row["source"]}])], ignore_index=True)
            df_ae_lot.drop_duplicates(subset=["id_marche", "num_ej", "titre_lot_ae"], keep="first", inplace=True)
    return df_ae_lot

df_ccap = get_files(classification="ccap")
df_ae = get_files(classification="acte_engagement")
# df_marche, df_lots = get_lots_from_ccap(df_ccap.query("num_EJ in ('1000157271', '1000168082', '1300192010', '1300191983')"))
df_marche, df_lots = get_lots_from_ccap(df_ccap)
# df_lot = get_lot_from_ae(df_ae)
# df_lot = get_lot_from_ae(df_ae.query("num_EJ in ('1000157271', '1000168082', '1300192010', '1300191983')"))
df_lot = get_lot_from_ae(df_ae.query("num_EJ in ('1300198801', '1300198912','1300192010', '1300191983')"))
df_ae_lot = get_ae_lot_from_ccap(df_lots, df_lot)
print(df_ae_lot)

# query = 'Lot 1: construction de bureaux'
# context, results = rag_env.get_relevant_context(query, top_k=len(df_lots), hybrid_weight=0.5, return_results=True)
# df_results = pd.DataFrame(results).sort_values(by='score', ascending=False).reset_index(drop=True)
# df_results["filename"] = df_results.chunk.apply(lambda x: x["filename"])
# for idx, row in df_results.query("score > 0.7").iterrows():
#     print(row.lot,":", round(row.score, 2),":", row.text)
# print(f"Nombre de résultats: {idx+1}")