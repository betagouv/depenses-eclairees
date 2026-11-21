import logging
from pathlib import Path

from django.core.management.base import BaseCommand

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from docia.file_processing.processor.classify.constants import DEFAULT_OUTPUT_DIR
from docia.file_processing.processor.classify.core_four_tracking import (
    build_core_four_reports,
    export_core_four_review_sample,
    summarize_core_four_review,
)
from docia.file_processing.processor.classify.llm_comparison_scoring import run_other_target_llm_scoring


class Command(BaseCommand):
    help = (
        "Agrège les scorings (hors cible, sous-médiane, autres cibles 8 classes) "
        "et liste les oublis LLM pour acte_engagement / ccap / sous_traitance / rib."
    )

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
        parser.add_argument(
            "--score-other-targets",
            action="store_true",
            help="Score avenant/devis/BPU/DQE en DB si other_target_llm_scored.parquet absent",
        )
        parser.add_argument("--skip-review-export", action="store_true")
        parser.add_argument("--per-pair", type=int, default=15)
        parser.add_argument("--max-total", type=int, default=400)
        parser.add_argument("--min-max-proba", type=float, default=0.85)
        parser.add_argument(
            "--summarize-review",
            type=Path,
            default=None,
            help="Agrège un CSV annoté (ex. 10_core_four_miss_review_sample.csv) et sort les oublis confirmés",
        )

    def handle(self, *args, **options):
        if options["summarize_review"]:
            stats = summarize_core_four_review(
                options["summarize_review"].resolve(),
                options["output_dir"].resolve(),
            )
            self.stdout.write(self.style.SUCCESS(str(stats)))
            return

        output_dir = options["output_dir"].resolve()
        other_path = output_dir / "other_target_llm_scored.parquet"
        if options["score_other_targets"] or not other_path.is_file():
            self.stdout.write("Scoring autres cibles (avenant, devis, BPU, DQE)…")
            run_other_target_llm_scoring(output_dir)

        summary, candidates, n = build_core_four_reports(output_dir)
        self.stdout.write(self.style.SUCCESS(f"Candidats oubli core-four: {n} -> {candidates}"))
        self.stdout.write(f"Résumé: {summary}")

        if not options["skip_review_export"]:
            review = export_core_four_review_sample(
                output_dir,
                per_pair=options["per_pair"],
                max_total=options["max_total"],
                min_max_proba=options["min_max_proba"],
            )
            self.stdout.write(self.style.SUCCESS(f"Échantillon revue: {review}"))