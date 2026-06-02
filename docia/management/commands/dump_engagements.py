import os

from django.core.management.base import BaseCommand, CommandError

from docia.documents.exporter import EngagementExporter
from docia.documents.models import Engagement


class Command(BaseCommand):
    help = "Dump Engagement(s) Juridique(s) and their associated documents to a JSON file"

    def add_arguments(self, parser):
        parser.add_argument(
            "num_ej",
            type=str,
            nargs="+",  # Accept one or more num_ej values
            help="One or more num_ej identifiers of Engagement(s) Juridique(s) to dump",
        )
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            default=None,
            help="Output file path (default: <num_ej>.json or engagements.json for multiple)",
        )
        parser.add_argument(
            "--pretty",
            action="store_true",
            help="Format the JSON output with indentation",
        )

    def handle(self, *args, **options):
        num_ejs = options["num_ej"]
        output_path = options["output"]
        pretty_print = options["pretty"]

        # Verify all engagements exist
        for num_ej in num_ejs:
            try:
                Engagement.objects.get(num_ej=num_ej)
            except Engagement.DoesNotExist:
                raise CommandError(f"Engagement with num_ej '{num_ej}' not found")

        self.stdout.write(f"Found {len(num_ejs)} Engagement(s): {', '.join(num_ejs)}")

        # Export using exporter
        exporter = EngagementExporter()
        json_bytes = exporter.export_to_json(num_ejs, pretty_print=pretty_print)
        json_str = json_bytes.decode("utf-8")

        # Generate output path if not provided
        if output_path is None:
            # If single engagement, use num_ej; otherwise use engagements.json
            if len(num_ejs) == 1:
                output_path = f"{num_ejs[0]}.json"
            else:
                output_path = "engagements.json"

        # Ensure directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # Write to file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_str)

        self.stdout.write(self.style.SUCCESS(f"Successfully dumped {len(num_ejs)} engagement(s) to {output_path}"))
