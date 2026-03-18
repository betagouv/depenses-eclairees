import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from docia.file_processing.pipeline.pipeline import sync_and_analyze

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Launch pipeline"

    def add_arguments(self, parser):
        parser.add_argument(
            "--timedelta", type=str, default="7d", help='Time delta for filtering documents (e.g., "24h", "1d", "7d")'
        )
        parser.add_argument(
            "--force-analyze",
            action="store_true",
            dest="force_analyze",
            default=False,
            help="Force running the pipeline on all documents even if already analyzed, default=False",
        )

    def handle(self, *args, **options):
        force_analyze = options["force_analyze"]
        # Parse timedelta parameter
        timedelta_str = options["timedelta"]

        # Parse the timedelta string
        if timedelta_str.endswith("h"):
            hours = int(timedelta_str[:-1])
            start = timezone.now() - timedelta(hours=hours)
        elif timedelta_str.endswith("d"):
            days = int(timedelta_str[:-1])
            start = timezone.now() - timedelta(days=days)
        else:
            self.stderr.write(
                self.style.ERROR(f"Invalid timedelta format: '{timedelta_str}'. Use formats like '24h' or '7d'")
            )
            return

        end = timezone.now()
        batch_id = sync_and_analyze(start, end, force_analyze=force_analyze)
        if batch_id:
            self.stdout.write(self.style.SUCCESS(f"Pipeline launched, batch: {batch_id}"))
        else:
            self.stdout.write(self.style.SUCCESS("Nothing to do"))
        self.stdout.write(self.style.SUCCESS("DONE."))
