"""Tests pour create_response_format et select_attr (schéma BPU / bordereau_prix)."""

import pytest

from docia.file_processing.processor.analyze_content import create_response_format
from docia.file_processing.processor.attributes_query import (
    ATTRIBUTES,
    DOC_TYPE_ATTRIBUTES_MAPPING,
    select_attr,
)


def test_select_attr_bordereau_prix_returns_bpu_attributes():
    """select_attr(ATTRIBUTES, "bordereau_prix") renvoie les lignes objet et prestations (schéma flat)."""
    df = select_attr(ATTRIBUTES, "bordereau_prix")
    assert len(df) == 2
    output_fields = set(df["output_field"].tolist())
    assert output_fields == {"objet", "prestations"}
    row_prestations = df[df["output_field"] == "prestations"].iloc[0]
    assert row_prestations["schema"] is not None
    assert "items" in row_prestations["schema"]
    assert row_prestations["schema"]["items"].get("$ref") == "#/$defs/prestationFlatItem"


def test_create_response_format_bordereau_prix_structure():
    """create_response_format pour bordereau_prix renvoie un format avec type json_schema et schéma complet."""
    response_format = create_response_format(ATTRIBUTES, "bordereau_prix")
    assert response_format["type"] == "json_schema"
    schema = response_format["json_schema"]["schema"]
    assert schema["type"] == "object"
    assert set(schema["properties"].keys()) == {"objet", "prestations"}
    assert schema["required"] == ["objet", "prestations"]
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["name"] == "bordereau_prix"


def test_create_response_format_bordereau_prix_defs():
    """Le schéma BPU flat utilise prestationFlatItem (liste plate id, parent, label, code, pricing)."""
    response_format = create_response_format(ATTRIBUTES, "bordereau_prix")
    defs = response_format["json_schema"]["schema"].get("$defs", {})
    assert "prestationFlatItem" in defs
    assert "prestationNode" not in defs
    assert "prestationSection" not in defs
    assert "prestationLeaf" not in defs


def test_create_response_format_bordereau_prix_prestation_flat_item_structure():
    """prestationFlatItem a id, parent, label, code, pricing (pas de oneOf section/leaf)."""
    response_format = create_response_format(ATTRIBUTES, "bordereau_prix")
    defs = response_format["json_schema"]["schema"]["$defs"]
    flat = defs["prestationFlatItem"]
    assert flat["type"] == "object"
    assert set(flat["properties"].keys()) == {"id", "parent", "label", "code", "pricing"}
    assert set(flat["required"]) == {"id", "parent", "label", "pricing"}


def test_create_response_format_bordereau_prix_prestation_flat_no_type_prix():
    """prestationFlatItem et pricing ne contiennent pas type_prix."""
    response_format = create_response_format(ATTRIBUTES, "bordereau_prix")
    flat = response_format["json_schema"]["schema"]["$defs"]["prestationFlatItem"]
    assert "type_prix" not in flat.get("properties", {})
    pricing = flat.get("properties", {}).get("pricing") or {}
    if isinstance(pricing.get("properties"), dict):
        assert "type_prix" not in pricing["properties"]


def test_create_response_format_bordereau_prix_prestation_flat_pricing_required():
    """prestationFlatItem.pricing a les champs requis : prix_ht, prix_ttc, taux_tva, quantite, unite."""
    response_format = create_response_format(ATTRIBUTES, "bordereau_prix")
    flat = response_format["json_schema"]["schema"]["$defs"]["prestationFlatItem"]
    pricing = flat["properties"]["pricing"]
    assert "properties" in pricing
    assert set(pricing["required"]) == {"prix_ht", "prix_ttc", "taux_tva", "quantite", "unite"}
    assert set(pricing["properties"].keys()) == {"prix_ht", "prix_ttc", "taux_tva", "quantite", "unite"}


# --- Tests pour d'autres types de documents (non régression) ---


def test_select_attr_returns_non_empty_for_other_doc_types():
    """select_attr renvoie des lignes pour kbis, rib, acte_engagement."""
    for doc_type in ("kbis", "rib", "acte_engagement"):
        df = select_attr(ATTRIBUTES, doc_type)
        assert len(df) >= 1, f"select_attr(ATTRIBUTES, {doc_type!r}) devrait renvoyer au moins une ligne"
        assert "output_field" in df.columns
        assert "schema" in df.columns


def test_create_response_format_kbis():
    """create_response_format pour kbis renvoie un format valide (schéma sans $defs)."""
    response_format = create_response_format(ATTRIBUTES, "kbis")
    assert response_format["type"] == "json_schema"
    schema = response_format["json_schema"]["schema"]
    assert schema["type"] == "object"
    assert len(schema["properties"]) >= 1
    assert schema["required"] == list(schema["properties"].keys())
    assert response_format["json_schema"]["name"] == "kbis"
    # kbis n'a pas de schéma récursif, donc pas de $defs (ou $defs vide selon les attributs)
    for prop_schema in schema["properties"].values():
        assert "type" in prop_schema


def test_create_response_format_rib():
    """create_response_format pour rib renvoie un format valide."""
    response_format = create_response_format(ATTRIBUTES, "rib")
    assert response_format["type"] == "json_schema"
    schema = response_format["json_schema"]["schema"]
    assert schema["type"] == "object"
    assert len(schema["properties"]) >= 1
    assert set(schema["required"]) == set(schema["properties"].keys())
    assert response_format["json_schema"]["name"] == "rib"


def test_create_response_format_acte_engagement():
    """create_response_format pour acte_engagement renvoie un format valide."""
    response_format = create_response_format(ATTRIBUTES, "acte_engagement")
    assert response_format["type"] == "json_schema"
    schema = response_format["json_schema"]["schema"]
    assert schema["type"] == "object"
    assert len(schema["properties"]) >= 1
    assert set(schema["required"]) == set(schema["properties"].keys())
    assert response_format["json_schema"]["name"] == "acte_engagement"


@pytest.mark.parametrize("doc_type", list(DOC_TYPE_ATTRIBUTES_MAPPING.keys()))
def test_create_response_format_all_doc_types(doc_type):
    """create_response_format fonctionne pour tous les types de document sans erreur."""
    response_format = create_response_format(ATTRIBUTES, doc_type)
    assert response_format["type"] == "json_schema"
    assert "json_schema" in response_format
    schema = response_format["json_schema"]["schema"]
    assert schema["type"] == "object"
    assert len(schema["properties"]) >= 1
    assert schema["required"] == list(schema["properties"].keys())
    assert response_format["json_schema"]["name"] == doc_type
