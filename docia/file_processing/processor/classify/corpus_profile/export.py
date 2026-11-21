from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from docia.file_processing.processor.classify.constants import MAX_TFIDF_FEATURES


def write_summary(
    out_dir: Path,
    global_rows: list[dict],
    *,
    scope: str,
    cohort_n: int,
    duration_s: float,
) -> None:
    lines = [
        "# Corpus profile — vocab vs N",
        "",
        f"- scope: `{scope}`",
        f"- cohort_rows: {cohort_n}",
        f"- max_features (prod text): {MAX_TFIDF_FEATURES}",
        f"- run_duration_s: {duration_s:.1f}",
        "",
    ]
    if not global_rows:
        lines.append("Aucune courbe produite.")
        (out_dir / "00_summary.md").write_text("\n".join(lines), encoding="utf-8")
        return

    last = global_rows[-1]
    hits = sum(1 for r in global_rows if r.get("hit_max_features"))
    lines.extend(
        [
            "## Dernier point",
            "",
            f"- n_docs: {last['n_docs']}",
            f"- vocab_size: {last['vocab_size']}",
            f"- hit_max_features: {last['hit_max_features']}",
            "",
            "## Interprétation",
            "",
        ]
    )
    if last["hit_max_features"] and hits >= 2:
        margins = [r.get("new_types_vs_prev") for r in global_rows if r.get("new_types_vs_prev") is not None]
        low_margin = margins and margins[-1] is not None and margins[-1] < 500
        if low_margin:
            lines.append(
                "- **Saturation probable** : plafond `max_features` atteint et faible gain de types en fin de courbe."
            )
            lines.append("  → Ajouter des documents enrichit peu le texte TF-IDF sans monter le cap ou changer le préprocesseur.")
        else:
            lines.append(
                "- Plafond `max_features` atteint mais la pente marginale reste notable : vérifier classes rares (`02_*`)."
            )
    elif not last["hit_max_features"]:
        lines.append(
            "- **Pas encore saturé** au plafond 50k : le corpus continue d’ajouter des types observables à l’échelle actuelle."
        )
    else:
        lines.append("- Courbe intermédiaire : voir `01_vocab_vs_n.csv` pour la pente marginale.")

    (out_dir / "00_summary.md").write_text("\n".join(lines), encoding="utf-8")


def write_exports(
    out_dir: Path,
    *,
    global_rows: list[dict],
    by_class_rows: list[dict] | None,
    manifest: dict,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(global_rows).to_csv(out_dir / "01_vocab_vs_n.csv", index=False)
    if by_class_rows:
        pd.DataFrame(by_class_rows).to_csv(out_dir / "02_vocab_vs_n_by_class.csv", index=False)
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")