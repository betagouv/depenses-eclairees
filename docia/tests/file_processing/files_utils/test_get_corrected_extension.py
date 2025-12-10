from unittest import mock

from docia.file_processing.files_utils import get_corrected_extension


def test_get_corrected_extension_both_match():
    with mock.patch("docia.file_processing.files_utils.detect_file_extension_from_content", autospec=True) as m:
        m.return_value = "pdf"
        ext = get_corrected_extension("toto.pdf", "toto.pdf")
        assert ext == "pdf"


def test_get_corrected_extension_no_name_ext():
    with mock.patch("docia.file_processing.files_utils.detect_file_extension_from_content", autospec=True) as m:
        m.return_value = "pdf"
        ext = get_corrected_extension("toto", "toto")
        assert ext == "pdf"


def test_get_corrected_extension_unknown_content_ext():
    with mock.patch("docia.file_processing.files_utils.detect_file_extension_from_content", autospec=True) as m:
        m.return_value = "unknown"
        ext = get_corrected_extension("toto.pdf", "toto.pdf")
        assert ext == "pdf"


def test_get_corrected_extension_content_and_name_missmatch():
    with mock.patch("docia.file_processing.files_utils.detect_file_extension_from_content", autospec=True) as m:
        m.return_value = "pdf"
        ext = get_corrected_extension("toto.docx", "toto.docx")
        assert ext == "pdf"
