from docia.file_processing.processor.post_processing_llm import post_processing_percentage


def test_post_processing_percentage_with_percent_symbol():
    """Test avec symbole pourcentage."""
    assert post_processing_percentage("20%") == "20.00"
    assert post_processing_percentage("5.5%") == "5.50"
    assert post_processing_percentage("100%") == "100.00"


def test_post_processing_percentage_with_comma():
    """Test avec virgule comme séparateur décimal."""
    assert post_processing_percentage("20,5%") == "20.50"
    assert post_processing_percentage("15,75") == "15.75"
    assert post_processing_percentage("0,5%") == "0.50"


def test_post_processing_percentage_with_dot():
    """Test avec point comme séparateur décimal."""
    assert post_processing_percentage("20.5%") == "20.50"
    assert post_processing_percentage("15.75") == "15.75"
    assert post_processing_percentage("0.5%") == "0.50"


def test_post_processing_percentage_without_decimal():
    """Test sans partie décimale."""
    assert post_processing_percentage("20") == "20.00"
    assert post_processing_percentage("100%") == "100.00"
    assert post_processing_percentage("0") == "0.00"


def test_post_processing_percentage_with_spaces():
    """Test avec espaces."""
    assert post_processing_percentage("20 %") == "20.00"
    assert post_processing_percentage("15,5 %") == "15.50"
    assert post_processing_percentage(" 10.5% ") == "10.50"


def test_post_processing_percentage_empty():
    """Test avec chaîne vide."""
    assert post_processing_percentage("") is None
    assert post_processing_percentage("   ") is None


def test_post_processing_percentage_no_number():
    """Test sans nombre."""
    assert post_processing_percentage("abc") is None
    assert post_processing_percentage("%") is None
    assert post_processing_percentage("pourcentage:") is None
    assert post_processing_percentage("text only") is None


def test_post_processing_percentage_not_string():
    """Test avec un type non-string (doit être converti)."""
    assert post_processing_percentage(20) == "20.00"
    assert post_processing_percentage(15.5) == "15.50"
    assert post_processing_percentage(0.5) == "0.50"
    assert post_processing_percentage(100) == "100.00"


def test_post_processing_percentage_with_text():
    """Test avec du texte autour du nombre."""
    assert post_processing_percentage("TVA 20%") == "20.00"
    assert post_processing_percentage("Réduction de 15,5%") == "15.50"
    assert post_processing_percentage("Le taux est de 10.5%") == "10.50"
    assert post_processing_percentage("20% de remise") == "20.00"
