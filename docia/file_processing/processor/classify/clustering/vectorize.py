from __future__ import annotations

from typing import Literal

import pandas as pd
from scipy import sparse
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline

from docia.file_processing.processor.classify.constants import MAX_TFIDF_FEATURES
from docia.file_processing.processor.classify.features import build_feature_preprocessor
from docia.file_processing.processor.classify.clustering.french_stop_words import FRENCH_STOP_WORDS

FeatureMode = Literal["text_only", "full"]

# Exclut les codes postaux / numéros de marché isolés (ex. 2124, 75042).
_LETTER_TOKEN_PATTERN = r"(?u)\b[^\d\W]\w+\b"


def build_text_only_preprocessor(n_samples: int) -> Pipeline:
    """TF-IDF texte seul (exploration : stop français, min_df adaptatif, max_df)."""
    min_df = max(2, min(10, n_samples // 500))
    return Pipeline(
        steps=[
            (
                "text",
                TfidfVectorizer(
                    analyzer="word",
                    ngram_range=(1, 2),
                    min_df=min_df,
                    max_df=0.85,
                    max_features=MAX_TFIDF_FEATURES,
                    sublinear_tf=True,
                    stop_words=list(FRENCH_STOP_WORDS),
                    token_pattern=_LETTER_TOKEN_PATTERN,
                ),
            ),
        ]
    )


def feature_frame(df: pd.DataFrame, mode: FeatureMode) -> pd.DataFrame:
    if mode == "text_only":
        return df[["text_2000"]].copy()
    x = df[["text_2000", "filename_normalized", "nb_mot"]].copy()
    x["nb_mot"] = x["nb_mot"].fillna(0)
    return x


def fit_transform_features(
    df: pd.DataFrame,
    *,
    mode: FeatureMode = "text_only",
) -> tuple[sparse.csr_matrix, Pipeline | ColumnTransformer]:
    if mode == "text_only":
        preprocessor = build_text_only_preprocessor(len(df))
    else:
        preprocessor = build_feature_preprocessor()
    x = feature_frame(df, mode)
    if mode == "text_only":
        matrix = preprocessor.fit_transform(x["text_2000"].fillna("").astype(str))
    else:
        matrix = preprocessor.fit_transform(x)
    if not sparse.issparse(matrix):
        matrix = sparse.csr_matrix(matrix)
    return matrix, preprocessor