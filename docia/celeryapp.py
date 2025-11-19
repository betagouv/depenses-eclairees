import logging
import os

from django.conf import settings
from django.db import transaction

from celery import Celery, Task, signals


# Use same name as Celery is using for its task success logger
logger_celery = logging.getLogger("celery.app.trace")


class BaseTask(Task):
    def on_commit(self, *args, **kwargs):
        if settings.ENV == "test":
            self.delay(*args, **kwargs)
        else:
            transaction.on_commit(lambda: self.delay(*args, **kwargs))


# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "docia.settings")

app = Celery("docia", task_cls=BaseTask)


# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()


@signals.task_prerun.connect()
def task_prerun(task_id, task, **kwargs):
    args = kwargs["args"]
    # Compact args for chords
    if isinstance(args[0], list) and len(args[0]) > 3:
        sargs = str([
            args[0][:3] + ['...'],
            *args[1:],
        ])
    else:
        sargs = str(args)
    logger_celery.info("Start task %s args=%s kwargs=%s", task.name, sargs, kwargs["kwargs"])
