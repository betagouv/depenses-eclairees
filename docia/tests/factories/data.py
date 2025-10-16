import factory

from docia.models import DataBatch, DataEngagement


class DataEngagementFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DataEngagement

    num_ej = factory.Sequence(lambda n: f"EJ{n:0>3}")


class DataBatchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DataBatch

    batch = factory.Sequence(lambda n: f"Batch_{n:0>3}")
    ej = factory.SubFactory(DataEngagementFactory)
