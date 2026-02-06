import base64
from unittest import mock
from unittest.mock import Mock, patch

import httpx
import pytest
from httpx import TimeoutException
from openai._base_client import SyncHttpxClientWrapper

from docia.file_processing.llm.client import (
    LLMApiError,
    LLMClient,
    _build_pdf_document_payload,
    _extract_markdown_from_ocr_response,
)

# --- _build_pdf_document_payload / _extract_markdown_from_ocr_response ---


def test_build_pdf_document_payload_empty():
    """Payload pour contenu vide : type document_url et data URI base64."""
    out = _build_pdf_document_payload(b"")
    assert out == {"type": "document_url", "document_url": "data:application/pdf;base64,"}
    assert out["document_url"].startswith("data:application/pdf;base64,")


def test_build_pdf_document_payload_content():
    """Payload encode le PDF en base64 dans un data URI."""
    content = b"%PDF-1.4 fake"
    out = _build_pdf_document_payload(content)
    assert out["type"] == "document_url"
    assert out["document_url"].startswith("data:application/pdf;base64,")
    b64 = out["document_url"].split(",", 1)[1]
    assert base64.b64decode(b64) == content


def test_extract_markdown_from_ocr_response_empty():
    """Réponse sans pages ou pages vides -> chaîne vide."""
    assert _extract_markdown_from_ocr_response({}) == ""
    assert _extract_markdown_from_ocr_response({"pages": []}) == ""


def test_extract_markdown_from_ocr_response_one_page():
    """Une page : marqueurs [[PAGE 1 / 1]] ... [[FIN PAGE 1 / 1]] et contenu."""
    out = _extract_markdown_from_ocr_response({"pages": [{"markdown": "Hello"}]})
    assert out == "[[PAGE 1 / 1]]\nHello\n[[FIN PAGE 1 / 1]]"


def test_extract_markdown_from_ocr_response_multiple_pages():
    """Plusieurs pages : marqueurs avec numéro de page et total."""
    out = _extract_markdown_from_ocr_response(
        {
            "pages": [{"markdown": "A"}, {"markdown": "B"}, {"markdown": "C"}],
        }
    )
    assert "[[PAGE 1 / 3]]\nA\n[[FIN PAGE 1 / 3]]" in out
    assert "[[PAGE 2 / 3]]\nB\n[[FIN PAGE 2 / 3]]" in out
    assert "[[PAGE 3 / 3]]\nC\n[[FIN PAGE 3 / 3]]" in out
    assert out.count("\n\n") == 2


def test_extract_markdown_from_ocr_response_missing_markdown():
    """Page sans clé markdown -> contenu vide pour cette page."""
    out = _extract_markdown_from_ocr_response({"pages": [{"markdown": "Ok"}, {}]})
    assert "[[PAGE 1 / 2]]\nOk\n[[FIN PAGE 1 / 2]]" in out
    assert "[[PAGE 2 / 2]]\n\n[[FIN PAGE 2 / 2]]" in out


# --- _api_call (retry / erreurs) ---


def test_api_call_429_retry_then_raise():
    """_api_call retente sur HTTP_429 puis lève après épuisement des retries."""
    client = LLMClient(use_rate_limiter=False)
    err = LLMApiError("Rate limited", code="HTTP_429", details="too many requests")
    func_api = Mock(side_effect=err)
    with (
        patch("docia.file_processing.llm.client.time.sleep", autospec=True) as m_sleep,
        patch("docia.file_processing.llm.client.random.random", return_value=0.5),
    ):
        with pytest.raises(LLMApiError) as exc_info:
            client._api_call(
                func_api,
                max_retries=3,
                retry_delay=60,
                retry_short_delay=10,
                limiter=None,
            )
        assert exc_info.value.code == "HTTP_429"
        assert func_api.call_count == 4
        assert m_sleep.call_count == 3
        m_sleep.assert_has_calls(
            [
                mock.call(60 * 1.05 * 1),
                mock.call(60 * 1.05 * 2),
                mock.call(60 * 1.05 * 3),
            ]
        )


def test_api_call_4xx_no_retry():
    """_api_call ne retente pas sur 4xx, relève immédiatement."""
    client = LLMClient(use_rate_limiter=False)
    err = LLMApiError("Bad request", code="HTTP_400", details="invalid")
    func_api = Mock(side_effect=err)
    with patch("docia.file_processing.llm.client.time.sleep", autospec=True) as m_sleep:
        with pytest.raises(LLMApiError) as exc_info:
            client._api_call(
                func_api,
                max_retries=3,
                retry_delay=60,
                retry_short_delay=10,
                limiter=None,
            )
        assert exc_info.value.code == "HTTP_400"
        assert func_api.call_count == 1
        m_sleep.assert_not_called()


