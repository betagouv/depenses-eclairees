import csv

from django.db.models import F, Value
from django.db.models.functions import Concat

from docia.models import DataEngagementItems


def read_csv(filename):
    with open(filename, "r") as file:
        reader = csv.DictReader(file, delimiter=";")
        data = []
        for row in reader:
            item = DataEngagementItems(**row)
            data.append(item)
    return data


def sync(data):
    to_create = []
    num_ejs = [f"{item.num_ej}__{item.poste_ej}" for item in data]
    existing_items = list(
        DataEngagementItems.objects.annotate(
            key=Concat(F("num_ej"), Value("__"), F("poste_ej")),
        )
        .filter(key__in=num_ejs)
        .values_list("key", flat=True)
    )
    for item in data:
        if f"{item.num_ej}__{item.poste_ej}" not in existing_items:
            to_create.append(item)
    created = DataEngagementItems.objects.bulk_create(to_create)
    return created
