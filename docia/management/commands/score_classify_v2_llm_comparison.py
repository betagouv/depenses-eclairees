import logging
from pathlib import Path

from django.core.management.base import BaseCommand

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from docia.file_processing.processor.classify.below_median import run_below_median_scoring
from docia.file_processing.processor.classify.constants import DEFAULT_OUTPUT_DIR
from docia.file_processing.processor.classify.llm_comparison_scoring import (
    run_non_target_llm_scoring,
    run_other_target_llm_scoring,
)


class Command(BaseCommand):
    help = "Compare LLM classification vs logreg on DB cohorts (below-median or hors 8 cibles)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--cohort",
            choices=("below-median", "non-target-llm", "other-target-llm"),
            default="non-target-llm",
            help="below-median: ratio < médiane; non-target-llm: hors 8 cibles; "
            "other-target-llm: avenant/devis/BPU/DQE (oublis AE/CCAP/ST/RIB)",
        )
        parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
        parser.add_argument("--out", type=Path, default=None)
        parser.add_argument("--max-rows", type=int, default=None)
        parser.add_argument("--recompute-medians", action="store_true")
        parser.add_argument("--tau", type=float, default=None)
        parser.add_argument("--margin", type=float, default=None)

    def handle(self, *args, **options):
        output_dir = options["output_dir"].resolve()
        common = {
            "output_dir": output_dir,
            "out_path": options["out"],
            "max_rows": options["max_rows"],
            "tau": options["tau"],
            "margin": options["margin"],
        }
        if options["cohort"] == "below-median":
            out_path, stats = run_below_median_scoring(
                **common,
                recompute_medians=options["recompute_medians"],
            )
            self.stdout.write(self.style.SUCCESS(f"below-median scored={stats.scored} -> {out_path}"))
        elif options["cohort"] == "other-target-llm":
            out_path, stats = run_other_target_llm_scoring(**common)
            self.stdout.write(self.style.SUCCESS(f"other-target-llm scored={stats.scored} -> {out_path}"))
        else:
            out_path, stats = run_non_target_llm_scoring(**common)
            self.stdout.write(
                self.style.SUCCESS(
                    f"non-target-llm scored={stats.scored} trio_missed_flags={stats.trio_flags} -> {out_path}"
                )
            )