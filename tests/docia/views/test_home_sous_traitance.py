"""Tests d'affichage (front) de la catégorie sous_traitance."""

import pytest

from tests.docia.views.test_home import create_ej_and_document
from tests.factories.users import UserFactory


def _sous_traitance_base_data(**overrides):
    """Données minimales pour un document sous-traitance (accroche + objet)."""
    data = {
        "objet_marche": "",
        "administration_beneficiaire": None,
        "societe_principale": None,
        "adresse_postale_titulaire": None,
        "siret_titulaire": None,
        "societe_sous_traitant": None,
        "adresse_postale_sous_traitant": None,
        "siret_sous_traitant": None,
        "montant_sous_traitance_ht": None,
        "montant_sous_traitance_ttc": None,
        "montant_tva": None,
        "description_prestations": None,
        "duree_sous_traitance": None,
        "paiement_direct": None,
        "conserve_avance": None,
        "rib_sous_traitant": None,
        "date_signature": None,
    }
    data.update(overrides)
    return data


def _login_and_get_sous_traitance(client, ej, doc):
    """Connexion admin et GET page d'accueil avec num_ej pour un EJ contenant le doc."""
    user = UserFactory(is_superuser=True)
    client.force_login(user)
    response = client.get(f"/?num_ej={ej.num_ej}")
    assert response.status_code == 200
    return response.text


# ----- Affichage complet -----


@pytest.mark.django_db
def test_sous_traitance_complet(client):
    """Sous-traitance avec toutes les sections remplies :
    accroche, titulaire, sous-traitant, montants, durée, prestations, paiement, dates."""
    ej, doc = create_ej_and_document()
    doc.classification = "sous_traitance"
    doc.structured_data = _sous_traitance_base_data(
        objet_marche="Marché de sous-traitance test",
        societe_principale="Titulaire SARL",
        societe_sous_traitant="Sous-traitant SA",
        administration_beneficiaire="Ministère Test",
        adresse_postale_titulaire={
            "numero_voie": "10",
            "nom_voie": "rue des Lilas",
            "complement_adresse": "",
            "code_postal": "69001",
            "ville": "Lyon",
            "pays": "France",
        },
        siret_titulaire="12345678901234",
        siret_sous_traitant="98765432109876",
        montant_sous_traitance_ht="15000.00",
        montant_sous_traitance_ttc="18000.00",
        montant_tva="0.20",
        description_prestations="Nettoyage et maintenance",
        duree_sous_traitance={
            "duree_initiale": 24,
            "duree_reconduction": 12,
            "nb_reconductions": 2,
            "delai_tranche_optionnelle": None,
        },
        paiement_direct="oui",
        conserve_avance="conserve",
        rib_sous_traitant={"banque": "SG", "iban": "FR7612345678901234567890123"},
        date_signature="01/03/2025",
    )
    doc.save()
    text = _login_and_get_sous_traitance(client, ej, doc)

    assert "Titulaire – Titulaire SARL – SIRET" in text and "Sous-traitant – Sous-traitant SA – SIRET" in text
    assert "123 456 789 012 34" in text and "987 654 321 098 76" in text

    assert "Éligible au paiement direct" in text and "Souhaite conserver l'avance" in text
    assert "Description des prestations" in text and "Nettoyage et maintenance" in text
    assert "Signé le" in text and "01/03/2025" in text
    assert "Durée des prestations" in text and "24 mois" in text and "reconductible" in text

    assert "Montants et TVA" in text and "Montant sous-traitance HT" in text
    assert "15000" in text and "18000" in text and "Taux TVA" in text


# ----- Sections grisées (données absentes) -----


@pytest.mark.django_db
def test_sous_traitance_sections_grisees(client):
    """Sous-traitance avec données minimales : sections Montants, Durée, Paiement, Dates grisées."""
    ej, doc = create_ej_and_document()
    doc.classification = "sous_traitance"
    doc.structured_data = _sous_traitance_base_data(
        objet_marche="Objet minimal",
        societe_principale="Titulaire",
        societe_sous_traitant="Sous-traitant",
    )
    doc.save()
    text = _login_and_get_sous_traitance(client, ej, doc)

    assert "Titulaire –" in text and "Sous-traitant –" in text
    assert "Éligible au paiement direct" in text and "Souhaite conserver l'avance" in text
    assert "Montants et TVA – Non disponibles dans le document." in text


