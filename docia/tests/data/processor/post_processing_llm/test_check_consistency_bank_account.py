from docia.file_processing.processor.post_processing_llm import check_consistency_iban


def test_check_consistency_iban_valid_iban():
    """Test avec un IBAN français valide."""
    # IBAN français valide (exemple fictif mais format correct)
    valid_iban = "FR7630001007941234567890185"
    assert check_consistency_iban(valid_iban) is True


def test_check_consistency_iban_empty_string():
    """Test avec une chaîne vide (doit retourner True)."""
    assert check_consistency_iban("") is True
    assert check_consistency_iban(None) is True


def test_check_consistency_iban_wrong_length():
    """Test avec un IBAN de longueur incorrecte."""
    # Trop court
    assert check_consistency_iban("FR76") is False
    # Trop long
    assert check_consistency_iban("FR7630001007941234567890185134") is False
    # 25 caractères
    assert check_consistency_iban("FR76300010079412345678901") is False


def test_check_consistency_iban_invalid_characters():
    """Test avec des caractères invalides dans l'IBAN."""
    # Caractères spéciaux
    assert check_consistency_iban("FR763000100794123456789018@") is False
    # Espaces
    assert check_consistency_iban("FR76 30001 0079 4123 4567 8901 85") is False


def test_check_consistency_iban_invalid_checksum():
    """Test avec un IBAN de longueur correcte mais checksum invalide."""
    # Format correct mais checksum incorrect
    invalid_iban = "FR7630001007941234567890186"  # Dernier chiffre modifié
    assert check_consistency_iban(invalid_iban) is False


def test_check_consistency_iban_lowercase():
    """Test avec un IBAN en minuscules (doit être converti en majuscules)."""
    # La fonction convertit en majuscules, donc un IBAN valide en minuscules devrait fonctionner
    # Mais le checksum doit être correct
    lowercase_iban = "fr7630001007941234567890185"
    assert check_consistency_iban(lowercase_iban) is True
