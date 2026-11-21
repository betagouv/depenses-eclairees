import logging
from pathlib import Path

from django.core.management.base import BaseCommand

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from docia.file_processing.processor.classify.constants import DEFAULT_OUTPUT_DIR, DEFAULT_SEED
from docia.file_processing.processor.classify.pipeline import run_training


class Command(BaseCommand):
    help = "Train classify v2 model from parquet (PR B)"

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
        parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
        parser.add_argument("--require-human-audit", action="store_true")
        parser.add_argument("--audit-csv", type=Path, default=None)
        parser.add_argument("--disagreement-review-csv", type=Path, default=None)
        parser.add_argument("--merge-financial", action="store_true")
        parser.add_argument("--write-patched-parquet", action="store_true")
        parser.add_argument(
            "--coarse-hierarchy",
            action="store_true",
            help="Train sur label_train coarse (label_hierarchy.py, 19 parents)",
        )

    def handle(self, *args, **options):
        run_training(
            output_dir=options["output_dir"].resolve(),
            seed=options["seed"],
            require_human_audit=options["require_human_audit"],
            audit_csv=options["audit_csv"],
            disagreement_review_csv=options["disagreement_review_csv"],
            merge_financial=options["merge_financial"],
            write_patched_parquet=options["write_patched_parquet"],
            coarse_hierarchy=options["coarse_hierarchy"],
        )
        self.stdout.write(self.style.SUCCESS("Training complete; see data/classify_v2/reports/"))