# ----- Montants et TVA -----


@pytest.mark.django_db
def test_sous_traitance_montants_et_tva_visibles(client):
    """Section Montants et TVA affichée avec HT, TTC et taux TVA."""
    ej, doc = create_ej_and_document()
    doc.classification = "sous_traitance"
    doc.structured_data = _sous_traitance_base_data(
        objet_marche="Marché",
        societe_principale="T",
        societe_sous_traitant="ST",
        montant_sous_traitance_ht="5000.00",
        montant_sous_traitance_ttc="6000.00",
        montant_tva="0.20",
    )
    doc.save()
    text = _login_and_get_sous_traitance(client, ej, doc)

    assert "Montants et TVA" in text
    assert "Montant sous-traitance HT" in text and "5000" in text
    assert "Montant sous-traitance TTC" in text and "6000" in text
    assert "Taux TVA" in text


# ----- Durée -----


@pytest.mark.django_db
def test_sous_traitance_duree_non_reconductible(client):
    """Section Durée affichée avec durée initiale, non reconductible."""
    ej, doc = create_ej_and_document()
    doc.classification = "sous_traitance"
    doc.structured_data = _sous_traitance_base_data(
        objet_marche="Marché",
        societe_principale="T",
        societe_sous_traitant="ST",
        duree_sous_traitance={
            "duree_initiale": 6,
            "duree_reconduction": None,
            "nb_reconductions": 0,
            "delai_tranche_optionnelle": None,
        },
    )
    doc.save()
    text = _login_and_get_sous_traitance(client, ej, doc)

    assert "Durée des prestations" in text and "6 mois" in text
    assert "non reconductible" in text


@pytest.mark.django_db
def test_sous_traitance_duree_avec_reconduction(client):
    """Section Durée avec reconductions et durée d'une reconduction."""
    ej, doc = create_ej_and_document()
    doc.classification = "sous_traitance"
    doc.structured_data = _sous_traitance_base_data(
        objet_marche="Marché",
        societe_principale="T",
        societe_sous_traitant="ST",
        duree_sous_traitance={
            "duree_initiale": 12,
            "duree_reconduction": 6,
            "nb_reconductions": 2,
            "delai_tranche_optionnelle": None,
        },
    )
    doc.save()
    text = _login_and_get_sous_traitance(client, ej, doc)

    assert "Durée des prestations" in text and "12 mois" in text and "reconductible" in text
    assert "2 reconductions" in text and "6" in text


# ----- Description des prestations -----


@pytest.mark.django_db
def test_sous_traitance_description_prestations_visible(client):
    """Section Description des prestations affichée quand renseignée."""
    ej, doc = create_ej_and_document()
    doc.classification = "sous_traitance"
    doc.structured_data = _sous_traitance_base_data(
        objet_marche="Marché",
        societe_principale="T",
        societe_sous_traitant="ST",
        description_prestations="Prestations détaillées ici",
    )
    doc.save()
    text = _login_and_get_sous_traitance(client, ej, doc)

    assert "Description des prestations" in text
    assert "Prestations détaillées ici" in text


# ----- Paiement -----


@pytest.mark.django_db
def test_sous_traitance_paiement_sans_rib(client):
    """Section Paiement affichée avec paiement direct et avance, sans RIB."""
    ej, doc = create_ej_and_document()
    doc.classification = "sous_traitance"
    doc.structured_data = _sous_traitance_base_data(
        objet_marche="Marché",
        societe_principale="T",
        societe_sous_traitant="ST",
        paiement_direct="non",
        conserve_avance="ne_conserve_pas",
    )
    doc.save()
    text = _login_and_get_sous_traitance(client, ej, doc)

    assert "Éligible au paiement direct" in text
    assert "Souhaite conserver l'avance" in text
    assert "Non" in text


# ----- Dates et signature -----


@pytest.mark.django_db
def test_sous_traitance_dates_et_signature_visibles(client):
    """Section Dates et signature affichée quand date_signature renseignée."""
    ej, doc = create_ej_and_document()
    doc.classification = "sous_traitance"
    doc.structured_data = _sous_traitance_base_data(
        objet_marche="Marché",
        societe_principale="T",
        societe_sous_traitant="ST",
        date_signature="20/12/2024",
    )
    doc.save()
    text = _login_and_get_sous_traitance(client, ej, doc)

    assert "Signé le" in text and "20/12/2024" in text
