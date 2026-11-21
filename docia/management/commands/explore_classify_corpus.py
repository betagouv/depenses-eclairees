import logging
from pathlib import Path

from django.core.management.base import BaseCommand

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from docia.file_processing.processor.classify.constants import DEFAULT_OUTPUT_DIR, DEFAULT_SEED
from docia.file_processing.processor.classify.corpus_profile import run_vocab_profile


class Command(BaseCommand):
    help = "Courbe vocabulaire TF-IDF texte (prod) vs nombre de documents — parquet offline."

    def add_arguments(self, parser):
        parser.add_argument("--parquet", type=Path, default=None)
        parser.add_argument(
            "--output-dir",
            type=Path,
            default=None,
            help="Défaut data/classify_v2/corpus_profile",
        )
        parser.add_argument(
            "--scope",
            choices=("train", "all"),
            default="train",
            help="train = split train avec label_train ; all = tout le parquet labellisé",
        )
        parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
        parser.add_argument(
            "--n-grid",
            type=int,
            nargs="*",
            default=None,
            help="Tailles N (défaut grille interne + cohort complet en dernier point)",
        )
        parser.add_argument("--by-class", action="store_true", help="Export 02_vocab_vs_n_by_class.csv")

    def handle(self, *args, **options):
        out = run_vocab_profile(
            parquet_path=options["parquet"] or (DEFAULT_OUTPUT_DIR / "documents_raw.parquet"),
            output_dir=options["output_dir"],
            scope=options["scope"],
            seed=options["seed"],
            n_grid=options["n_grid"],
            by_class=options["by_class"],
        )
        self.stdout.write(self.style.SUCCESS(str(out)))