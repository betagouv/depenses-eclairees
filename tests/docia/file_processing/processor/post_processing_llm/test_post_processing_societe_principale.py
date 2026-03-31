from docia.file_processing.processor.post_processing_llm import post_processing_societe_principale


def test_post_processing_societe_principale_none_et_vide():
    assert post_processing_societe_principale(None) is None
    assert post_processing_societe_principale("") is None
    assert post_processing_societe_principale("   ") is None


def test_post_processing_societe_principale_retire_suffixes_juridiques():
    assert post_processing_societe_principale("Société DEMO SARL") == "DEMO"
    assert post_processing_societe_principale("SASU ACME INDUSTRIE SASU") == "ACME INDUSTRIE"


def test_post_processing_societe_principale_forme_abregee_points():
    assert post_processing_societe_principale("S.A.S.U. ACME") == "ACME"


def test_post_processing_societe_principale_conserve_la_poste():
    assert post_processing_societe_principale("La Poste SA") == "La Poste"


def test_post_processing_societe_principale_retire_parentheses():
    assert post_processing_societe_principale("Société CHOSE (MDC) SARL") == "CHOSE"
    assert post_processing_societe_principale("Société ACME (holding) SARL") == "ACME"


def test_post_processing_societe_principale_coerce_non_str():
    assert post_processing_societe_principale(123) == "123"
