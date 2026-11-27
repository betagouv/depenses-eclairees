"""Copie pipeline + seuils + rapports test dans data/classify_v2/releases/<tag>/."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand

from docia.file_processing.processor.classify.constants import (
    CLASSIFIER_ARTIFACT_NAME,
    DEFAULT_OUTPUT_DIR,
    THRESHOLD_ARTIFACT_NAME,
)
from docia.file_processing.processor.classify.label_hierarchy import HIERARCHY_REVISION


class Command(BaseCommand):
    help = "Gèle les artefacts classify_v2 (modèle, seuils, métriques test) dans releases/<tag>/"

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
        parser.add_argument(
            "--tag",
            type=str,
            default=None,
            help="Nom du dossier release (défaut: YYYY-MM-DD_HHMM)",
        )
        parser.add_argument("--note", type=str, default="", help="Courte note (RELEASE.md)")

    def handle(self, *args, **options):
        out = options["output_dir"].resolve()
        tag = options["tag"] or datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
        dest = out / "releases" / tag
        if dest.exists() and any(dest.iterdir()):
            raise FileExistsError(f"Release non vide: {dest}")
        dest.mkdir(parents=True, exist_ok=True)

        artifacts = [
            out / CLASSIFIER_ARTIFACT_NAME,
            out / THRESHOLD_ARTIFACT_NAME,
        ]
        reports = [
            out / "reports" / "05_metrics.json",
            out / "reports" / "05_test_summary.md",
            out / "reports" / "RUN_SUMMARY.md",
            out / "reports" / "05_confusion_matrix.csv",
        ]
        missing = [p for p in artifacts + reports if not p.is_file()]
        if missing:
            raise FileNotFoundError("Fichiers manquants:\n" + "\n".join(str(p) for p in missing))

        for src in artifacts:
            shutil.copy2(src, dest / src.name)
        rep_dest = dest / "reports"
        rep_dest.mkdir(parents=True, exist_ok=True)
        for src in reports:
            shutil.copy2(src, rep_dest / src.name)

        git_sha = ""
        try:
            git_sha = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                text=True,
                cwd=Path.cwd(),
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        metrics = json.loads((rep_dest / "05_metrics.json").read_text(encoding="utf-8"))
        th = json.loads((dest / THRESHOLD_ARTIFACT_NAME).read_text(encoding="utf-8"))
        note = options["note"].strip()
        lines = [
            f"# Classify v2 release `{tag}`",
            "",
            f"- **Date (UTC)** : {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
            f"- **Git** : `{git_sha[:12]}`" if git_sha else "- **Git** : n/a",
            f"- **HIERARCHY_REVISION** : `{HIERARCHY_REVISION}`",
            f"- **Seuils** : tau={th.get('tau')}, margin={th.get('margin')}",
            f"- **macro_f1 (test prod)** : {metrics.get('macro_f1')}",
            f"- **macro_f1_classifier** : {metrics.get('macro_f1_classifier')}",
            "",
        ]
        if note:
            lines.extend([f"**Note** : {note}", ""])
        lines.extend(
            [
                "## Fichiers",
                "",
                f"- `{CLASSIFIER_ARTIFACT_NAME}`",
                f"- `{THRESHOLD_ARTIFACT_NAME}`",
                "- `reports/05_metrics.json`, `05_test_summary.md`, `RUN_SUMMARY.md`, `05_confusion_matrix.csv`",
                "",
                "Charger : `load_pipeline(Path('.../releases/<tag>'))` + lire `classify_v2_thresholds.json`.",
            ]
        )
        (dest / "RELEASE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(str(dest)))
        self.stdout.write(f"macro_f1={metrics.get('macro_f1')}")