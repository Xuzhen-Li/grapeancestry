"""IBD / kinship matrix (KING-like) on a dosage subset."""

from __future__ import annotations

import numpy as np

from grapeancestry.identity.parentage import kinship_king


def kinship_matrix(mat: np.ndarray) -> np.ndarray:
    n = mat.shape[0]
    K = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            k = kinship_king(mat[i], mat[j])
            K[i, j] = K[j, i] = k
    return K
