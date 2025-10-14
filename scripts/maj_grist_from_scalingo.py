import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from app.data.sql.sql import connect
from app import grist
from tqdm import tqdm


def get_engagements(limit=None):
    sql = '''
        SELECT * FROM engagements
    '''
    if limit:
        sql += f' LIMIT {limit}'

    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            data = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(data, columns=columns)
        print("Nombre d'engagements récupérés : ", len(df))
        return df

def get_attachments(limit=None):
    batch_size = 4000
    dfs = []
    offset = 0

    with connect() as conn:
        with conn.cursor() as cursor:
            # Get total number of rows in attachments
            cursor.execute('SELECT COUNT(*) FROM attachments')
            total_rows = cursor.fetchone()[0]
            print("Nombre total d'attachments à traiter :", total_rows)

            while True:
                sql = f'''
                    SELECT * FROM attachments
                    LIMIT {batch_size} OFFSET {offset}
                '''
                cursor.execute(sql)
                data = cursor.fetchall()
                if not data:
                    break
                columns = [desc[0] for desc in cursor.description]
                df_batch = pd.DataFrame(data, columns=columns)
                dfs.append(df_batch)
                print(f"Batch attachments récupérés (offset {offset}) : {len(df_batch)}")
                offset += batch_size
                if len(df_batch) < batch_size:
                    break  # last batch fetched

    if dfs:
        df = pd.concat(dfs, ignore_index=True)
    else:
        df = pd.DataFrame()  # empty dataframe if no data

    print("Nombre d'attachments récupérés : ", len(df))
    return df


def get_batch(limit=None):
    sql = '''
        SELECT * FROM batch
    '''
    if limit:
        sql += f' LIMIT {limit}'

    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            data = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(data, columns=columns)
        print("Nombre de lignes de batch récupérés : ", len(df))
        return df

# grist.check_connexion()
# print(connect().infos)

grist.delete_table_records(grist.URL_TABLE_ENGAGEMENTS, grist.API_KEY_GRIST)
grist.delete_table_records(grist.URL_TABLE_ATTACHMENTS, grist.API_KEY_GRIST)
grist.delete_table_records(grist.URL_TABLE_BATCH, grist.API_KEY_GRIST)

dfEngagements = get_engagements()
dfAttachments = get_attachments()
dfBatch = get_batch()

dfEngagements = dfEngagements.drop(columns=['id'])
dfBatch = dfBatch.drop(columns=['id'])
dfAttachments = dfAttachments.drop(columns=['id', 'num_ej', 'batch'])

dfAttachments['text'] = dfAttachments['text'].apply(lambda x: x[:30]+" ..." if type(x) == str else "")
dfAttachments['relevant_content'] = dfAttachments['relevant_content'].apply(lambda x: x[:30]+" ..." if type(x) == str else "")

grist.post_new_data_to_grist(dfEngagements, "num_ej", grist.URL_TABLE_ENGAGEMENTS, grist.API_KEY_GRIST, columns_to_send=dfEngagements.columns.tolist(), batch_size=200)
grist.post_new_data_to_grist(dfAttachments, "filename", grist.URL_TABLE_ATTACHMENTS, grist.API_KEY_GRIST, columns_to_send=dfAttachments.columns.tolist(), batch_size=300)
grist.post_data_to_grist_multiple_keys(dfBatch, ["num_ej", "batch"], grist.URL_TABLE_BATCH, grist.API_KEY_GRIST, columns_to_send=dfBatch.columns.tolist(), batch_size=300)


