from __future__ import annotations

import numpy as np
from scipy import sparse
def _feature_names(preprocessor) -> np.ndarray:
    if hasattr(preprocessor, "get_feature_names_out"):
        return preprocessor.get_feature_names_out()
    # Pipeline text_only : un seul step TfidfVectorizer
    return preprocessor.named_steps["text"].get_feature_names_out()


def cluster_top_terms(
    matrix: sparse.csr_matrix,
    labels: np.ndarray,
    preprocessor,
    *,
    top_n: int = 25,
) -> list[dict]:
    names = _feature_names(preprocessor)
    rows: list[dict] = []
    for cluster_id in sorted(np.unique(labels).tolist()):
        idx = np.where(labels == cluster_id)[0]
        if len(idx) == 0:
            continue
        block = matrix[idx]
        mean_vec = np.asarray(block.mean(axis=0)).ravel()
        if mean_vec.size == 0:
            continue
        order = np.argsort(-mean_vec)[:top_n]
        for rank, feat_i in enumerate(order, start=1):
            weight = float(mean_vec[feat_i])
            if weight <= 0:
                continue
            rows.append(
                {
                    "cluster": int(cluster_id),
                    "rank": rank,
                    "feature": str(names[feat_i]),
                    "weight": weight,
                }
            )
    return rows