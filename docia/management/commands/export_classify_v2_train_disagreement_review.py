import logging
from pathlib import Path

from django.core.management.base import BaseCommand

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from docia.file_processing.processor.classify.constants import DEFAULT_OUTPUT_DIR
from docia.file_processing.processor.classify.train_set_review import (
    export_train_disagreement_review,
    export_train_priority_agreement_low_confidence_review,
)


class Command(BaseCommand):
    help = (
        "Exporte un échantillon LLM vs logreg sur le split TRAIN (parquet) pour revue silver avant retrain."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--pool",
            choices=("disagree", "priority-agree-low-conf"),
            default="disagree",
            help="disagree: désaccord coarse ; priority-agree-low-conf: accord prioritaire, max_proba basse",
        )
        parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
        parser.add_argument("--parquet", type=Path, default=None, help="documents_raw.parquet")
        parser.add_argument("--scored-parquet", type=Path, default=None)
        parser.add_argument("--rescore", action="store_true", help="Rescore train même si train_scored.parquet existe")
        parser.add_argument("--per-pair", type=int, default=25, help="(disagree) max par paire coarse")
        parser.add_argument(
            "--per-class",
            type=int,
            default=40,
            help="(priority-agree-low-conf) max par classe prioritaire",
        )
        parser.add_argument("--max-total", type=int, default=800)
        parser.add_argument("--min-max-proba", type=float, default=0.85)
        parser.add_argument(
            "--max-proba-ceiling",
            type=float,
            default=0.92,
            help="(priority-agree-low-conf) plafond inclusif exclus",
        )
        parser.add_argument(
            "--min-proba-floor",
            type=float,
            default=0.55,
            help="(priority-agree-low-conf) plancher minimal",
        )
        parser.add_argument(
            "--exclude-ccp-fine",
            action="store_true",
            help="(priority-agree-low-conf) exclure ccp_simple/ccp_vae (artefact joblib 19 classes)",
        )
        parser.add_argument(
            "--require-accept",
            action="store_true",
            help="Uniquement si logreg accepte (max_proba>=tau, hors rejet prod)",
        )
        parser.add_argument(
            "--priority-only",
            action="store_true",
            help="Limiter aux paires touchant PRIORITY_COARSE_LABELS",
        )
        parser.add_argument(
            "--refresh-text-from-db",
            action="store_true",
            help="Recharger text_2000 / num_ej depuis la DB (tunnel requis)",
        )

    def handle(self, *args, **options):
        from docia.file_processing.processor.classify.train_set_review import score_train_split_from_parquet

        out_dir = options["output_dir"].resolve()
        scored_path = options["scored_parquet"] or (out_dir / "train_scored.parquet")
        if options["rescore"] or not scored_path.is_file():
            parquet = options["parquet"] or (out_dir / "documents_raw.parquet")
            score_train_split_from_parquet(
                out_dir,
                parquet_path=parquet,
                out_path=scored_path,
            )

        if options["pool"] == "priority-agree-low-conf":
            out_path, stats_path = export_train_priority_agreement_low_confidence_review(
                out_dir,
                scored_parquet=scored_path,
                per_class=options["per_class"],
                max_total=options["max_total"],
                max_proba_ceiling=options["max_proba_ceiling"],
                min_max_proba=options["min_proba_floor"],
                exclude_ccp_fine=options["exclude_ccp_fine"],
                with_text=True,
                refresh_text_from_db=options["refresh_text_from_db"],
            )
            self.stdout.write(self.style.SUCCESS(f"Review CSV: {out_path}\nStats: {stats_path}"))
            self.stdout.write(
                "Accord LLM+logreg mais confiance basse. review_ok=oui si l'accord est bon ; "
                "non si les deux se trompent → review_correct_label = parent coarse."
            )
        else:
            out_path, pairs_path = export_train_disagreement_review(
                out_dir,
                scored_parquet=scored_path,
                per_pair=options["per_pair"],
                max_total=options["max_total"],
                min_max_proba=options["min_max_proba"],
                require_logreg_accept=options["require_accept"],
                priority_only=options["priority_only"],
                with_text=True,
                refresh_text_from_db=options["refresh_text_from_db"],
            )
            self.stdout.write(self.style.SUCCESS(f"Review CSV: {out_path}\nPairs (fine): {pairs_path}"))
            self.stdout.write(
                "Annoter review_ok: non = erreur LLM (silver faux), oui = logreg tort. "
                "review_correct_label = parent coarse si non."
            )
        self.stdout.write("Puis: python manage.py prepare_classify_retrain")