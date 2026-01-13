from docia.file_processing.processor.post_processing_llm import normalize_text


def test_normalize_text_simple():
    """Test avec un texte simple."""
    assert normalize_text("Hello World") == "Hello World"


def test_normalize_text_multiple_spaces():
    """Test avec plusieurs espaces."""
    assert normalize_text("Hello    World") == "Hello World"
    assert normalize_text("Hello   World   Test") == "Hello World Test"


def test_normalize_text_leading_trailing_spaces():
    """Test avec espaces en début et fin."""
    assert normalize_text("  Hello World  ") == "Hello World"
    assert normalize_text("\tHello World\n") == "Hello World"


def test_normalize_text_empty():
    """Test avec chaîne vide."""
    assert normalize_text("") == ""
    assert normalize_text("   ") == ""


def test_normalize_text_tabs_and_newlines():
    """Test avec tabulations et retours à la ligne."""
    assert normalize_text("Hello\tWorld") == "Hello World"
    assert normalize_text("Hello\nWorld") == "Hello World"
    assert normalize_text("Hello\r\nWorld") == "Hello World"


def test_normalize_text_mixed_whitespace():
    """Test avec mélange d'espaces, tabs, etc."""
    assert normalize_text("Hello  \t  \n  World") == "Hello World"
