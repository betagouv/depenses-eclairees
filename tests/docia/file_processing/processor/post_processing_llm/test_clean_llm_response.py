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
        "cotraitants": [{"nom": "Co A", "siret": "1234 5678 9012 34"}],
        "sous_traitants": [{"nom": "Sub A", "siret": "98765432109876"}],
        "siret_mandataire": "123 456 789 01234",
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
        "cotraitants": [{"nom": "Co A", "siret": "12345678901234"}],
        "sous_traitants": [{"nom": "Sub A", "siret": "98765432109876"}],
        "siret_mandataire": "12345678901234",
        "duree": {
            "duree_initiale": 12,
            "duree_reconduction": 6,
            "nb_reconductions": 2,
            "delai_tranche_optionnelle": None,
        },
        "rib_autres": [
            {
                "societe": "Société test",
                "rib": {"banque": "Banque test", "iban": _IBAN_AUTRE},
            }
        ],
        "societe_principale": "test",
    }
    assert llm_response == original_payload
