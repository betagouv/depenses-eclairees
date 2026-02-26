import pytest

from tests.docia.views.test_home import create_ej_and_document
from tests.factories.users import UserFactory


def _ccap_base_data(**overrides):
    """Données de base pour un CCAP (sans lots)."""
    data = {
        "ccag": None,
        "lots": [],
        "intro": None,
        "id_marche": None,
        "duree_lots": [],
        "montant_ht": None,
        "duree_marche": None,
        "forme_marche": None,
        "objet_marche": "",
        "montant_ht_lots": [],
        "forme_marche_lots": [],
    }
    data.update(overrides)
    return data


def _login_and_get_ccap(client, ej, doc):
    """Connexion admin et GET page d'accueil avec num_ej."""
    user = UserFactory(is_superuser=True)
    client.force_login(user)
    response = client.get(f"/?num_ej={ej.num_ej}")
    assert response.status_code == 200
    return response.text


# ----- CCAP sans lots -----


@pytest.mark.django_db
def test_ccap_sans_lots_complet(client):
    """CCAP sans lots : objet, infos générales, montants, durée, avance, révision des prix, pénalités."""
    ej, doc = create_ej_and_document()
    doc.classification = "ccap"
    doc.structured_data = _ccap_base_data(
        objet_marche="Objet du marché test",
        id_marche="MAR-2024-001",
        ccag="CCAG Travaux",
        forme_marche={"tranches": None, "structure": "simple", "forme_prix": "forfaitaires"},
        montant_ht={"type_montant": "total", "montant_ht_maximum": "101234.00"},
        duree_marche={
            "duree_initiale": 12,
            "nb_reconductions": 1,
            "duree_reconduction": 6,
            "delai_tranche_optionnelle": 3,
        },
        avance={
            "taux": {"standard": "30 %", "pme": "35 %"},
            "assiette": {"base_calcul": "Acomptes", "regle_prorata_12_mois": True},
        },
        revision_prix="révisables",
        formule_revision_prix={"formule_brute": "P = P0 × (M/M0)", "termes_variables": []},
        penalites=[{"condition": "retard", "montant": "500", "unite": "€/jour"}],
    )
    doc.save()
    text = _login_and_get_ccap(client, ej, doc)

    assert "Objet du contrat" in text and "Objet du marché test" in text
    assert (
        "Informations générales" in text
        and "MAR-2024-001" in text
        and "CCAG Travaux" in text
        and "forfaitaires" in text
    )
    assert "Montants" in text and "101234" in text and "€ Total" in text
    assert "Durée" in text and "12 mois" in text and "reconductible" in text and "6" in text
    assert "Avance" in text and "30" in text and "Assiette de l'avance" in text and "Activée" in text
    assert "Révision des prix" in text and "P = P0" in text
    assert "Pénalités" in text and "Pénalité pour retard" in text and "500" in text


@pytest.mark.django_db
def test_ccap_sections_grisees(client):
    """CCAP avec données minimales : sections grisées (infos générales, avance, durée, pénalités, montants)."""
    ej, doc = create_ej_and_document()
    doc.classification = "ccap"
    doc.structured_data = _ccap_base_data(objet_marche="Objet minimal")
    doc.save()
    text = _login_and_get_ccap(client, ej, doc)

    assert "Objet du contrat" in text and "Objet minimal" in text
    assert "Informations générales – Non disponibles dans le document." in text
    assert "Avance – Non disponible dans le document." in text
    assert "Durée – Information non disponible dans le document." in text
    assert "Pénalités – Non disponibles dans le document." in text
    assert "Montants – Information non disponible dans le document." in text


@pytest.mark.django_db
def test_ccap_infos_optionnels_mode_consultation_cpv(client):
    """CCAP : mode de consultation et codes CPV affichés dans les infos générales."""
    ej, doc = create_ej_and_document()
    doc.classification = "ccap"
    doc.structured_data = _ccap_base_data(
        id_marche="MAR-2024-001",
        mode_consultation={"type_procedure": "Appel d'offres ouvert"},
        code_cpv=["45000000", "71000000"],
        objet_marche="Travaux et services",
    )
    doc.save()
    text = _login_and_get_ccap(client, ej, doc)

    assert "Informations générales" in text
    assert "Mode de consultation" in text and "Appel d&#x27;offres ouvert" in text
    assert "CPV" in text and "45000000" in text and "71000000" in text


