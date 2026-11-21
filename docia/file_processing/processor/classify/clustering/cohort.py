from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

COHORT_COLUMNS = (
    "id",
    "hash",
    "classification",
    "text_2000",
    "filename_normalized",
    "nb_mot",
    "num_ej",
    "split",
)


@dataclass
class CohortStats:
    rows_matching: int
    rows_nonempty_text: int
    rows_dedup: int
    dropped_duplicates: int
    split_counts: dict[str, int]


def load_cohort(parquet_path: Path, classification: str) -> tuple[pd.DataFrame, CohortStats]:
    path = parquet_path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    df = pd.read_parquet(path, columns=list(COHORT_COLUMNS))
    mask = df["classification"].astype(str) == classification
    sub = df.loc[mask].copy()
    n_matching = len(sub)
    sub = sub[sub["text_2000"].fillna("").astype(str).str.strip().ne("")]
    n_nonempty = len(sub)
    sub = sub.drop_duplicates(subset=["hash"], keep="first")
    n_dedup = len(sub)
    split_counts = sub["split"].fillna("none").astype(str).value_counts().to_dict()
    stats = CohortStats(
        rows_matching=n_matching,
        rows_nonempty_text=n_nonempty,
        rows_dedup=n_dedup,
        dropped_duplicates=n_nonempty - n_dedup,
        split_counts={str(k): int(v) for k, v in split_counts.items()},
    )
    sub["nb_mot"] = sub["nb_mot"].fillna(0)
    return sub, stats