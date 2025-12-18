from unittest import mock
from unittest.mock import Mock, patch

import httpx
import pytest
from openai._base_client import SyncHttpxClientWrapper

from docia.file_processing.llm import LLMApiError, LLMClient


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
    messages = [
        {"role": "system", "content": "Vous êtes un assistant utile qui analyse des histoires."},
        {"role": "user", "content": "Question: Répondez simplement 'OK' à ce message."},
    ]

    # Créer un client httpx avec un mock transport pour renvoyer une erreur
    # et compter le nombre d'appels
    mock_handler = Mock(side_effect=lambda request: httpx.Response(status_code=status_code, json=error_message))
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
        ex_message = f"Api Error: {status_code} - {error_message}"
        assert ex.status_code == status_code
        assert ex.message == ex_message
        assert str(ex) == ex_message
