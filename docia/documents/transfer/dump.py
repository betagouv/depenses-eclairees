from datetime import datetime

from rest_framework.renderers import JSONRenderer

from docia.documents.models import Engagement
from docia.documents.transfer.serializers import EngagementSerializer


class EngagementDumper:
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

    def dump_engagements(self, num_ejs: list[str]) -> dict:
        """
        Dump documents of a list of engagements.
        Will keep num_ej, document (full) and engagement scopes.

        Args:
            num_ejs: List of num_ej

        Returns:
            dict: The dumped data
        """
        data = {
            "version": "1.0",
            "dump_date": datetime.now().isoformat(),
            "engagements": self.serialize_engagements(num_ejs),
        }
        return data

    def dump_to_json(self, num_ejs: list[str], pretty_print=True) -> bytes:
        data = self.dump_engagements(num_ejs)
        renderer = JSONRenderer()
        renderer_context = {} if not pretty_print else {"indent": 2}
        return renderer.render(data, renderer_context=renderer_context)
