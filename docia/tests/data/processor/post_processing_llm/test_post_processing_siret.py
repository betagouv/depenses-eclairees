from app.processor.post_processing_llm import post_processing_siret


def test_post_processing_siret_valid():
    """Test avec un SIRET valide."""
    siret = "12345678901234"
    assert post_processing_siret(siret) == "12345678901234"


def test_post_processing_siret_with_spaces():
    """Test avec un SIRET contenant des espaces."""
    siret = "1234 5678 9012 34"
    assert post_processing_siret(siret) == "12345678901234"


def test_post_processing_siret_with_non_breaking_spaces():
    """Test avec des espaces insécables."""
    siret = "1234\xa05678\u202f901234"
    assert post_processing_siret(siret) == "12345678901234"


def test_post_processing_siret_float_format():
    """Test avec un SIRET au format float (ex: "12345678901234.0")."""
    siret = "12345678901234.0"
    assert post_processing_siret(siret) == "12345678901234"

    siret = "12345678901234.00"
    assert post_processing_siret(siret) == "12345678901234"


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
