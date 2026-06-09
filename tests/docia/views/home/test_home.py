import pytest

from tests.docia.views.home.utils import create_ej_and_document
from tests.factories.users import UserFactory


@pytest.mark.django_db
def test_acte_engagement(client):
    """Vérifie l'affichage des champs acte_engagement."""
    ej, doc = create_ej_and_document()
    doc.classification = "acte_engagement"
    doc.structured_data = {
        "objet_marche": "[[objet_marche]]",
        "administration_beneficiaire": "[[administration_beneficiaire]]",
        "societe_principale": "[[societe_principale]]",
        "siret_mandataire": "73282932000074",
        "siren_mandataire": "123456789",
        "rib_mandataire": {"iban": "[[rib_mandataire.iban]]", "banque": "[[rib_mandataire.banque]]"},
        "cotraitants": [
            {"nom": "[[cotraitants.0.nom]]", "siret": "[[cotraitants.0.siret]]"},
            {"nom": "[[cotraitants.1.nom]]", "siret": "[[cotraitants.1.siret]]"},
        ],
        "sous_traitants": [
            {"nom": "[[sous_traitants.0.nom]]", "siret": "[[sous_traitants.0.siret]]"},
            {"nom": "[[sous_traitants.1.nom]]", "siret": "[[sous_traitants.1.siret]]"},
        ],
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
        "montant_ttc": "60123.50",
        "montant_ht": "40123.50",
        "date_signature_mandataire": "[[date_signature_mandataire]]",
        "date_signature_administration": "[[date_signature_administration]]",
        "date_notification": "[[date_notification]]",
        "duree": {
            "duree_initiale": 12,
            "nb_reconductions": 3,
            "duree_reconduction": 8,
            "delai_tranche_optionnelle": 24,
        },
        "conserve_avance": "renonce",
        "montants_en_annexe": {
            "annexe_financière": True,
            "classification": ["BPU", "Annexe financière"],
        },
        "forme_marche": {
            "lot_concerne": {"numero_lot": 1, "titre_lot": "[[forme_marche.lot_concerne.titre_lot]]"},
            "marche_subsequent": True,
            "marche_parent": "[[forme_marche.marche_parent]]",
        },
        "code_cpv": "[[code_cpv]]",
        "montant_tva": "0.20",
        "mode_consultation": "[[mode_consultation]]",
        "mode_reconduction": "tacite",
        "ligne_imputation_budgetaire": "[[ligne_imputation_budgetaire]]",
        "lot_concerne": "[[lot_concerne]]",
    }
    doc.save()
    user = UserFactory(is_superuser=True)
    client.force_login(user)
    response = client.get(f"/?num_ej={ej.num_ej}")
    assert response.status_code == 200
    text = response.text

    # Ordre des assertions = ordre des sections dans document_acte_engagement.html

    # En-tête (signataires + objet)
    assert "[[administration_beneficiaire]]" in text
    assert "[[societe_principale]]" in text
    assert "[[objet_marche]]" in text
    assert "[[lot_concerne]]" in text

    # Section Informations générales
    assert "[[forme_marche.lot_concerne.titre_lot]]" in text
    assert "[[forme_marche.marche_parent]]" in text
    assert "[[code_cpv]]" in text
    assert "[[mode_consultation]]" in text

    # Section Titulaire
    assert "123 456 789" in text
    assert "732 829 320 000 74" in text
    assert "Oui" in text  # En groupement

    # Section Prix
    assert "40\u00a0123,50 €" in text
    assert "60\u00a0123,50 €" in text
    assert "20" in text  # Taux TVA
    assert "Non" in text  # conserve_avance = renonce
    assert "BPU" in text or "Annexe financière" in text  # montants_en_annexe

    # Section Durée du marché
    assert "12 mois" in text
    assert "Nombre de reconductions" in text
    assert "8 mois" in text
    assert "tacite" in text  # Type reconduction

    # Section Informations bancaires
    assert "[[rib_mandataire.iban]]" in text
    assert "[[RIB_MANDATAIRE.BANQUE]]" in text

    # Section Dates et signatures
    assert "[[date_signature_mandataire]]" in text
    assert "[[date_signature_administration]]" in text
    assert "[[date_notification]]" in text

    # Section Cotraitants
    assert "[[cotraitants.0.nom]]" in text
    assert "[[cotraitants.0.siret]]" in text
    assert "[[cotraitants.1.nom]]" in text
    assert "[[cotraitants.1.siret]]" in text

    # Section Sous-traitants
    assert "[[sous_traitants.0.nom]]" in text
    assert "[[sous_traitants.0.siret]]" in text
    assert "[[sous_traitants.1.nom]]" in text
    assert "[[sous_traitants.1.siret]]" in text

    # Section RIBs (sous-traitants / co-traitants)
    assert "[[rib_autres.0.societe]]" in text
    assert "[[rib_autres.0.rib.banque]]" in text
    assert "[[rib_autres.0.rib.iban]]" in text
    assert "[[rib_autres.1.societe]]" in text
    assert "[[rib_autres.1.rib.banque]]" in text
    assert "[[rib_autres.1.rib.iban]]" in text


