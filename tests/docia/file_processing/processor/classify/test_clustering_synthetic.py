import numpy as np
import pandas as pd

from docia.file_processing.processor.classify.clustering.cluster import grid_kmeans
from docia.file_processing.processor.classify.clustering.vectorize import fit_transform_features


def test_kmeans_separates_two_lexical_themes():
    n = 40
    df_a = pd.DataFrame(
        {
            "text_2000": ["acte engagement marché titulaire lots clause"] * n,
            "filename_normalized": ["ae_lot1.pdf"] * n,
            "nb_mot": [500] * n,
        }
    )
    df_b = pd.DataFrame(
        {
            "text_2000": ["avenant modification prix reconduction tranche"] * n,
            "filename_normalized": ["avenant_2.pdf"] * n,
            "nb_mot": [400] * n,
        }
    )
    df = pd.concat([df_a, df_b], ignore_index=True)
    matrix, _ = fit_transform_features(df, mode="text_only")
    from sklearn.decomposition import TruncatedSVD

    reduced = TruncatedSVD(n_components=10, random_state=42).fit_transform(matrix)
    rows, best_k, labels, _criterion = grid_kmeans(reduced, 2, 4, seed=42)
    assert best_k >= 2
    assert len(np.unique(labels)) >= 2
    theme_a = labels[:n]
    theme_b = labels[n:]
    assert len(np.unique(theme_a)) == 1
    assert len(np.unique(theme_b)) == 1
    assert theme_a[0] != theme_b[0]
    k2 = next(r for r in rows if r["k"] == 2)
    assert k2["silhouette"] > 0.05