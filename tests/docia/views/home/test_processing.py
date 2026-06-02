from docia.views import compute_ratio_data_extraction, format_ratio_to_percent


def test_compute_ratio_data_extraction():
    """Test compute_ratio_data_extraction function with various inputs."""
    # Empty dictionary should return 0
    assert compute_ratio_data_extraction({}) == 0

    # All values are empty/None/False, should return 0
    assert compute_ratio_data_extraction({"key1": None, "key2": "", "key3": False}) == 0

    # All values are non-empty, should return 1.0
    assert compute_ratio_data_extraction({"key1": "value", "key2": "data", "key3": True}) == 1.0

    # Mix of empty and non-empty values, should return ratio
    response = {"key1": "value", "key2": None, "key3": "data", "key4": ""}
    assert compute_ratio_data_extraction(response) == 0.5

    # More complex example
    complex_response = {
        "field1": "extracted data",
        "field2": None,
        "field3": "",
        "field4": "more data",
        "field5": 123,
        "field6": False,
    }
    # 3 out of 6 have values (field1, field4, field5)
    assert compute_ratio_data_extraction(complex_response) == 0.5


def test_format_ratio_to_percent():
    """Test format_ratio_to_percent function with various inputs."""
    # Zero should return 0%
    assert format_ratio_to_percent(0) == "0%"

    # 0.5 should return 50%
    assert format_ratio_to_percent(0.5) == "50%"

    # 1.0 should return 100%
    assert format_ratio_to_percent(1.0) == "100%"

    # Values are rounded to nearest integer
    assert format_ratio_to_percent(0.333) == "33%"
    assert format_ratio_to_percent(0.667) == "67%"

    # Values greater than 1 are allowed
    assert format_ratio_to_percent(1.5) == "150%"

    # Small values are rounded properly
    assert format_ratio_to_percent(0.01) == "1%"
    assert format_ratio_to_percent(0.001) == "0%"  # Rounds to 0

