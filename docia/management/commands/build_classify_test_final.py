import logging
from pathlib import Path

from django.core.management.base import BaseCommand

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from docia.file_processing.processor.classify.constants import DEFAULT_OUTPUT_DIR
from docia.file_processing.processor.classify.grist_test_set import (
    DEFAULT_TEST_FINAL_DIR,
    build_test_final_dataframe,
    write_test_final_dataset,
)


class Command(BaseCommand):
    help = "Construit le golden test set classification (Grist → parquet figé, hors train classify_v2)."

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", type=Path, default=DEFAULT_TEST_FINAL_DIR)
        parser.add_argument("--classif-only", action="store_true", help="Uniquement Classif_gt")
        parser.add_argument("--include-fiche-navette", action="store_true")
        parser.add_argument(
            "--classify-v2-parquet",
            type=Path,
            default=None,
            help="Pour joindre in_classify_v2_parquet (défaut data/classify_v2/documents_raw.parquet)",
        )
        parser.add_argument("--dataset-version", type=str, default=None)
        parser.add_argument("--dry-run", action="store_true", help="Stats sans écrire le parquet")
        parser.add_argument(
            "--push-grist",
            action="store_true",
            help="(réservé) Export miroir Grist — non implémenté en v1",
        )
        parser.add_argument(
            "--skip-db-enrich",
            action="store_true",
            help="Ne pas joindre Document (hash → métadonnées prod)",
        )

    def handle(self, *args, **options):
        if options["push_grist"]:
            self.stderr.write(self.style.WARNING("push-grist non implémenté en v1"))

        v2_path = options["classify_v2_parquet"]
        if v2_path is None:
            v2_path = DEFAULT_OUTPUT_DIR / "documents_raw.parquet"

        if options["dry_run"]:
            _, _, stats = build_test_final_dataframe(
                classif_only=options["classif_only"],
                include_fiche_navette=options["include_fiche_navette"],
                classify_v2_parquet=v2_path,
                enrich_from_db=not options["skip_db_enrich"],
            )
            self.stdout.write(f"Dry-run stats: {stats}")
            return

        path, stats = write_test_final_dataset(
            options["output_dir"].resolve(),
            dataset_version=options["dataset_version"],
            classif_only=options["classif_only"],
            include_fiche_navette=options["include_fiche_navette"],
            classify_v2_parquet=v2_path,
            dry_run=False,
            enrich_from_db=not options["skip_db_enrich"],
        )
        self.stdout.write(self.style.SUCCESS(f"Test final: {path}\n{stats}"))