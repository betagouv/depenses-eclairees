import time
from contextlib import contextmanager
import sys

import pandas as pd


oda_filepath = sys.argv[1]
chorus_filepath = sys.argv[2]


@contextmanager
def timer(message):
    start_time = time.perf_counter()
    yield
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    minutes, seconds = divmod(elapsed_time, 60)
    print(f"Temps d'exécution {message}: {minutes}min {seconds:.1f}s")


key_ej = 'Numéro EJ référencé facture'

with timer("Load ODA"):
    dtype_oda = {key_ej: 'str', 'Domaine': 'str'}
    if oda_filepath.endswith('.csv'):
        df_oda = pd.read_csv(oda_filepath, dtype=dtype_oda, parse_dates=['Date notification (E)', 'Date fin de marché (E)'])
    elif oda_filepath.endswith('.xlsx'):
        df_oda = pd.read_excel(oda_filepath, dtype=dtype_oda)
    else:
        print(f"Unsupported file format {oda_filepath}")
        exit(1)
print("Lignes ODA:", df_oda.shape[0])


with timer("Load Chorus"):
    df_chorus = pd.read_csv(
        chorus_filepath,
        sep=';',
        decimal=',',
        thousands=None,
        encoding='latin-1',
        dtype={
            'MARCHE': 'str', 'EJ': 'str', 'ANNEE': 'str', 'DATE': 'str', 'FACTURE': 'str',
            'REFERENCE': 'str', 'MONTANT': 'float64', 'SEDP': 'str',
        }
    )
print("Lignes csv:", df_chorus.shape[0])


# Aggregation
with timer("Do agg"):
    # Dictionnaire pour stocker les données agrégées par EJ
    agg_data = {}

    # Parcourir chaque ligne de df2
    for _, row in df_chorus.iterrows():
        ej = row['EJ']
        sedp = row['SEDP']
        facture = row['FACTURE']
        reference = row['REFERENCE']
        montant = row['MONTANT']

        # Initialiser l'entrée pour cet EJ si elle n'existe pas
        if ej not in agg_data:
            agg_data[ej] = {
                'SEDP': set(),
                'FACTURE': [],
                'REFERENCE': [],
                'MONTANT': [],
                'SOMME_MONTANT': 0.0
            }

        # Ajouter les données
        if pd.notna(sedp):
            agg_data[ej]['SEDP'].add(str(sedp))
        if pd.notna(facture):
            agg_data[ej]['FACTURE'].append(str(facture))
        if pd.notna(reference):
            agg_data[ej]['REFERENCE'].append(str(reference))
        if pd.notna(montant):
            agg_data[ej]['MONTANT'].append(str(montant))
            agg_data[ej]['SOMME_MONTANT'] += float(montant)

    # Convertir le dictionnaire en DataFrame pandas
    df2_agg = pd.DataFrame([
        {
            'EJ': ej,
            'SEDP': ' '.join(sorted(data['SEDP'])),
            'NB_SEDP': len(data['SEDP']),
            'FACTURE': ' '.join(data['FACTURE']),
            'NB_FACTURE': len(data['FACTURE']),
            'REFERENCE': ' '.join(data['REFERENCE']),
            'MONTANT': ' '.join(data['MONTANT']),
            'SOMME_MONTANT': data['SOMME_MONTANT']
        }
        for ej, data in agg_data.items()
    ])



df_merged = pd.merge(
    df_oda,
    df2_agg,
    left_on=key_ej,
    right_on='EJ',
    how='left'  # Garde toutes les lignes de df_oda, même sans correspondance
)


df_merged['Montant match?'] = df_merged['Dépenses  2025'] == df_merged['SOMME_MONTANT']
print("Montants OK:", df_merged[df_merged['Montant match?'] == True].shape[0])


df_ok = df_merged[
    (~df_merged['SEDP'].isna()) &
    (df_merged[key_ej] != '#')
]
print("Lignes OK:", df_ok.shape[0])

# Filtrer les lignes où SEDP est NaN (pas de correspondance dans df2) et EJ n'est pas '#'
df_missing_sedp = df_merged[
    (df_merged['SEDP'].isna()) &
    (df_merged[key_ej] != '#')
]
print("Lignes sans correspondance:", df_missing_sedp.shape[0])

df_missing_ej = df_merged[
    (df_merged[key_ej] == '#')
]
print("Lignes EJ absent ODA (#):", df_missing_ej.shape[0])


with timer("Save results to csv"):
    df_merged.to_csv('fusion.csv', index=False, header=True)
    # Load
    # df_merged = pd.read_csv('mon_fichier.csv', dtype={key_ej: 'str', 'EJ': 'str', 'Domaine': 'str'}, parse_dates=['Date notification (E)', 'Date fin de marché (E)'])
    # Liste de travail
    df = df_merged
    # SPM
    # df[(df['Ministère'] == 'SPM') | (df['V_Ministère_Service bénéficaire'] == 'SPM')]
    # MEFSIN
    # df[(df['Ministère'] == 'MEFSIN & MTFP') | (df['V_Ministère_Service bénéficaire'] == 'MEFSIN & MTFP')]
    # MINSOC
    # df[(df['Ministère'] == 'MINSOC') | (df['V_Ministère_Service bénéficaire'] == 'MINSOC')]
    # MTECT
    # df[(df['Ministère'] == 'MTECT') | (df['V_Ministère_Service bénéficaire'] == 'MTECT')]
    df = df[[key_ej, "SEDP"]]
    df = df.rename(columns={key_ej: "EJ"})
    df = df[df["EJ"] != "#"]  # Retire les lignes avec EJ = "#"
    df = df.dropna()  # Supprime toutes les lignes avec SEDP vide
    df = pd.DataFrame(list(df.value_counts().keys()), columns=['EJ', 'SERVICES'])
    df.to_csv('liste_telechargement.csv', index=False, header=True)
