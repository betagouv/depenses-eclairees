from unittest import mock
from unittest.mock import Mock, patch

import httpx
import pytest
from httpx import TimeoutException
from openai._base_client import SyncHttpxClientWrapper

from docia.file_processing.llm.client import LLMApiError, LLMClient


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
    llm_env = LLMClient(llm_model="albert-large", http_client=httpx_client)

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
            {"detail": "100 requests for albert-large per minute exceeded (remaining: 0)."},
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
