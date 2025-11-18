import pytest

from docia.file_processing.models import BatchJob, DocumentJob, JobName, JobStatus
from docia.file_processing.utils import get_batch_progress
from docia.tests.factories.data import DataAttachmentFactory


@pytest.mark.django_db
def test_get_batch_progress():
    batch = BatchJob.objects.create(job_name=JobName.TEXT_EXTRACTION, folder="myfolder", status=JobStatus.STARTED)
    doc1 = DataAttachmentFactory(dossier="myfolder", filename="doc1.pdf")
    doc2 = DataAttachmentFactory(dossier="myfolder", filename="doc2.pdf")
    ext1 = DocumentJob.objects.create(batch=batch, document=doc1, status=JobStatus.PENDING)
    ext2 = DocumentJob.objects.create(batch=batch, document=doc2, status=JobStatus.PENDING)
    progress = get_batch_progress(batch.id)
    assert progress == {
        "status": JobStatus.STARTED,
        "completed": 0,
        "errors": 0,
        "total": 2,
    }

    # One running
    ext1.status = JobStatus.STARTED
    ext1.save()

    progress = get_batch_progress(batch.id)
    assert progress == {
        "status": JobStatus.STARTED,
        "completed": 0,
        "errors": 0,
        "total": 2,
    }

    # One finished
    ext1.status = JobStatus.SUCCESS
    ext1.save()

    progress = get_batch_progress(batch.id)
    assert progress == {
        "status": JobStatus.STARTED,
        "completed": 1,
        "errors": 0,
        "total": 2,
    }

    # One failed
    ext1.status = JobStatus.FAILURE
    ext1.save()

    progress = get_batch_progress(batch.id)
    assert progress == {
        "status": JobStatus.STARTED,
        "completed": 1,
        "errors": 1,
        "total": 2,
    }

    # Finished
    ext1.status = JobStatus.FAILURE
    ext1.save()
    ext2.status = JobStatus.SUCCESS
    ext2.save()
    batch.status = JobStatus.FAILURE
    batch.save()

    progress = get_batch_progress(batch.id)
    assert progress == {
        "status": JobStatus.FAILURE,
        "completed": 2,
        "errors": 1,
        "total": 2,
    }
