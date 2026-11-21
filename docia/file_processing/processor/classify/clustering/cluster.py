from __future__ import annotations

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

SILHOUETTE_SAMPLE_CAP = 10_000


def _silhouette(reduced: np.ndarray, labels: np.ndarray, seed: int) -> float:
    n = len(labels)
    if n < 3 or len(np.unique(labels)) < 2:
        return float("nan")
    if n > SILHOUETTE_SAMPLE_CAP:
        rng = np.random.default_rng(seed)
        idx = rng.choice(n, size=SILHOUETTE_SAMPLE_CAP, replace=False)
        reduced = reduced[idx]
        labels = labels[idx]
    return float(silhouette_score(reduced, labels))


def _min_cluster_ok(labels: np.ndarray, n: int, min_cluster_frac: float) -> bool:
    min_n = max(50, int(min_cluster_frac * n))
    sizes = np.bincount(labels)
    return int(sizes.min()) >= min_n


def choose_best_k(
    rows: list[dict],
    labels_by_k: dict[int, np.ndarray],
    n: int,
    *,
    min_cluster_frac: float = 0.01,
    silhouette_plateau: float = 0.02,
    k_cap_silhouette: int = 8,
) -> tuple[int, str]:
    """Évite k trop grand : plateau silhouette + taille minimale de grappe."""
    valid = [r for r in rows if not np.isnan(r["silhouette"])]
    if not valid:
        return min(labels_by_k), "fallback_min_k"
    max_sil = max(r["silhouette"] for r in valid)
    plateau = [r for r in valid if r["silhouette"] >= max_sil - silhouette_plateau]
    plateau.sort(key=lambda r: r["k"])
    for row in plateau:
        k = int(row["k"])
        if _min_cluster_ok(labels_by_k[k], n, min_cluster_frac):
            return k, "silhouette_plateau_min_cluster_size"
    capped = [r for r in valid if r["k"] <= k_cap_silhouette]
    if capped:
        pick = max(capped, key=lambda r: r["silhouette"])
        return int(pick["k"]), f"max_silhouette_k_lte_{k_cap_silhouette}"
    pick = max(valid, key=lambda r: r["silhouette"])
    return int(pick["k"]), "max_silhouette"


def grid_kmeans(
    reduced: np.ndarray,
    k_min: int,
    k_max: int,
    seed: int,
    *,
    min_cluster_frac: float = 0.01,
    silhouette_plateau: float = 0.02,
    k_cap_silhouette: int = 8,
) -> tuple[list[dict], int, np.ndarray, str]:
    n = reduced.shape[0]
    k_hi = min(k_max, n - 1)
    k_lo = max(2, k_min)
    rows: list[dict] = []
    labels_by_k: dict[int, np.ndarray] = {}

    for k in range(k_lo, k_hi + 1):
        km = KMeans(n_clusters=k, n_init="auto", random_state=seed)
        labels = km.fit_predict(reduced)
        labels_by_k[k] = labels
        sil = _silhouette(reduced, labels, seed)
        sizes = np.bincount(labels)
        rows.append(
            {
                "k": k,
                "inertia": float(km.inertia_),
                "silhouette": sil,
                "min_cluster_size": int(sizes.min()),
                "max_cluster_size": int(sizes.max()),
            }
        )

    best_k, criterion = choose_best_k(
        rows,
        labels_by_k,
        n,
        min_cluster_frac=min_cluster_frac,
        silhouette_plateau=silhouette_plateau,
        k_cap_silhouette=k_cap_silhouette,
    )
    return rows, best_k, labels_by_k[best_k], criterion