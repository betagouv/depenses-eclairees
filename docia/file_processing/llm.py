import logging
import random
import time

from django.conf import settings

from openai import APIStatusError, OpenAI

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(
        self,
        llm_model: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        self.api_key = api_key or settings.ALBERT_API_KEY
        self.base_url = base_url or settings.ALBERT_BASE_URL
        self.llm_model = llm_model

        # Initialisation du client OpenAI
        self.client = self._initialize_openai_client()

    def _initialize_openai_client(self) -> OpenAI:
        """
        Initialise le client OpenAI avec la clé API fournie et éventuellement une URL de base personnalisée.

        Returns:
            Instance du client OpenAI
        """
        client_kwargs = {
            "api_key": self.api_key,
            # Disable openai client retry feature, handle retry ourselves
            "max_retries": 0,
        }

        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        return OpenAI(**client_kwargs)

    def ask_llm(
        self,
        messages: list[dict],
        response_format: dict = None,
        temperature: float = 0.0,
        max_retries: int = 3,
        retry_delay: float = 60,
        retry_short_delay: float = 10,
    ) -> str:
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
            retry_delay: Délai d'attente en secondes entre les tentatives (défaut: 60)

        Returns:
            Réponse du LLM

        Raises:
            Exception: Si toutes les tentatives échouent ou si l'erreur n'est pas de type 429
        """
        if max_retries < 0:
            max_retries = 0

        response = ""

        for attempt in range(max_retries + 1):
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

            except APIStatusError as e:
                if e.status_code == 429:
                    effective_retry_delay = retry_delay
                elif e.status_code in (500, 504):
                    effective_retry_delay = retry_short_delay
                else:
                    raise

                if effective_retry_delay and attempt < max_retries:
                    rnd = 1 + (0.1 * random.random())  # Ajout d'un peu de random (10%)
                    wait_time = effective_retry_delay * rnd * (attempt + 1)
                    logger.warning(
                        f"ApiError {e.status_code} ({str(e)}), wait {wait_time:.1f}s before retry ({attempt + 1}/{max_retries})"  # noqa: E501
                    )
                    time.sleep(wait_time)
                    continue  # Retry
                raise

        return response
