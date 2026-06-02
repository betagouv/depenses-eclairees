import json

import pytest

from docia.documents.transfer.dump import EngagementDumper
from tests.factories.data import (
    DocumentFactory,
    EngagementFactory,
    EngagementScopeFactory,
)


@pytest.mark.django_db
class TestEngagementDumper:
    """Tests for EngagementDumper class."""

    def test_dump_to_json_nominal_case(self):
        """Test nominal case: dump 2 engagements with 2 documents each and 1 scope per EJ."""
        # Step 1: Build test data using factories
        scope1 = EngagementScopeFactory(purchase_organization="OA_TEST_1", purchase_group="GA_TEST_1")
        scope2 = EngagementScopeFactory(purchase_organization="OA_TEST_2", purchase_group="GA_TEST_2")

        engagement1 = EngagementFactory(num_ej="EJ_DUMP_1")
        engagement1.scopes.add(scope1)
        doc1a = DocumentFactory(hash="hash_doc1a")
        doc1b = DocumentFactory(hash="hash_doc1b")
        doc1a.engagements.add(engagement1)
        doc1b.engagements.add(engagement1)

        engagement2 = EngagementFactory(num_ej="EJ_DUMP_2")
        engagement2.scopes.add(scope2)
        doc2a = DocumentFactory(hash="hash_doc2a")
        doc2b = DocumentFactory(hash="hash_doc2b")
        doc2a.engagements.add(engagement2)
        doc2b.engagements.add(engagement2)

        # Step 2: Run the dump_to_json
        dumper = EngagementDumper()
        json_bytes = dumper.dump_to_json(["EJ_DUMP_1", "EJ_DUMP_2"])
        result = json.loads(json_bytes)

        # Simplify result: keep only hash for documents
        simplified_result = {
            "version": result["version"],
            "dump_date": result["dump_date"],
            "engagements": [
                {
                    "num_ej": ej["num_ej"],
                    "scopes": ej["scopes"],
                    "documents": [{"hash": doc["hash"]} for doc in ej["documents"]],
                }
                for ej in result["engagements"]
            ],
        }

        # Step 3: Assert the result
        expected = {
            "version": "1.0",
            "dump_date": simplified_result["dump_date"],
            "engagements": [
                {
                    "num_ej": "EJ_DUMP_1",
                    "scopes": [{"purchase_organization": "OA_TEST_1", "purchase_group": "GA_TEST_1"}],
                    "documents": [
                        {"hash": "hash_doc1a"},
                        {"hash": "hash_doc1b"},
                    ],
                },
                {
                    "num_ej": "EJ_DUMP_2",
                    "scopes": [{"purchase_organization": "OA_TEST_2", "purchase_group": "GA_TEST_2"}],
                    "documents": [
                        {"hash": "hash_doc2a"},
                        {"hash": "hash_doc2b"},
                    ],
                },
            ],
        }
        assert simplified_result == expected
