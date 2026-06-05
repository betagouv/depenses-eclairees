from docia.file_processing.processor.post_processing_llm import post_processing_iban


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
    invalid_iban = "FR1420041010050500013M02617"  # Checksum incorrect
    assert post_processing_iban(invalid_iban) is None


def test_post_processing_iban_corrects_one_char_error():
    """Test que post_processing_iban peut corriger un IBAN invalide à un caractère près (try_correct_false_iban)."""
    valid_iban = "FR1420041010050500013M02606"
    # Une seule erreur : dernier chiffre 6 -> 7
    wrong_iban = "FR1420041010050500013M02607"
    result = post_processing_iban(wrong_iban)
    assert result == valid_iban


def test_post_processing_iban_wrong_length():
    """Test avec IBAN de longueur incorrecte."""
    assert post_processing_iban("FR14") is None
    assert post_processing_iban("FR1420041010050500013M02606123") is None


def test_post_processing_iban_empty():
    """Test avec chaîne vide."""
    assert post_processing_iban("") is None
    assert post_processing_iban("   ") is None


def test_post_processing_iban_foreign_valid():
    """Test qu'un IBAN étranger valide est conservé."""
    foreign_iban = "DE89370400440532013000"
    result = post_processing_iban(foreign_iban)
    assert result == foreign_iban


def test_post_processing_iban_foreign_with_spaces():
    """Test qu'un IBAN étranger avec espaces est normalisé et conservé."""
    foreign_iban = "DE89 3704 0044 0532 0130 00"
    result = post_processing_iban(foreign_iban)
    assert result == "DE89370400440532013000"


def test_post_processing_iban_foreign_invalid_checksum():
    """Test qu'un IBAN étranger invalide non corrigeable de façon unique est rejeté."""
    invalid_foreign_iban = "DE89370400440532013001"
    assert post_processing_iban(invalid_foreign_iban) is None


def test_post_processing_iban_foreign_corrects_one_char_error():
    """Test qu'un IBAN étranger invalide à un caractère près peut être corrigé."""
    valid_iban = "BE68539007547034"
    wrong_iban = "BE68539007547030"
    result = post_processing_iban(wrong_iban)
    assert result == valid_iban


def test_post_processing_iban_foreign_corrects_extra_char_error():
    """Test qu'un IBAN étranger avec un caractère en trop peut être corrigé par retrait."""
    valid_iban = "BE68539007547034"
    wrong_iban = "BE685390075470034"
    result = post_processing_iban(wrong_iban)
    assert result == valid_iban
