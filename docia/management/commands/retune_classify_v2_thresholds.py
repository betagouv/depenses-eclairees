import json
import logging
from pathlib import Path

from django.core.management.base import BaseCommand

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from docia.file_processing.processor.classify.artifacts import load_pipeline, save_thresholds
from docia.file_processing.processor.classify.constants import (
    DEFAULT_MAX_LLM_FALLBACK_RATE,
    DEFAULT_MIN_ROUTING_F1,
    DEFAULT_OUTPUT_DIR,
)
from docia.file_processing.processor.classify.evaluate import choose_thresholds, evaluate_test, rejection_curve_rows
from docia.file_processing.processor.classify.reporting import write_test_reports
import pandas as pd


class Command(BaseCommand):
    help = "Recherche tau/margin sur le split calib (plafond llm_fallback) sans retrain."

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
        parser.add_argument(
            "--max-llm-fallback-rate",
            type=float,
            default=DEFAULT_MAX_LLM_FALLBACK_RATE,
            help="Fraction max de docs renvoyés au LLM (défaut 0.40)",
        )
        parser.add_argument(
            "--no-fallback-cap",
            action="store_true",
            help="Désactive le plafond (comportement historique sur la grille)",
        )
        parser.set_defaults(coarse_priority_objective=True)
        parser.add_argument(
            "--no-coarse-priority-objective",
            action="store_false",
            dest="coarse_priority_objective",
            help="Objectif classique acc - false_accept (sans poids priorité)",
        )
        parser.add_argument(
            "--min-routing-f1",
            type=float,
            default=DEFAULT_MIN_ROUTING_F1,
            help="F1 routage minimal par classe (toutes classes calib)",
        )
        parser.add_argument(
            "--no-routing-f1-floor",
            action="store_true",
            help="Sans plancher min F1 par classe",
        )
        parser.add_argument("--skip-test-report", action="store_true")

    def handle(self, *args, **options):
        out = options["output_dir"].resolve()
        parquet = out / "documents_raw.parquet"
        if not parquet.is_file():
            raise FileNotFoundError(parquet)

        df = pd.read_parquet(parquet)
        calib = df[df["split"] == "calib"]
        test = df[df["split"] == "test"]
        model = load_pipeline(out)
        cap = None if options["no_fallback_cap"] else options["max_llm_fallback_rate"]
        f1_floor = None if options["no_routing_f1_floor"] else options["min_routing_f1"]
        th = choose_thresholds(
            calib,
            model,
            optimize_priority=options["coarse_priority_objective"],
            max_llm_fallback_rate=cap,
            min_routing_f1=f1_floor,
        )
        save_thresholds(
            out,
            th.tau,
            th.margin,
            extra={
                "max_llm_fallback_rate": cap,
                "min_routing_f1": f1_floor,
                "constraint_met": th.constraint_met,
                "routing_calib": th.routing,
                "objective_score": th.score,
            },
        )
        self.stdout.write(
            json.dumps(
                {
                    "tau": th.tau,
                    "margin": th.margin,
                    "constraint_met": th.constraint_met,
                    "routing_calib": th.routing,
                },
                indent=2,
            )
        )

        if not options["skip_test_report"] and not test.empty:
            metrics, cm = evaluate_test(
                test,
                model,
                th.tau,
                th.margin,
                report_priority=options["coarse_priority_objective"],
            )
            rej = out / "reports" / "05_rejection_curve.csv"
            rej_rows = pd.read_csv(rej).to_dict("records") if rej.is_file() else []
            write_test_reports(out, metrics, cm, rej_rows)
            r = metrics.get("routing") or {}
            self.stdout.write(
                self.style.SUCCESS(
                    f"Test: macro_f1={metrics.get('macro_f1'):.4f} "
                    f"llm_fallback={r.get('llm_fallback_rate'):.1%} "
                    f"acc_if_accepted={r.get('labeled_accuracy_on_accepted')}"
                )
            )