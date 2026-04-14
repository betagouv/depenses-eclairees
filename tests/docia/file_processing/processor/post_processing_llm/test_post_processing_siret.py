from docia.file_processing.processor.post_processing_llm import post_processing_siret

# SIRET fictifs avec clé Luhn valide (INSEE).
_SIRET_LUHN_OK = "73282932000074"


def test_post_processing_siret_valid():
    """Test avec un SIRET valide (Luhn)."""
    assert post_processing_siret(_SIRET_LUHN_OK) == _SIRET_LUHN_OK


def test_post_processing_siret_with_spaces():
    """Test avec un SIRET contenant des espaces."""
    siret = "7328 2932 0000 74"
    assert post_processing_siret(siret) == _SIRET_LUHN_OK


def test_post_processing_siret_with_non_breaking_spaces():
    """Test avec des espaces insécables."""
    siret = "7328\xa02932\u202f000074"
    assert post_processing_siret(siret) == _SIRET_LUHN_OK


def test_post_processing_siret_float_format():
    """Test avec un SIRET au format float (ex: "...0")."""
    siret = f"{_SIRET_LUHN_OK}.0"
    assert post_processing_siret(siret) == _SIRET_LUHN_OK

    siret = f"{_SIRET_LUHN_OK}.00"
    assert post_processing_siret(siret) == _SIRET_LUHN_OK


def test_post_processing_siret_invalid_luhn():
    """14 chiffres mais clé Luhn incorrecte : rejeté."""
    assert post_processing_siret("12345678901234") is None


def test_post_processing_siret_empty():
    """Test avec une chaîne vide ou None."""
    assert post_processing_siret("") is None
    assert post_processing_siret(None) is None


def test_post_processing_siret_wrong_length():
    """Test avec un SIRET de longueur incorrecte."""
    # Trop court
    assert post_processing_siret("1234567890123") is None  # 13 chiffres
    # Trop long
    assert post_processing_siret("123456789012345") is None  # 15 chiffres


def test_post_processing_siret_with_letters():
    """Test avec des lettres dans le SIRET."""
    assert post_processing_siret("1234567890123A") is None
    assert post_processing_siret("ABCD5678901234") is None


def test_post_processing_siret_with_special_characters():
    """Test avec des caractères spéciaux."""
    assert post_processing_siret("1234-5678-9012-34") is None
    assert post_processing_siret("1234.5678.9012.34") is None
