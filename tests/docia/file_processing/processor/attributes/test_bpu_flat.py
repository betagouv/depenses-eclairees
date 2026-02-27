"""Tests pour la structure plate BPU et la reconstruction d'arbre (bpu_flat_to_tree, post_processing_bpu_flat)."""

import pytest

from docia.file_processing.processor.attributes.bpu import (
    _guid_for_flat_item,
    bpu_flat_to_tree,
    post_processing_bpu_flat,
    set_guid_on_flat_prestations,
)


def test_bpu_flat_to_tree_empty():
    assert bpu_flat_to_tree(None) is None
    assert bpu_flat_to_tree([]) is None


def test_bpu_flat_to_tree_single_root_leaf():
    flat = [
        {"guid": "a1", "id": "1", "parent": None, "label": "Prestation 1", "pricing": {"prix_ht": 100, "prix_ttc": 120, "taux_tva": 20, "quantite": 1, "unite": "U"}},
    ]
    tree = bpu_flat_to_tree(flat)
    assert tree == [
        {"code": "1", "titre": "Prestation 1", "prix_ht": 100, "prix_ttc": 120, "taux_tva": 20, "quantite": 1, "unité": "U"},
    ]


def test_bpu_flat_to_tree_section_and_children():
    flat = [
        {"guid": "r", "id": "I", "parent": None, "label": "I. Section", "pricing": None},
        {"guid": "c1", "id": "I.1", "parent": "I", "label": "I.1 Ligne", "pricing": {"prix_ht": 10, "prix_ttc": 12, "taux_tva": 20, "quantite": 1, "unite": "jour"}},
    ]
    tree = bpu_flat_to_tree(flat)
    # Titre et intitule = texte du document (label), sans reformulation
    assert tree == [
        {"code": "I", "intitule": "I. Section", "content": [{"code": "I.1", "titre": "I.1 Ligne", "prix_ht": 10, "prix_ttc": 12, "taux_tva": 20, "quantite": 1, "unité": "jour"}]},
    ]


def test_bpu_flat_to_tree_accepts_missing_guid():
    """Quand guid est vide, l'arbre est quand même construit (guid complété en interne sur copie)."""
    flat = [
        {"guid": "", "id": "1", "parent": None, "label": "L", "pricing": None},
    ]
    tree = bpu_flat_to_tree(flat)
    assert tree == [{"code": "1", "intitule": "L", "content": []}]


def test_post_processing_bpu_flat_adds_tree():
    """Guid utilisé en interne pour la fusion, retiré de la sortie après reconstitution de l'arbre."""
    data = {
        "objet": "Marché test",
        "prestations": [
            {"id": "1", "parent": None, "label": "Ligne", "pricing": {"prix_ht": 1, "prix_ttc": 1.2, "taux_tva": 20, "quantite": 1, "unite": "U"}},
        ],
    }
    out = post_processing_bpu_flat(data)
    assert out["prestations"] == [
        {"code": "1", "titre": "Ligne", "prix_ht": 1, "prix_ttc": 1.2, "taux_tva": 20, "quantite": 1, "unité": "U"},
    ]
    # Liste plate en prestations_flat, guid retiré
    assert "guid" not in out["prestations_flat"][0]
    assert out["prestations_flat"][0]["id"] == "1"


def test_post_processing_bpu_flat_no_prestations():
    data = {"objet": "Marché", "prestations": None}
    assert post_processing_bpu_flat(data) == data
    data2 = {"objet": "Marché"}
    assert post_processing_bpu_flat(data2) == data2
    # Liste vide → prestations = arbre vide, prestations_flat = []
    data3 = {"objet": "Marché", "prestations": []}
    out3 = post_processing_bpu_flat(data3)
    assert out3["prestations"] is None
    assert out3["prestations_flat"] == []


def test_bpu_flat_to_tree_synthetic_id_no_prefix():
    """Quand id est synthétique, afficher uniquement le libellé ; titre = niveau le plus bas uniquement."""
    flat = [
        {"id": "maintenance_parc_materiel", "parent": None, "label": "Prestation de maintenance du parc matériel", "pricing": None},
        {"id": "periode_1", "parent": "maintenance_parc_materiel", "label": "Forfait pour la période du 27/08/18 au 08/04/2020", "pricing": {"prix_ht": 124423.7, "prix_ttc": 149308.44, "taux_tva": 20, "quantite": 1, "unite": None}},
    ]
    tree = bpu_flat_to_tree(flat)
    assert tree[0]["code"] is None  # id synthétique
    assert tree[0]["intitule"] == "Prestation de maintenance du parc matériel"
    assert tree[0]["content"][0]["code"] is None  # id synthétique
    assert tree[0]["content"][0]["titre"] == "Forfait pour la période du 27/08/18 au 08/04/2020"


