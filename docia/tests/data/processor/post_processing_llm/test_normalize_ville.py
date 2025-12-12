import pytest

from app.processor.post_processing_llm import normalize_ville


def test_normalize_ville_simple():
    """Test avec une ville simple."""
    assert normalize_ville("paris") == "Paris"
    assert normalize_ville("LYON") == "Lyon"
    assert normalize_ville("Marseille") == "Marseille"


def test_normalize_ville_with_dash():
    """Test avec tiret (cas comme Saint-Étienne)."""
    assert normalize_ville("saint-etienne") == "Saint-Etienne"
    assert normalize_ville("SAINT-ETIENNE") == "Saint-Etienne"
    assert normalize_ville("le-havre") == "Le-Havre"


def test_normalize_ville_multiple_dashes():
    """Test avec plusieurs tirets."""
    assert normalize_ville("saint-jean-de-luz") == "Saint-Jean-De-Luz"


def test_normalize_ville_with_spaces():
    """Test avec espaces (normalisés par normalize_text)."""
    assert normalize_ville("  paris  ") == "Paris"
    assert normalize_ville("saint  etienne") == "Saint Etienne"


def test_normalize_ville_empty():
    """Test avec chaîne vide."""
    assert normalize_ville("") == ""
    assert normalize_ville("   ") == ""


def test_normalize_ville_single_letter():
    """Test avec une seule lettre."""
    assert normalize_ville("a") == "A"
    assert normalize_ville("A") == "A"


def test_normalize_ville_special_cases():
    """Test avec des cas spéciaux (Le, La, etc.)."""
    assert normalize_ville("le mans") == "Le Mans"
    assert normalize_ville("la rochelle") == "La Rochelle"
    assert normalize_ville("les sables d'olonne") == "Les Sables D'olonne"
