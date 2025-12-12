import pytest

from app.processor.post_processing_llm import post_processing_bank_account


def test_post_processing_bank_account_with_iban():
    """Test avec IBAN présent."""
    bank_account = {
        'banque': 'Crédit Agricole',
        'iban': 'FR76 30001 0079 4123 4567 8901 85'
    }
    result = post_processing_bank_account(bank_account)
    assert result == {
        'banque': 'Crédit Agricole',
        'iban': 'FR7630001007941234567890185'
    }


def test_post_processing_bank_account_with_rib_fields():
    """Test avec les 4 champs RIB (code_banque, code_guichet, numero_compte, cle_rib)."""
    bank_account = {
        'banque': 'Banque de France',
        'code_banque': '30001',
        'code_guichet': '00794',
        'numero_compte': '12345678901',
        'cle_rib': '85'
    }
    result = post_processing_bank_account(bank_account)
    assert result['banque'] == 'Banque de France'
    assert result['iban'].startswith('FR76')
    assert len(result['iban']) == 27


def test_post_processing_bank_account_empty():
    """Test avec dictionnaire vide."""
    assert post_processing_bank_account({}) is None
    assert post_processing_bank_account(None) is None


def test_post_processing_bank_account_missing_banque():
    """Test sans clé 'banque' (doit lever une erreur)."""
    bank_account = {
        'iban': 'FR7630001007941234567890185'
    }
    with pytest.raises(ValueError, match="doit contenir la clé 'banque'"):
        post_processing_bank_account(bank_account)


def test_post_processing_bank_account_no_iban_no_rib():
    """Test sans IBAN ni les 4 champs RIB (doit lever une erreur)."""
    bank_account = {
        'banque': 'Crédit Agricole'
    }
    with pytest.raises(ValueError, match="doit contenir soit un IBAN"):
        post_processing_bank_account(bank_account)


def test_post_processing_bank_account_incomplete_rib():
    """Test avec seulement quelques champs RIB."""
    bank_account = {
        'banque': 'Banque de France',
        'code_banque': '30001',
        'code_guichet': '00794'
        # Manque numero_compte et cle_rib
    }
    with pytest.raises(ValueError, match="doit contenir soit un IBAN"):
        post_processing_bank_account(bank_account)


def test_post_processing_bank_account_invalid_iban():
    """Test avec IBAN invalide."""
    bank_account = {
        'banque': 'Crédit Agricole',
        'iban': 'FR7630001007941234567890186'  # Checksum incorrect (dernier chiffre modifié)
    }
    result = post_processing_bank_account(bank_account)
    assert result == {
        'banque': 'Crédit Agricole',
        'iban': None
    }


def test_post_processing_bank_account_empty_iban_and_banque():
    """Test avec IBAN et banque vides."""
    bank_account = {
        'banque': '',
        'iban': ''
    }
    assert post_processing_bank_account(bank_account) is None


def test_post_processing_bank_account_iban_with_spaces():
    """Test avec IBAN contenant des espaces."""
    bank_account = {
        'banque': 'Crédit Agricole',
        'iban': 'FR76 30001 0079 4123 4567 8901 85'
    }
    result = post_processing_bank_account(bank_account)
    assert result['iban'] == 'FR7630001007941234567890185'


def test_post_processing_bank_account_rib_fields_with_none():
    """Test avec les 4 champs RIB présents mais avec valeurs None."""
    bank_account = {
        'banque': 'Banque de France',
        'code_banque': None,
        'code_guichet': None,
        'numero_compte': None,
        'cle_rib': None
    }
    # Si tous les champs RIB sont None, la fonction construit un IBAN invalide
    # (FR76 + '' + '' + '' + '' = 'FR76') et retourne iban: None
    result = post_processing_bank_account(bank_account)
    assert result == {
        'banque': 'Banque de France',
        'iban': None
    }


def test_post_processing_bank_account_rib_fields_with_empty_strings():
    """Test avec les 4 champs RIB présents mais avec valeurs vides ('')."""
    bank_account = {
        'banque': 'Banque de France',
        'code_banque': '',
        'code_guichet': '',
        'numero_compte': '',
        'cle_rib': ''
    }
    # Si tous les champs RIB sont vides, la fonction construit un IBAN invalide
    # (FR76 + '' + '' + '' + '' = 'FR76') et retourne iban: None
    result = post_processing_bank_account(bank_account)
    assert result == {
        'banque': 'Banque de France',
        'iban': None
    }

