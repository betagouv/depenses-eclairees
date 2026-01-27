import factory

from docia.documents.models import EngagementScope
from docia.models import DataBatch, DataEngagement, Document


class DataEngagementFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DataEngagement

    num_ej = factory.Sequence(lambda n: f"EJ{n:0>3}")


class DataBatchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DataBatch

    batch = factory.Sequence(lambda n: f"Batch_{n:0>3}")
    ej = factory.SubFactory(DataEngagementFactory)


class DocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Document

    filename = factory.Sequence(lambda n: f"file_{n:0>3}.txt")
    dossier = factory.Sequence(lambda n: f"raw/folder{n // 5:0>3}")
    file = factory.lazy_attribute(lambda a: f"{a.dossier}/{a.filename}")
    extension = factory.lazy_attribute(lambda a: a.filename.split(".")[-1])


class EngagementScopeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EngagementScope

    name = factory.Sequence(lambda n: f"scope_{n}")
