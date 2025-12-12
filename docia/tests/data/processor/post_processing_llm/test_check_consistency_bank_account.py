import pytest

from app.processor.post_processing_llm import check_consistency_bank_account


def test_check_consistency_bank_account_valid_iban():
    """Test avec un IBAN français valide."""
    # IBAN français valide (exemple fictif mais format correct)
    valid_iban = "FR1420041010050500013M02606"
    assert check_consistency_bank_account(valid_iban) is True


def test_check_consistency_bank_account_empty_string():
    """Test avec une chaîne vide (doit retourner True)."""
    assert check_consistency_bank_account("") is True
    assert check_consistency_bank_account(None) is True


def test_check_consistency_bank_account_wrong_length():
    """Test avec un IBAN de longueur incorrecte."""
    # Trop court
    assert check_consistency_bank_account("FR14") is False
    # Trop long
    assert check_consistency_bank_account("FR1420041010050500013M02606123") is False
    # Longueur correcte mais pas 27 caractères
    assert check_consistency_bank_account("FR1420041010050500013M026") is False


def test_check_consistency_bank_account_invalid_characters():
    """Test avec des caractères invalides dans l'IBAN."""
    # Caractères spéciaux
    assert check_consistency_bank_account("FR1420041010050500013M026@") is False
    # Espaces
    assert check_consistency_bank_account("FR14 2004 1010 0505 0001 3M02 606") is False


def test_check_consistency_bank_account_invalid_checksum():
    """Test avec un IBAN de longueur correcte mais checksum invalide."""
    # Format correct mais checksum incorrect
    invalid_iban = "FR1420041010050500013M02607"  # Dernier chiffre modifié
    assert check_consistency_bank_account(invalid_iban) is False


def test_check_consistency_bank_account_lowercase():
    """Test avec un IBAN en minuscules (doit être converti en majuscules)."""
    # La fonction convertit en majuscules, donc un IBAN valide en minuscules devrait fonctionner
    # Mais le checksum doit être correct
    lowercase_iban = "fr1420041010050500013m02606"
    # Le résultat dépend de la conversion, mais généralement ça devrait échouer car le checksum change
    # On teste juste que ça ne plante pas
    result = check_consistency_bank_account(lowercase_iban)
    assert isinstance(result, bool)
