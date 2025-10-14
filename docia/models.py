from django.contrib.postgres.functions import RandomUUID
from django.db import models

# Import other models so Django can discover them
from .common.models import BaseModel, User  # noqa
from .ratelimit import models as ratelimit_models  # noqa
from .tracking import models as tracking_models  # noqa


class DataEngagement(models.Model):
    id = models.UUIDField(
        primary_key=True,
        db_default=RandomUUID(),
        editable=False,
    )
    num_ej = models.CharField(max_length=20, unique=True)
    designation = models.TextField(null=True, blank=True)  # noqa: DJ001
    descriptif_prestations = models.TextField(null=True, blank=True)  # noqa: DJ001
    date = models.CharField(max_length=255, null=True, blank=True)  # noqa: DJ001  # This is a response from an LLM
    prestataire = models.CharField(null=True, blank=True)  # noqa: DJ001
    administration = models.CharField(null=True, blank=True)  # noqa: DJ001
    siret = models.CharField(max_length=20, null=True, blank=True)  # noqa: DJ001
    sources_et_conflits = models.JSONField(null=True, blank=True)  # noqa: DJ001
    date_creation = models.DateField(null=True, blank=True)  # noqa: DJ001

    class Meta:
        db_table = "engagements"

    def __str__(self):
        return f"{self.num_ej}"


class DataAttachments(models.Model):
    id = models.UUIDField(
        primary_key=True,
        db_default=RandomUUID(),
        editable=False,
    )
    filename = models.CharField(unique=True)
    extension = models.CharField(null=True, blank=True)  # noqa: DJ001
    dossier = models.CharField(null=True, blank=True)  # noqa: DJ001
    num_ej = models.ForeignKey(
        DataEngagement, on_delete=models.PROTECT, db_column="num_ej", to_field="num_ej", null=True, blank=True
    )
    text = models.TextField(null=True, blank=True)  # noqa: DJ001
    is_ocr = models.BooleanField(null=True, blank=True)
    nb_mot = models.IntegerField(null=True, blank=True)
    relevant_content = models.TextField(null=True, blank=True)  # noqa: DJ001
    is_embedded = models.BooleanField(null=True, blank=True)
    llm_response = models.JSONField(null=True, blank=True)
    json_error = models.CharField(null=True, blank=True)  # noqa: DJ001
    date_creation = models.DateField(null=True, blank=True)  # noqa: DJ001
    batch = models.CharField(null=True, blank=True)  # noqa: DJ001
    taille = models.IntegerField(null=True, blank=True)  # noqa: DJ001
    hash = models.CharField(null=True, blank=True)  # noqa: DJ001
    classification = models.CharField(max_length=255, null=True, blank=True)  # noqa: DJ001
    classification_type = models.CharField(max_length=255, null=True, blank=True)  # noqa: DJ001

    class Meta:
        db_table = "attachments"

    def __str__(self):
        return f"{self.num_ej_id, self.filename}"


class DataBatch(models.Model):
    id = models.UUIDField(
        primary_key=True,
        db_default=RandomUUID(),
        editable=False,
    )
    batch = models.CharField(max_length=255, null=True, blank=True)  # noqa: DJ001
    num_ej = models.ForeignKey(
        DataEngagement, on_delete=models.PROTECT, db_column="num_ej", to_field="num_ej", null=True, blank=True
    )

    class Meta:
        db_table = "batch"
        unique_together = ("batch", "num_ej")

    def __str__(self):
        return f"{self.batch} - {self.num_ej_id}"


class DataEngagementItems(models.Model):
    id = models.UUIDField(
        primary_key=True,
        db_default=RandomUUID(),
        editable=False,
    )
    num_ej = models.ForeignKey(DataEngagement, on_delete=models.CASCADE, db_column="num_ej", to_field="num_ej")
    poste_ej = models.CharField()
    num_contrat = models.CharField(null=True, blank=True)  # noqa: DJ001
    groupe_marchandise = models.CharField(null=True, blank=True)  # noqa: DJ001
    centre_financier = models.CharField(null=True, blank=True)  # noqa: DJ001

    class Meta:
        db_table = "engagements_items"
        unique_together = [("num_ej", "poste_ej")]

    def __str__(self):
        return f"{self.num_ej_id} - {self.poste_ej}"


class DataProgrammesMinisteriels(models.Model):
    id = models.UUIDField(
        primary_key=True,
        db_default=RandomUUID(),
        editable=False,
    )
    programme = models.IntegerField(unique=True)
    libelle = models.CharField()
    nom_ministere = models.CharField()

    class Meta:
        db_table = "programmes_ministeriels"

    def __str__(self):
        return f"{self.programme} - {self.libelle}"
