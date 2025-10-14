from rest_framework import serializers

from .models import TrackingEvent


class TrackingEventSerializer(serializers.ModelSerializer):
    """Serializer for TrackingEvent model."""

    class Meta:
        model = TrackingEvent
        fields = ["category", "action", "name", "num_ej"]

    def create(self, validated_data):
        """Create a new tracking event with additional data from request."""
        request = self.context.get("request")

        # Add user_agent and referer from request
        validated_data["user_agent"] = request.META.get("HTTP_USER_AGENT", "")
        validated_data["page_url"] = request.META.get("HTTP_REFERER", "")

        # Add user if authenticated
        if request.user and request.user.is_authenticated:
            validated_data["user"] = request.user

        return super().create(validated_data)
