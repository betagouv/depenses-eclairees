import logging
import unicodedata
from dataclasses import dataclass
from typing import Literal

from django.conf import settings

import pydantic
import requests

logger = logging.getLogger(__name__)


class ApiRawDocumentMetadata(pydantic.BaseModel):
    """Raw representation of document metadata from API"""

    id_pj: str = pydantic.Field(..., description="Document ID")
    nom_pj: str = pydantic.Field(..., description="Document name")
    num_ej: str = pydantic.Field(..., description="Engagement number")
    size_pj: str = pydantic.Field(..., description="Document size")


@dataclass
class ApiDocumentMetadata:
    """Represents processed document metadata with normalized values."""

    id: str
    name: str
    num_ej: str
    size: int

    @classmethod
    def from_raw_doc(cls, doc: ApiRawDocumentMetadata):
        try:
            size = int(doc.size_pj)
        except (ValueError, TypeError):
            logger.warning(f"Invalid size_pj value: {doc.size_pj}, defaulting to -1")
            size = -1
        # Normalize name
        name_nfc = unicodedata.normalize("NFC", doc.nom_pj)
        return cls(
            id=doc.id_pj,
            name=name_nfc,
            num_ej=doc.num_ej,
            size=size,
        )


class SyncClient:
    def __init__(
        self,
        base_url: str,
        auth_base_url: str,
        client_id: str,
        client_secret: str,
        env: Literal["prod","sandbox"],
    ):
        self.base_url = base_url
        if not self.base_url.endswith("/"):
            self.base_url += "/"
        self.auth_base_url = auth_base_url
        if not self.auth_base_url.endswith("/"):
            self.auth_base_url += "/"
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = ""
        self.session = requests.Session()
        self.env = env

    @classmethod
    def from_settings(cls):
        return cls(
            base_url=settings.FILE_SYNC_API_BASE_URL,
            auth_base_url=settings.FILE_SYNC_AUTH_BASE_URL,
            client_id=settings.FILE_SYNC_CLIENT_ID,
            client_secret=settings.FILE_SYNC_CLIENT_SECRET,
            env=settings.FILE_SYNC_ENV,
        )

    def authenticate(self):
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "openid",
        }
        response = self.session.post(
            self.auth_base_url + "oauth/token",
            data=data,
        )
        data = response.json()
        self.token = data["access_token"]
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            }
        )

    def list_documents_for_ej(self, num_ej: str) -> list[ApiDocumentMetadata]:
        """Get list of documents associated with an engagement number"""
        endpoint = "export_pj_ej/pieces_jointes_metadata"
        if self.env == "prod":
            params = {"$filter": f"num_ej eq '{num_ej}'"}
        else:
            object_type = "BUS2201"
            params = {"$filter": f"num_ej eq '{num_ej}' and object_type eq '{object_type}'"}

        response = self.session.get(
            self.base_url + endpoint,
            params=params,
        )
        response.raise_for_status()

        data = response.json()

        result = []
        for doc_data in data["d"]["results"]:
            try:
                raw_doc = ApiRawDocumentMetadata(**doc_data)
                doc = ApiDocumentMetadata.from_raw_doc(raw_doc)
                result.append(doc)
            except pydantic.ValidationError as e:
                logger.warning(f"Validation error for document data={data!r} error={e}")
                raise
        return result

    def download_document(self, doc_id: str) -> bytes:
        """Download document content by ID"""
        endpoint = f"export_pj_ej/pieces_jointes_data('{doc_id.strip()}')/$value"
        response = self.session.get(
            self.base_url + endpoint,
        )
        response.raise_for_status()
        return response.content
