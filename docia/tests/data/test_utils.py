import pandas as pd

from app.utils import clean_nul_bytes, clean_nul_bytes_from_dataframe


def test_clean_nul_bytes():
    text = "\x00Hello \x00World!\x00"
    cleaned = clean_nul_bytes(text)
    assert cleaned == "Hello World!"


def test_clean_nul_bytes_df():
    # Create test dataframe with null bytes
    df = pd.DataFrame({
        'text': ['\x00Hello\x00', 'World\x00!'],
        'number': [1, 2],
        'other_text': ['Test\x00', '\x00Data']
    })

    # Test cleaning specific text column
    df_cleaned = clean_nul_bytes_from_dataframe(df, text_columns=['text'])
    assert df_cleaned['text'].tolist() == ['Hello', 'World!']
    assert df_cleaned['other_text'].tolist() == ['Test\x00', '\x00Data']

    # Test cleaning multiple text columns
    df_cleaned = clean_nul_bytes_from_dataframe(df, text_columns=['text', 'other_text'])
    assert df_cleaned['text'].tolist() == ['Hello', 'World!']
    assert df_cleaned['other_text'].tolist() == ['Test', 'Data']

    # Test cleaning with no columns specified (should clean all string columns)
    df_cleaned = clean_nul_bytes_from_dataframe(df)
    assert df_cleaned['text'].tolist() == ['Hello', 'World!']
    assert df_cleaned['other_text'].tolist() == ['Test', 'Data']
    assert df_cleaned['number'].tolist() == [1, 2]
