from datetime import datetime

from docia.views import sort_documents


def test_sort_documents():
    """Test sort_documents : tri par ORDER_CLASSIFICATIONS, date décroissante, puis ratio_extracted décroissant."""

    # Tri par classification selon ORDER_CLASSIFICATIONS
    items = [
        {"classification": "fiche_navette", "date": datetime(2024, 1, 1), "ratio_extracted": 0.5},
        {"classification": "acte_engagement", "date": datetime(2024, 1, 1), "ratio_extracted": 0.5},
        {"classification": "ccp_vae", "date": datetime(2024, 1, 1), "ratio_extracted": 0.5},
    ]
    sort_documents(items)
    assert [x["classification"] for x in items] == ["acte_engagement", "ccp_vae", "fiche_navette"]

    # Classifications hors ORDER_CLASSIFICATIONS vont à la fin
    items = [
        {"classification": "autre", "date": datetime(2024, 1, 1), "ratio_extracted": 0.5},
        {"classification": "acte_engagement", "date": datetime(2024, 1, 1), "ratio_extracted": 0.5},
        {"classification": "ccp_vae", "date": datetime(2024, 1, 1), "ratio_extracted": 0.5},
    ]
    sort_documents(items)
    assert [x["classification"] for x in items] == ["acte_engagement", "ccp_vae", "autre"]

    # Tri par date décroissante dans même classification
    items = [
        {"classification": "acte_engagement", "date": datetime(2024, 1, 1), "ratio_extracted": 0.5},
        {"classification": "acte_engagement", "date": datetime(2024, 6, 15), "ratio_extracted": 0.5},
        {"classification": "acte_engagement", "date": datetime(2024, 3, 1), "ratio_extracted": 0.5},
    ]
    sort_documents(items)
    assert [x["date"] for x in items] == [datetime(2024, 6, 15), datetime(2024, 3, 1), datetime(2024, 1, 1)]

    # Tri par ratio_extracted décroissant pour même classification et date
    date_fixed = datetime(2024, 1, 1)
    items = [
        {"classification": "acte_engagement", "date": date_fixed, "ratio_extracted": 0.3},
        {"classification": "acte_engagement", "date": date_fixed, "ratio_extracted": 0.9},
        {"classification": "acte_engagement", "date": date_fixed, "ratio_extracted": 0.6},
    ]
    sort_documents(items)
    assert [x["ratio_extracted"] for x in items] == [0.9, 0.6, 0.3]

    # Documents sans date vont à la fin du groupe
    date_fixed = datetime(2024, 1, 1)
    items = [
        {"classification": "acte_engagement", "date": date_fixed, "ratio_extracted": 0.5},
        {"classification": "acte_engagement", "date": None, "ratio_extracted": 0.8},
        {"classification": "acte_engagement", "date": date_fixed, "ratio_extracted": 0.5},
    ]
    sort_documents(items)
    # Les documents avec date viennent en premier (même date), puis celui sans date
    assert items[0]["date"] == date_fixed
    assert items[1]["date"] == date_fixed
    assert items[2]["date"] is None

    # Plusieurs documents sans date : tri par ratio_extracted décroissant
    items = [
        {"classification": "acte_engagement", "date": None, "ratio_extracted": 0.3},
        {"classification": "acte_engagement", "date": None, "ratio_extracted": 0.9},
        {"classification": "acte_engagement", "date": None, "ratio_extracted": 0.6},
    ]
    sort_documents(items)
    assert [x["ratio_extracted"] for x in items] == [0.9, 0.6, 0.3]

    # Tri complet : classification, puis date, puis ratio
    items = [
        {"classification": "ccp_vae", "date": datetime(2024, 1, 1), "ratio_extracted": 0.3},
        {"classification": "acte_engagement", "date": datetime(2024, 1, 1), "ratio_extracted": 0.9},
        {"classification": "acte_engagement", "date": datetime(2024, 6, 1), "ratio_extracted": 0.5},
        {"classification": "ccp_vae", "date": datetime(2024, 1, 1), "ratio_extracted": 0.8},
    ]
    sort_documents(items)
    # acte_engagement d'abord (ordre 0), puis ccp_vae (ordre 1)
    assert items[0]["classification"] == "acte_engagement"
    assert items[1]["classification"] == "acte_engagement"
    assert items[2]["classification"] == "ccp_vae"
    assert items[3]["classification"] == "ccp_vae"
    # Dans acte_engagement : date 2024-06-01 avant 2024-01-01
    assert items[0]["date"] == datetime(2024, 6, 1)
    assert items[1]["date"] == datetime(2024, 1, 1)
    # Dans ccp_vae : ratio 0.8 avant 0.3
    assert items[2]["ratio_extracted"] == 0.8
    assert items[3]["ratio_extracted"] == 0.3

    # Liste vide
    items = []
    sort_documents(items)
    assert items == []


def test_sort_documents_by_date():
    """Test sort_documents avec sort_type='date' : tri par date puis ratio uniquement, sans classification."""

    items = [
        {"id": 3, "classification": "acte_engagement", "date": datetime(2024, 1, 1), "ratio_extracted": 0.9},
        {"id": 1, "classification": "sous_traitance", "date": datetime(2024, 6, 1), "ratio_extracted": 0.8},
        {"id": 2, "classification": "acte_engagement", "date": datetime(2024, 6, 1), "ratio_extracted": 0.5},
        {"id": 5, "classification": "fiche_navette", "date": None, "ratio_extracted": 0.8},
        {"id": 4, "classification": "sous_traitance", "date": datetime(2024, 1, 1), "ratio_extracted": 0.3},
    ]
    sort_documents(items, sort_type="date")

    assert [x["id"] for x in items] == list(range(1, 6))
