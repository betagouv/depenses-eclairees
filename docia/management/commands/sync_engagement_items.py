import os

from django.core.management.base import BaseCommand, CommandError

from docia.sync.sync_engagement_items import read_csv, sync


class Command(BaseCommand):
    help = "Syncs engagement items from a CSV file to the database"

    def add_arguments(self, parser):
        parser.add_argument("filename", type=str, help="Path to the CSV file to import")

    def handle(self, *args, **options):
        filename = options["filename"]

        # Check if file exists
        if not os.path.exists(filename):
            raise CommandError(f'File "{filename}" does not exist')

        data = read_csv(filename)
        self.stdout.write(self.style.SUCCESS(f"Found {len(data)} items in CSV file"))

        # Perform the sync operation
        created = sync(data)

        self.stdout.write(self.style.SUCCESS(f"Successfully synced engagement items ({len(created)} created)"))
