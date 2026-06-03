import time
from contextlib import contextmanager

import pandas as pd


@contextmanager
def timer(message):
    start_time = time.perf_counter()
    yield
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    minutes, seconds = divmod(elapsed_time, 60)
    print(f"Temps d'exécution {message}: {minutes}min {seconds:.1f}s")


key_ej = 'Numéro EJ référencé facture'

with timer("Load ODA xlsx"):
    df1 = pd.read_excel('../data/gestion_eclairee/ODA_2025_Complet.xlsx', dtype={key_ej: 'str'})
print("Lignes ODA xlsx:", df1.shape[0])

with timer("Load csv"):
    df2 = pd.read_csv(
        '../data/gestion_eclairee/export_factures_33_2025.csv',
        sep=';',
        decimal=',',
        thousands=None,
        encoding='latin-1',
        dtype={
            'EJ': 'str', 'ANNEE': 'int64', 'FACTURE': 'str', 'REFERENCE': 'str'
        , 'MONTANT': 'float64', 'SEDP': 'str',
        }
    )
print("Lignes csv:", df2.shape[0])


with timer("Do agg"):
    df2_agg = df2.groupby('EJ').agg(
        SEDP=('SEDP', lambda x: ' '.join(sorted(x.dropna().unique().astype(str)))),
        NB_SEDP=('SEDP', lambda x: int(x.count())),
        FACTURE=('FACTURE', lambda x: ' '.join(x.dropna().astype(str))),
        MONTANT=('MONTANT', lambda x: ' '.join(x.dropna().astype(str))),
        SOMME_MONTANT=('MONTANT', 'sum')
    ).reset_index()


df_merged = pd.merge(
    df1,
    df2_agg,
    left_on='Numéro EJ référencé facture',
    right_on='EJ',
    how='left'  # Garde toutes les lignes de df1, même sans correspondance
)


df_merged['Montant match?'] = df_merged['Dépenses  2025'] == df_merged['SOMME_MONTANT']
print("Montants OK:", df_merged[df_merged['Montant match?'] == True].shape[0])


df_ok = df_merged[
    (~df_merged['SEDP'].isna()) &
    (df_merged[key_ej] != '#')
]
print("EJs OK:", df_ok.shape[0])

# Filtrer les lignes où SEDP est NaN (pas de correspondance dans df2) et EJ n'est pas '#'
df_missing_sedp = df_merged[
    (df_merged['SEDP'].isna()) &
    (df_merged[key_ej] != '#')
]
print("EJs sans correspondance:", df_missing_sedp.shape[0])

df_missing_ej = df_merged[
    (df_merged[key_ej] == '#')
]
print("EJs absents ODA (#):", df_missing_ej.shape[0])


with timer("Save results to csv"):
    #df_merged.to_excel(
    #    'mon_fichier.xlsx',
    #    index=False,
    #    sheet_name='Résultats',
    #    header=True,         # Inclut les noms de colonnes
    #    freeze_panes=(1, 0)  # Figé la 1ère ligne (en-têtes)
    #)
    df_merged.to_csv('mon_fichier.csv', index=False, header=True)