def test_api_call_success_on_second_attempt():
    """_api_call retente puis renvoie la valeur au succès."""
    client = LLMClient(use_rate_limiter=False)
    err = LLMApiError("Rate limited", code="HTTP_429", details="")
    func_api = Mock(side_effect=[err, "result"])
    with (
        patch("docia.file_processing.llm.client.time.sleep", autospec=True) as m_sleep,
        patch("docia.file_processing.llm.client.random.random", return_value=0.5),
    ):
        out = client._api_call(
            func_api,
            max_retries=3,
            retry_delay=60,
            retry_short_delay=10,
            limiter=None,
        )
        assert out == "result"
        assert func_api.call_count == 2
        m_sleep.assert_called_once()
        m_sleep.assert_called_with(60 * 1.05 * 1)


def run_llm_error_test(mock_handler, retry_delay, expected_code, expected_message):
    """
    Helper function to test LLM error handling and retry logic.

    Tests that the LLMClient properly handles errors, implements retry logic with exponential backoff,
    and raises appropriate LLMApiError exceptions after exhausting retries.

    Args:
        mock_handler: Mock httpx transport handler that simulates API errors or timeouts
        retry_delay: Expected base delay in seconds between retry attempts
        expected_code: Expected error code in the raised LLMApiError
        expected_message: Expected error message in the raised LLMApiError
    """
    messages = [
        {"role": "system", "content": "Vous êtes un assistant utile qui analyse des histoires."},
        {"role": "user", "content": "Question: Répondez simplement 'OK' à ce message."},
    ]

    # Créer un client httpx avec un mock transport pour renvoyer une erreur
    # et compter le nombre d'appels
    httpx_client = SyncHttpxClientWrapper(transport=httpx.MockTransport(handler=mock_handler))

    # Créer le client
    llm_env = LLMClient(http_client=httpx_client)

    # Mock
    with (
        patch("time.sleep", autospec=True) as m_sleep,
        patch("random.random", autospec=True) as m_random,
    ):
        # Toujours renvoyer 0.5 lors de la génération d'un random
        m_random.return_value = 0.5

        # Appeler ask_llm - cela devrait lever une exception après les retries
        with pytest.raises(LLMApiError) as exc_info:
            llm_env.ask_llm(messages=messages, model="openweight-medium", temperature=0.0, max_retries=3)

        # Vérifier que create a été appelé 4 fois (appel initial + 3 retry)
        assert mock_handler.call_count == 4

        # Vérifier le temps de sleep
        expected_calls = [
            mock.call(retry_delay * 1.05),
            mock.call(retry_delay * 1.05 * 2),
            mock.call(retry_delay * 1.05 * 3),
        ]
        m_sleep.assert_has_calls(expected_calls)
        assert len(m_sleep.mock_calls) == len(expected_calls)

        # Vérifier l'erreur
        ex = exc_info.value
        assert ex.code == expected_code
        assert ex.message == expected_message
        assert str(ex) == expected_message


@pytest.mark.parametrize(
    "status_code,retry_delay,error_message",
    [
        (
            429,
            60,
            {"detail": "100 requests for openweight-medium per minute exceeded (remaining: 0)."},
        ),
        (503, 10, {"detail": "Model is too busy, please try again later."}),
        (504, 10, {"detail": "Model is too busy."}),
        (500, 10, {"detail": ""}),
        (500, 10, {"detail": "ConnectError"}),
    ],
)
def test_ask_llm_api_error(status_code, retry_delay, error_message):
    """
    Test que ask_llm gère correctement les erreurs de rate limiting (429).
    """
    # Créer un mock handler pour renvoyer une erreur
    mock_handler = Mock(side_effect=lambda request: httpx.Response(status_code=status_code, json=error_message))

    # Construire les valeurs attendues
    expected_code = f"HTTP_{status_code}"
    expected_message = f"Api Error: HTTP_{status_code} - {error_message}"

    # Exécuter le test
    run_llm_error_test(mock_handler, retry_delay, expected_code, expected_message)


def test_ask_llm_timeout_error():
    """
    Test que ask_llm gère correctement les erreurs de timeout.
    """
    retry_delay = 10

    # Créer un mock handler pour lever une TimeoutException
    mock_handler = Mock(side_effect=TimeoutException("Request timeout"))

    # Construire les valeurs attendues
    expected_code = "ERROR_APITimeoutError"
    expected_message = "Api Error: ERROR_APITimeoutError - Request timed out."

    # Exécuter le test
    run_llm_error_test(mock_handler, retry_delay, expected_code, expected_message)


# --- ocr_pdf tests (injected httpx client with MockTransport, like ask_llm) ---

PDF_CONTENT = b"%PDF-1.4 fake content"