@pytest.mark.django_db
def test_ccap_avance_non_disponible(client):
    """CCAP sans avance : section Avance grisée."""
    ej, doc = create_ej_and_document()
    doc.classification = "ccap"
    doc.structured_data = _ccap_base_data(id_marche="MAR-001", objet_marche="Sans avance")
    doc.save()
    text = _login_and_get_ccap(client, ej, doc)
    assert "Avance – Non disponible dans le document." in text


@pytest.mark.django_db
def test_ccap_revision_prix_sans_formule_non_affichee(client):
    """CCAP : section Révision des prix absente si prix révisables mais formule vide."""
    ej, doc = create_ej_and_document()
    doc.classification = "ccap"
    doc.structured_data = _ccap_base_data(
        id_marche="MAR-001",
        objet_marche="Marché",
        revision_prix="révisables",
        formule_revision_prix=None,
    )
    doc.save()
    text = _login_and_get_ccap(client, ej, doc)
    assert "Révision des prix" not in text


# ----- CCAP avec lots -----


@pytest.mark.django_db
def test_ccap_avec_lots(client):
    """CCAP alloti : forme du marché 'plusieurs lots', durée du marché, deux lots (forme, montants, durée)."""
    ej, doc = create_ej_and_document()
    doc.classification = "ccap"
    doc.structured_data = {
        "objet_marche": "Marché alloti",
        "id_marche": "MAR-001",
        "ccag": "CCAG",
        "lots": [
            {
                "numero_lot": 1,
                "titre": "Prestations de nettoyage",
                "forme": {
                    "structure": "à marchés subséquents",
                    "tranches": 3,
                    "forme_prix": "unitaires",
                    "attributaires": 2,
                },
                "duree_lot": {
                    "duree_initiale": 24,
                    "nb_reconductions": 2,
                    "duree_reconduction": 12,
                },
                "montant_ht": {"type_montant": "annuel", "montant_ht_maximum": "1111.00"},
            },
            {
                "numero_lot": 2,
                "titre": "Maintenance informatique",
                "forme": {
                    "structure": "sans marchés subséquents",
                    "tranches": None,
                    "forme_prix": "forfaitaires",
                    "attributaires": 1,
                },
                "duree_lot": "identique à la durée du marché",
                "montant_ht": {"type_montant": "total", "montant_ht_maximum": "2222.00"},
            },
        ],
        "duree_marche": {
            "duree_initiale": 36,
            "nb_reconductions": 1,
            "duree_reconduction": 12,
            "delai_tranche_optionnelle": None,
        },
        "forme_marche": {"tranches": None, "structure": "simple", "forme_prix": "forfaitaires"},
        "duree_lots": [],
        "montant_ht": None,
        "montant_ht_lots": [],
        "forme_marche_lots": [],
    }
    doc.save()
    text = _login_and_get_ccap(client, ej, doc)

    assert "Forme du marché" in text and "plusieurs lots" in text
    assert "Durée du marché" in text and "36 mois" in text

    assert "Lot 1" in text and "Prestations de nettoyage" in text
    assert (
        "marchés subséquents" in text and "3 tranches" in text and "prix unitaires" in text and "2 titulaires" in text
    )
    assert "1111" in text and "€ / An" in text
    assert "Durée du lot" in text and "24 mois" in text and "reconductible" in text

    assert "Lot 2" in text and "Maintenance informatique" in text
    assert (
        "sans marchés subséquents" in text
        and "sans tranches" in text
        and "prix forfaitaires" in text
        and "1 titulaire" in text
    )
    assert "2222" in text and "€ Total" in text
    assert "Identique à la durée du marché" in text


@pytest.mark.django_db
def test_ccap_lot_sections_grisees(client):
    """CCAP : dans un lot, sections Montants et Durée grisées quand absentes."""
    ej, doc = create_ej_and_document()
    doc.classification = "ccap"
    doc.structured_data = _ccap_base_data(
        id_marche="MAR-001",
        objet_marche="Marché alloti",
        duree_marche={
            "duree_initiale": 12,
            "nb_reconductions": 0,
            "duree_reconduction": None,
            "delai_tranche_optionnelle": None,
        },
        lots=[
            {
                "numero_lot": 1,
                "titre": "Lot sans montant ni durée",
                "forme": None,
                "duree_lot": None,
                "montant_ht": None,
            },
        ],
    )
    doc.save()
    text = _login_and_get_ccap(client, ej, doc)

    assert "Lot 1" in text and "Lot sans montant ni durée" in text
    assert "Montants – Information non disponible dans le document." in text
    assert "Durée – Information non disponible dans le document." in text
