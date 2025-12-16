from unittest import mock
from unittest.mock import Mock, patch

import pytest
from openai import APIStatusError, InternalServerError, RateLimitError

from docia.file_processing.llm import LLMClient


@pytest.mark.parametrize(
    "error_class,status_code,retry_delay,error_message",
    [
        (
            RateLimitError,
            429,
            60,
            "Error code: 429 - {'detail': '100 requests for albert-large per minute exceeded (remaining: 0).'}",
        ),
        (APIStatusError, 503, 10, "Error code: 503 - {'detail': 'Model is too busy, please try again later.'}"),
        (APIStatusError, 504, 10, "Error code: 504 - {'detail': 'Model is too busy.'}"),
        (InternalServerError, 500, 10, "Error code: 500 - {'detail': ''}"),
        (InternalServerError, 500, 10, "Error code: 500 - {'detail': 'ConnectError'}"),
    ],
)
def test_ask_llm_rate_limit_error(error_class, status_code, retry_delay, error_message):
    """
    Test que ask_llm gère correctement les erreurs de rate limiting (429).
    """
    messages = [
        {"role": "system", "content": "Vous êtes un assistant utile qui analyse des histoires."},
        {"role": "user", "content": "Question: Répondez simplement 'OK' à ce message."},
    ]

    # Créer l'objet d'abord
    llm_env = LLMClient(llm_model="albert-large")

    # Mocker la méthode create de l'instance
    with (
        patch.object(llm_env.client.chat.completions, "create", autospec=True) as mock_create,
        patch("time.sleep", autospec=True) as m_sleep,
        patch("random.random", autospec=True) as m_random,
    ):
        # Toujours renvoyer 0.5 lors de la génération d'un random
        m_random.return_value = 0.5

        # Configurer le mock pour lever une exception
        response_mock = Mock(status_code=status_code)
        mock_create.side_effect = error_class(error_message, response=response_mock, body=Mock())

        # Appeler ask_llm - cela devrait lever une exception après les retries
        with pytest.raises(error_class) as exc_info:
            llm_env.ask_llm(messages=messages, temperature=0.0, max_retries=3)

        # Vérifier que create a été appelé deux fois (appel initial + 3 retry)
        assert mock_create.call_count == 4

        # Vérifier le temps de sleep
        expected_calls = [
            mock.call(retry_delay * 1.05),
            mock.call(retry_delay * 1.05 * 2),
            mock.call(retry_delay * 1.05 * 3),
        ]
        m_sleep.assert_has_calls(expected_calls)
        assert len(m_sleep.mock_calls) == len(expected_calls)

        # Vérifier que l'erreur contient bien 429
        assert str(status_code) in str(exc_info.value) or "rate limiting" in str(exc_info.value).lower()
