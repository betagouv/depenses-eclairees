from __future__ import annotations

from dataclasses import dataclass

from scipy import sparse
from sklearn.decomposition import TruncatedSVD


@dataclass
class ReductionResult:
    svd: TruncatedSVD
    reduced: sparse.csr_matrix | object
    explained_variance_ratio: list[float]
    n_components: int


def reduce_svd(matrix: sparse.csr_matrix, n_components: int, seed: int) -> ReductionResult:
    n_samples, n_features = matrix.shape
    n_comp = min(n_components, n_samples - 1, max(1, n_features - 1))
    n_comp = max(2, n_comp)
    svd = TruncatedSVD(n_components=n_comp, random_state=seed)
    reduced = svd.fit_transform(matrix)
    return ReductionResult(
        svd=svd,
        reduced=reduced,
        explained_variance_ratio=svd.explained_variance_ratio_.tolist(),
        n_components=n_comp,
    )