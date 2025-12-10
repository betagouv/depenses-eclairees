import io
import os
from pathlib import Path
from unittest import mock

import pytest

from docia.file_processing.files_utils import detect_file_extension_from_content

ASSETS_DIR = Path(__file__).resolve().parent / "assets"


@pytest.mark.parametrize(
    "filename",
    [
        "calc.ods",
        "calc.xls",
        "calc.xlsx",
        "hello.txt",
        "hello.unknown",
        "hello.xml",
        "image.jpg",
        "image.png",
        "image.tiff",
        "lettre.doc",
        "lettre.docx",
        "lettre.odt",
        "lettre.pdf",
    ],
)
def test_detect_file_extension_from_content(filename):
    filepath = str(ASSETS_DIR / filename)
    expected_ext = os.path.splitext(filepath)[1].strip(".")
    with open(filepath, "rb") as f:
        file_content = f.read()
    with mock.patch("django.core.files.storage.default_storage.open", autospec=True) as m:
        m.side_effect = lambda filepath, mode: io.BytesIO(file_content)
        ext = detect_file_extension_from_content(filepath)
        m.assert_called_with(filepath, "rb")
    assert ext == expected_ext
