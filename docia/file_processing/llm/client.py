import base64
import json
import logging
import random
import time
from urllib.parse import urljoin

from django.conf import settings

import httpx
from openai import APIConnectionError, APIError, APIStatusError, OpenAI

from docia.file_processing.llm.rategate.gate import RateGate

logger = logging.getLogger(__name__)

# --- OCR (API Albert / OpenGateLLM, convention Mistral) ---
# Modèle OCR (image-to-text). https://albert.status.staging.etalab.gouv.fr/status/api
DEFAULT_OCR_MODEL = "mistral-ocr-2512"
OCR_ENDPOINT = "/ocr"


def _build_pdf_document_payload(pdf_content: bytes) -> dict:
    """Payload document pour l'API OCR : PDF en base64 (data URI)."""
    b64 = base64.b64encode(pdf_content).decode("utf-8")
    data_uri = f"data:application/pdf;base64,{b64}"
    return {"type": "document_url", "document_url": data_uri}


def _extract_markdown_from_ocr_response(response_data: dict) -> str:
    """Extrait le texte markdown de la réponse OCR (toutes les pages)."""
    pages = response_data.get("pages", [])
    parts = [page.get("markdown") or "" for page in pages]
    return "\n\n".join(parts).strip()


class OCRApiError(Exception):
    """Erreur renvoyée par l'API OCR."""

    def __init__(self, message: str, *, status_code: int | None = None, details: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


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
        llm_model: str | None = None,
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

    def ocr_pdf(
        self,
        pdf_content: bytes,
        model: str = DEFAULT_OCR_MODEL,
        max_retries: int = 3,
        retry_delay: float = 60,
        retry_short_delay: float = 10,
    ) -> str:
        """
        Envoie le contenu d'un PDF à l'API OCR et retourne le texte extrait (markdown).

        Retry : 429 (retry_delay), 5XX et erreurs de connexion (retry_short_delay).
        À utiliser dans extract_text_from_pdf (processor) quand le PDF est un scan / peu de texte.
        """
        if max_retries < 0:
            max_retries = 0

        payload = {
            "model": model,
            "document": _build_pdf_document_payload(pdf_content),
            "include_image_base64": False,
        }
        url = urljoin(self.base_url.rstrip("/") + "/", OCR_ENDPOINT.lstrip("/"))
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error = None
        for attempt in range(max_retries + 1):
            if self.limiter:
                self.limiter.wait_turn()
            # Unlike ask_llm (OpenAI client), httpx does not raise on 4xx/5xx: we get a Response.
            # Only transport errors (connection, timeout) raise.
            try:
                response = httpx.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=120.0,
                )
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                # Network/timeout error: no Response, handle retry here.
                last_error = OCRApiError(
                    f"OCR API error: {e!s}",
                    details=str(e),
                )
                if attempt < max_retries:
                    wait_time = retry_short_delay * (1 + 0.1 * random.random()) * (attempt + 1)
                    logger.warning(
                        "OCR %s, wait %.1fs before retry (%d/%d)",
                        e,
                        wait_time,
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(wait_time)
                    continue
                raise last_error from e

            # HTTP response received: handle status (success, 429, 5xx, or other → raise).
            if response.is_success:
                return _extract_markdown_from_ocr_response(response.json())

            if response.status_code == 429:
                effective_retry_delay = retry_delay
            elif 500 <= response.status_code < 600:
                effective_retry_delay = retry_short_delay
            else:
                raise OCRApiError(
                    f"OCR API error: {response.status_code}",
                    status_code=response.status_code,
                    details=response.text,
                )

            # 429 or 5xx: retry (same sleep/continue logic as above for network errors).
            last_error = OCRApiError(
                f"OCR API error: {response.status_code}",
                status_code=response.status_code,
                details=response.text,
            )
            if attempt < max_retries:
                wait_time = effective_retry_delay * (1 + 0.1 * random.random()) * (attempt + 1)
                logger.warning(
                    "OCR HTTP %s, wait %.1fs before retry (%d/%d)",
                    response.status_code,
                    wait_time,
                    attempt + 1,
                    max_retries,
                )
                time.sleep(wait_time)
                continue
            raise last_error
