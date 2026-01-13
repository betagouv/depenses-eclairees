import datetime

import pytest
from freezegun import freeze_time

from docia.file_processing.models import BATCH_STUCK_TIMEOUT, ProcessDocumentBatch, ProcessingStatus
from tests.factories.file_processing import (
    ProcessDocumentBatchFactory,
    ProcessDocumentJobFactory,
    ProcessDocumentStepFactory,
)


@pytest.mark.django_db
def test_filter_stuck_batches():
    now = datetime.datetime(year=2025, month=6, day=1, hour=9, tzinfo=datetime.timezone.utc)
    time_stuck = now - datetime.timedelta(seconds=BATCH_STUCK_TIMEOUT + 1)
    time_not_stuck = now - datetime.timedelta(seconds=BATCH_STUCK_TIMEOUT - 1)

    # This one is stuck
    batch_1 = ProcessDocumentBatchFactory(status=ProcessingStatus.STARTED)
    ProcessDocumentStepFactory(job__batch=batch_1, finished_at=time_stuck)

    # This one is not (not enough time has passed since last step finished)
    batch_2 = ProcessDocumentBatchFactory(status=ProcessingStatus.STARTED)
    ProcessDocumentStepFactory(job__batch=batch_2, finished_at=time_not_stuck)

    # This one is not (status)
    batch_2 = ProcessDocumentBatchFactory(status=ProcessingStatus.SUCCESS)
    ProcessDocumentStepFactory(job__batch=batch_2, finished_at=time_stuck)

    with freeze_time(now):
        stuck_batches = ProcessDocumentBatch.objects.filter_stuck_batches()

    assert list(stuck_batches) == [batch_1]
    assert stuck_batches[0].last_job_step_finished_at == time_stuck


@pytest.mark.django_db
def test_get_next():
    job = ProcessDocumentJobFactory()
    step1 = ProcessDocumentStepFactory(job=job, order=1, status=ProcessingStatus.PENDING)
    step2 = ProcessDocumentStepFactory(job=job, order=2, status=ProcessingStatus.PENDING)
    next_step = step1.get_next()
    assert next_step == step2
