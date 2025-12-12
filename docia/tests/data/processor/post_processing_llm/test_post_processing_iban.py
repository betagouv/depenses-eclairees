import pytest

from app.processor.post_processing_llm import post_processing_iban


def test_post_processing_iban_valid():
    """Test avec un IBAN valide."""
    valid_iban = "FR1420041010050500013M02606"
    result = post_processing_iban(valid_iban)
    assert result == "FR1420041010050500013M02606"


def test_post_processing_iban_with_spaces():
    """Test avec espaces dans l'IBAN."""
    iban = "FR14 2004 1010 0505 0001 3M02 606"
    result = post_processing_iban(iban)
    assert result == "FR1420041010050500013M02606"


def test_post_processing_iban_lowercase():
    """Test avec IBAN en minuscules."""
    iban = "fr1420041010050500013m02606"
    result = post_processing_iban(iban)
    assert result == "FR1420041010050500013M02606"


def test_post_processing_iban_invalid():
    """Test avec un IBAN invalide."""
    invalid_iban = "FR1420041010050500013M02607"  # Checksum incorrect
    assert post_processing_iban(invalid_iban) is None


def test_post_processing_iban_wrong_length():
    """Test avec IBAN de longueur incorrecte."""
    assert post_processing_iban("FR14") is None
    assert post_processing_iban("FR1420041010050500013M02606123") is None


def test_post_processing_iban_empty():
    """Test avec chaîne vide."""
    assert post_processing_iban("") is None
    assert post_processing_iban("   ") is None
