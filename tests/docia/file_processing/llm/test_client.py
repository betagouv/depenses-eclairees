from unittest import mock
from unittest.mock import Mock, patch

import httpx
import pytest
from httpx import TimeoutException
from openai._base_client import SyncHttpxClientWrapper

from docia.file_processing.llm.client import LLMApiError, LLMClient, OCRApiError


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
    llm_env = LLMClient(llm_model="openweight-medium", http_client=httpx_client)

    # Mock
    with (
        patch("time.sleep", autospec=True) as m_sleep,
        patch("random.random", autospec=True) as m_random,
    ):
        # Toujours renvoyer 0.5 lors de la génération d'un random
        m_random.return_value = 0.5

        # Appeler ask_llm - cela devrait lever une exception après les retries
        with pytest.raises(LLMApiError) as exc_info:
            llm_env.ask_llm(messages=messages, temperature=0.0, max_retries=3)

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


# --- ocr_pdf tests (mock httpx.post, no real API calls) ---

PDF_CONTENT = b"%PDF-1.4 fake content"


def run_ocr_error_test(
    mock_post: Mock,
    retry_delay: float,
    expected_status_code: int | None,
    expected_message_prefix: str,
    max_retries: int = 3,
):
    """
    Helper to assert ocr_pdf retry logic and final OCRApiError.

    Args:
        mock_post: Mock for httpx.post (in docia.file_processing.llm.client).
        retry_delay: Base delay used for sleep (429 -> retry_delay, 5xx/network -> retry_short_delay).
        expected_status_code: status_code on OCRApiError (None for network errors).
        expected_message_prefix: str that the raised error message must start with.
        max_retries: max_retries passed to ocr_pdf.
    """
    client = LLMClient(llm_model="openweight-medium", use_rate_limiter=False)
    with (
        patch("docia.file_processing.llm.client.httpx.post", mock_post),
        patch("time.sleep", autospec=True) as m_sleep,
        patch("random.random", autospec=True) as m_random,
    ):
        m_random.return_value = 0.5
        with pytest.raises(OCRApiError) as exc_info:
            client.ocr_pdf(PDF_CONTENT, max_retries=max_retries)

        ex = exc_info.value
        assert ex.status_code == expected_status_code
        msg = str(ex)
        assert msg.startswith(expected_message_prefix) or expected_message_prefix in msg
        assert mock_post.call_count == max_retries + 1
        # Sleeps: one per failed attempt (3 sleeps for max_retries=3)
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
    """ocr_pdf retries on 429 (retry_delay) or 5xx (retry_short_delay), then raises OCRApiError."""
    delay = 60 if status_code == 429 else 10
    mock_post = Mock(return_value=httpx.Response(status_code=status_code, text="error"))
    m_sleep = run_ocr_error_test(
        mock_post,
        retry_delay=delay,
        expected_status_code=status_code,
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
    """ocr_pdf does not retry on 4xx (e.g. 400), raises OCRApiError immediately."""
    client = LLMClient(llm_model="openweight-medium", use_rate_limiter=False)
    mock_post = Mock(return_value=httpx.Response(status_code=400, text="Bad request"))
    with (
        patch("docia.file_processing.llm.client.httpx.post", mock_post),
        patch("time.sleep", autospec=True) as m_sleep,
    ):
        with pytest.raises(OCRApiError) as exc_info:
            client.ocr_pdf(PDF_CONTENT, max_retries=3)
        ex = exc_info.value
        assert ex.status_code == 400
        assert "400" in str(ex)
        assert mock_post.call_count == 1
        m_sleep.assert_not_called()


def test_ocr_pdf_network_error_retry_then_raise():
    """ocr_pdf retries on ConnectError then raises OCRApiError."""
    mock_post = Mock(side_effect=httpx.ConnectError("Connection refused"))
    run_ocr_error_test(
        mock_post,
        retry_delay=10,
        expected_status_code=None,
        expected_message_prefix="OCR API error",
        max_retries=3,
    )


def test_ocr_pdf_timeout_retry_then_raise():
    """ocr_pdf retries on TimeoutException then raises OCRApiError."""
    mock_post = Mock(side_effect=TimeoutException("Request timeout"))
    run_ocr_error_test(
        mock_post,
        retry_delay=10,
        expected_status_code=None,
        expected_message_prefix="OCR API error",
        max_retries=3,
    )


def test_ocr_pdf_success():
    """ocr_pdf returns extracted markdown when API returns 200 with pages."""
    client = LLMClient(llm_model="openweight-medium", use_rate_limiter=False)
    mock_post = Mock(
        return_value=httpx.Response(
            status_code=200,
            json={"pages": [{"markdown": "Page one"}, {"markdown": "Page two"}]},
        )
    )
    with patch("docia.file_processing.llm.client.httpx.post", mock_post):
        result = client.ocr_pdf(PDF_CONTENT)
    assert result == "Page one\n\nPage two"
    assert mock_post.call_count == 1
