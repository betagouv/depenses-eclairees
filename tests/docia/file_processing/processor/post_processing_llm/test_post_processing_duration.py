import pytest

from docia.file_processing.processor.post_processing_llm import post_processing_duration


def test_post_processing_duration_valid():
    """Test avec une durée valide."""
    duration = {"duree_initiale": 12, "duree_reconduction": 6, "nb_reconductions": 2, "delai_tranche_optionnelle": 0}
    result = post_processing_duration(duration)
    assert result == duration


def test_post_processing_duration_with_string_numbers():
    """Test avec des nombres en string (doivent être convertis en int)."""
    duration = {
        "duree_initiale": "12",
        "duree_reconduction": "6",
        "nb_reconductions": "2",
        "delai_tranche_optionnelle": "0",
    }
    result = post_processing_duration(duration)
    assert result["duree_initiale"] == 12
    assert result["duree_reconduction"] == 6
    assert result["nb_reconductions"] == 2
    assert result["delai_tranche_optionnelle"] == 0


def test_post_processing_duration_with_none():
    """Test avec des valeurs None."""
    duration = {
        "duree_initiale": None,
        "duree_reconduction": 6,
        "nb_reconductions": None,
        "delai_tranche_optionnelle": 0,
    }
    result = post_processing_duration(duration)
    assert result == duration


def test_post_processing_duration_all_none():
    """Test avec tous les champs à None (doit retourner None)."""
    duration = {
        "duree_initiale": None,
        "duree_reconduction": None,
        "nb_reconductions": None,
        "delai_tranche_optionnelle": None,
    }
    assert post_processing_duration(duration) is None


def test_post_processing_duration_all_zero():
    """Test avec tous les champs à 0 (doit retourner None)."""
    duration = {"duree_initiale": 0, "duree_reconduction": 0, "nb_reconductions": 0, "delai_tranche_optionnelle": 0}
    assert post_processing_duration(duration) is None


def test_post_processing_duration_mixed_none_and_zero():
    """Test avec mélange de None et 0 (doit retourner None)."""
    duration = {
        "duree_initiale": None,
        "duree_reconduction": 0,
        "nb_reconductions": None,
        "delai_tranche_optionnelle": 0,
    }
    assert post_processing_duration(duration) is None


def test_post_processing_duration_empty():
    """Test avec dictionnaire vide."""
    assert post_processing_duration({}) is None
    assert post_processing_duration(None) is None


def test_post_processing_duration_invalid_type():
    """Test avec type invalide (doit lever une erreur)."""
    duration = {
        "duree_initiale": "abc",  # Pas un entier
        "duree_reconduction": 6,
        "nb_reconductions": 2,
        "delai_tranche_optionnelle": 0,
    }
    with pytest.raises(ValueError, match="n'est pas un entier ou None"):
        post_processing_duration(duration)


def test_post_processing_duration_missing_fields():
    """Test avec champs manquants (doit lever une erreur listant les champs manquants)."""
    duration = {
        "duree_initiale": 12
        # Manque les autres champs
    }
    with pytest.raises(ValueError, match="sont manquants") as excinfo:
        post_processing_duration(duration)
    # On vérifie que le message contient tous les champs manquants
    error_message = str(excinfo.value)
    for field in ["duree_reconduction", "nb_reconductions", "delai_tranche_optionnelle"]:
        assert field in error_message


def test_post_processing_duration_float_string():
    """Test avec string contenant un float (doit lever une erreur)."""
    duration = {
        "duree_initiale": "12.5",  # Float en string
        "duree_reconduction": 6,
        "nb_reconductions": 2,
        "delai_tranche_optionnelle": 0,
    }
    with pytest.raises(ValueError, match="n'est pas un entier ou None"):
        post_processing_duration(duration)
