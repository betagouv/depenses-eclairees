import pytest

from app.processor.post_processing_llm import post_processing_co_contractors


def test_post_processing_co_contractors_valid():
    """Test avec une liste valide de cotraitants."""
    co_contractors = [
        {"nom": "Entreprise A", "siret": "12345678901234"},
        {"nom": "Entreprise B", "siret": "98765432109876"},
    ]
    result = post_processing_co_contractors(co_contractors)
    assert len(result) == 2
    assert result[0] == {"nom": "Entreprise A", "siret": "12345678901234"}
    assert result[1] == {"nom": "Entreprise B", "siret": "98765432109876"}


def test_post_processing_co_contractors_with_spaces_in_siret():
    """Test avec SIRET contenant des espaces."""
    co_contractors = [{"nom": "Entreprise A", "siret": "1234 5678 9012 34"}]
    result = post_processing_co_contractors(co_contractors)
    assert result[0]["siret"] == "12345678901234"


def test_post_processing_co_contractors_empty_list():
    """Test avec liste vide."""
    assert post_processing_co_contractors([]) is None
    assert post_processing_co_contractors(None) is None


def test_post_processing_co_contractors_empty_nom():
    """Test avec nom vide (doit être exclu)."""
    co_contractors = [{"nom": "", "siret": "12345678901234"}, {"nom": "Entreprise B", "siret": "98765432109876"}]
    result = post_processing_co_contractors(co_contractors)
    assert len(result) == 1
    assert result[0] == {"nom": "Entreprise B", "siret": "98765432109876"}


def test_post_processing_co_contractors_invalid_siret():
    """Test avec SIRET invalide (doit être exclu)."""
    co_contractors = [
        {"nom": "Entreprise A", "siret": "123"},  # SIRET invalide
        {"nom": "Entreprise B", "siret": "98765432109876"},
    ]
    result = post_processing_co_contractors(co_contractors)
    assert len(result) == 1
    assert result[0] == {"nom": "Entreprise B", "siret": "98765432109876"}


def test_post_processing_co_contractors_empty_siret():
    """Test avec SIRET vide (doit être exclu)."""
    co_contractors = [{"nom": "Entreprise A", "siret": ""}, {"nom": "Entreprise B", "siret": "98765432109876"}]
    result = post_processing_co_contractors(co_contractors)
    assert len(result) == 1
    assert result[0]["nom"] == "Entreprise B"


def test_post_processing_co_contractors_all_invalid():
    """Test avec tous les cotraitants invalides."""
    co_contractors = [{"nom": "", "siret": "12345678901234"}, {"nom": "Entreprise B", "siret": ""}]
    assert post_processing_co_contractors(co_contractors) is None


def test_post_processing_co_contractors_siret_float_format():
    """Test avec SIRET au format float."""
    co_contractors = [{"nom": "Entreprise A", "siret": "12345678901234.0"}]
    result = post_processing_co_contractors(co_contractors)
    assert result[0] == {"nom": "Entreprise A", "siret": "12345678901234"}


def test_post_processing_co_contractors_missing_siret_key():
    """Test avec clé 'siret' manquante (doit lever KeyError)."""
    co_contractors = [
        {"nom": "Entreprise A"}  # Pas de clé 'siret'
    ]
    with pytest.raises(KeyError):
        post_processing_co_contractors(co_contractors)


def test_post_processing_co_contractors_missing_nom_key():
    """Test avec clé 'nom' manquante (doit lever KeyError)."""
    co_contractors = [
        {"siret": "12345678901234"}  # Pas de clé 'nom'
    ]
    with pytest.raises(KeyError):
        post_processing_co_contractors(co_contractors)


def test_post_processing_co_contractors_wrong_keys():
    """Test avec de mauvaises clés (doit lever KeyError)."""
    co_contractors = [
        {"name": "Entreprise A", "siret_number": "12345678901234"}  # Mauvaises clés
    ]
    with pytest.raises(KeyError):
        post_processing_co_contractors(co_contractors)