@pytest.mark.django_db
def test_ccp_vae_uses_acte_engagement_template(client):
    """ccp_vae : même gabarit que l'acte d'engagement (enrichissement + document_acte_engagement)."""
    ej, doc = create_ej_and_document()
    doc.classification = "ccp_vae"
    doc.structured_data = {
        "objet_marche": "[[objet_marche]]",
        "administration_beneficiaire": "[[administration_beneficiaire]]",
        "societe_principale": "[[societe_principale]]",
        "montant_ht": "40123.50",
        "montant_ttc": "60123.50",
        "montant_tva": "0.20",
    }
    doc.save()
    user = UserFactory(is_superuser=True)
    client.force_login(user)
    response = client.get(f"/?num_ej={ej.num_ej}")
    assert response.status_code == 200
    text = response.text
    assert "[[objet_marche]]" in text
    assert "40\u00a0123,50 €" in text
    assert "60\u00a0123,50 €" in text


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
def test_avenant(client):
    """Vérifie l'affichage d'un document avenant (bloc avenant + accordéon Informations Marché)."""
    ej, doc = create_ej_and_document()
    doc.classification = "avenant"
    doc.structured_data = {
        "numero_avenant": "2",
        "objet_avenant": "[[objet_avenant]]",
        "incidence_financiere": {"ht": "10000.00", "taux_tva": "0.20", "tva": "2000.00", "ttc": "12000.00"},
        "incidence_duree": {"prolongation": 6, "date_fin_execution": "31/12/2027"},
        "incidence_bpu": True,
        "date_derniere_signature": "15/03/2026",
        "objet_marche": "[[objet_marche]]",
        "administration_beneficiaire": "[[administration_beneficiaire]]",
        "societe_principale": "[[societe_principale]]",
        "date_marche": {
            "duree_execution": 48,
            "date_notification": "01/01/2024",
            "date_fin_execution": "31/12/2027",
        },
        "montant_initial": {"ht": "50000.00", "taux_tva": "0.20", "tva": "10000.00", "ttc": "60000.00"},
    }
    doc.save()
    user = UserFactory(is_superuser=True)
    client.force_login(user)
    response = client.get(f"/?num_ej={ej.num_ej}")
    assert response.status_code == 200
    text = response.text

    assert "Avenant n°2" in text
    assert "[[objet_avenant]]" in text
    assert "Incidence financière" in text
    assert "10\u00a0000,00 € HT" in text
    assert "12\u00a0000,00 € TTC" in text
    assert "Incidence durée" in text
    assert "Prolongation 6 mois" in text
    assert "Fin 31/12/2027" in text
    assert "Incidence BPU" in text
    assert "Date de dernière signature" in text
    assert "15/03/2026" in text
    assert "Informations Marché" in text
    assert "Objet du marché" in text
    assert "[[objet_marche]]" in text
    assert "Administration bénéficiaire" in text
    assert "[[administration_beneficiaire]]" in text
    assert "Société principale" in text
    assert "[[societe_principale]]" in text
    assert "Durée d'exécution" in text
    assert "48 mois" in text
    assert "Date de notification" in text
    assert "01/01/2024" in text
    assert "Montant initial" in text
    assert "50\u00a0000,00 € HT" in text


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
        "montant_maximum": "20000.00",
        "reconduction": "Oui",
        "taux_tva": "0.20",
        "centre_cout": "DRIEETR075",
        "centre_financier": "0174-CLIM-SCEE",
        "activite": "020304DGTUCT",
        "domaine_fonctionnel": "0203-04-02",
        "fond": "1-1-00733",
        "localisation_interministerielle": "N9130",
        "groupe_marchandise": "40.01.02",
        "axe_ministeriel_1": "10-SG-SIMJ",
        "projet_analytique": "PROJ-001",
        "localisation_ministerielle": "LOC-001",
        "axe_ministeriel_2": "10-SG-SIMJ",
        "remarque": "[[remarque]]",
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
    assert "Montant maximum" in response.text
    assert "20" in response.text and "000" in response.text
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
    assert "Fond" in response.text
    assert "1-1-00733" in response.text
    assert "Localisation interministérielle" in response.text
    assert "N9130" in response.text
    assert "Groupe de marchandise" in response.text
    assert "40.01.02" in response.text
    assert "Axe ministériel 1" in response.text
    assert "10-SG-SIMJ" in response.text
    assert "Projet analytique" in response.text
    assert "PROJ-001" in response.text
    assert "Localisation ministérielle" in response.text
    assert "LOC-001" in response.text
    assert "Axe ministériel 2" in response.text

    # Section Remarque
    assert "Remarque" in response.text
    assert "[[remarque]]" in response.text


