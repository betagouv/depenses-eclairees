import os

from django.core.management.base import BaseCommand, CommandError

from docia.documents.transfer.load import EngagementLoader


class Command(BaseCommand):
    help = "Load Engagement(s) Juridique(s) and their associated documents from a JSON file"

    def add_arguments(self, parser):
        parser.add_argument(
            "input_file",
            type=str,
            help="Path to the JSON file containing engagement(s) to import",
        )

    def handle(self, *args, **options):
        input_path = options["input_file"]

        # Verify input file exists
        if not os.path.exists(input_path):
            raise CommandError(f"Input file '{input_path}' not found")

        if not os.path.isfile(input_path):
            raise CommandError(f"'{input_path}' is not a file")

        # Read the JSON file
        self.stdout.write(f"Reading from file: {input_path}")
        with open(input_path, "rb") as f:
            json_data = f.read()

        # Load using loader
        loader = EngagementLoader()
        engagements = loader.load_from_json(json_data)

        self.stdout.write(
            self.style.SUCCESS(f"Successfully imported {len(engagements)} engagement(s)")
        )

        # Display summary
        for engagement in engagements:
            self.stdout.write(f"  - {engagement.num_ej} (scopes: {engagement.scopes.count()}, documents: {engagement.documents.count()})")
