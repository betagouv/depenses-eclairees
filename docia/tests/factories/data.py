import factory

from docia.models import DataAttachment, DataBatch, DataEngagement


class DataEngagementFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DataEngagement

    num_ej = factory.Sequence(lambda n: f"EJ{n:0>3}")


class DataBatchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DataBatch

    batch = factory.Sequence(lambda n: f"Batch_{n:0>3}")
    ej = factory.SubFactory(DataEngagementFactory)


class DataAttachmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DataAttachment

    filename = factory.Sequence(lambda n: f"file_{n:0>3}.txt")
    dossier = "raw"
    file = factory.lazy_attribute(lambda a: f"{a.dossier}/{a.filename}")
    extension = factory.lazy_attribute(lambda a: a.filename.split(".")[-1])
