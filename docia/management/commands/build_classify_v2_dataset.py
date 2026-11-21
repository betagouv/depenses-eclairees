import logging
from pathlib import Path

from django.core.management.base import BaseCommand

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from docia.file_processing.processor.classify.constants import DEFAULT_OUTPUT_DIR, DEFAULT_SEED
from docia.file_processing.processor.classify.pipeline import run_dataset_build


class Command(BaseCommand):
    help = "Build classify v2 dataset parquet, splits, and reports (PR A)"

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
        parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
        parser.add_argument("--rejection-budget", type=int, default=None)
        parser.add_argument("--strict-audit", action="store_true")
        parser.add_argument("--stop-after-audit", action="store_true")
        parser.add_argument(
            "--coarse-hierarchy",
            action="store_true",
            help="Dataset avec parents coarse (label_hierarchy.py, 19 classes trainables)",
        )

    def handle(self, *args, **options):
        path = run_dataset_build(
            output_dir=options["output_dir"].resolve(),
            seed=options["seed"],
            rejection_budget=options["rejection_budget"],
            strict_audit=options["strict_audit"],
            stop_after_audit=options["stop_after_audit"],
            coarse_hierarchy=options["coarse_hierarchy"],
        )
        self.stdout.write(self.style.SUCCESS(f"Dataset written to {path}"))