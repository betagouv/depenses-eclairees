import logging
import sys

from django.core.management.base import BaseCommand, CommandError

from docia.file_processing.text_extraction import (
    JobStatus,
    extract_text_for_folder,
)
from docia.file_processing.utils import display_batch_progress, get_batch_progress

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Extract text from all documents in a specified folder"

    def add_arguments(self, parser):
        parser.add_argument("folder", type=str, help="Folder path containing documents to process")
        parser.add_argument(
            "--no-progress",
            action="store_false",
            dest="show_progress",
            default=True,
            help="Hide progress bar during text extraction",
        )

    def handle(self, *args, **options):
        folder = options["folder"]
        show_progress = options["show_progress"]

        self.stdout.write(f"Starting text extraction for folder: {folder}")

        try:
            batch, result = extract_text_for_folder(folder=folder)

            # Wait for the tasks to complete if progress bar is not shown
            if not show_progress:
                self.stdout.write("Batch running (id={batch.id}).")
                return

            # Show progress
            display_batch_progress(batch.id)

            # Refresh batch
            batch.refresh_from_db()

            # Display final status
            if batch.status == JobStatus.SUCCESS:
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
            if batch.status != JobStatus.SUCCESS:
                sys.exit(1)

        except Exception as e:
            raise CommandError(f"Error extracting text from folder '{folder}': {str(e)}")
