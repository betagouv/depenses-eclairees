import pytest

from app.processor.post_processing_llm import post_processing_other_bank_accounts


def test_post_processing_other_bank_accounts_valid():
    """Test avec une liste valide de comptes bancaires."""
    other_accounts = [
        {"societe": "Entreprise A", "rib": {"banque": "Crédit Agricole", "iban": "FR1420041010050500013M02606"}},
        {
            "societe": "Entreprise B",
            "rib": {
                "banque": "BNP Paribas",
                "code_banque": "20041",
                "code_guichet": "01005",
                "numero_compte": "0500013M026",
                "cle_rib": "06",
            },
        },
    ]
    result = post_processing_other_bank_accounts(other_accounts)
    assert len(result) == 2
    assert result[0]["societe"] == "Entreprise A"
    assert "iban" in result[0]["rib"]
    assert result[1]["societe"] == "Entreprise B"


def test_post_processing_other_bank_accounts_empty_list():
    """Test avec liste vide."""
    assert post_processing_other_bank_accounts([]) is None
    assert post_processing_other_bank_accounts(None) is None


def test_post_processing_other_bank_accounts_empty_rib():
    """Test avec RIB vide (doit être exclu)."""
    other_accounts = [
        {"societe": "Entreprise A", "rib": {}},
        {"societe": "Entreprise B", "rib": {"banque": "BNP Paribas", "iban": "FR1420041010050500013M02606"}},
    ]
    result = post_processing_other_bank_accounts(other_accounts)
    assert len(result) == 1
    assert result[0]["societe"] == "Entreprise B"


def test_post_processing_other_bank_accounts_invalid_iban():
    """Test avec IBAN invalide (doit être inclus si banque présente)."""
    other_accounts = [
        {
            "societe": "Entreprise A",
            "rib": {
                "banque": "Crédit Agricole",
                "iban": "FR1420041010050500013M02607",  # IBAN invalide
            },
        }
    ]
    result = post_processing_other_bank_accounts(other_accounts)
    assert len(result) == 1
    assert result[0]["rib"]["iban"] is None
    assert result[0]["rib"]["banque"] == "Crédit Agricole"


def test_post_processing_other_bank_accounts_no_iban_no_banque():
    """Test sans IBAN ni banque (doit être exclu)."""
    other_accounts = [{"societe": "Entreprise A", "rib": {"banque": "", "iban": ""}}]
    assert post_processing_other_bank_accounts(other_accounts) is None


def test_post_processing_other_bank_accounts_only_banque():
    """Test avec seulement banque (sans IBAN valide)."""
    other_accounts = [
        {
            "societe": "Entreprise A",
            "rib": {
                "banque": "Crédit Agricole",
                "iban": "",  # Pas d'IBAN
            },
        }
    ]
    result = post_processing_other_bank_accounts(other_accounts)
    assert result[0]["societe"] == "Entreprise A"
    assert result[0]["rib"] == {"banque": "Crédit Agricole", "iban": None}


def test_post_processing_other_bank_accounts_missing_societe():
    """Test avec société manquante (doit quand même fonctionner)."""
    other_accounts = [{"societe": "", "rib": {"banque": "Crédit Agricole", "iban": "FR1420041010050500013M02606"}}]
    result = post_processing_other_bank_accounts(other_accounts)
    assert len(result) == 1
    assert result[0]["societe"] == ""


def test_post_processing_other_bank_accounts_all_invalid():
    """Test avec tous les comptes invalides."""
    other_accounts = [
        {"societe": "Entreprise A", "rib": {"banque": "", "iban": ""}},
        {"societe": "Entreprise B", "rib": {}},
    ]
    assert post_processing_other_bank_accounts(other_accounts) is None


def test_post_processing_other_bank_accounts_missing_rib_key():
    """Test avec clé 'rib' manquante (doit lever KeyError dans post_processing_bank_account)."""
    other_accounts = [
        {
            "societe": "Entreprise A"
            # Pas de clé 'rib'
        }
    ]
    # post_processing_other_bank_accounts utilise .get('rib', {}) donc ne lève pas d'erreur
    # Mais post_processing_bank_account({}) retourne None, donc le compte sera exclu
    result = post_processing_other_bank_accounts(other_accounts)
    assert result is None


def test_post_processing_other_bank_accounts_missing_societe_key():
    """Test avec clé 'societe' manquante (doit fonctionner car utilise .get())."""
    other_accounts = [
        {
            "rib": {"banque": "Crédit Agricole", "iban": "FR1420041010050500013M02606"}
            # Pas de clé 'societe'
        }
    ]
    result = post_processing_other_bank_accounts(other_accounts)
    assert len(result) == 1
    assert result[0]["societe"] == ""  # .get('societe', '') retourne ''


def test_post_processing_other_bank_accounts_rib_missing_banque():
    """Test avec RIB sans clé 'banque' (doit lever ValueError)."""
    other_accounts = [
        {
            "societe": "Entreprise A",
            "rib": {
                "iban": "FR1420041010050500013M02606"
                # Pas de clé 'banque'
            },
        }
    ]
    with pytest.raises(ValueError, match="doit contenir la clé 'banque'"):
        post_processing_other_bank_accounts(other_accounts)


def test_post_processing_other_bank_accounts_rib_wrong_keys():
    """Test avec RIB ayant de mauvaises clés (doit lever ValueError)."""
    other_accounts = [
        {
            "societe": "Entreprise A",
            "rib": {
                "bank_name": "Crédit Agricole",  # Mauvaise clé
                "account_number": "FR1420041010050500013M02606",  # Mauvaise clé
            },
        }
    ]
    with pytest.raises(ValueError):
        post_processing_other_bank_accounts(other_accounts)


print(0)
