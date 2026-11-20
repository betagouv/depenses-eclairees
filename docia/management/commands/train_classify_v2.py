from pathlib import Path

from django.core.management.base import BaseCommand

from docia.file_processing.processor.classify.constants import DEFAULT_OUTPUT_DIR, DEFAULT_SEED
from docia.file_processing.processor.classify.pipeline import run_training


class Command(BaseCommand):
    help = "Train classify v2 model from parquet (PR B)"

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
        parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
        parser.add_argument("--require-human-audit", action="store_true")
        parser.add_argument("--audit-csv", type=Path, default=None)

    def handle(self, *args, **options):
        run_training(
            output_dir=options["output_dir"].resolve(),
            seed=options["seed"],
            require_human_audit=options["require_human_audit"],
            audit_csv=options["audit_csv"],
        )
        self.stdout.write(self.style.SUCCESS("Training complete; see data/classify_v2/reports/"))