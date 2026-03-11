from django.core.management.base import BaseCommand

from docia.file_processing.sync.tasks import task_sync_all_externals


class Command(BaseCommand):
    """
    Django management command to synchronize all external documents.

    This command launches a background task that:
    1. Connects to external document sources
    2. Synchronizes document metadata and content
    3. Updates the local database with the latest information

    The command runs asynchronously - it initiates the synchronization but doesn't
    wait for completion. The task runs in the background using Celery.

    This is typically used in cron jobs to keep the local document repository
    in sync with external sources on a regular schedule.

    Examples:
        # Launch synchronization process
        python manage.py cron_sync_externals
    """

    help = "Launch the task to sync all external documents (does not wait for completion)"

    def handle(self, *args, **options):
        # Launch the task asynchronously without waiting for the result
        task_sync_all_externals.delay()

        self.stdout.write(self.style.SUCCESS("Successfully launched task_sync_all_externals (running in background)"))
