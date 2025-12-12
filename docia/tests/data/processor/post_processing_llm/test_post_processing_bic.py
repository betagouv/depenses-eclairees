from app.processor.post_processing_llm import post_processing_bic


def test_post_processing_bic_valid_8_chars():
    """Test avec un BIC valide de 8 caractères."""
    bic = "BNPAFRPP"
    result = post_processing_bic(bic)
    assert result == "BNPAFRPP"


def test_post_processing_bic_valid_11_chars():
    """Test avec un BIC valide de 11 caractères."""
    bic = "BNPAFRPPXXX"
    result = post_processing_bic(bic)
    assert result == "BNPAFRPPXXX"


def test_post_processing_bic_with_spaces():
    """Test avec espaces dans le BIC."""
    bic = "BNPA FRPP"
    result = post_processing_bic(bic)
    assert result == "BNPAFRPP"


def test_post_processing_bic_lowercase():
    """Test avec BIC en minuscules."""
    bic = "bnpafrpp"
    result = post_processing_bic(bic)
    assert result == "BNPAFRPP"


def test_post_processing_bic_wrong_length():
    """Test avec BIC de longueur incorrecte."""
    assert post_processing_bic("BNPA") is None  # Trop court
    assert post_processing_bic("BNPAFRPPXXXYYY") is None  # Trop long
    assert post_processing_bic("BNPAFRPPX") is None  # 9 caractères


def test_post_processing_bic_empty():
    """Test avec chaîne vide."""
    assert post_processing_bic("") is None
    assert post_processing_bic("   ") is None
