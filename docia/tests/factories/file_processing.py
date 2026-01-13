import datetime
import hashlib

import factory.fuzzy

from docia.file_processing.pipeline.steps.content_analysis import SUPPORTED_DOCUMENT_TYPES
from docia.file_processing.models import (
    FileInfo,
    ProcessDocumentBatch,
    ProcessDocumentJob,
    ProcessDocumentStep,
    ProcessingStatus,
)
from docia.file_processing.pipeline.pipeline import DEFAULT_PROCESS_STEPS
from docia.tests.factories.data import DocumentFactory


class ProcessDocumentBatchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProcessDocumentBatch

    folder = factory.Sequence(lambda n: f"folder{n:0>3}")
    steps = DEFAULT_PROCESS_STEPS
    status = ProcessingStatus.PENDING
    target_classifications = SUPPORTED_DOCUMENT_TYPES


class ProcessDocumentJobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProcessDocumentJob

    batch = factory.SubFactory(ProcessDocumentBatchFactory)
    document = factory.SubFactory(DocumentFactory)
    status = ProcessingStatus.PENDING


class ProcessDocumentStepFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProcessDocumentStep

    job = factory.SubFactory(ProcessDocumentJobFactory)
    order = 0
    status = ProcessingStatus.PENDING


class FileInfoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FileInfo

    file = factory.lazy_attribute(lambda i: f"{i.folder}/{i.filename}")
    filename = factory.Sequence(lambda n: f"file_{n:0>3}.pdf")
    folder = factory.Sequence(lambda n: f"raw/folder{n // 5:0>3}")
    num_ej = factory.fuzzy.FuzzyText(length=10, chars="0123456789")
    extension = factory.lazy_attribute(lambda i: i.filename.split(".")[-1])
    size = 1042
    hash = factory.lazy_attribute(lambda i: hashlib.md5(i.file.encode()).hexdigest())
    created_date = factory.fuzzy.FuzzyDate(start_date=datetime.date(2025, 1, 1))
