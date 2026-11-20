from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from docia.file_processing.processor.classify.annotation_audit import import_audit_results


class Command(BaseCommand):
    help = "Summarize human annotation audit CSV for classify v2"

    def add_arguments(self, parser):
        parser.add_argument("audit_csv", type=Path)

    def handle(self, *args, **options):
        path = options["audit_csv"]
        if not path.exists():
            raise CommandError(f"File not found: {path}")
        stats = import_audit_results(path)
        self.stdout.write(str(stats))