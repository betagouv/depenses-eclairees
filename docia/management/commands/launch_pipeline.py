import logging
import sys

from django.core.management.base import BaseCommand, CommandError

from docia.file_processing.models import ProcessingStatus
from docia.file_processing.pipeline import launch_batch
from docia.file_processing.pipeline.steps.init_documents import init_documents_in_folder
from docia.file_processing.pipeline.utils import display_batch_progress, display_group_progress, get_batch_progress

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Launch pipeline for all documents in a specified folder"

    def add_arguments(self, parser):
        parser.add_argument("folder", type=str, help="Folder path containing documents to process")
        parser.add_argument(
            "--batch-grist",
            help="Batch id to group files",
        )
        parser.add_argument(
            "--no-progress",
            action="store_false",
            dest="show_progress",
            default=True,
            help="Hide progress bar during text extraction",
        )

    def handle(self, *args, **options):
        folder = options["folder"]
        batch_grist = options["batch_grist"]
        show_progress = options["show_progress"]

        self.stdout.write(f"Init documents for folder: {folder}")
        gr = init_documents_in_folder(folder, batch_grist)
        display_group_progress(gr.id)

        self.stdout.write(f"Starting text extraction for folder: {folder}")

        try:
            batch, result = launch_batch(folder=folder)

            # Wait for the tasks to complete if progress bar is not shown
            if not show_progress:
                self.stdout.write("Batch running (id={batch.id}).")
                return

            # Show progress
            display_batch_progress(batch.id)

            # Refresh batch
            batch.refresh_from_db()

            # Display final status
            if batch.status == ProcessingStatus.SUCCESS:
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully extracted text from all documents in folder: {folder}")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Completed with errors. Some documents could not be processed in folder: {folder}"
                    )
                )

            # Display stats
            progress = get_batch_progress(batch.id)
            total_docs = progress["total"]
            successful = progress["completed"] - progress["errors"]
            failed = progress["errors"]

            self.stdout.write(f"Total documents: {total_docs}")
            self.stdout.write(self.style.SUCCESS(f"Successfully processed: {successful}"))
            if failed > 0:
                self.stdout.write(self.style.ERROR(f"Failed to process: {failed}"))

            # Return appropriate exit code
            if batch.status != ProcessingStatus.SUCCESS:
                sys.exit(1)

        except Exception as e:
            raise CommandError(f"Error extracting text from folder '{folder}': {str(e)}")
