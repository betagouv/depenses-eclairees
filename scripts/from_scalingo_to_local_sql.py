import os
import sys

# Ajouter le répertoire parent au path pour les imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json

import psycopg

from app.data.sql.sql import select_attachments


def load_local_sql_engagements(dfFiles, connexion):
    columns = ["num_EJ", "date_creation"]
    dfToSend = dfFiles[columns].drop_duplicates()

    sql = """
        INSERT INTO engagements(num_EJ, date_creation)
        VALUES (%s, %s) ON CONFLICT DO NOTHING
    """

    # Convert to tuples
    data = [tuple(record) for record in dfToSend.to_records(index=False)]

    batch_size = 100
    with conn.cursor() as cursor:
        data = list(data)
        rows_affected = 0
        for i in range(0, len(data), batch_size):
            batch = data[i : i + batch_size]
            cursor.executemany(sql, batch)
            rows_affected += cursor.rowcount
        print(f"Nombre de lignes modifiées: {rows_affected}")


def load_local_sql_attachments(dfFiles, connexion):
    columns = [
        "filename",
        "extension",
        "dossier",
        "num_EJ",
        "date_creation",
        "taille",
        "hash",
        "text",
        "is_ocr",
        "nb_mot",
        "relevant_content",
        "is_embedded",
        "llm_response",
        "json_error",
        "classification",
        "classification_type",
    ]
    dfToSend = dfFiles[columns].drop_duplicates(["filename", "extension", "hash"])
    dfToSend["llm_response"] = dfToSend["llm_response"].apply(lambda x: json.dumps(x) if isinstance(x, dict) else x)

    params = ", ".join(tuple(["%s"] * len(columns)))

    sql_creation = f"""
          INSERT INTO attachments({", ".join(columns)})
          VALUES {params} ON CONFLICT DO NOTHING \
    """

    print(sql_creation)
    # Convert to tuples
    data = [tuple(record) for record in dfToSend.to_records(index=False)]

    batch_size = 100
    with conn.cursor() as cursor:
        data = list(data)
        rows_affected = 0
        for i in range(0, len(data), batch_size):
            batch = data[i : i + batch_size]
            # Creation des nouvelles lignes
            cursor.executemany(sql_creation, batch)
            rows_affected += cursor.rowcount
        print(f"Nombre de lignes créées : {rows_affected}")


def remove_engagements_local_sql(dfFiles, connexion):
    dfToRemove = dfFiles[["num_EJ"]].drop_duplicates()

    sql = """
        DELETE FROM engagements WHERE num_EJ = %s
    """

    data = [tuple(record) for record in dfToRemove.to_records(index=False)]

    batch_size = 100

    with conn.cursor() as cursor:
        data = list(data)
        rows_affected = 0
        for i in range(0, len(data), batch_size):
            batch = data[i : i + batch_size]
            cursor.executemany(sql, batch)
            rows_affected += cursor.rowcount
        print(f"Nombre de lignes supprimées : {rows_affected}")


def remove_attachments_local_sql(dfFiles, connexion):
    dfToRemove = dfFiles[["filename"]].drop_duplicates()

    sql = """
        DELETE FROM attachments WHERE filename = %s
    """

    data = [tuple(record) for record in dfToRemove.to_records(index=False)]

    batch_size = 100

    with conn.cursor() as cursor:
        data = list(data)
        rows_affected = 0
        for i in range(0, len(data), batch_size):
            batch = data[i : i + batch_size]
            cursor.executemany(sql, batch)
            rows_affected += cursor.rowcount
        print(f"Nombre de lignes supprimées : {rows_affected}")


# Récupération de 5000 records dans la base distante
dfFiles = select_attachments(
    columns=[
        "filename",
        "extension",
        "dossier",
        "num_EJ",
        "date_creation",
        "taille",
        "hash",
        "text",
        "is_ocr",
        "nb_mot",
        "relevant_content",
        "is_embedded",
        "llm_response",
        "json_error",
        "classification",
        "classification_type",
    ],
    order_by=["filename", "extension", "hash"],
    offset=0,
    limit=5000,
    where="dossier = '../data/raw/batch_4_conseil_2024_202507'",
)

print("Nombre de records récupérés : ", len(dfFiles))


# Enregistrement dans la base locale
config = dict(host="localhost", port="5432", dbname="depec", autocommit=True)

conn = psycopg.connect(**config)

remove_attachments_local_sql(dfFiles, conn)
remove_engagements_local_sql(dfFiles, conn)

load_local_sql_engagements(dfFiles, conn)
load_local_sql_attachments(dfFiles, conn)
