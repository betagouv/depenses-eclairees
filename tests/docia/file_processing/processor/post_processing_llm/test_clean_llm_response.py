import copy

from schwifty import IBAN

from docia.file_processing.processor.post_processing_llm import clean_llm_response

# IBAN français valides (checksum OK) mais volontairement fictifs — pas de code banque réel.
_IBAN_MANDATAIRE = str(IBAN.generate("FR", bank_code="99000", branch_code="00000", account_code="00000000000"))
_IBAN_AUTRE = str(IBAN.generate("FR", bank_code="99001", branch_code="00001", account_code="00000000001"))


def _iban_espaces_quatre(iban: str) -> str:
    return " ".join(iban[i : i + 4] for i in range(0, len(iban), 4))


def test_clean_llm_response_acte_engagement():
    """Vérifie le post-traitement de tous les champs configurés pour acte_engagement (CLEAN_FUNCTIONS)."""
    llm_response = {
        "rib_mandataire": {
            "banque": "Banque test",
            "iban": _iban_espaces_quatre(_IBAN_MANDATAIRE),
        },
        "montant_ttc": "1 234,5 €",
        "montant_ht": "1000",
        "montant_tva": "20%",
        "cotraitants": [{"nom": "Co A", "siret": "7328 2932 0000 74"}],
        "sous_traitants": [{"nom": "Sub A", "siret": "44306184100047"}],
        "siret_mandataire": "732 829 320 00074",
        "duree": {
            "duree_initiale": "12",
            "duree_reconduction": "6",
            "nb_reconductions": "2",
            "delai_tranche_optionnelle": None,
        },
        "rib_autres": [
            {
                "societe": "Société test",
                "rib": {"banque": "Banque test", "iban": _iban_espaces_quatre(_IBAN_AUTRE)},
            }
        ],
        "societe_principale": "Société test (SARL)",
    }
    original_payload = copy.deepcopy(llm_response)

    result = clean_llm_response("acte_engagement", llm_response)

    assert result == {
        "rib_mandataire": {"banque": "Banque test", "iban": _IBAN_MANDATAIRE},
        "montant_ttc": "1234.50",
        "montant_ht": "1000.00",
        "montant_tva": "20.00",
        "cotraitants": [{"nom": "Co A", "siret": "73282932000074"}],
        "sous_traitants": [{"nom": "Sub A", "siret": "44306184100047"}],
        "siret_mandataire": "73282932000074",
        "duree": {
            "duree_initiale": 12,
            "duree_reconduction": 6,
            "nb_reconductions": 2,
            "delai_tranche_optionnelle": None,
        },
        "rib_autres": [
            {
                "societe": "test",
                "rib": {"banque": "Banque test", "iban": _IBAN_AUTRE},
            }
        ],
        "societe_principale": "test",
    }
    assert llm_response == original_payload


def test_clean_llm_response_rib_rebuilds_iban_from_rib_fields():
    """Vérifie qu'un document RIB reconstruit l'IBAN depuis les champs RIB si besoin."""
    llm_response = {
        "iban": None,
        "code_pays": "FR",
        "code_banque": "30001",
        "code_guichet": "00794",
        "numero_compte": "12345678901",
        "cle_rib": "85",
        "bic": "AGRIFRPP",
        "titulaire_compte": "Entreprise Test (SARL)",
        "adresse_postale_titulaire": {
            "numero_voie": "1",
            "nom_voie": "Rue de la Paix",
            "complement_adresse": "",
            "code_postal": "75001",
            "ville": "PARIS",
            "pays": "France",
        },
        "domiciliation": "Agence Paris",
        "banque": "Banque de France",
    }

    result = clean_llm_response("rib", llm_response)

    assert result["iban"].startswith("FR76")
    assert len(result["iban"]) == 27
    assert result["iban"][:2] == "FR"  # IBAN FR
    assert result["iban"][2:4] == "76"  # Code pays FR
    assert result["iban"][4:9] == "30001"  # Code banque
    assert result["iban"][9:14] == "00794"  # Code guichet
    assert result["iban"][14:25] == "12345678901"  # Numero de compte
    assert result["iban"][25:27] == "85"  # Cle rib

    assert result["bic"] == "AGRIFRPP"
    assert result["banque"] == "Banque de France"
    assert result["titulaire_compte"] == "Entreprise Test"


def test_clean_llm_response_rib_missing_iban_key_rebuilds():
    """Clé iban absente du JSON LLM : même comportement que iban null (reconstruction)."""
    llm_response = {
        "code_banque": "30001",
        "code_guichet": "00794",
        "numero_compte": "12345678901",
        "cle_rib": "85",
        "bic": "AGRIFRPP",
        "titulaire_compte": "Entreprise Test",
        "banque": "Banque de France",
    }

    result = clean_llm_response("rib", llm_response)

    assert result["iban"] is not None
    assert result["iban"].startswith("FR76")
    assert len(result["iban"]) == 27


def test_clean_llm_response_rib_titulaire_compte_postprocessing():
    """Le titulaire du compte est nettoyé comme societe_principale (formes juridiques, parenthèses)."""
    llm_response = {
        "iban": _IBAN_MANDATAIRE,
        "titulaire_compte": "La Poste SA",
    }

    result = clean_llm_response("rib", llm_response)

    assert result["titulaire_compte"] == "La Poste"


def test_clean_llm_response_fiche_navette_amounts_independent():
    """montant_ht et montant_maximum sont normalisés séparément, sans repli l'un sur l'autre."""
    llm_response = {
        "montant_ht": "25 000,50 €",
        "montant_maximum": "1 234,56 €",
        "taux_tva": "0.20",
    }

    result = clean_llm_response("fiche_navette", llm_response)

    assert result["montant_ht"] == "25000.50"
    assert result["montant_maximum"] == "1234.56"


def test_clean_llm_response_rib_no_iban_and_incomplete_rib_sets_iban_none():
    """Reconstruction impossible et post_processing_bank_account renvoie None : pas de plantage."""
    llm_response = {
        "bic": "AGRIFRPP",
        "titulaire_compte": "Entreprise Test",
    }

    result = clean_llm_response("rib", llm_response)

    assert result["iban"] is None
