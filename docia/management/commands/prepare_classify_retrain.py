import logging
from pathlib import Path

from django.core.management.base import BaseCommand

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from docia.file_processing.processor.classify.constants import DEFAULT_OUTPUT_DIR
from docia.file_processing.processor.classify.label_hierarchy import COARSE_LABELS, HIERARCHY_REVISION
from docia.file_processing.processor.classify.pipeline import report_hierarchy_gaps
from docia.file_processing.processor.classify.silver_corrections import export_silver_corrections


class Command(BaseCommand):
    help = "Prépare le réentraînement : fusion corrections silver + audit trous hierarchy."

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)

    def handle(self, *args, **options):
        out_dir = options["output_dir"].resolve()
        corrections = export_silver_corrections(out_dir)
        try:
            gaps = report_hierarchy_gaps(out_dir)
        except FileNotFoundError:
            gaps = None
        self.stdout.write(self.style.SUCCESS(f"Silver corrections: {corrections}"))
        if gaps:
            self.stdout.write(f"Unmapped prod labels (n>=100): {gaps}")
        self.stdout.write(f"Hierarchy revision={HIERARCHY_REVISION} parents={list(COARSE_LABELS)}")
        self.stdout.write(
            "\nEnsuite:\n"
            "  python manage.py build_classify_v2_dataset --coarse-hierarchy\n"
            "  python manage.py train_classify_v2 --coarse-hierarchy "
            "--disagreement-review-csv data/classify_v2/reports/11_silver_corrections_for_train.csv "
            "--write-patched-parquet\n"
        )