def test_bpu_flat_to_tree_id_composite_label_starts_with_suffix():
    """Quand id = Parent-Numero (ex. Phasage-1) et label = '1 – ...', pas de duplication ; titre = niveau le plus bas."""
    flat = [
        {"id": "Phasage", "parent": None, "label": "Phasage", "pricing": None},
        {"id": "Phasage-1", "parent": "Phasage", "label": "1 – Mise à jour du référentiel", "pricing": {"prix_ht": 5535, "prix_ttc": 5535, "taux_tva": None, "quantite": None, "unite": None}},
    ]
    tree = bpu_flat_to_tree(flat)
    assert tree[0]["code"] == "Phasage"
    assert tree[0]["intitule"] == "Phasage"
    assert tree[0]["content"][0]["code"] == "Phasage-1"
    assert tree[0]["content"][0]["titre"] == "1 – Mise à jour du référentiel"


def test_bpu_flat_to_tree_composite_id_with_site_code_null():
    """Id composite avec label vide → id utilisé pour code et intitule. Avec label non vide → code null, titre sans redondance."""
    flat = [
        {"id": "Rénovation-lourde-Fleury-Mérogis", "parent": None, "label": "", "pricing": None},
        {"id": "M1-Fleury-Mérogis", "parent": "Rénovation-lourde-Fleury-Mérogis", "label": "Conception de la maquette", "pricing": {"prix_ht": 8389, "prix_ttc": 10067, "taux_tva": None, "quantite": None, "unite": "Forfaitaire"}},
    ]
    tree = bpu_flat_to_tree(flat)
    # Section racine sans label : id utilisé pour code et intitule (éviter intitulé vide)
    assert tree[0]["code"] == "Rénovation-lourde-Fleury-Mérogis"
    assert tree[0]["intitule"] == "Rénovation-lourde-Fleury-Mérogis"
    # Ligne avec label : code M1 extrait de l'id, titre = libellé du document uniquement (pas de préfixe)
    assert tree[0]["content"][0]["code"] == "M1"
    assert tree[0]["content"][0]["titre"] == "Conception de la maquette"


def test_bpu_flat_to_tree_code_from_prompt():
    """Quand le flat contient le champ code (extrait par le LLM), il est repris dans l'arbre."""
    flat = [
        {"id": "LOT 1", "parent": None, "label": "Lot 1 - Prestations", "code": "LOT 1", "pricing": None},
        {"id": "UO 2.1.1", "parent": "LOT 1", "label": "Coordination opérationnelle", "code": "UO 2.1.1", "pricing": {"prix_ht": 1100, "prix_ttc": 1193.5, "taux_tva": 8.5, "quantite": 1, "unite": "U"}},
    ]
    tree = bpu_flat_to_tree(flat)
    assert tree[0]["code"] == "LOT 1"
    assert tree[0]["intitule"] == "Lot 1 - Prestations"
    assert tree[0]["content"][0]["code"] == "UO 2.1.1"
    assert tree[0]["content"][0]["titre"] == "Coordination opérationnelle"


def test_set_guid_on_flat_prestations():
    """Guid calculé en préprocessing (hors LLM) pour fusion chunks sûre."""
    prestations = [
        {"id": "I", "parent": None, "label": "Section", "pricing": None},
        {"id": "I.1", "parent": "I", "label": "Ligne", "pricing": {"prix_ht": 10, "prix_ttc": 12, "taux_tva": 20, "quantite": 1, "unite": "U"}},
    ]
    set_guid_on_flat_prestations(prestations)
    assert prestations[0]["guid"] == _guid_for_flat_item(prestations[0])
    assert prestations[1]["guid"] == _guid_for_flat_item(prestations[1])
    assert len(prestations[0]["guid"]) == 16
    # Idempotent : rappel ne change pas (même entrée → même guid)
    set_guid_on_flat_prestations(prestations)
    assert prestations[0]["guid"] == _guid_for_flat_item(prestations[0])
