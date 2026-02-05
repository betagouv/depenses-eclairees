import base64
import json
import logging
import random
import time
from collections.abc import Callable
from typing import TypeVar
from urllib.parse import urljoin

T = TypeVar("T")

from django.conf import settings
import httpx
from openai import APIConnectionError, APIError, APIStatusError, OpenAI

from docia.file_processing.llm.rategate.gate import RateGate

logger = logging.getLogger(__name__)


def _build_pdf_document_payload(pdf_content: bytes) -> dict:
    """Payload document pour l'API OCR : PDF en base64 (data URI)."""
    b64 = base64.b64encode(pdf_content).decode("utf-8")
    data_uri = f"data:application/pdf;base64,{b64}"
    return {"type": "document_url", "document_url": data_uri}


def _extract_markdown_from_ocr_response(response_data: dict) -> str:
    """Extrait le texte markdown de la réponse OCR (toutes les pages)."""
    pages = response_data.get("pages", [])
    total = len(pages)
    parts = []
    for i, page in enumerate(pages, start=1):
        content = (page.get("markdown") or "").strip()
        parts.append(f"[[PAGE {i} {total}]]\n{content}\n[[FIN PAGE {i} {total}]]")
    return "\n\n".join(parts).strip()


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
        api_key: str | None = None,
        base_url: str | None = None,
        http_client: httpx.Client | None = None,
        ocr_http_client: httpx.Client | None = None,
        use_rate_limiter: bool | None = None,
    ):
        if use_rate_limiter is None:
            use_rate_limiter = settings.ALBERT_USE_RATE_LIMITER

        self.api_key = api_key or settings.ALBERT_API_KEY
        self.base_url = base_url or settings.ALBERT_BASE_URL
        self._use_rate_limiter = use_rate_limiter
        self._ocr_http_client = ocr_http_client

        # Initialisation du client OpenAI
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            http_client=http_client,
            # Disable openai client retry feature, handle retry ourselves
            max_retries=0,
        )

    def _get_limiter(self, model: str, rate_per_minute: int | None = None) -> RateGate | None:
        """
        Retourne le RateGate pour le modèle (créé à chaque appel ; l'état est en base).
        rate_per_minute: override optionnel ; sinon valeur depuis settings (ALBERT_RATE_PER_MINUTE_BY_MODEL
        ou ALBERT_RATE_PER_MINUTE_DEFAULT).
        """
        if not self._use_rate_limiter:
            return None
        effective_rate = (
            rate_per_minute
            if rate_per_minute is not None
            else settings.ALBERT_RATE_PER_MINUTE_BY_MODEL.get(
                model, settings.ALBERT_RATE_PER_MINUTE_DEFAULT
            )
        )
        return RateGate(effective_rate, key=f"{model}_{effective_rate}")

    def _api_call(
        self,
        func_api: Callable[[], T],
        *,
        max_retries: int,
        retry_delay: float,
        retry_short_delay: float,
        limiter: RateGate | None = None,
    ) -> T:
        """Appelle func_api() en boucle avec retry. func_api doit lever LLMApiError en cas d'erreur."""
        for attempt in range(max_retries + 1):
            if limiter:
                limiter.wait_turn()
            try:
                return func_api()
            except LLMApiError as e:
                # 429 / 5xx / erreurs réseau → retry. 4xx (ex. 400) = faute client → pas de retry.
                if e.code == "HTTP_429":
                    effective_delay = retry_delay
                elif e.code.startswith("HTTP_5") or e.code.startswith("ERROR_"):
                    effective_delay = retry_short_delay
                else:
                    raise  # 4xx : on relève tout de suite
                if attempt < max_retries:
                    wait_time = effective_delay * (1 + 0.1 * random.random()) * (attempt + 1)
                    logger.warning("%s, wait %.1fs before retry (%d/%d)", e.code, wait_time, attempt + 1, max_retries)
                    time.sleep(wait_time)
                    continue
                raise

    def ask_llm(
        self,
        messages: list[dict],
        model: str,
        response_format: dict = None,
        temperature: float = 0.0,
        rate_per_minute: int | None = None,
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
            model: Nom du modèle à utiliser (ex. "openweight-medium").
            response_format: Format de réponse à utiliser
            temperature: Température pour la génération (0.0 = déterministe)
            rate_per_minute: Override optionnel pour la limite (sinon depuis settings par modèle, défaut 100).
            max_retries: Nombre maximum de tentatives en cas d'erreur 429 (défaut: 3)
            retry_delay: Délai d'attente en secondes entre les tentatives erreur rate limit (défaut: 60)
            retry_short_delay: Délai d'attente en secondes entre les tentatives erreur 5XX (défaut: 10)

        Returns:
            Réponse du LLM

        Raises:
            Exception: Si toutes les tentatives échouent ou si l'erreur n'est pas de type 429
        """
        max_retries = max(0, max_retries)
        limiter = self._get_limiter(model, rate_per_minute)

        def _do_call() -> str:
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    response_format=response_format if response_format else None,
                )
                return response.choices[0].message.content.strip()
            except APIError as e:
                raise LLMApiError.from_api_error(e) from e

        content = self._api_call(
            _do_call,
            max_retries=max_retries,
            retry_delay=retry_delay,
            retry_short_delay=retry_short_delay,
            limiter=limiter,
        )
        return json.loads(content) if response_format else content

    def ocr_pdf(
        self,
        pdf_content: bytes,
        model: str = "mistral-ocr-2512",
        rate_per_minute: int | None = None,
        max_retries: int = 3,
        retry_delay: float = 60,
        retry_short_delay: float = 10,
    ) -> str:
        """
        Envoie le contenu d'un PDF à l'API OCR et retourne le texte extrait (markdown).

        Retry : 429 (retry_delay), 5XX et erreurs de connexion (retry_short_delay).
        À utiliser dans extract_text_from_pdf (processor) quand le PDF est un scan / peu de texte.
        rate_per_minute: Override optionnel pour la limite (sinon depuis settings par modèle, défaut 100).
        """
        max_retries = max(0, max_retries)
        url = urljoin(self.base_url.rstrip("/") + "/", "/ocr".lstrip("/"))
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "document": _build_pdf_document_payload(pdf_content),
            "include_image_base64": False,
        }

        def _do_call() -> str:
            post = (self._ocr_http_client.post if self._ocr_http_client else httpx.post)
            try:
                response = post(url, headers=headers, json=payload, timeout=180.0)
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                raise LLMApiError(
                    f"OCR API error: {e!s}",
                    code=f"ERROR_{e.__class__.__name__}",
                    details=str(e),
                ) from e
            if response.is_success:
                return _extract_markdown_from_ocr_response(response.json())
            raise LLMApiError(
                f"OCR API error: {response.status_code}",
                code=f"HTTP_{response.status_code}",
                details=response.text,
            )

        return self._api_call(
            _do_call,
            max_retries=max_retries,
            retry_delay=retry_delay,
            retry_short_delay=retry_short_delay,
            limiter=self._get_limiter(model, rate_per_minute),
        )
