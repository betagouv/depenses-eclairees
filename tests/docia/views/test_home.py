from contextlib import contextmanager
from unittest.mock import patch

import pytest

from docia.views import compute_ratio_data_extraction, format_ratio_to_percent
from tests.factories.data import DataEngagementFactory, DocumentFactory
from tests.factories.users import UserFactory


def create_ej_and_document(**kwargs):
    ej = DataEngagementFactory(**kwargs)
    doc = DocumentFactory()
    doc.engagements.add(ej)
    return ej, doc


def test_home(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Se connecter" in response.text


@pytest.mark.django_db
def test_home_logged_in(client):
    user = UserFactory()
    client.force_login(user)
    response = client.get("/")
    assert response.status_code == 200
    assert user.email in response.text


@pytest.mark.django_db
def test_restrict_unauthenticated(client):
    ej, doc = create_ej_and_document()
    response = client.get(f"/?num_ej={ej.num_ej}")
    assert "Se connecter" in response.text


@contextmanager
def mock_user_perms(authorize: bool):
    with patch("docia.views.user_can_view_ej", autospec=True) as m:
        m.return_value = authorize
        yield m


@pytest.mark.django_db
def test_restrict_no_permission(client):
    ej, doc = create_ej_and_document()
    user = UserFactory()
    client.force_login(user)
    with mock_user_perms(authorize=False) as m:
        response = client.get(f"/?num_ej={ej.num_ej}")
        m.assert_called_once()
    assert "Aucun résultat" in response.text


@pytest.mark.django_db
def test_user_with_perm_and_scope_can_view_ej(client):
    """User has django permission and has the required scope to see the ej."""
    ej, doc = create_ej_and_document()
    user = UserFactory()
    client.force_login(user)
    with mock_user_perms(authorize=True) as m:
        response = client.get(f"/?num_ej={ej.num_ej}")
        m.assert_called_once()
    assert doc.filename in response.text


@pytest.mark.django_db
def test_admin_can_see_anything(client):
    ej, doc = create_ej_and_document()
    user = UserFactory(is_superuser=True)
    client.force_login(user)
    response = client.get(f"/?num_ej={ej.num_ej}")
    assert doc.filename in response.text


def test_compute_ratio_data_extraction():
    """Test compute_ratio_data_extraction function with various inputs."""
    # Empty dictionary should return 0
    assert compute_ratio_data_extraction({}) == 0

    # All values are empty/None/False, should return 0
    assert compute_ratio_data_extraction({"key1": None, "key2": "", "key3": False}) == 0

    # All values are non-empty, should return 1.0
    assert compute_ratio_data_extraction({"key1": "value", "key2": "data", "key3": True}) == 1.0

    # Mix of empty and non-empty values, should return ratio
    response = {"key1": "value", "key2": None, "key3": "data", "key4": ""}
    assert compute_ratio_data_extraction(response) == 0.5

    # More complex example
    complex_response = {
        "field1": "extracted data",
        "field2": None,
        "field3": "",
        "field4": "more data",
        "field5": 123,
        "field6": False,
    }
    # 3 out of 6 have values (field1, field4, field5)
    assert compute_ratio_data_extraction(complex_response) == 0.5


def test_format_ratio_to_percent():
    """Test format_ratio_to_percent function with various inputs."""
    # Zero should return 0%
    assert format_ratio_to_percent(0) == "0%"

    # 0.5 should return 50%
    assert format_ratio_to_percent(0.5) == "50%"

    # 1.0 should return 100%
    assert format_ratio_to_percent(1.0) == "100%"

    # Values are rounded to nearest integer
    assert format_ratio_to_percent(0.333) == "33%"
    assert format_ratio_to_percent(0.667) == "67%"

    # Values greater than 1 are allowed
    assert format_ratio_to_percent(1.5) == "150%"

    # Small values are rounded properly
    assert format_ratio_to_percent(0.01) == "1%"
    assert format_ratio_to_percent(0.001) == "0%"  # Rounds to 0


@pytest.mark.django_db
def test_acte_engagement(client):
    ej, doc = create_ej_and_document()
    doc.classification = "acte_engagement"
    doc.structured_data = {
        "duree": {
            "duree_initiale": 12,
            "nb_reconductions": 3,
            "duree_reconduction": 8,
            "delai_tranche_optionnelle": 24,
        },
        "montant_ht": "40123.50",
        "montant_ttc": "60123.50",
        "rib_autres": [
            {
                "societe": "[[rib_autres.0.societe]]",
                "rib": {"banque": "[[rib_autres.0.rib.banque]]", "iban": "[[rib_autres.0.rib.iban]]"},
            },
            {
                "societe": "[[rib_autres.1.societe]]",
                "rib": {"banque": "[[rib_autres.1.rib.banque]]", "iban": "[[rib_autres.1.rib.iban]]"},
            },
        ],
        "cotraitants": [
            {"nom": "[[cotraitants.0.nom]]", "siret": "[[cotraitants.0.siret]]"},
            {"nom": "[[cotraitants.1.nom]]", "siret": "[[cotraitants.1.siret]]"},
        ],
        "sous_traitants": [
            {"nom": "[[sous_traitants.0.nom]]", "siret": "[[sous_traitants.0.siret]]"},
            {"nom": "[[sous_traitants.1.nom]]", "siret": "[[sous_traitants.1.siret]]"},
        ],
        "lot_concerne": "[[lot_concerne]]",
        "objet_marche": "[[objet_marche]]",
        "rib_mandataire": {"iban": "[[rib_mandataire.iban]]", "banque": "[[rib_mandataire.banque]]"},
        "siren_mandataire": "123456789",
        "siret_mandataire": "12345678901234",
        "date_notification": "[[date_notification]]",
        "societe_principale": "[[societe_principale]]",
        "date_signature_mandataire": "[[date_signature_mandataire]]",
        "administration_beneficiaire": "[[administration_beneficiaire]]",
        "date_signature_administration": "[[date_signature_administration]]",
    }
    doc.save()
    user = UserFactory(is_superuser=True)
    client.force_login(user)
    response = client.get(f"/?num_ej={ej.num_ej}")
    assert response.status_code == 200
    assert "[[rib_autres.0.societe]]" in response.text
    assert "[[rib_autres.0.rib.banque]]" in response.text
    assert "[[rib_autres.0.rib.iban]]" in response.text
    assert "[[rib_autres.1.societe]]" in response.text
    assert "[[rib_autres.1.rib.banque]]" in response.text
    assert "[[rib_autres.1.rib.iban]]" in response.text
    assert "[[cotraitants.0.nom]]" in response.text
    assert "[[cotraitants.0.siret]]" in response.text
    assert "[[cotraitants.1.nom]]" in response.text
    assert "[[cotraitants.1.siret]]" in response.text
    assert "[[sous_traitants.0.nom]]" in response.text
    assert "[[sous_traitants.0.siret]]" in response.text
    assert "[[sous_traitants.1.nom]]" in response.text
    assert "[[sous_traitants.1.siret]]" in response.text
    assert "[[lot_concerne]]" in response.text
    assert "[[objet_marche]]" in response.text
    assert "[[rib_mandataire.iban]]" in response.text
    assert "[[RIB_MANDATAIRE.BANQUE]]" in response.text
    assert "123 456 789" in response.text
    assert "123 456 789 012 34" in response.text
    assert "[[date_notification]]" in response.text
    assert "[[societe_principale]]" in response.text
    assert "[[date_signature_mandataire]]" in response.text
    assert "[[administration_beneficiaire]]" in response.text
    assert "[[date_signature_administration]]" in response.text
    # Séparateur de milliers = espace insécable (U+00A0) avec Django + locale FR
    assert "40\u00a0123,50 €" in response.text  # Montant total ht
    assert "60\u00a0123,50 €" in response.text  # Montant total ttc
    assert "12 mois" in response.text


@pytest.mark.django_db
def test_ccap_without_lots(client):
    ej, doc = create_ej_and_document()
    doc.classification = "ccap"
    doc.structured_data = {
        "ccag": "[[ccag]]",
        "lots": [],
        "intro": None,
        "id_marche": "[[id_marche]]",
        "duree_lots": [],
        "montant_ht": {"type_montant": "total", "montant_ht_maximum": "101234.00"},
        "duree_marche": {
            "duree_initiale": 12,
            "nb_reconductions": 1,
            "duree_reconduction": 6,
            "delai_tranche_optionnelle": 3,
        },
        "forme_marche": {"tranches": None, "structure": "simple", "forme_prix": "forfaitaires"},
        "objet_marche": "[[objet_marche]]",
        "montant_ht_lots": [],
        "forme_marche_lots": [],
    }
    doc.save()
    user = UserFactory(is_superuser=True)
    client.force_login(user)
    response = client.get(f"/?num_ej={ej.num_ej}")
    assert response.status_code == 200
    assert "[[ccag]]" in response.text
    assert "[[id_marche]]" in response.text
    assert "101234" in response.text
    assert "[[objet_marche]]" in response.text
    assert "forfaitaires" in response.text


@pytest.mark.django_db
def test_ccap_with_lots(client):
    ej, doc = create_ej_and_document()
    doc.classification = "ccap"
    doc.structured_data = {
        "ccag": "[[ccag]]",
        "lots": [
            {
                "titre": "[[lots.0.titre]]",
                "numero_lot": 1,
                "forme_marche": {"tranches": None, "structure": "simple", "forme_prix": "forfaitaires"},
                "duree_marche": {
                    "duree_initiale": 12,
                    "nb_reconductions": 1,
                    "duree_reconduction": 6,
                    "delai_tranche_optionnelle": 3,
                },
                "montant_ht": {"type_montant": "total", "montant_ht_maximum": "1111.00"},
            },
            {
                "titre": "[[lots.1.titre]]",
                "numero_lot": 2,
                "forme_marche": {"tranches": None, "structure": "simple", "forme_prix": "forfaitaires"},
                "duree_marche": {
                    "duree_initiale": 12,
                    "nb_reconductions": 1,
                    "duree_reconduction": 6,
                    "delai_tranche_optionnelle": 3,
                },
                "montant_ht": {"type_montant": "total", "montant_ht_maximum": "2222.00"},
            },
        ],
        "intro": None,
        "id_marche": "[[id_marche]]",
        "duree_lots": [],
        "montant_ht": "101234",
        "duree_marche": {
            "duree_initiale": 12,
            "nb_reconductions": 1,
            "duree_reconduction": 6,
            "delai_tranche_optionnelle": 3,
        },
        "forme_marche": {"tranches": None, "structure": "simple", "forme_prix": "forfaitaires"},
        "objet_marche": "[[objet_marche]]",
        "montant_ht_lots": [],
        "forme_marche_lots": [],
        "condition_avance_ccap": {
            "remboursement": "65%-100%",
            "montant_avance": "30%",
            "montant_reference": "montant annuel",
            "condition_declenchement": "Avance systématique",
        },
    }
    doc.save()
    user = UserFactory(is_superuser=True)
    client.force_login(user)
    response = client.get(f"/?num_ej={ej.num_ej}")
    assert response.status_code == 200
    assert "[[ccag]]" in response.text
    assert "[[id_marche]]" in response.text
    assert "[[objet_marche]]" in response.text

    # Lots
    assert "Lot 1&nbsp;" in response.text
    assert "[[lots.0.titre]]" in response.text
    assert "Lot 2&nbsp;" in response.text
    assert "[[lots.1.titre]]" in response.text
    assert "1111" in response.text
    assert "2222" in response.text


@pytest.mark.django_db
def test_rib(client):
    """Vérifie l'affichage correct d'un document RIB (titulaire, adresse, banque, IBAN, etc.)."""
    ej, doc = create_ej_and_document()
    doc.classification = "rib"
    doc.structured_data = {
        "titulaire_compte": "[[titulaire_compte]]",
        "adresse_postale_titulaire": {
            "numero_voie": "10",
            "nom_voie": "rue de la Banque",
            "complement_adresse": "Bâtiment A",
            "code_postal": "75001",
            "ville": "Paris",
            "pays": "France",
        },
        "banque": "[[banque]]",
        "domiciliation": "[[domiciliation]]",
        "bic": "BNPAFRPP",
        "iban": "FR7612345678901234567890123",
    }
    doc.save()
    user = UserFactory(is_superuser=True)
    client.force_login(user)
    response = client.get(f"/?num_ej={ej.num_ej}")
    assert response.status_code == 200

    # Champs affichés par document_rib.html
    assert "Titulaire du compte" in response.text
    assert "[[titulaire_compte]]" in response.text
    assert "Adresse postale" in response.text
    # format_postal_address : "10 rue de la Banque, Bâtiment A, 75001 Paris, France"
    assert "10 rue de la Banque" in response.text
    assert "75001 Paris" in response.text
    assert "France" in response.text
    assert "Banque" in response.text
    assert "[[banque]]" in response.text
    assert "Domiciliation" in response.text
    assert "[[domiciliation]]" in response.text
    assert "BIC" in response.text
    assert "BNPAFRPP" in response.text
    assert "IBAN" in response.text
    # iban_spaces : espace tous les 4 caractères
    assert "FR76 1234 5678 9012 3456 7890 123" in response.text


@pytest.mark.django_db
def test_fiche_navette(client):
    """Vérifie l'affichage des champs du document fiche navette (parties, accord-cadre, prix, imputations)."""
    ej, doc = create_ej_and_document()
    doc.classification = "fiche_navette"
    doc.structured_data = {
        "administration_beneficiaire": "[[administration_beneficiaire]]",
        "objet": "[[objet]]",
        "societe_principale": "[[societe_principale]]",
        "accord_cadre": "[[accord_cadre]]",
        "id_accord_cadre": "[[id_accord_cadre]]",
        "montant_ht": "15000.00",
        "reconduction": "Oui",
        "taux_tva": "0.20",
        "centre_cout": "DRIEETR075",
        "centre_financier": "0174-CLIM-SCEE",
        "activite": "020304DGTUCT",
        "domaine_fonctionnel": "0203-04-02",
        "localisation_interministerielle": "N9130",
        "groupe_marchandise": "40.01.02",
    }
    doc.save()
    user = UserFactory(is_superuser=True)
    client.force_login(user)
    response = client.get(f"/?num_ej={ej.num_ej}")
    assert response.status_code == 200

    # Objet (intro)
    assert "Objet :" in response.text
    assert "[[objet]]" in response.text

    # Section Signataires
    assert "Signataires" in response.text
    assert "Administration bénéficiaire" in response.text
    assert "[[administration_beneficiaire]]" in response.text
    assert "Société principale" in response.text
    assert "[[societe_principale]]" in response.text

    # Section Accord-cadre
    assert "Accord-cadre" in response.text
    assert "Libellé accord-cadre" in response.text
    assert "[[accord_cadre]]" in response.text
    assert "Identifiant accord-cadre" in response.text
    assert "[[id_accord_cadre]]" in response.text

    # Section Prix et reconduction (taux_tva affiché en % via as_percentage)
    assert "Prix et reconduction" in response.text
    assert "Montant HT" in response.text
    assert "15" in response.text and "000" in response.text  # montant formaté (locale)
    assert "Taux TVA" in response.text
    assert "20&nbsp;%" in response.text
    assert "Reconduction" in response.text
    assert "Oui" in response.text

    # Section Imputations budgétaires et comptables
    assert "Imputations budgétaires et comptables" in response.text
    assert "Centre de coût" in response.text
    assert "DRIEETR075" in response.text
    assert "Centre financier" in response.text
    assert "0174-CLIM-SCEE" in response.text
    assert "Activité" in response.text
    assert "020304DGTUCT" in response.text
    assert "Domaine fonctionnel" in response.text
    assert "0203-04-02" in response.text
    assert "Localisation interministérielle" in response.text
    assert "N9130" in response.text
    assert "Groupe de marchandise" in response.text
    assert "40.01.02" in response.text
