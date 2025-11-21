import pytest

from docia.file_processing.models import ProcessDocumentStepType, ProcessingStatus
from docia.file_processing.utils import get_batch_progress
from docia.tests.factories.file_processing import ProcessDocumentBatchFactory, ProcessDocumentJobFactory


@pytest.mark.django_db
def test_get_batch_progress():
    batch = ProcessDocumentBatchFactory(status=ProcessingStatus.STARTED)
    job1 = ProcessDocumentJobFactory(batch=batch, status=ProcessingStatus.PENDING)
    job2 = ProcessDocumentJobFactory(batch=batch, status=ProcessingStatus.PENDING)
    progress = get_batch_progress(batch.id)
    assert progress == {
        "status": ProcessingStatus.STARTED,
        "completed": 0,
        "errors": 0,
        "total": 2,
        "steps": {
            ProcessDocumentStepType.TEXT_EXTRACTION: {"completed": 0, "errors": 0, "total": 0},
            ProcessDocumentStepType.CLASSIFICATION: {"completed": 0, "errors": 0, "total": 0},
            ProcessDocumentStepType.INFO_EXTRACTION: {"completed": 0, "errors": 0, "total": 0},
        },
    }

    # One running
    job1.status = ProcessingStatus.STARTED
    job1.save()

    progress = get_batch_progress(batch.id)
    del progress["steps"]
    assert progress == {
        "status": ProcessingStatus.STARTED,
        "completed": 0,
        "errors": 0,
        "total": 2,
    }

    # One finished
    job1.status = ProcessingStatus.SUCCESS
    job1.save()

    progress = get_batch_progress(batch.id)
    del progress["steps"]
    assert progress == {
        "status": ProcessingStatus.STARTED,
        "completed": 1,
        "errors": 0,
        "total": 2,
    }

    # One failed
    job1.status = ProcessingStatus.FAILURE
    job1.save()

    progress = get_batch_progress(batch.id)
    del progress["steps"]
    assert progress == {
        "status": ProcessingStatus.STARTED,
        "completed": 1,
        "errors": 1,
        "total": 2,
    }

    # Finished
    job1.status = ProcessingStatus.FAILURE
    job1.save()
    job2.status = ProcessingStatus.SUCCESS
    job2.save()
    batch.status = ProcessingStatus.FAILURE
    batch.save()

    progress = get_batch_progress(batch.id)
    del progress["steps"]
    assert progress == {
        "status": ProcessingStatus.FAILURE,
        "completed": 2,
        "errors": 1,
        "total": 2,
    }
