from django.core.management.base import BaseCommand

from docia.file_processing.pipeline.utils import display_batch_progress


class Command(BaseCommand):
    help = "Display batch progress"

    def add_arguments(self, parser):
        parser.add_argument("batch_id", type=str, help="Batch ID to display progress for")

    def handle(self, *args, **options):
        batch_id = options["batch_id"]
        display_batch_progress(batch_id)