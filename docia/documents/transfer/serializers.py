from rest_framework import serializers
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
