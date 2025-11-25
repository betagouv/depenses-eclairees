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
                    if hasattr(module, "__all__"):
                        objs = list(module.__all__)
                    else:
                        # Fall back to all public attributes (those not starting with underscore)
                        objs = [name for name in dir(module) if not name.startswith('_')]
                for obj in objs:
                    imports.append(f"{module_path}.{obj}")
        return imports
