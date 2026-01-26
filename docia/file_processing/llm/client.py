import json
import logging
import random
import time

from django.conf import settings

import httpx
from openai import APIConnectionError, APIError, APIStatusError, OpenAI

from docia.file_processing.llm.rategate.gate import RateGate

logger = logging.getLogger(__name__)


class LLMApiError(Exception):
    message: str
    code: str
    details: any

    def __init__(self, message: str, *, code: str, details: any):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details

    @classmethod
    def pretty_code_from_error(cls, e: APIError):
        if isinstance(e, APIStatusError):
            code = f"HTTP_{e.status_code}"
        else:
            code = f"ERROR_{e.__class__.__name__}"
        return code

    @classmethod
    def details_from_error(cls, e: APIError):
        if isinstance(e, APIStatusError):
            details = e.body
        else:
            details = str(e)
        return details

    @classmethod
    def from_api_error(cls, e: APIError):
        code = cls.pretty_code_from_error(e)
        details = cls.details_from_error(e)
        return cls(
            f"Api Error: {code} - {details}",
            code=code,
            details=details,
        )


class LLMClient:
    def __init__(
        self,
        llm_model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        http_client: httpx.Client | None = None,
        use_rate_limiter: bool | None = None,
        rate_per_minute: int | None = None,
    ):
        if use_rate_limiter is None:
            use_rate_limiter = settings.ALBERT_USE_RATE_LIMITER
        if rate_per_minute is None:
            rate_per_minute = settings.ALBERT_RATE_PER_MINUTE

        self.api_key = api_key or settings.ALBERT_API_KEY
        self.base_url = base_url or settings.ALBERT_BASE_URL
        self.llm_model = llm_model

        if use_rate_limiter:
            self.limiter = RateGate(rate_per_minute, key=llm_model)
        else:
            self.limiter = None

        # Initialisation du client OpenAI
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            http_client=http_client,
            # Disable openai client retry feature, handle retry ourselves
            max_retries=0,
        )

    def ask_llm(
        self,
        messages: list[dict],
        response_format: dict = None,
        temperature: float = 0.0,
        max_retries: int = 3,
        retry_delay: float = 60,
        retry_short_delay: float = 10,
    ) -> str | dict:
        """
        Interroge le LLM avec un prompt système et utilisateur.
        En cas d'erreur de rate limiting (429), attend et réessaye automatiquement.

        Args:
            messages:
                {"role": "system", "content": "..."},
                {"role": "user", "content": "..."}
            response_format: Format de réponse à utiliser
            temperature: Température pour la génération (0.0 = déterministe)
            max_retries: Nombre maximum de tentatives en cas d'erreur 429 (défaut: 3)
            retry_delay: Délai d'attente en secondes entre les tentatives erreur rate limit (défaut: 60)
            retry_short_delay: Délai d'attente en secondes entre les tentatives erreur 5XX (défaut: 10)

        Returns:
            Réponse du LLM

        Raises:
            Exception: Si toutes les tentatives échouent ou si l'erreur n'est pas de type 429
        """
        if max_retries < 0:
            max_retries = 0

        response = ""

        for attempt in range(max_retries + 1):
            if self.limiter:
                self.limiter.wait_turn()
            try:
                response = self.client.chat.completions.create(
                    model=self.llm_model,
                    messages=messages,
                    temperature=temperature,
                    response_format=response_format if response_format else None,
                )

                content = response.choices[0].message.content.strip()

                response = content  # Success
                break

            # Retry mechanism for API errors:
            # - 429 (rate limit): retry with longer delay (retry_delay)
            # - 5XX (server errors): retry with shorter delay (retry_short_delay)
            # - Connection errors: retry with shorter delay (retry_short_delay)
            # - Other errors: raise immediately without retry
            # Each retry multiplies the delay by (attempt + 1) with 10% randomization
            except APIError as e:
                if isinstance(e, APIStatusError):
                    if e.status_code == 429:
                        effective_retry_delay = retry_delay
                    elif 500 <= e.status_code < 600:
                        effective_retry_delay = retry_short_delay
                    else:
                        raise LLMApiError.from_api_status_error(e) from e
                elif isinstance(e, APIConnectionError):
                    effective_retry_delay = retry_short_delay
                else:
                    raise LLMApiError.from_api_error(e) from e

                if effective_retry_delay and attempt < max_retries:
                    rnd = 1 + (0.1 * random.random())  # Ajout d'un peu de random (10%)
                    wait_time = effective_retry_delay * rnd * (attempt + 1)
                    error_code = LLMApiError.pretty_code_from_error(e)
                    logger.warning(
                        f"ApiError {error_code} ({str(e)}), wait {wait_time:.1f}s before retry ({attempt + 1}/{max_retries})"  # noqa: E501
                    )
                    time.sleep(wait_time)
                    continue  # Retry
                raise LLMApiError.from_api_error(e) from e

        if response_format:
            return json.loads(response)
        else:
            return response
