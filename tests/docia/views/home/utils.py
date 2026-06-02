from contextlib import contextmanager
from unittest.mock import patch

from tests.factories.data import DocumentFactory, EngagementFactory


def create_ej_and_document(**kwargs):
    ej = EngagementFactory(**kwargs)
    doc = DocumentFactory()
    doc.engagements.add(ej)
    return ej, doc


@contextmanager
def mock_user_perms(authorize: bool):
    with patch("docia.views.user_can_view_ej", autospec=True) as m:
        m.return_value = authorize
        yield m
