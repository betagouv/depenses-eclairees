import logging
from pathlib import Path

from django.core.management.base import BaseCommand

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from docia.file_processing.processor.classify.constants import (
    DEFAULT_MAX_LLM_FALLBACK_RATE,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SEED,
)
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
            help="Train sur label_train coarse (label_hierarchy.py, 17 parents)",
        )
        parser.add_argument(
            "--train-sample-n",
            type=int,
            default=None,
            help="Plafond global optionnel après sampling (sinon taille = équilibre priorités + autres)",
        )
        parser.add_argument(
            "--train-sample-mode",
            choices=("stratified", "priority_undersample"),
            default="stratified",
            help="Avec --coarse-hierarchy, stratified bascule en priority_undersample",
        )
        parser.add_argument(
            "--priority-per-class-n",
            type=int,
            default=None,
            help="Max docs par classe PRIORITY_COARSE_LABELS (défaut: effectif acte_engagement sur train)",
        )
        parser.add_argument(
            "--non-priority-cap",
            type=int,
            default=None,
            help="Plafond par classe hors priorité (défaut = priority-per-class-n)",
        )
        parser.add_argument(
            "--c-grid",
            type=float,
            nargs="+",
            default=None,
            help="Valeurs C pour la grille logreg (défaut 1e-3..100)",
        )
        parser.add_argument(
            "--max-llm-fallback-rate",
            type=float,
            default=DEFAULT_MAX_LLM_FALLBACK_RATE,
            help="Plafond fraction docs → LLM lors du choix tau/margin (calib)",
        )
        parser.add_argument(
            "--no-fallback-cap",
            action="store_true",
            help="Choix seuils sans plafond llm_fallback (ancien comportement)",
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
            train_sample_n=options["train_sample_n"],
            train_sample_mode=options["train_sample_mode"],
            non_priority_cap=options["non_priority_cap"],
            priority_per_class_n=options["priority_per_class_n"],
            c_grid=options["c_grid"],
            max_llm_fallback_rate=None if options["no_fallback_cap"] else options["max_llm_fallback_rate"],
        )
        self.stdout.write(self.style.SUCCESS("Training complete; see data/classify_v2/reports/"))