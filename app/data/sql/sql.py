import os

import psycopg

import pandas as pd


def connect():
    db_url = os.getenv("DATABASE_URL", "")
    return psycopg.connect(db_url)


def get_config():
    info = connect().info
    return dict(host=info.host, port=info.port, dbname=info.dbname, user=info.user)


def executemany(sql, values, batch_size=100):
    # Process data in batches
    with connect() as conn:
        with conn.cursor() as cursor:
            values = list(values)
            for i in range(0, len(values), batch_size):
                batch = values[i : i + batch_size]
                cursor.executemany(sql, batch)


def df_to_values(df):
    return [tuple(record) for record in df.to_records(index=False)]


def _executemany_df(df, columns, sql, batch_size=100):
    # Only pick specified columns
    df = df[columns]
    # Drop duplicates (keep first)
    df = df.drop_duplicates()
    # Convert to tuples
    data = df_to_values(df)
    # Insert in database
    executemany(sql, data, batch_size=batch_size)


def bulk_create_engagements_items(df, batch_size=100):
    sql = """
        INSERT INTO engagements_items(num_EJ, poste_EJ, num_contrat, groupe_marchandise, centre_financier)
        VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING
    """
    # Convert data frame to tuples
    columns = ["num_EJ", "poste_EJ", "num_contrat", "groupe_marchandise", "centre_financier"]
    _executemany_df(df, columns, sql, batch_size=batch_size)


def _bulk_update_by_key(df, table, columns, key_column):
    sql = f"UPDATE {table} SET "
    sql += ", ".join([f"{column} = %s" for column in columns])
    sql += f" WHERE {key_column} = %s"
    _executemany_df(df, columns + [key_column], sql)


def bulk_update_attachments(df, columns):
    _bulk_update_by_key(df, "attachments", columns, "filename")


def bulk_update_engagements(df, columns):
    _bulk_update_by_key(df, "engagements", columns, "num_EJ")


def select_attachments(columns, offset, limit, where, order_by=None):
    order_by = order_by or ["filename", "extension", "hash"]
    SQL = f"""
    SELECT {", ".join(columns)} FROM attachments
    WHERE {where}
    ORDER BY {", ".join(order_by)}
    OFFSET {offset}
    LIMIT {limit}
    """
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(SQL)
            data = cursor.fetchall()
        return pd.DataFrame(data, columns=columns)


def select_attachments_for_classification(offset=0, limit=200):
    return select_attachments(
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
        ],
        order_by=["filename", "extension", "hash"],
        offset=offset,
        limit=limit,
        where="text is not null",
    )


def select_engagements_with_attachments(columns_ej=None, columns_attachments=None, list_cat=None, offset=0, limit=200):
    """
    Sélectionne les 200 premiers num_ej de la table engagements puis fait la jointure avec attachments.

    Args:
        columns (list): Liste des colonnes à récupérer depuis attachments
        list_cat (list): Liste des catégories à filtrer (optionnel)
        offset (int): Offset de la sélection
        limit (int): Limite de la sélection
    Returns:
        pd.DataFrame: DataFrame contenant les données jointes
    """
    if columns_ej is None:
        columns_ej = [
            "num_EJ",
            "Designation",
            "Descriptif_prestations",
            "Date",
            "Prestataire",
            "SIRET",
            "Administration",
            "Sources_et_conflits",
        ]
    if columns_attachments is None:
        columns_attachments = [
            "filename",
            "extension",
            "dossier",
            "date_creation",
            "taille",
            "hash",
            "text",
            "is_ocr",
            "nb_mot",
            "llm_response",
            "json_error",
            "classification",
            "classification_type",
        ]
    order_by = ["engagements.num_EJ", "filename", "extension", "hash"]
    if list_cat is None:
        req_synthesis = "1=1"  # Always true condition
    else:
        req_synthesis = (
            "attachments.llm_response is not null and attachments.classification in ("
            + f"'{"','".join(list_cat)}'"
            + ")"
        )
    columns_with_prefix = [f"engagements.{column}" for column in columns_ej] + [
        f"attachments.{column}" for column in columns_attachments
    ]
    SQL = f"""
    SELECT {", ".join(columns_with_prefix)}
    FROM (
        SELECT {", ".join(columns_ej)}
        FROM engagements 
        WHERE engagements.Designation is null
        ORDER BY num_EJ 
        OFFSET {offset}
        LIMIT {limit}
    ) AS engagements
    JOIN attachments ON engagements.num_EJ = attachments.num_EJ
    WHERE {req_synthesis}
    ORDER BY {", ".join(order_by)}
    """
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(SQL)
            data = cursor.fetchall()
        return pd.DataFrame(data, columns=columns_with_prefix)
