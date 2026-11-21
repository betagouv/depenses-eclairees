import logging
from pathlib import Path

from django.core.management.base import BaseCommand

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from docia.file_processing.processor.classify.below_median import run_below_median_scoring
from docia.file_processing.processor.classify.constants import DEFAULT_OUTPUT_DIR


class Command(BaseCommand):
    help = (
        "Score documents excluded at dataset build (ratio < class median): "
        "compare llm_pred (DB classification) vs logreg_pred."
    )

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
        parser.add_argument(
            "--out",
            type=Path,
            default=None,
            help="Parquet path (default: <output-dir>/below_median_scored.parquet)",
        )
        parser.add_argument("--max-rows", type=int, default=None, help="Cap scored rows (pilot / dev)")
        parser.add_argument(
            "--recompute-medians",
            action="store_true",
            help="Recompute class medians from DB instead of dataset_manifest.json",
        )
        parser.add_argument("--tau", type=float, default=None)
        parser.add_argument("--margin", type=float, default=None)

    def handle(self, *args, **options):
        out_path, stats = run_below_median_scoring(
            options["output_dir"].resolve(),
            out_path=options["out"],
            max_rows=options["max_rows"],
            recompute_medians=options["recompute_medians"],
            tau=options["tau"],
            margin=options["margin"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Scored {stats.scored} below-median docs (excluded pool={stats.excluded_below_median}) -> {out_path}"
            )
        )