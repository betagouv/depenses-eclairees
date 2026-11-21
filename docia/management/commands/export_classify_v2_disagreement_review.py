import logging
from pathlib import Path

from django.core.management.base import BaseCommand

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from docia.file_processing.processor.classify.constants import DEFAULT_OUTPUT_DIR
from docia.file_processing.processor.classify.core_four_tracking import export_core_four_review_sample
from docia.file_processing.processor.classify.disagreement_review import (
    export_below_median_disagreement_review,
    export_non_target_trio_review,
    summarize_llm_error_reviews,
)


class Command(BaseCommand):
    help = "Export a human-review CSV for LLM vs logreg disagreements (below-median pool)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--pool",
            choices=("below-median", "non-target-trio", "core-four"),
            default="below-median",
            help="below-median: désaccords sous-médiane; non-target-trio: LLM hors devis/BPU/DQE, logreg accepte le trio",
        )
        parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
        parser.add_argument("--scored-parquet", type=Path, default=None)
        parser.add_argument("--per-pair", type=int, default=20, help="Max rows per (llm, logreg) pair")
        parser.add_argument("--max-total", type=int, default=500)
        parser.add_argument("--min-max-proba", type=float, default=0.85)
        parser.add_argument(
            "--include-rejects",
            action="store_true",
            help="Include rows where logreg would reject (Non classifié)",
        )
        parser.add_argument("--full", action="store_true", help="All disagreements with text (heavy CSV)")
        parser.add_argument("--no-text", action="store_true", help="Skip DB text fetch (IDs only)")
        parser.add_argument(
            "--summarize",
            type=Path,
            default=None,
            help="Only print stats for an existing review CSV (no export)",
        )

    def handle(self, *args, **options):
        if options["summarize"]:
            stats = summarize_llm_error_reviews(options["summarize"])
            self.stdout.write(str(stats))
            return

        if options["pool"] == "core-four":
            out_path = export_core_four_review_sample(
                options["output_dir"].resolve(),
                per_pair=options["per_pair"],
                max_total=options["max_total"],
                min_max_proba=options["min_max_proba"],
            )
            self.stdout.write(self.style.SUCCESS(f"Review CSV: {out_path}"))
            return

        if options["pool"] == "non-target-trio":
            out_path = export_non_target_trio_review(
                options["output_dir"].resolve(),
                per_pair=options["per_pair"],
                max_total=options["max_total"],
            )
            self.stdout.write(self.style.SUCCESS(f"Review CSV: {out_path}"))
            return

        out_path, pairs_path = export_below_median_disagreement_review(
            options["output_dir"].resolve(),
            scored_parquet=options["scored_parquet"],
            per_pair=options["per_pair"],
            max_total=options["max_total"],
            min_max_proba=options["min_max_proba"],
            require_logreg_accept=not options["include_rejects"],
            full_unsampled=options["full"],
            with_text=not options["no_text"],
        )
        self.stdout.write(self.style.SUCCESS(f"Review CSV: {out_path}\nPairs: {pairs_path}"))
        self.stdout.write(
            "Annoter review_ok: non = erreur LLM (silver faux), oui = logreg tort. "
            "review_correct_label = classe réelle si non."
        )
        self.stdout.write(
            "Colonnes num_ej / texte: nécessite DATABASE_URL prod (tunnel Scalingo ouvert)."
        )