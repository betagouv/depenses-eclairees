"""Utilities for importing Engagement Juridique from JSON using DRF serializers."""

import io

from rest_framework.parsers import JSONParser

from docia.documents.exporter import (
    DocumentSerializer,
)
from docia.documents.models import Document, Engagement, EngagementScope


class ScopeImporter:
    def import_one(self, data: dict) -> EngagementScope:
        scope, _ = EngagementScope.objects.get_or_create(
            purchase_organization=data["purchase_organization"],
            purchase_group=data["purchase_group"],
        )
        return scope


class DocumentImporter:
    def import_one(self, data: dict) -> Document:
        instance = Document.objects.filter(hash=data["hash"]).first()
        serializer = DocumentSerializer(data=data, instance=instance)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return serializer.instance


class EngagementImporter:
    def __init__(self):
        self.parser = JSONParser()
        self.scope_importer = ScopeImporter()
        self.document_importer = DocumentImporter()

    def import_from_json(self, json_data: bytes):
        data = self.parser.parse(io.BytesIO(json_data))
        engagements = []

        for ej_data in data.get("engagements", []):
            engagement = self.import_one(ej_data)
            engagements.append(engagement)

        return engagements

    def import_one(self, data):
        num_ej = data["num_ej"]
        engagement, _ = Engagement.objects.get_or_create(num_ej=num_ej)

        for scope_data in data["scopes"]:
            scope = self.scope_importer.import_one(scope_data)
            engagement.scopes.add(scope)

        for doc_data in data["documents"]:
            document = self.document_importer.import_one(doc_data)
            engagement.documents.add(document)

        return engagement
