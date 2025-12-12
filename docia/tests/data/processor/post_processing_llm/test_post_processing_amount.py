from app.processor.post_processing_llm import post_processing_amount


def test_post_processing_amount_with_euro_symbol():
    """Test avec symbole euro."""
    assert post_processing_amount("1234.56€") == "1234.56"
    assert post_processing_amount("1 234,56 €") == "1234.56"


def test_post_processing_amount_with_comma():
    """Test avec virgule comme séparateur décimal."""
    assert post_processing_amount("200,00") == "200.00"
    assert post_processing_amount("2300,5€") == "2300.50"


def test_post_processing_amount_with_dot():
    """Test avec point comme séparateur décimal."""
    assert post_processing_amount("85.00") == "85.00"
    assert post_processing_amount("1234.56") == "1234.56"


def test_post_processing_amount_without_decimal():
    """Test sans partie décimale."""
    assert post_processing_amount("2400") == "2400.00"
    assert post_processing_amount("1200€") == "1200.00"


def test_post_processing_amount_with_spaces():
    """Test avec espaces."""
    assert post_processing_amount("2 400,50") == "2400.50"
    assert post_processing_amount("1 234 567,89") == "1234567.89"


def test_post_processing_amount_empty():
    """Test avec chaîne vide."""
    assert post_processing_amount("") is None
    assert post_processing_amount("   ") is None


def test_post_processing_amount_no_number():
    """Test sans nombre."""
    assert post_processing_amount("abc") is None
    assert post_processing_amount("€") is None
    assert post_processing_amount("montant:") is None


def test_post_processing_amount_not_string():
    """Test avec un type non-string (doit être converti)."""
    assert post_processing_amount(1234.56) == "1234.56"
    assert post_processing_amount(200) == "200.00"
    assert post_processing_amount(85.5) == "85.50"
