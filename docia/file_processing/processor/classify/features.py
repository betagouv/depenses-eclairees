from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from docia.file_processing.processor.classify.constants import MAX_TFIDF_FEATURES


def build_feature_preprocessor() -> ColumnTransformer:
    text_vectorizer = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        min_df=2,
        max_features=MAX_TFIDF_FEATURES,
        sublinear_tf=True,
    )
    filename_vectorizer = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        min_df=2,
        max_features=10_000,
        sublinear_tf=True,
    )
    return ColumnTransformer(
        transformers=[
            ("text", text_vectorizer, "text_2000"),
            ("filename", filename_vectorizer, "filename_normalized"),
            ("nb_mot", StandardScaler(), ["nb_mot"]),
        ],
        sparse_threshold=0.3,
    )


def build_model_pipeline(classifier) -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocess", build_feature_preprocessor()),
            ("clf", classifier),
        ]
    )