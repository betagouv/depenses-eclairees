import enum
import logging
import random
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from django.conf import settings

import pydantic
import requests
from requests import HTTPError

logger = logging.getLogger(__name__)


class ApiRawDocumentMetadata(pydantic.BaseModel):
    """Raw representation of document metadata from API"""

    id_pj: str = pydantic.Field(..., description="Document ID")
    nom_pj: str = pydantic.Field(..., description="Document name")
    num_ej: str = pydantic.Field(..., description="Engagement number")
    size_pj: str = pydantic.Field(..., description="Document size")
    date_pj: str = pydantic.Field(..., description="Document date")


@dataclass
class ApiDocumentMetadata:
    """Represents processed document metadata with normalized values."""

    id: str
    name: str
    num_ej: str
    size: int
    date: datetime

    @classmethod
    def from_raw_doc(cls, doc: ApiRawDocumentMetadata):
        try:
            size = int(doc.size_pj)
        except (ValueError, TypeError):
            logger.warning(f"Invalid size_pj value: {doc.size_pj}, defaulting to -1")
            size = -1
        # Normalize name
        name_nfc = unicodedata.normalize("NFC", doc.nom_pj)
        date = parse_api_datetime(doc.date_pj)
        return cls(
            id=doc.id_pj,
            name=name_nfc,
            num_ej=doc.num_ej,
            size=size,
            date=date,
        )


class ApiRawEngagementActivity(pydantic.BaseModel):
    alerte: str = pydantic.Field(...)
    num_ej: str = pydantic.Field(...)
    date_reception: str = pydantic.Field(...)  # Format '/Date(<timestamp ms>)/'
    pur_org: str = pydantic.Field(...)
    pur_group: str = pydantic.Field(...)


@dataclass
class ApiEngagementActivity:
    class Type(enum.StrEnum):
        CREATE = "CREATE"
        UPDATE = "UPDATE"

    type: Type
    num_ej: str = pydantic.Field(...)
    purchase_organization: str = pydantic.Field(...)
    purchase_group: str = pydantic.Field(...)
    received_at: datetime = pydantic.Field(...)

    @classmethod
    def from_raw_activity(cls, activity: ApiRawEngagementActivity):
        return cls(
            type=cls.parse_type(activity.alerte),
            num_ej=activity.num_ej,
            purchase_organization=activity.pur_org,
            purchase_group=activity.pur_group,
            received_at=parse_api_datetime(activity.date_reception),
        )

    @classmethod
    def parse_type(cls, value: str) -> Type:
        if value.endswith("Création"):
            return cls.Type.CREATE
        elif value.endswith("Modification"):
            return cls.Type.UPDATE
        else:
            raise ValueError(f"Invalid type {value!r}")


def parse_api_datetime(value: str) -> datetime:
    m = re.match(r"/Date\((?P<timestamp>[0-9]+)\)/", value)
    if not m:
        raise ValueError(f"Invalid datetime format {value!r}")
    ts_ms = int(m.group("timestamp"))
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)


def datetime_to_api(value: datetime) -> str:
    s = value.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
    return f"datetime'{s}'"


class SyncApiError(Exception):
    message: str
    code: str
    details: any

    def __init__(self, message: str, *, code: str, details: any):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details

    @classmethod
    def from_httperror(cls, err: HTTPError):
        return cls(
            message=str(err),
            code=f"HTTP_{err.response.status_code}",
            details=err.response.text,
        )


class SyncClient:
    def __init__(
        self,
        base_url: str,
        auth_base_url: str,
        client_id: str,
        client_secret: str,
        env: Literal["prod", "sandbox"],
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
        self.is_authenticated = False

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
        self.is_authenticated = True

    def list_documents_for_ej(
        self, num_ej: str, object_type: str = "BUS2201", return_raw: bool = False
    ) -> list[ApiDocumentMetadata]:
        """Get list of documents associated with an engagement number"""
        endpoint = "export_pj_ej/pieces_jointes_metadata"
        params = {"$filter": f"num_ej eq '{num_ej}' and object_type eq '{object_type}'"}

        response = self.session.get(
            self.base_url + endpoint,
            params=params,
        )
        response.raise_for_status()

        data = response.json()

        if return_raw:
            return data

        result = []
        doc_by_id = {}  # Save already processed docs to remove duplicates
        for doc_data in data["d"]["results"]:
            try:
                raw_doc = ApiRawDocumentMetadata(**doc_data)
                doc = ApiDocumentMetadata.from_raw_doc(raw_doc)
                # Remove duplicates on the fly
                if doc.id not in doc_by_id:
                    result.append(doc)
                    doc_by_id[doc.id] = doc
                else:
                    # Make sure it's a true duplicate (same filename and size)
                    duplicate = doc_by_id[doc.id]
                    if duplicate != doc:
                        raise ValueError(f"Invalid duplicate: {duplicate!r} != {doc!r}")

            except pydantic.ValidationError as e:
                logger.warning(f"Validation error for document data={data!r} error={e}")
                raise
        return result

    def list_ej_place(
        self,
        start: datetime,
        end: datetime,
        purchase_organization: str,
        purchase_group: str,
        return_raw: bool = False,
    ) -> list[ApiEngagementActivity]:
        """
        Liste les EJ (actes d'engagement) dans le périmètre défini.
        Un seul OA et un seul GA sont supportés (strings).
        """
        start_api = datetime_to_api(start)
        end_api = datetime_to_api(end)

        endpoint = "export_pj_ej/liste_ej_place"
        filter_str = (
            f"date_reception ge {start_api} and "
            f"date_reception le {end_api} and "
            f"pur_org eq '{purchase_organization}' and pur_group eq '{purchase_group}'"
        )
        response = self.session.get(
            self.base_url + endpoint,
            params={"$filter": filter_str},
        )
        response.raise_for_status()
        data = response.json()

        if return_raw:
            return data

        result = []
        for obj_data in data["d"]["results"]:
            try:
                raw_obj = ApiRawEngagementActivity(**obj_data)
                obj = ApiEngagementActivity.from_raw_activity(raw_obj)
                result.append(obj)
            except pydantic.ValidationError as e:
                logger.warning(f"Validation error for object {data!r} error={e}")
                raise
        return result

    def download_document(self, doc_id: str, *, max_retries: int = 0, retry_delay: float = 0) -> bytes:
        """Download document content by ID"""
        endpoint = f"export_pj_ej/pieces_jointes_data('{doc_id.strip()}')/$value"

        def _do_call():
            response = self.session.get(
                self.base_url + endpoint,
            )
            response.raise_for_status()
            return response.content

        return self._retry_call(_do_call, max_retries=max_retries, retry_delay=retry_delay)

    def _retry_call(
            self,
            func_api,
            *,
            max_retries: int,
            retry_delay: float,
    ):
        """Appelle func_api() en boucle avec retry. func_api doit lever SyncApiError en cas d'erreur."""
        for attempt in range(max_retries + 1):
            try:
                return func_api()
            except HTTPError as err:
                # 429 / 5xx / erreurs réseau → retry. 4xx (ex. 400) = faute client → pas de retry.
                if err.response.code == 429:
                    effective_delay = retry_delay
                elif 500 <= err.response.status_code < 600:
                    effective_delay = retry_delay
                else:
                    raise  # 4xx : on relève tout de suite
                if attempt < max_retries:
                    wait_time = effective_delay * (1 + 0.1 * random.random()) * (attempt + 1)
                    logger.warning("%s, wait %.1fs before retry (%d/%d)", err.code, wait_time, attempt + 1, max_retries)
                    time.sleep(wait_time)
                    continue
                raise SyncApiError.from_httperror(err)
