from unittest.mock import patch

import pandas as pd

from docia.file_processing.processor.classifier import (
    DIC_CLASS_FILE_BY_NAME,
    classify_file_with_llm,
    classify_files,
    create_classification_prompt,
)


# --- create_classification_prompt ---


def test_create_classification_prompt_returns_tuple():
    """Retourne (prompt, system_prompt)."""
    list_class = {
        "x": {"nom_complet": "Catégorie X", "description": "Desc X"},
    }
    prompt, system_prompt = create_classification_prompt("f.pdf", "contenu", list_class)
    assert isinstance(prompt, str)
    assert isinstance(system_prompt, str)
    assert "Catégorie X" in prompt
    assert "Desc X" in prompt
    assert "f.pdf" in prompt
    assert "contenu" in prompt


def test_create_classification_prompt_truncates_text_to_2000():
    """Le texte dans le prompt est limité à 2000 caractères."""
    long_text = "a" * 3000
    list_class = {"x": {"nom_complet": "X", "description": ""}}
    prompt, _ = create_classification_prompt("f", long_text, list_class)
    assert "a" * 2000 in prompt
    assert "a" * 2001 not in prompt


def test_create_classification_prompt_category_without_description():
    """Une catégorie sans description n'affiche que le nom_complet."""
    list_class = {"k": {"nom_complet": "Nom seul", "description": ""}}
    prompt, _ = create_classification_prompt("f", "t", list_class)
    assert "'Nom seul'" in prompt


# --- classify_file_with_llm ---


def test_classify_file_with_llm_returns_key_for_known_nom_complet():
    """Quand le LLM retourne un nom_complet connu, on retourne la clé."""
    with patch("docia.file_processing.processor.classifier.LLMClient") as mock_cls:
        mock_cls.return_value.ask_llm.return_value = ["Extrait Kbis"]
        r = classify_file_with_llm("doc.pdf", "Hello World", DIC_CLASS_FILE_BY_NAME)
    assert r == "kbis"


def test_classify_file_with_llm_empty_list_returns_non_clasifie():
    """Réponse vide -> 'Non classifié'."""
    with patch("docia.file_processing.processor.classifier.LLMClient") as mock_cls:
        mock_cls.return_value.ask_llm.return_value = []
        r = classify_file_with_llm("f", "text", DIC_CLASS_FILE_BY_NAME)
    assert r == "Non classifié"


def test_classify_file_with_llm_none_response_returns_non_clasifie():
    """Réponse None -> 'Non classifié'."""
    with patch("docia.file_processing.processor.classifier.LLMClient") as mock_cls:
        mock_cls.return_value.ask_llm.return_value = None
        r = classify_file_with_llm("f", "text", DIC_CLASS_FILE_BY_NAME)
    assert r == "Non classifié"


def test_classify_file_with_llm_unknown_nom_complet_returns_non_clasifie():
    """Réponse avec des libellés inconnus uniquement -> 'Non classifié'."""
    with patch("docia.file_processing.processor.classifier.LLMClient") as mock_cls:
        mock_cls.return_value.ask_llm.return_value = ["Inconnu", "Autre inconnu"]
        r = classify_file_with_llm("f", "text", DIC_CLASS_FILE_BY_NAME)
    assert r == "Non classifié"


def test_classify_file_with_llm_takes_first_matching_category():
    """La première catégorie reconnue dans la liste est retournée."""
    with patch("docia.file_processing.processor.classifier.LLMClient") as mock_cls:
        mock_cls.return_value.ask_llm.return_value = ["Facture", "Extrait Kbis"]
        r = classify_file_with_llm("f", "text", DIC_CLASS_FILE_BY_NAME)
    assert r == "facture"



# --- classify_files ---


def test_classify_files_empty_dataframe():
    """DataFrame vide -> retourne un DataFrame avec colonne classification."""
    df = pd.DataFrame(columns=["filename", "text"])
    out = classify_files(df, DIC_CLASS_FILE_BY_NAME, max_workers=1)
    assert "classification" in out.columns
    assert len(out) == 0


def test_classify_files_fills_classification_from_llm():
    """Un fichier est classifié via le LLM ; la colonne est remplie."""
    df = pd.DataFrame([{"filename": "d.pdf", "text": "contenu"}])
    with patch("docia.file_processing.processor.classifier.LLMClient") as mock_cls:
        mock_cls.return_value.ask_llm.return_value = ["Devis"]
        out = classify_files(df, DIC_CLASS_FILE_BY_NAME, max_workers=1)
    assert out["classification"].iloc[0] == "devis"


# --- DIC_CLASS_FILE_BY_NAME (structure) ---


def test_dic_class_file_by_name_has_expected_structure():
    """Chaque entrée a nom_complet, short_name, description."""
    for key, value in DIC_CLASS_FILE_BY_NAME.items():
        assert "nom_complet" in value, key
        assert "short_name" in value, key
        assert "description" in value, key
        assert isinstance(value["nom_complet"], str), key
        assert isinstance(value["description"], str), key
