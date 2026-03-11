from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from docia.documents.models import DataEngagement, Document
from docia.file_processing.pipeline.pipeline import launch_batch
from docia.file_processing.pipeline.steps.init_documents import init_documents_from_external_filter_by_num_ejs


class Command(BaseCommand):
    """
    Django management command to launch the document processing pipeline for
    engagements that have been updated within a specified time window.

    This command:
    1. Filters DataEngagement records updated since the specified timedelta
    2. Initializes documents for those engagements
    3. Launches a background batch processing job for the documents

    The command runs asynchronously - it initiates the pipeline but doesn't
    wait for completion. Progress can be monitored through the batch ID
    displayed in the output.

    Examples:
        # Default: process engagements updated in the last 24 hours
        python manage.py cron_launch_pipeline

        # Process engagements updated in the last 12 hours
        python manage.py cron_launch_pipeline --timedelta 12h

        # Process engagements updated in the last 7 days
        python manage.py cron_launch_pipeline --timedelta 7d
    """

    help = "Launch the pipeline task (does not wait for completion)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--timedelta", type=str, default="24h", help='Time delta for filtering documents (e.g., "24h", "1d", "7d")'
        )

    def handle(self, *args, **options):
        # Parse timedelta parameter
        timedelta_str = options["timedelta"]

        # Parse the timedelta string
        if timedelta_str.endswith("h"):
            hours = int(timedelta_str[:-1])
            start = now() - timedelta(hours=hours)
        elif timedelta_str.endswith("d"):
            days = int(timedelta_str[:-1])
            start = now() - timedelta(days=days)
        else:
            self.stderr.write(
                self.style.ERROR(f"Invalid timedelta format: '{timedelta_str}'. Use formats like '24h' or '7d'")
            )
            return
        qs = DataEngagement.objects.filter(external_updated_at__gt=start)
        ej_ids = list(qs.values_list("num_ej", flat=True))
        batch_name = f"cron-{now().isoformat()}"
        self.stdout.write("Init documents...")
        init_documents_from_external_filter_by_num_ejs(ej_ids, batch_name)
        qs_docs = Document.objects.filter(engagements__num_ej__in=ej_ids).distinct()
        self.stdout.write("Launch batch...")
        batch, r = launch_batch(qs_documents=qs_docs)
        self.stdout.write(
            self.style.SUCCESS(f"Successfully launched pipeline (running in background with id {batch.id})")
        )
