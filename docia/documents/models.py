from django.contrib.postgres.functions import RandomUUID
from django.db import models

from docia.common.models import BaseModel


class Engagement(BaseModel):
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
    sources_et_conflits = models.JSONField(null=True, blank=True)
    date_creation = models.DateField(null=True, blank=True)
    external_updated_at = models.DateTimeField(null=True, blank=True)
    external_created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Engagement Juridique"
        verbose_name_plural = "Engagements Juridique"

    def __str__(self):
        return f"{self.num_ej}"


class Document(BaseModel):
    id = models.UUIDField(
        primary_key=True,
        db_default=RandomUUID(),
        editable=False,
    )
    filename = models.CharField()
    file = models.FileField(max_length=1000, unique=True)
    extension = models.CharField(null=True, blank=True)  # noqa: DJ001
    dossier = models.CharField()
    engagements = models.ManyToManyField(
        Engagement,
        related_name="documents",
        related_query_name="documents",
    )
    text = models.TextField(null=True, blank=True)  # noqa: DJ001
    is_ocr = models.BooleanField(null=True, blank=True)
    nb_mot = models.IntegerField(null=True, blank=True)
    nb_pages = models.IntegerField(null=True, blank=True)
    relevant_content = models.TextField(null=True, blank=True)  # noqa: DJ001
    is_embedded = models.BooleanField(null=True, blank=True)
    llm_response = models.JSONField(null=True, blank=True)
    structured_data = models.JSONField(null=True, blank=True)
    date_creation = models.DateField(null=True, blank=True)  # noqa: DJ001
    batch = models.CharField(null=True, blank=True)  # noqa: DJ001
    taille = models.IntegerField(null=True, blank=True)  # noqa: DJ001
    hash = models.CharField(unique=True)
    classification = models.CharField(max_length=255, null=True, blank=True)  # noqa: DJ001

    # Metadata text extraction
    text_tokens_count = models.IntegerField(null=True, blank=True)
    text_extracted_at = models.DateTimeField(null=True, blank=True)

    # Metadata classification
    classification_type = models.CharField(max_length=255, null=True, blank=True)  # noqa: DJ001
    classification_prompt_tokens_count = models.IntegerField(null=True, blank=True)
    classification_completion_tokens_count = models.IntegerField(null=True, blank=True)
    classified_at = models.DateTimeField(null=True, blank=True)

    # Metadata analyze
    analyze_prompt_tokens_count = models.IntegerField(null=True, blank=True)
    analyze_completion_tokens_count = models.IntegerField(null=True, blank=True)
    analyzed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.file.name


class EngagementScope(BaseModel):
    # OA: Organisation d'achat
    purchase_organization = models.CharField(max_length=255)
    # GA: Groupe d'achat
    purchase_group = models.CharField(max_length=255)
    engagements = models.ManyToManyField(Engagement, related_name="scopes", related_query_name="scopes")

    class Meta:
        unique_together = [("purchase_organization", "purchase_group")]
        verbose_name = "Périmètre EJ"
        verbose_name_plural = "Pérmiètres EJ"

    def __str__(self):
        return f"{self.purchase_organization}/{self.purchase_group}"


class EngagementTag(BaseModel):
    id = models.UUIDField(
        primary_key=True,
        db_default=RandomUUID(),
        editable=False,
    )
    name = models.CharField(max_length=255, null=True, blank=True)  # noqa: DJ001
    ej = models.ForeignKey(
        Engagement,
        on_delete=models.PROTECT,
        db_column="num_ej",
        to_field="num_ej",
        null=True,
        blank=True,
        related_name="tag_set",
        related_query_name="tag",
    )

    class Meta:
        unique_together = ("name", "ej")

    def __str__(self):
        return f"{self.name} - {self.ej_id}"


class DataEngagementItems(BaseModel):
    id = models.UUIDField(
        primary_key=True,
        db_default=RandomUUID(),
        editable=False,
    )
    num_ej = models.CharField(max_length=20)
    poste_ej = models.CharField()
    num_contrat = models.CharField(null=True, blank=True)  # noqa: DJ001
    groupe_marchandise = models.CharField(null=True, blank=True)  # noqa: DJ001
    centre_financier = models.CharField(null=True, blank=True)  # noqa: DJ001

    class Meta:
        db_table = "engagements_items"
        unique_together = [("num_ej", "poste_ej")]

    def __str__(self):
        return f"{self.num_ej} - {self.poste_ej}"


class DataProgrammesMinisteriels(BaseModel):
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
