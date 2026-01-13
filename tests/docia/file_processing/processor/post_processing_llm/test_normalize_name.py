from docia.file_processing.processor.post_processing_llm import normalize_name


def test_normalize_name_simple():
    """Test avec une ville simple."""
    assert normalize_name("paris") == "Paris"
    assert normalize_name("LYON") == "Lyon"
    assert normalize_name("Marseille") == "Marseille"


def test_normalize_name_with_dash():
    """Test avec tiret (cas comme Saint-Étienne)."""
    assert normalize_name("saint-etienne") == "Saint-Etienne"
    assert normalize_name("SAINT-ETIENNE") == "Saint-Etienne"
    assert normalize_name("le-havre") == "Le-Havre"


def test_normalize_name_multiple_dashes():
    """Test avec plusieurs tirets."""
    assert normalize_name("saint-jean-de-luz") == "Saint-Jean-De-Luz"


def test_normalize_name_with_spaces():
    """Test avec espaces (normalisés par normalize_text)."""
    assert normalize_name("  paris  ") == "Paris"
    assert normalize_name("saint  etienne") == "Saint Etienne"


def test_normalize_name_empty():
    """Test avec chaîne vide."""
    assert normalize_name("") == ""
    assert normalize_name("   ") == ""


def test_normalize_name_single_letter():
    """Test avec une seule lettre."""
    assert normalize_name("a") == "A"
    assert normalize_name("A") == "A"


def test_normalize_name_special_cases():
    """Test avec des cas spéciaux (Le, La, etc.)."""
    assert normalize_name("le mans") == "Le Mans"
    assert normalize_name("la rochelle") == "La Rochelle"
    assert normalize_name("les sables d'olonne") == "Les Sables D'olonne"
