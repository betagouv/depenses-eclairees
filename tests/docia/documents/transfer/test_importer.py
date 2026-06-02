import pytest
from rest_framework.renderers import JSONRenderer

from docia.documents.transfer.importer import (
    DocumentImporter,
    EngagementImporter,
    ScopeImporter,
)
from docia.documents.transfer.serializers import (
    DocumentSerializer,
    EngagementSerializer,
    ScopeSerializer,
)
from docia.documents.models import Document, Engagement, EngagementScope
from tests.factories.data import (
    DocumentFactory,
    EngagementFactory,
    EngagementScopeFactory,
)


@pytest.mark.django_db
class TestScopeImporter:
    """Tests for ScopeImporter class."""

    def test_import_one_creates_scope(self):
        """Test creating a new scope via importer."""
        importer = ScopeImporter()
        data = {
            "purchase_organization": "OA_TEST_1",
            "purchase_group": "GA_TEST_1",
        }

        scope = importer.import_one(data)

        assert scope.purchase_organization == "OA_TEST_1"
        assert scope.purchase_group == "GA_TEST_1"
        db_scope = EngagementScope.objects.get()  # Only one scope should be present in DB
        assert db_scope.purchase_organization == "OA_TEST_1"
        assert db_scope.purchase_group == "GA_TEST_1"

    def test_import_one_returns_existing_scope(self):
        """Test that importing existing scope returns the same instance."""
        # Create existing scope
        existing = EngagementScopeFactory(
            purchase_organization="OA_EXISTING",
            purchase_group="GA_EXISTING",
        )

        importer = ScopeImporter()
        data = {
            "purchase_organization": "OA_EXISTING",
            "purchase_group": "GA_EXISTING",
        }

        scope = importer.import_one(data)

        assert scope.id == existing.id
        db_scope = EngagementScope.objects.get()  # Only one scope should be present in DB
        assert db_scope.id == existing.id


@pytest.mark.django_db
class TestDocumentImporter:
    """Tests for DocumentImporter class."""

    def test_import_one_creates_document(self):
        """Test creating a new document via importer."""
        importer = DocumentImporter()
        input_doc = DocumentFactory.build()
        input_data = DocumentSerializer(input_doc).data

        doc = importer.import_one(input_data)

        db_doc = Document.objects.get()  # Only one doc should be present in DB
        assert db_doc.id == doc.id
        db_data = DocumentSerializer(doc).data
        assert db_data == input_data

    def test_import_one_updates_existing_document(self):
        """Test that importing existing document updates its fields."""
        input_doc = DocumentFactory.build(
            filename="new_name.txt",
            dossier="new/folder",
        )
        input_data = DocumentSerializer(input_doc).data
        DocumentFactory(hash=input_data["hash"])

        importer = DocumentImporter()
        doc = importer.import_one(input_data)

        db_doc = Document.objects.get()  # Only one doc should be present in DB
        assert db_doc.id == doc.id
        db_data = DocumentSerializer(db_doc).data
        assert db_data == input_data


@pytest.mark.django_db
class TestEngagementImporter:
    """Tests for EngagementImporter class."""

    def test_import_from_json(self):
        """Test nominal case: import multiple engagements (2 new + 1 existing) from JSON."""

        # Build input data
        input_engagement_1 = EngagementFactory.build(num_ej="NEW_EJ_1")
        input_engagement_2 = EngagementFactory.build(num_ej="NEW_EJ_2")
        input_engagement_existing = EngagementFactory(num_ej="EXISTING_EJ")
        existing_scope = EngagementScopeFactory()
        input_engagement_existing.scopes.add(existing_scope)

        input_data = {
            "version": "1.0",
            "dump_date": "2024-01-01T00:00:00",
            "engagements": [
                EngagementSerializer(input_engagement_1).data,
                EngagementSerializer(input_engagement_2).data,
                EngagementSerializer(input_engagement_existing).data,
            ],
        }

        scope = EngagementScopeFactory.build()
        input_data["engagements"][0]["scopes"].append(ScopeSerializer(scope).data)
        input_data["engagements"][1]["scopes"].append(ScopeSerializer(existing_scope).data)

        doc1 = DocumentFactory.build()
        doc2 = DocumentFactory.build()
        doc3 = DocumentFactory.build()
        input_data["engagements"][0]["documents"].append(DocumentSerializer(doc1).data)
        input_data["engagements"][1]["documents"].append(DocumentSerializer(doc2).data)
        input_data["engagements"][2]["documents"].append(DocumentSerializer(doc3).data)

        importer = EngagementImporter()
        renderer = JSONRenderer()
        json_data = renderer.render(input_data)

        engagements = importer.import_from_json(json_data)

        # Check num_ejs
        expected_num_ejs = {"NEW_EJ_1", "NEW_EJ_2", "EXISTING_EJ"}
        num_ejs = {e.num_ej for e in engagements}
        assert num_ejs == expected_num_ejs
        db_num_ejs = set(Engagement.objects.values_list("num_ej", flat=True))
        assert db_num_ejs == expected_num_ejs

        # Check number of scopes and documents inserted
        assert EngagementScope.objects.count() == 2
        assert Document.objects.count() == 3
