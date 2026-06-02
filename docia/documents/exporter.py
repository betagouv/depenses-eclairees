from datetime import datetime

from rest_framework import serializers
from rest_framework.renderers import JSONRenderer
from rest_framework.serializers import ModelSerializer

from docia.documents.models import Document, Engagement, EngagementScope


class DocumentSerializer(ModelSerializer):
    file = serializers.CharField()

    class Meta:
        model = Document
        exclude = ["id", "updated_at", "created_at", "engagements"]


class ScopeSerializer(ModelSerializer):
    class Meta:
        model = EngagementScope
        fields = ["purchase_organization", "purchase_group"]


class EngagementSerializer(ModelSerializer):
    scopes = ScopeSerializer(many=True)
    documents = DocumentSerializer(many=True)

    class Meta:
        model = Engagement
        fields = ["num_ej", "scopes", "documents"]


class EngagementExporter:
    """Handles serialization of Engagement and related objects to JSON."""

    def serialize_engagement(self, engagement: Engagement) -> dict:
        return {
            "num_ej": engagement.num_ej,
            "scopes": self.serialize_scopes(list(engagement.scopes.all())),
            "documents": self.serialize_documents(list(engagement.documents.all())),
        }

    def serialize_engagements(self, num_ejs: list[str]) -> list[dict]:
        qs_ejs = Engagement.objects.filter(num_ej__in=num_ejs).prefetch_related("documents", "scopes")
        engagements = list(qs_ejs)
        ser = EngagementSerializer(engagements, many=True)
        return ser.data

    def export_engagements(self, num_ejs: list[str]) -> dict:
        """
        Export documents of a list of engagements.
        Will keep num_ej, document (full) and engagement scopes.

        Args:
            num_ejs: List of num_ej

        Returns:
            dict: The exported data
        """
        data = {
            "version": "1.0",
            "dump_date": datetime.now().isoformat(),
            "engagements": self.serialize_engagements(num_ejs),
        }
        return data

    def export_to_json(self, num_ejs: list[str], pretty_print=True) -> bytes:
        data = self.export_engagements(num_ejs)
        renderer = JSONRenderer()
        renderer_context = {} if not pretty_print else {"indent": 2}
        return renderer.render(data, renderer_context=renderer_context)
