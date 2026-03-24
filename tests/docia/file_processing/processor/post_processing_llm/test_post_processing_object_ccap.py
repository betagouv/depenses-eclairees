import copy

from docia.file_processing.processor.post_processing_llm import post_processing_object_ccap


def test_post_processing_object_ccap_nominal():
    """Cas nominal : les quatre listes contiennent des entrées cohérentes pour un lot."""
    data = {
        "lots": [{"numero_lot": 1, "titre_lot": "Lot test"}],
        "forme_marche_lots": [
            {
                "numero_lot": 1,
                "structure": "Alloti",
                "tranches": None,
                "forme_prix": "Prix unitaires",
                "attributaires": None,
            }
        ],
        "duree_lots": [{"numero_lot": 1, "duree_lot": {"duree_initiale": 12}}],
        "montant_ht_lots": [{"numero_lot": 1, "montant_ht_maximum": 10000, "type_montant": "maximum"}],
        "autre_champ": "conservé",
    }
    payload = copy.deepcopy(data)

    result = post_processing_object_ccap(payload)

    assert result is payload
    assert result["autre_champ"] == "conservé"
    assert result["lots"] == [
        {
            "numero_lot": 1,
            "titre": "Lot test",
            "forme": {
                "structure": "Alloti",
                "tranches": None,
                "forme_prix": "Prix unitaires",
                "attributaires": None,
            },
            "duree_lot": {"duree_initiale": 12},
            "montant_ht": {"montant_ht_maximum": 10000, "type_montant": "maximum"},
        }
    ]


def test_post_processing_object_ccap_listes_vides():
    """Cas vide : les quatre listes sont vides → aucun lot agrégé."""
    data = {
        "lots": [],
        "forme_marche_lots": [],
        "duree_lots": [],
        "montant_ht_lots": [],
    }
    payload = copy.deepcopy(data)

    result = post_processing_object_ccap(payload)

    assert result == {"lots": []}


def test_post_processing_object_ccap_listes_none():
    """Cas None : le LLM renvoie None à la place des listes → traité comme des listes vides
    (évite les erreurs dans create_lots)."""
    data = {
        "lots": None,
        "forme_marche_lots": None,
        "duree_lots": None,
        "montant_ht_lots": None,
    }
    payload = copy.deepcopy(data)

    result = post_processing_object_ccap(payload)

    assert result == {"lots": []}
