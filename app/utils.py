import time as t
import re
import pandas as pd
import json

from contextlib import contextmanager
import time

from . import config_data


@contextmanager
def log_execution_time(title, treshold=10):
    """
    A context manager that logs the execution time of a code block if it exceeds a specified threshold.
    
    Args:
        title (str): Description of the operation being timed
        treshold (float, optional): Minimum execution time in seconds to trigger logging.

    Example:
        with log_execution_time("Database query", treshold=0.5):
            # Some time-consuming operation
            perform_database_query()
    """

    # Skip logging if disabled in config
    if not config_data.LOG_EXECUTION_TIME:
        yield
        return

    def log(error=None):
        # Calculate elapsed time
        end_time = time.monotonic()
        ellapsed = end_time - start_time
        # Only log if execution time exceeds threshold
        if ellapsed > treshold:
            text = f'{title} took {ellapsed:.1f} seconds to execute'
            if error:
                text += f' with error: {str(error)}'
            print(text)

    # Record start time before executing code block
    start_time = time.monotonic()
    try:
        yield
        log()
    except Exception as e:
        log(e)
        raise


def getDate():
    """
    Retourne la date du jour sous le format 'yyyy-mm-dd"
    """
    date_ajd = str(t.localtime().tm_year)+"-"+str(t.localtime().tm_mon)+"-"+str(t.localtime().tm_mday)
    return date_ajd

# Fonction pour compter le nombre de mots
def count_words(text):
    """Compte le nombre de mots dans un texte"""
    if not text:
        return 0
    words = re.findall(r'\w+', text)
    return len(words)

def json_print(obj):
    """
    Affiche joliment un objet au format JSON.
    Si l'objet est une chaîne (str), tente de le parser en JSON avant affichage.
    Si l'objet est un dict ou une liste, l'affiche directement.
    """
    if isinstance(obj, str):
        try:
            parsed = json.loads(obj)
            print(json.dumps(parsed, indent=3, ensure_ascii=False))
        except Exception:
            print(obj)  # Affiche la chaîne brute si ce n'est pas du JSON
    else:
        print(json.dumps(obj, indent=3, ensure_ascii=False))


def clean_nul_bytes(text: str) -> str:
    """
    Clean NUL bytes (0x00) from text
    PostgreSQL doesn't allow NUL bytes in text fields.
    """
    return text.replace('\x00', '')


def clean_nul_bytes_from_dataframe(df: pd.DataFrame, text_columns: list = None) -> pd.DataFrame:
    """
    Clean NUL bytes (0x00) from text columns in a DataFrame.
    PostgreSQL doesn't allow NUL bytes in text fields.
    
    Args:
        df (pd.DataFrame): The DataFrame to clean
        text_columns (list, optional): List of column names to clean. 
                                     If None, will clean all object/string columns.
    
    Returns:
        pd.DataFrame: A copy of the DataFrame with NUL bytes removed from text columns
    """
    df_clean = df.copy()
    
    if text_columns is None:
        # Clean all object/string columns
        text_columns = df_clean.select_dtypes(include=['object', 'string']).columns.tolist()
    
    for col in text_columns:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].astype(str).apply(clean_nul_bytes)
    return df_clean