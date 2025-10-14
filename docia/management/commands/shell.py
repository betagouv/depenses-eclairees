import importlib

from django.conf import settings
from django.core.management.commands import shell


class Command(shell.Command):
    def get_auto_imports(self):
        # Preload some modules, otherwise autoimport fails
        # when trying to import some of them (2025-09-18, Django 5.2)
        importlib.import_module("docia.tasks")

        imports = super().get_auto_imports()
        for import_description in settings.SHELL_AUTO_IMPORTS:
            if isinstance(import_description, str):
                imports.append(import_description)
            else:
                module_path, objs = import_description
                if objs == "*":
                    module = importlib.import_module(module_path)
                    objs = list(module.__all__)
                for obj in objs:
                    imports.append(f"{module_path}.{obj}")
        return imports
