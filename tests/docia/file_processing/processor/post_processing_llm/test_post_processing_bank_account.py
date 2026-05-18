from docia.file_processing.processor.post_processing_llm import post_processing_bank_account


def test_post_processing_bank_account_with_iban():
    """Test avec IBAN présent."""
    bank_account = {"banque": "Crédit Agricole", "iban": "FR76 30001 0079 4123 4567 8901 85"}
    result = post_processing_bank_account(bank_account)
    assert result == {"banque": "Crédit Agricole", "iban": "FR7630001007941234567890185"}


def test_post_processing_bank_account_with_rib_fields():
    """Test avec les 4 champs RIB (code_banque, code_guichet, numero_compte, cle_rib)."""
    bank_account = {
        "banque": "Banque de France",
        "code_banque": "30001",
        "code_guichet": "00794",
        "numero_compte": "12345678901",
        "cle_rib": "85",
    }
    result = post_processing_bank_account(bank_account)
    assert result["banque"] == "Banque de France"
    assert result["iban"].startswith("FR76")
    assert len(result["iban"]) == 27
    assert result["iban"].endswith("85")


def test_post_processing_bank_account_empty():
    """Test avec dictionnaire vide."""
    assert post_processing_bank_account({}) is None
    assert post_processing_bank_account(None) is None


def test_post_processing_bank_account_missing_banque():
    """Test sans clé 'banque' : l'IBAN valide est conservé."""
    bank_account = {"iban": "FR7630001007941234567890185"}
    result = post_processing_bank_account(bank_account)
    assert result == {"banque": None, "iban": "FR7630001007941234567890185"}


def test_post_processing_bank_account_no_iban_no_rib():
    """Test avec banque seule, sans IBAN ni composants RIB exploitables."""
    bank_account = {"banque": "Crédit Agricole"}
    assert post_processing_bank_account(bank_account) is None


def test_post_processing_bank_account_incomplete_rib():
    """Test avec seulement quelques champs RIB : pas assez pour reconstruire l'IBAN."""
    bank_account = {
        "banque": "Banque de France",
        "code_banque": "30001",
        "code_guichet": "00794",
    }
    assert post_processing_bank_account(bank_account) is None


def test_post_processing_bank_account_invalid_iban():
    """Test avec IBAN invalide non corrigeable : conserve la banque, IBAN à null."""
    bank_account = {
        "banque": "Crédit Agricole",
        "iban": "FR7630001007941234567890186",  # Checksum incorrect (dernier chiffre modifié)
    }
    result = post_processing_bank_account(bank_account)
    assert result == {"banque": "Crédit Agricole", "iban": None}


def test_post_processing_bank_account_empty_iban_and_banque():
    """Test avec IBAN et banque vides."""
    bank_account = {"banque": "", "iban": ""}
    assert post_processing_bank_account(bank_account) is None


def test_post_processing_bank_account_iban_with_spaces():
    """Test avec IBAN contenant des espaces."""
    bank_account = {"banque": "Crédit Agricole", "iban": "FR76 30001 0079 4123 4567 8901 85"}
    result = post_processing_bank_account(bank_account)
    assert result["iban"] == "FR7630001007941234567890185"


def test_post_processing_bank_account_rib_fields_with_none():
    """Test avec les 4 champs RIB à null : aucun composant exploitable."""
    bank_account = {
        "banque": "Banque de France",
        "code_banque": None,
        "code_guichet": None,
        "numero_compte": None,
        "cle_rib": None,
    }
    assert post_processing_bank_account(bank_account) is None


def test_post_processing_bank_account_rib_fields_with_empty_strings():
    """Test avec les 4 champs RIB vides : aucun composant exploitable."""
    bank_account = {
        "banque": "Banque de France",
        "code_banque": "",
        "code_guichet": "",
        "numero_compte": "",
        "cle_rib": "",
    }
    assert post_processing_bank_account(bank_account) is None


def test_post_processing_bank_account_rib_fields_wrong_check_digit():
    """Test avec clé RIB incohérente : l'IBAN généré est rejeté, la banque est conservée."""
    bank_account = {
        "banque": "Banque de France",
        "code_banque": "30001",
        "code_guichet": "00794",
        "numero_compte": "12345678901",
        "cle_rib": "99",
    }
    result = post_processing_bank_account(bank_account)
    assert result == {"banque": "Banque de France", "iban": None}


def test_post_processing_bank_account_numero_compte_only():
    """Test avec seulement un numéro de compte à 11 chiffres."""
    bank_account = {
        "banque": "Crédit Agricole",
        "numero_compte": "12345678901",
    }
    result = post_processing_bank_account(bank_account)
    assert result == {
        "banque": "Crédit Agricole",
        "iban": "XXXXXXXXXXXXXX12345678901XX",
    }


def test_post_processing_bank_account_numero_compte_wrong_length():
    """Test avec numéro de compte trop court : pas de reconstruction partielle."""
    bank_account = {
        "banque": "Crédit Agricole",
        "numero_compte": "1234567890",
    }
    assert post_processing_bank_account(bank_account) is None
