import pandas as pd
import os
import numpy as np
import re
from .cleaner import extract_num_EJ

def getStatistics(dfFiles, df_ground_truth):
    try:
        df_ground_truth[["Marché"]] = df_ground_truth[["Marché"]].astype(str)
        df_ground_truth[["n° EJ"]] = df_ground_truth[["n° EJ"]].astype(str)
        dfFiles = dfFiles.astype(str)

        # Récupération des EJ avec un numéro de marchés et des autres EJ sans marché
        dfEJAvecMarche = df_ground_truth.query("Marché != 'nan' and Marché != '#'")
        dfEJSansMarche = df_ground_truth.query("Marché == 'nan' or Marché == '#'")

        # Identification des fichiers provenant d'un numéro de marché
        dfJoinMarches = pd.merge(
            dfEJAvecMarche, 
            dfFiles, 
            left_on='Marché', 
            right_on='num_EJ', 
            how='left',
            suffixes=('_Cible', '_PJ')
        ).query("filename.notna()")

        # Identification des fichiers provenant d'un EJ quelconque (avec ou sans marché)
        dfJoinAchats = pd.merge(
            df_ground_truth, 
            dfFiles, 
            left_on='n° EJ', 
            right_on='num_EJ', 
            how='left',
            suffixes=('_Cible', '_PJ')
        ).query("filename.notna()")

        # Chaque fichier est désormais rattaché à un EJ 
        dfJoin = pd.concat([dfJoinMarches, dfJoinAchats])

        dfEJDiffMarche = df_ground_truth.query("Marché != `n° EJ` and Marché != '#' and Marché.notna()")
        dfAchatsAvecPJ = dfJoinAchats.query("filename.notna()")
        dfMarchesAvecPJ = dfJoinMarches.query("Marché_Cible != `n° EJ_Cible` and filename.notna()")

        EJAchatsGroundTruth = list(df_ground_truth['n° EJ'])
        EJMarchesGroundTruth = list(df_ground_truth['Marché'])

        # Compter le nombre de lignes dans le sous-dataframe
        print("Analyse des PJ par rapport à df_ground_truth :\n")
        print("Analyse de df_ground_truth :")
        print("Nb n° EJ de commande : ", len(df_ground_truth))
        print("Nb n° EJ de marchés : ", len(dfEJDiffMarche.drop_duplicates("Marché")))
        print("Nb n° EJ de commande ayant un (vrai) marché : ", len(dfEJDiffMarche))

        print("\nAvec des PJ : ")
        print("Nb d'EJ (commande + marché) identifiés dans les PJ : ", len(dfFiles.drop_duplicates("num_EJ")))
        print("Nb d'EJ d'achat ayant des PJ d'achats : ", len(dfAchatsAvecPJ.drop_duplicates("n° EJ_Cible")))
        print("Nb d'EJ de marché ayant des PJ de marché : ", len(dfMarchesAvecPJ.drop_duplicates("Marché_Cible")))
        print("Nb EJ (commande ou marché ?) hors df_ground_truth : ", len(dfFiles.query("num_EJ not in @EJAchatsGroundTruth and num_EJ not in @EJMarchesGroundTruth").drop_duplicates("num_EJ")))
        print("Nb d'EJ d'achat ayant des PJ de marché : ", len(dfMarchesAvecPJ.drop_duplicates("n° EJ_Cible")))

        print("\nRattachement des PJ reçues : ")
        print("Nb de PJ reçues (après dezip) : ", len(dfFiles))
        print("Nb de PJ attachées à un achat : ",len(dfJoinAchats.query("filename.notna()")))
        print("Nb de PJ attachées à un marché : ", len(dfJoinMarches.query("filename.notna()").drop_duplicates("filename")))
        print("Nb de PJ non rattachées à la cible : ", len(dfFiles.query("num_EJ not in @EJAchatsGroundTruth and num_EJ not in @EJMarchesGroundTruth").drop_duplicates("filename")))

    except Exception as e:
        print("Erreur dans la génération des statistiques :",e)

def missingEJ(dfFiles, df_ground_truth):
    """
    Retourne les lignes de df_ground_truth dont le 'n° EJ' n'est pas présent dans dfFiles['num_EJ'].
    Args:
        dfFiles (pd.DataFrame): DataFrame contenant au moins la colonne 'num_EJ'
        df_ground_truth (pd.DataFrame): DataFrame contenant au moins la colonne 'n° EJ'
    Returns:
        pd.DataFrame: Sous-ensemble de df_ground_truth avec les 'n° EJ' manquants dans dfFiles
    """
    # S'assurer que les colonnes sont bien des chaînes pour la comparaison
    df_ground_truth = df_ground_truth.copy()
    df_ground_truth["n° EJ"] = df_ground_truth["n° EJ"].astype(str)
    dfFiles = dfFiles.copy()
    dfFiles["num_EJ"] = dfFiles["num_EJ"].astype(str)

    # Extraire les 'n° EJ' absents de dfFiles
    missing_mask = ~df_ground_truth["n° EJ"].isin(dfFiles["num_EJ"])
    df_missing = df_ground_truth[missing_mask].copy()
    return df_missing

def getEJStatistics(dfFilesClassified, list_classification: list):
    """
    Génère des statistiques sur les fichiers en fonction de leur classification.
    
    Args:
        dfFiles (pd.DataFrame): DataFrame contenant les noms des fichiers et leurs n° d'EJ
        list_classification (dict): Dictionnaire de classification des fichiers
    """
    dfStatsEJ = pd.DataFrame(columns=['type_doc', 'nb_PJ', 'nb_EJ'])
    dfStatsEJ["type_doc"] = list_classification
    # Compter le nombre de fichiers pour chaque type de classification
    
    for idx, row in dfStatsEJ.iterrows():
        dfStatsEJ.at[idx, "nb_PJ"] = dfFilesClassified.query("classification == @row['type_doc']")['filename'].drop_duplicates().count()
        dfStatsEJ.at[idx, "nb_EJ"] = dfFilesClassified.query("classification == @row['type_doc']")['filename'].map(lambda filename: extract_num_EJ(filename)).drop_duplicates().count()
    dfStatsEJ.loc[len(list_classification), "type_doc"] = "PJ avec info"
    dfStatsEJ.loc[len(list_classification), "nb_PJ"] = dfFilesClassified.query("classification in @list_classification")['filename'].drop_duplicates().count()
    dfStatsEJ.loc[len(list_classification), "nb_EJ"] = dfFilesClassified.query("classification in @list_classification")['filename'].map(lambda filename: extract_num_EJ(filename)).drop_duplicates().count()    
    print("Statistiques sur le nombre d'EJ avec de l'info :")
    print(dfStatsEJ)
    return dfStatsEJ