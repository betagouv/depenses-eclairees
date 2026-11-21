"""Entrée ML sans connexion DB."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from docia.file_processing.processor.classify.constants import DEFAULT_OUTPUT_DIR, DEFAULT_SEED
from docia.file_processing.processor.classify.pipeline import run_training


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Train classify v2 from parquet only")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--require-human-audit", action="store_true")
    parser.add_argument("--audit-csv", type=Path, default=None)
    parser.add_argument("--disagreement-review-csv", type=Path, default=None)
    parser.add_argument("--merge-financial", action="store_true")
    parser.add_argument("--write-patched-parquet", action="store_true")
    parser.add_argument("--coarse-hierarchy", action="store_true")
    args = parser.parse_args(argv)
    run_training(
        output_dir=args.output_dir.resolve(),
        seed=args.seed,
        require_human_audit=args.require_human_audit,
        audit_csv=args.audit_csv,
        disagreement_review_csv=args.disagreement_review_csv,
        merge_financial=args.merge_financial,
        write_patched_parquet=args.write_patched_parquet,
        coarse_hierarchy=args.coarse_hierarchy,
    )


if __name__ == "__main__":
    main()