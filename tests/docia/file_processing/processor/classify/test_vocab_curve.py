import pandas as pd

from docia.file_processing.processor.classify.corpus_profile.vocab_curve import vocab_curve_global


def test_vocab_curve_grows_then_plateaus_on_repetitive_corpus():
    n = 50
    df_a = pd.DataFrame(
        {
            "text_2000": ["alpha beta gamma clause marché titulaire"] * n,
            "label_train": ["acte_engagement"] * n,
        }
    )
    df_b = pd.DataFrame(
        {
            "text_2000": ["delta epsilon prix avenant reconduction"] * n,
            "label_train": ["avenant"] * n,
        }
    )
    df = pd.concat([df_a, df_b], ignore_index=True)
    grid = [20, 50, 100]
    rows = vocab_curve_global(df, grid, seed=42)
    assert len(rows) == 3
    sizes = [r["vocab_size"] for r in rows]
    assert sizes[0] <= sizes[1] <= sizes[-1]
    assert rows[-1]["n_docs"] == len(df)
    assert rows[0]["new_types_vs_prev"] is None
    assert rows[1]["new_types_vs_prev"] is not None