def run_ocr_error_test(
    mock_handler: Mock,
    retry_delay: float,
    expected_code: str,
    expected_message_prefix: str,
    max_retries: int = 3,
):
    """
    Helper to assert ocr_pdf retry logic and final LLMApiError.
    Uses an injected httpx client with MockTransport (same approach as ask_llm).

    Args:
        mock_handler: Handler for httpx.MockTransport (receives request, returns Response or raises).
        retry_delay: Base delay used for sleep (429 -> retry_delay, 5xx/network -> retry_short_delay).
        expected_code: code on LLMApiError (e.g. "HTTP_429", "ERROR_ConnectError").
        expected_message_prefix: str that the raised error message must start with.
        max_retries: max_retries passed to ocr_pdf.
    """
    ocr_client = httpx.Client(transport=httpx.MockTransport(handler=mock_handler))
    client = LLMClient(use_rate_limiter=False, ocr_http_client=ocr_client)
    with (
        patch("time.sleep", autospec=True) as m_sleep,
        patch("random.random", autospec=True) as m_random,
    ):
        m_random.return_value = 0.5
        with pytest.raises(LLMApiError) as exc_info:
            client.ocr_pdf(PDF_CONTENT, max_retries=max_retries)

        ex = exc_info.value
        assert ex.code == expected_code
        msg = str(ex)
        assert msg.startswith(expected_message_prefix) or expected_message_prefix in msg
        assert mock_handler.call_count == max_retries + 1
        assert len(m_sleep.mock_calls) == max_retries
        return m_sleep


@pytest.mark.parametrize(
    "status_code,retry_delay",
    [
        (429, 60),
        (503, 10),
        (504, 10),
        (500, 10),
    ],
)
def test_ocr_pdf_retry_then_error(status_code, retry_delay):
    """ocr_pdf retries on 429 (retry_delay) or 5xx (retry_short_delay), then raises LLMApiError."""
    delay = 60 if status_code == 429 else 10
    mock_handler = Mock(return_value=httpx.Response(status_code=status_code, text="error"))
    m_sleep = run_ocr_error_test(
        mock_handler,
        retry_delay=delay,
        expected_code=f"HTTP_{status_code}",
        expected_message_prefix="OCR API error",
        max_retries=3,
    )
    expected_calls = [
        mock.call(delay * 1.05),
        mock.call(delay * 1.05 * 2),
        mock.call(delay * 1.05 * 3),
    ]
    m_sleep.assert_has_calls(expected_calls)


def test_ocr_pdf_4xx_no_retry():
    """ocr_pdf does not retry on 4xx (e.g. 400), raises LLMApiError immediately."""
    mock_handler = Mock(return_value=httpx.Response(status_code=400, text="Bad request"))
    ocr_client = httpx.Client(transport=httpx.MockTransport(handler=mock_handler))
    client = LLMClient(use_rate_limiter=False, ocr_http_client=ocr_client)
    with patch("time.sleep", autospec=True) as m_sleep:
        with pytest.raises(LLMApiError) as exc_info:
            client.ocr_pdf(PDF_CONTENT, max_retries=3)
        ex = exc_info.value
        assert ex.code == "HTTP_400"
        assert "400" in str(ex)
        assert mock_handler.call_count == 1
        m_sleep.assert_not_called()


def test_ocr_pdf_network_error_retry_then_raise():
    """ocr_pdf retries on ConnectError then raises LLMApiError."""
    mock_handler = Mock(side_effect=httpx.ConnectError("Connection refused"))
    run_ocr_error_test(
        mock_handler,
        retry_delay=10,
        expected_code="ERROR_ConnectError",
        expected_message_prefix="OCR API error",
        max_retries=3,
    )


def test_ocr_pdf_timeout_retry_then_raise():
    """ocr_pdf retries on TimeoutException then raises LLMApiError."""
    mock_handler = Mock(side_effect=TimeoutException("Request timeout"))
    run_ocr_error_test(
        mock_handler,
        retry_delay=10,
        expected_code="ERROR_TimeoutException",
        expected_message_prefix="OCR API error",
        max_retries=3,
    )


def test_ocr_pdf_success():
    """ocr_pdf returns extracted markdown with page markers when API returns 200 with pages."""
    mock_handler = Mock(
        return_value=httpx.Response(
            status_code=200,
            json={"pages": [{"markdown": "Page one"}, {"markdown": "Page two"}]},
        )
    )
    ocr_client = httpx.Client(transport=httpx.MockTransport(handler=mock_handler))
    client = LLMClient(use_rate_limiter=False, ocr_http_client=ocr_client)
    result = client.ocr_pdf(PDF_CONTENT)
    expected = "[[PAGE 1 / 2]]\nPage one\n[[FIN PAGE 1 / 2]]\n\n[[PAGE 2 / 2]]\nPage two\n[[FIN PAGE 2 / 2]]"
    assert result == expected
    assert mock_handler.call_count == 1
