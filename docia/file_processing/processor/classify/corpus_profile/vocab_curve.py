from __future__ import annotations

import time
from typing import Literal

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from docia.file_processing.processor.classify.constants import DEFAULT_SEED, MAX_TFIDF_FEATURES

DEFAULT_N_GRID: tuple[int, ...] = (
    1_000,
    2_500,
    5_000,
    10_000,
    25_000,
    50_000,
    100_000,
    150_000,
    200_000,
)

Scope = Literal["train", "all"]


def build_prod_text_vectorizer() -> TfidfVectorizer:
    """Miroir branche texte de build_feature_preprocessor (prod)."""
    return TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        min_df=2,
        max_features=MAX_TFIDF_FEATURES,
        sublinear_tf=True,
    )


def load_cohort(parquet_path, *, scope: Scope = "train") -> pd.DataFrame:
    cols = ["text_2000", "label_train", "split"]
    df = pd.read_parquet(parquet_path, columns=cols)
    df = df[df["label_train"].notna() & df["text_2000"].fillna("").astype(str).str.strip().ne("")]
    if scope == "train":
        df = df[df["split"] == "train"]
    return df.reset_index(drop=True)


def _allocate_per_label(counts: dict[str, int], n: int) -> dict[str, int]:
    total = sum(counts.values())
    if n >= total:
        return dict(counts)
    labels = sorted(counts.keys())
    raw = {lb: n * counts[lb] / total for lb in labels}
    alloc = {lb: int(raw[lb]) for lb in labels}
    # ensure at least min_df support where possible
    for lb in labels:
        if counts[lb] > 0 and alloc[lb] == 0 and n >= len(labels):
            alloc[lb] = 1
    short = n - sum(alloc.values())
    order = sorted(labels, key=lambda lb: raw[lb] - int(raw[lb]), reverse=True)
    i = 0
    while short > 0 and order:
        lb = order[i % len(order)]
        if alloc[lb] < counts[lb]:
            alloc[lb] += 1
            short -= 1
        i += 1
        if i > len(order) * total:
            break
    return alloc


def _shuffled_by_label(df: pd.DataFrame, seed: int) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for label, grp in df.groupby("label_train", sort=True):
        lb = str(label)
        out[lb] = grp.sample(frac=1.0, random_state=seed + hash(lb) % 10_000).reset_index(drop=True)
    return out


def nested_stratified_take(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    if len(df) <= n:
        return df
    by_label = _shuffled_by_label(df, seed)
    counts = {lb: len(g) for lb, g in by_label.items()}
    alloc = _allocate_per_label(counts, n)
    parts = [by_label[lb].iloc[: alloc[lb]] for lb in sorted(alloc) if alloc[lb] > 0]
    return pd.concat(parts, ignore_index=True)


def resolve_n_grid(requested: list[int] | None, cohort_n: int) -> list[int]:
    base = list(requested or DEFAULT_N_GRID)
    seen: set[int] = set()
    grid: list[int] = []
    for x in base:
        if x not in seen and x > 0:
            seen.add(x)
            grid.append(min(x, cohort_n))
    if cohort_n not in seen:
        grid.append(cohort_n)
    return sorted(set(grid))


def fit_vocab_size(texts: pd.Series) -> tuple[int, bool, float]:
    vec = build_prod_text_vectorizer()
    t0 = time.perf_counter()
    vec.fit(texts.fillna("").astype(str))
    elapsed = time.perf_counter() - t0
    names = vec.get_feature_names_out()
    size = len(names)
    hit_cap = size >= MAX_TFIDF_FEATURES
    return size, hit_cap, elapsed


def vocab_curve_global(
    df: pd.DataFrame,
    n_grid: list[int],
    seed: int = DEFAULT_SEED,
) -> list[dict]:
    texts = df["text_2000"]
    rows: list[dict] = []
    prev_size: int | None = None
    for n in n_grid:
        sub = nested_stratified_take(df, n, seed)
        size, hit_cap, fit_s = fit_vocab_size(sub["text_2000"])
        row = {
            "n_docs": len(sub),
            "n_target": n,
            "vocab_size": size,
            "hit_max_features": hit_cap,
            "new_types_vs_prev": (size - prev_size) if prev_size is not None else None,
            "fit_seconds": round(fit_s, 3),
        }
        rows.append(row)
        prev_size = size
    return rows


def vocab_curve_by_class(
    df: pd.DataFrame,
    n_grid: list[int],
    labels: list[str],
    seed: int = DEFAULT_SEED,
) -> list[dict]:
    rows: list[dict] = []
    for label in labels:
        sub_all = df[df["label_train"].astype(str) == label]
        if sub_all.empty:
            continue
        class_grid = resolve_n_grid(n_grid, len(sub_all))
        prev_size: int | None = None
        for n in class_grid:
            sub = nested_stratified_take(sub_all, n, seed)
            size, hit_cap, fit_s = fit_vocab_size(sub["text_2000"])
            rows.append(
                {
                    "label_train": label,
                    "n_docs": len(sub),
                    "n_target": n,
                    "vocab_size": size,
                    "hit_max_features": hit_cap,
                    "new_types_vs_prev": (size - prev_size) if prev_size is not None else None,
                    "fit_seconds": round(fit_s, 3),
                }
            )
            prev_size = size
    return rows


def labels_for_by_class(df: pd.DataFrame, *, priority_only: bool = False) -> list[str]:
    from docia.file_processing.processor.classify.label_hierarchy import PRIORITY_COARSE_LABELS

    counts = df["label_train"].astype(str).value_counts()
    if priority_only:
        labels = [lb for lb in sorted(PRIORITY_COARSE_LABELS) if lb in counts.index]
        return labels
    priority = [lb for lb in sorted(PRIORITY_COARSE_LABELS) if lb in counts.index]
    rest = [lb for lb in counts.index.tolist() if lb not in PRIORITY_COARSE_LABELS]
    return priority + rest