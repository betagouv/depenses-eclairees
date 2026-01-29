"""
Client pour l'API OCR (OpenGateLLM / Albert), convention Mistral /v1/ocr.

Utilisé dans extract_text_from_pdf quand le PDF contient peu de texte
(scan/image) : envoie le contenu PDF à l'API et récupère le texte extrait.
"""

import base64
from urllib.parse import urljoin

import httpx

from docia.file_processing.llm.client import LLMClient

# Modèle OCR (image-to-text) exposé par l'API Albert / OpenGateLLM.
# https://albert.status.staging.etalab.gouv.fr/status/api
DEFAULT_OCR_MODEL = "mistral-ocr-2512"

OCR_ENDPOINT = "/ocr"


def _build_pdf_document_payload(pdf_content: bytes) -> dict:
    """
    Construit le "document" du payload : le PDF encodé en base64
    dans un data URI (format attendu par l'API).
    """
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


class OCRClient(LLMClient):
    """
    Client pour l'endpoint OCR. Réutilise api_key/base_url de LLMClient.
    Une seule méthode publique : extract_text(pdf_content) pour un PDF en entrée.
    """

    def __init__(
        self,
        ocr_model: str = DEFAULT_OCR_MODEL,
        api_key: str | None = None,
        base_url: str | None = None,
        http_client: httpx.Client | None = None,
        **kwargs,
    ):
        super().__init__(
            llm_model=ocr_model,
            api_key=api_key,
            base_url=base_url,
            http_client=http_client,
            **kwargs,
        )
        self._http = http_client or httpx.Client(timeout=120.0)

    def _ocr_post(self, payload: dict) -> dict:
        """
        Envoie une requête POST à /v1/ocr.

        payload : corps JSON de la requête HTTP (voir extract_text pour sa structure).
        """
        url = urljoin(self.base_url.rstrip("/") + "/", OCR_ENDPOINT.lstrip("/"))
        response = self._http.post(
            url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if not response.is_success:
            raise OCRApiError(
                f"OCR API error: {response.status_code}",
                status_code=response.status_code,
                details=response.text,
            )
        return response.json()

    def extract_text(self, pdf_content: bytes) -> str:
        """
        Envoie le contenu d'un PDF à l'API OCR et retourne le texte extrait (markdown).

        À utiliser dans extract_text_from_pdf quand le PDF est un scan / peu de texte.
        """
        # Payload = corps JSON de la requête POST : ce qu'on envoie à l'API
        # (modèle à utiliser, document à traiter, options).
        payload = {
            "model": self.llm_model,
            "document": _build_pdf_document_payload(pdf_content),
            "include_image_base64": False,
        }
        response_data = self._ocr_post(payload)
        return _extract_markdown_from_ocr_response(response_data)
