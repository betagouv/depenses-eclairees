import logging
from pathlib import Path

from django.core.management.base import BaseCommand

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from docia.file_processing.processor.classify.clustering import CORE_FIVE_LLM, run_class_exploration
from docia.file_processing.processor.classify.constants import DEFAULT_OUTPUT_DIR, DEFAULT_SEED


class Command(BaseCommand):
    help = "Exploration k-means par libellé LLM (TF-IDF + SVD, hors modèle prod)."

    def add_arguments(self, parser):
        parser.add_argument(
            "classification",
            nargs="?",
            help="Libellé LLM (ex. acte_engagement). Ignoré si --all-core-five.",
        )
        parser.add_argument("--all-core-five", action="store_true")
        parser.add_argument("--parquet", type=Path, default=None)
        parser.add_argument("--output-dir", type=Path, default=None, help="Racine clustering (défaut data/classify_v2/clustering)")
        parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
        parser.add_argument("--k-min", type=int, default=2)
        parser.add_argument("--k-max", type=int, default=8)
        parser.add_argument("--svd-components", type=int, default=100)
        parser.add_argument("--samples-per-cluster", type=int, default=30)
        parser.add_argument(
            "--features",
            choices=("text_only", "full"),
            default="text_only",
            help="text_only (défaut, audit sémantique) ou full (= logreg)",
        )

    def handle(self, *args, **options):
        parquet = options["parquet"] or (DEFAULT_OUTPUT_DIR / "documents_raw.parquet")
        out_root = options["output_dir"] or (DEFAULT_OUTPUT_DIR / "clustering")
        labels = list(CORE_FIVE_LLM) if options["all_core_five"] else []
        if not labels:
            label = options["classification"]
            if not label:
                raise SystemExit("Indiquer classification ou --all-core-five")
            labels = [label]

        common = dict(
            parquet_path=parquet,
            output_root=out_root,
            seed=options["seed"],
            k_min=options["k_min"],
            k_max=options["k_max"],
            svd_components=options["svd_components"],
            samples_per_cluster=options["samples_per_cluster"],
            feature_mode=options["features"],
        )
        for cls in labels:
            path = run_class_exploration(cls, **common)
            self.stdout.write(self.style.SUCCESS(f"{cls} -> {path}"))