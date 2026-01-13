import pytest

from docia.file_processing.processor.post_processing_llm import post_processing_postal_address


def test_post_processing_postal_address_valid():
    """Test avec une adresse valide complète."""
    address = {
        "numero_voie": "123",
        "nom_voie": "rue de la paix",
        "complement_adresse": "bâtiment A",
        "code_postal": "75001",
        "ville": "paris",
        "pays": "france",
    }
    result = post_processing_postal_address(address)
    assert result["numero_voie"] == "123"
    assert result["nom_voie"] == "rue de la paix"
    assert result["complement_adresse"] == "bâtiment A"
    assert result["code_postal"] == "75001"
    assert result["ville"] == "Paris"
    assert result["pays"] == "France"


def test_post_processing_postal_address_empty():
    """Test avec dictionnaire vide."""
    assert post_processing_postal_address({}) is None
    assert post_processing_postal_address(None) is None


def test_post_processing_postal_address_all_empty_fields():
    """Test avec tous les champs importants vides (doit retourner None)."""
    address = {"numero_voie": "", "nom_voie": "", "complement_adresse": "", "code_postal": "", "ville": "", "pays": ""}
    assert post_processing_postal_address(address) is None


def test_post_processing_postal_address_code_postal_with_spaces():
    """Test avec code postal contenant des espaces."""
    address = {
        "numero_voie": "123",
        "nom_voie": "rue de la paix",
        "code_postal": "75 001",
        "ville": "paris",
        "pays": "france",
    }
    result = post_processing_postal_address(address)
    assert result["code_postal"] == "75001"


def test_post_processing_postal_address_code_postal_invalid():
    """Test avec code postal invalide."""
    address = {
        "numero_voie": "123",
        "nom_voie": "rue de la paix",
        "code_postal": "1234",  # Trop court
        "ville": "paris",
        "pays": "france",
    }
    result = post_processing_postal_address(address)
    assert result["code_postal"] is None  # Doit être vidé


def test_post_processing_postal_address_code_postal_with_letters():
    """Test avec code postal contenant des lettres."""
    address = {
        "numero_voie": "123",
        "nom_voie": "rue de la paix",
        "code_postal": "7500A",  # Contient une lettre
        "ville": "paris",
        "pays": "france",
    }
    result = post_processing_postal_address(address)
    assert result["code_postal"] is None  # Doit être vidé


def test_post_processing_postal_address_pays_default_france():
    """Test avec pays vide mais code postal français."""
    address = {"numero_voie": "123", "nom_voie": "rue de la paix", "code_postal": "75001", "ville": "paris", "pays": ""}
    result = post_processing_postal_address(address)
    assert result["pays"] == "France"


def test_post_processing_postal_address_pays_fr():
    """Test avec pays 'fr' ou 'FR'."""
    address = {
        "numero_voie": "123",
        "nom_voie": "rue de la paix",
        "code_postal": "75001",
        "ville": "paris",
        "pays": "fr",
    }
    result = post_processing_postal_address(address)
    assert result["pays"] == "France"


def test_post_processing_postal_address_pays_other():
    """Test avec un autre pays."""
    address = {
        "numero_voie": "123",
        "nom_voie": "rue de la paix",
        "code_postal": "75001",
        "ville": "paris",
        "pays": "belgique",
    }
    result = post_processing_postal_address(address)
    assert result["pays"] == "Belgique"


def test_post_processing_postal_address_ville_normalization():
    """Test de normalisation de la ville."""
    address = {
        "numero_voie": "123",
        "nom_voie": "rue de la paix",
        "code_postal": "75001",
        "ville": "SAINT-ETIENNE",
        "pays": "france",
    }
    result = post_processing_postal_address(address)
    assert result["ville"] == "Saint-Etienne"


def test_post_processing_postal_address_spaces_normalization():
    """Test de normalisation des espaces."""
    address = {
        "numero_voie": "  123  ",
        "nom_voie": "rue    de   la   paix",
        "code_postal": "75001",
        "ville": "  paris  ",
        "pays": "france",
    }
    result = post_processing_postal_address(address)
    assert result["numero_voie"] == "123"
    assert result["nom_voie"] == "rue de la paix"
    assert result["ville"] == "Paris"


def test_post_processing_postal_address_missing_required_fields():
    """Test avec champs requis manquants (doit lever une erreur)."""
    # Test avec numero_voie manquant
    address = {"nom_voie": "rue de la paix", "code_postal": "75001", "ville": "paris"}
    with pytest.raises(ValueError, match="sont manquants") as excinfo:
        post_processing_postal_address(address)
    assert "numero_voie" in str(excinfo.value)

    # Test avec plusieurs champs manquants
    address = {
        "nom_voie": "rue de la paix"
        # Manque numero_voie, code_postal, ville
    }
    with pytest.raises(ValueError, match="sont manquants") as excinfo:
        post_processing_postal_address(address)
    error_message = str(excinfo.value)
    assert "numero_voie" in error_message
    assert "code_postal" in error_message
    assert "ville" in error_message


def test_post_processing_postal_address_missing_optional_fields():
    """Test avec champs optionnels manquants (doit fonctionner)."""
    address = {
        "numero_voie": "123",
        "nom_voie": "rue de la paix",
        "code_postal": "75001",
        "ville": "paris",
        # Pas de complement_adresse ni pays (optionnels)
    }
    result = post_processing_postal_address(address)
    assert result["complement_adresse"] == ""
    assert result["pays"] == "France"  # Défaut si code postal français


def test_post_processing_postal_address_wrong_keys():
    """Test avec de mauvaises clés (doit lever une erreur)."""
    address = {
        "street_number": "123",  # Mauvaise clé
        "street_name": "rue de la paix",  # Mauvaise clé
        "postal_code": "75001",  # Mauvaise clé
        "city": "paris",  # Mauvaise clé
    }
    with pytest.raises(ValueError, match="sont manquants"):
        post_processing_postal_address(address)


def test_post_processing_postal_address_minimal_valid():
    """Test avec minimum requis pour être valide."""
    address = {"numero_voie": "123", "nom_voie": "rue de la paix", "code_postal": "75001", "ville": "paris"}
    result = post_processing_postal_address(address)
    assert result is not None
    assert result["numero_voie"] == "123"
    assert result["nom_voie"] == "rue de la paix"
