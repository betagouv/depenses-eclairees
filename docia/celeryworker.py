from celery import signals

worker_nodename = None


@signals.worker_init.connect
def capture_worker_name(sender=None, **kwargs):
    global worker_nodename
    worker_nodename = sender
