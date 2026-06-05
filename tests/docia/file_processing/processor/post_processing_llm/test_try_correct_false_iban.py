from docia.file_processing.processor.post_processing_llm import try_correct_false_iban


def test_try_correct_false_iban_substitution_french():
    """Corrige un IBAN français invalide par substitution d'un caractère."""
    valid_iban = "FR1420041010050500013M02606"
    wrong_iban = "FR1420041010050500013M02607"
    assert try_correct_false_iban(wrong_iban) == valid_iban


def test_try_correct_false_iban_substitution_foreign():
    """Corrige un IBAN étranger invalide par substitution d'un caractère."""
    valid_iban = "BE68539007547034"
    wrong_iban = "BE68539007547030"
    assert try_correct_false_iban(wrong_iban) == valid_iban


def test_try_correct_false_iban_removal_foreign():
    """Corrige un IBAN étranger avec un caractère en trop par retrait."""
    valid_iban = "BE68539007547034"
    wrong_iban = "BE685390075470034"
    assert try_correct_false_iban(wrong_iban) == valid_iban


def test_try_correct_false_iban_ambiguous_foreign_returns_none():
    """Ne corrige pas si plusieurs corrections possibles."""
    ambiguous_iban = "DE89370400440532013001"
    assert try_correct_false_iban(ambiguous_iban) is None


def test_try_correct_false_iban_french_wrong_length_returns_none():
    """Un IBAN français de longueur incorrecte n'est pas corrigé."""
    assert try_correct_false_iban("FR14") is None
    assert try_correct_false_iban("FR1420041010050500013M02606123") is None


def test_try_correct_false_iban_empty_returns_none():
    """Une chaîne vide n'est pas corrigée."""
    assert try_correct_false_iban("") is None
    assert try_correct_false_iban(None) is None