@pytest.mark.django_db
def test_sous_traitance(client):
    """Vérifie l'affichage du document sous-traitance
    (Titulaire/Sous-traitant – SIRET, puis sections Montants, Durée, etc.)."""
    ej, doc = create_ej_and_document()
    doc.classification = "sous_traitance"
    doc.structured_data = {
        "objet_marche": "[[objet_marche]]",
        "administration_beneficiaire": "[[administration_beneficiaire]]",
        "societe_principale": "[[societe_principale]]",
        "adresse_postale_titulaire": {
            "numero_voie": "1",
            "nom_voie": "rue Example",
            "complement_adresse": "",
            "code_postal": "75001",
            "ville": "Paris",
            "pays": "France",
        },
        "siret_titulaire": "73282932000074",
        "societe_sous_traitant": "[[societe_sous_traitant]]",
        "siret_sous_traitant": "44306184100047",
        "montant_sous_traitance_ht": "10000.00",
        "montant_sous_traitance_ttc": "12000.00",
        "montant_tva": "0.20",
        "description_prestations": "[[description_prestations]]",
        "duree_sous_traitance": {
            "duree_initiale": 12,
            "duree_reconduction": 12,
            "nb_reconductions": 2,
            "delai_tranche_optionnelle": None,
        },
        "paiement_direct": "oui",
        "conserve_avance": "conserve",
        "rib_sous_traitant": {"banque": "BNP", "iban": "FR7612345678901234567890123"},
        "date_signature": "15/01/2025",
    }
    doc.save()
    user = UserFactory(is_superuser=True)
    client.force_login(user)
    response = client.get(f"/?num_ej={ej.num_ej}")
    assert response.status_code == 200

    # Titulaire / Sous-traitant : libellé et SIRET (une ligne chacun)
    assert "Titulaire – [[societe_principale]] – SIRET" in response.text
    assert "Sous-traitant – [[societe_sous_traitant]] – SIRET" in response.text
    assert "732 829 320 000 74" in response.text
    assert "443 061 841 000 47" in response.text

    # Lignes sous le sous-traitant : paiement direct, avance, prestations, signé le, durée
    # (style acte_engagement : icône check/close + Oui/Non)
    assert "Éligible au paiement direct" in response.text
    assert "Oui" in response.text
    assert "Souhaite conserver l'avance" in response.text
    assert "Description des prestations" in response.text
    assert "[[description_prestations]]" in response.text
    assert "Signé le" in response.text
    assert "15/01/2025" in response.text
    assert "Durée des prestations" in response.text
    assert "12 mois" in response.text
    assert "reconductible" in response.text

    # Seul menu déroulant : Montants et TVA
    assert "Montants et TVA" in response.text
    assert "Montant sous-traitance HT" in response.text
    assert "Montant sous-traitance TTC" in response.text
    assert "Taux TVA" in response.text
    assert "20&nbsp;%" in response.text
