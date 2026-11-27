import logging
from pathlib import Path

from django.core.management.base import BaseCommand

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from docia.file_processing.processor.classify.constants import DEFAULT_OUTPUT_DIR
from docia.file_processing.processor.classify.label_hierarchy import (
    COARSE_ACTE_ENGAGEMENT,
    COARSE_CCAP,
    COARSE_SOUS_TRAITANCE,
)
from docia.file_processing.processor.classify.train_set_review import (
    export_coarse_classes_below_threshold_review,
    score_train_split_from_parquet,
)

DEFAULT_BELOW_THRESHOLD_CLASSES = (
    COARSE_CCAP,
    COARSE_ACTE_ENGAGEMENT,
    COARSE_SOUS_TRAITANCE,
)


class Command(BaseCommand):
    help = (
        "Exporte ccap, acte_engagement, sous_traitance sous le seuil prod "
        "(train + calib + test) dans 15_train_ccap_below_threshold_review.csv."
    )

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
        parser.add_argument("--scored-parquet", type=Path, default=None)
        parser.add_argument(
            "--rescore",
            action="store_true",
            help="Rescore tout le train avant export (long)",
        )
        parser.add_argument(
            "--coarse-classes",
            type=str,
            default=",".join(DEFAULT_BELOW_THRESHOLD_CLASSES),
            help="label_train coarse, séparés par des virgules (défaut: ccap,acte_engagement,sous_traitance)",
        )
        parser.add_argument(
            "--splits",
            type=str,
            default="calib,test",
            help="Splits additionnels au train, séparés par des virgules (défaut: calib,test)",
        )

    def handle(self, *args, **options):
        out = options["output_dir"].resolve()
        if options["rescore"]:
            score_train_split_from_parquet(
                out,
                out_path=options["scored_parquet"] or (out / "train_scored.parquet"),
            )
        extra = tuple(s.strip() for s in options["splits"].split(",") if s.strip())
        classes = tuple(c.strip() for c in options["coarse_classes"].split(",") if c.strip())
        csv_path, summary_path = export_coarse_classes_below_threshold_review(
            out,
            coarse_classes=classes,
            scored_parquet=options["scored_parquet"],
            rescore=False,
            extra_splits=extra,
        )
        self.stdout.write(self.style.SUCCESS(str(csv_path)))
        self.stdout.write(f"Summary: {summary_path}")