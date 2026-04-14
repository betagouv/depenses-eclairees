import pytest

from docia.file_processing.processor.post_processing_llm import post_processing_subcontractors


def test_post_processing_subcontractors_valid():
    """Test avec une liste valide de sous-traitants."""
    subcontractors = [
        {"nom": "Sous-traitant A", "siret": "73282932000074"},
        {"nom": "Sous-traitant B", "siret": "44306184100047"},
    ]
    result = post_processing_subcontractors(subcontractors)
    assert len(result) == 2
    assert result[0] == {"nom": "Sous-traitant A", "siret": "73282932000074"}
    assert result[1] == {"nom": "Sous-traitant B", "siret": "44306184100047"}


def test_post_processing_subcontractors_with_spaces_in_siret():
    """Test avec SIRET contenant des espaces."""
    subcontractors = [{"nom": "Sous-traitant A", "siret": "7328 2932 0000 74"}]
    result = post_processing_subcontractors(subcontractors)
    assert result[0] == {"nom": "Sous-traitant A", "siret": "73282932000074"}


def test_post_processing_subcontractors_empty_list():
    """Test avec liste vide."""
    assert post_processing_subcontractors([]) is None
    assert post_processing_subcontractors(None) is None


def test_post_processing_subcontractors_empty_nom():
    """Test avec nom vide (doit être exclu)."""
    subcontractors = [{"nom": "", "siret": "73282932000074"}, {"nom": "Sous-traitant B", "siret": "44306184100047"}]
    result = post_processing_subcontractors(subcontractors)
    assert len(result) == 1
    assert result[0] == {"nom": "Sous-traitant B", "siret": "44306184100047"}


def test_post_processing_subcontractors_invalid_siret():
    """Test avec SIRET invalide (doit être exclu)."""
    subcontractors = [
        {"nom": "Sous-traitant A", "siret": "123"},  # SIRET invalide
        {"nom": "Sous-traitant B", "siret": "44306184100047"},
    ]
    result = post_processing_subcontractors(subcontractors)
    assert len(result) == 1
    assert result[0] == {"nom": "Sous-traitant B", "siret": "44306184100047"}


def test_post_processing_subcontractors_empty_siret():
    """Test avec SIRET vide (doit être exclu)."""
    subcontractors = [{"nom": "Sous-traitant A", "siret": ""}, {"nom": "Sous-traitant B", "siret": "44306184100047"}]
    result = post_processing_subcontractors(subcontractors)
    assert len(result) == 1
    assert result[0] == {"nom": "Sous-traitant B", "siret": "44306184100047"}


def test_post_processing_subcontractors_all_invalid():
    """Test avec tous les sous-traitants invalides."""
    subcontractors = [{"nom": "", "siret": "73282932000074"}, {"nom": "Sous-traitant B", "siret": ""}]
    assert post_processing_subcontractors(subcontractors) is None


def test_post_processing_subcontractors_siret_float_format():
    """Test avec SIRET au format float."""
    subcontractors = [{"nom": "Sous-traitant A", "siret": "73282932000074.0"}]
    result = post_processing_subcontractors(subcontractors)
    assert result[0] == {"nom": "Sous-traitant A", "siret": "73282932000074"}


def test_post_processing_subcontractors_missing_siret_key():
    """Test avec clé 'siret' manquante (doit lever KeyError)."""
    subcontractors = [
        {"nom": "Sous-traitant A"}  # Pas de clé 'siret'
    ]
    with pytest.raises(KeyError):
        post_processing_subcontractors(subcontractors)


def test_post_processing_subcontractors_missing_nom_key():
    """Test avec clé 'nom' manquante (doit lever KeyError)."""
    subcontractors = [
        {"siret": "73282932000074"}  # Pas de clé 'nom'
    ]
    with pytest.raises(KeyError):
        post_processing_subcontractors(subcontractors)


def test_post_processing_subcontractors_wrong_keys():
    """Test avec de mauvaises clés (doit lever KeyError)."""
    subcontractors = [
        {"name": "Sous-traitant A", "siret_number": "73282932000074"}  # Mauvaises clés
    ]
    with pytest.raises(KeyError):
        post_processing_subcontractors(subcontractors)
