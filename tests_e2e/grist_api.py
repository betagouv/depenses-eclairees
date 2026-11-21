from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings

import pandas as pd
import requests

logger = logging.getLogger(__name__)

CLASSIF_GT_TABLE = "Classif_gt"
CLASSIF_GT_COLUMNS = (
    "filename",
    "num_ej",
    "hash",
    "classification",
    "is_ocr",
    "commentaire",
    "traitement",
    "text",
)


def auth_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.GRIST_API_KEY}",
    }


def get_tables() -> None:
    r = requests.get(settings.GRIST_DOCS_URL + "/tables", headers=auth_headers())
    print(json.dumps(r.json(), indent=4))


def fetch_all_records(table: str, *, page_size: int = 500) -> pd.DataFrame:
    """
    Récupère toutes les lignes d'une table Grist (pagination par id).
    """
    if not settings.GRIST_DOCS_URL or not settings.GRIST_API_KEY:
        raise RuntimeError("GRIST_DOCS_URL et GRIST_API_KEY requis")

    base_url = f"{settings.GRIST_DOCS_URL}/tables/{table}/records"
    all_records: list[dict[str, Any]] = []
    last_id = 0

    while True:
        params: dict[str, str | int] = {
            "limit": page_size,
            "sort": "id",
        }
        if last_id:
            params["filter"] = json.dumps({"id": [">", last_id]})
        r = requests.get(base_url, headers=auth_headers(), params=params, timeout=120)
        r.raise_for_status()
        payload = r.json()
        batch = payload.get("records", [])
        if not batch:
            break
        added = 0
        for rec in batch:
            rec_id = int(rec["id"])
            if rec_id <= last_id:
                continue
            row = {**rec.get("fields", {}), "id": rec_id}
            all_records.append(row)
            last_id = max(last_id, rec_id)
            added += 1
        if added == 0 or len(batch) < page_size:
            break
        logger.debug("Grist %s: fetched %s rows (last_id=%s)", table, len(all_records), last_id)

    return pd.DataFrame(all_records) if all_records else pd.DataFrame()


def get_data_from_grist(table: str) -> pd.DataFrame:
    """Rétrocompat : charge toute la table (paginé)."""
    return fetch_all_records(table)


def parse_classification_list(value: Any) -> list[str] | None:
    """Parse le champ classification Grist (liste JSON ou déjà liste)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    text = str(value).strip()
    if not text or text.lower() in ("nan", "none"):
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    out = [str(x).strip() for x in parsed if str(x).strip()]
    return out if out else None


def load_classif_gt(*, columns: tuple[str, ...] | None = None) -> pd.DataFrame:
    """
    Charge Classif_gt avec filtre aligné sur test_quality_classification.
    """
    cols = columns or CLASSIF_GT_COLUMNS
    df = fetch_all_records(CLASSIF_GT_TABLE)
    if df.empty:
        return df
    keep = [c for c in cols if c in df.columns]
    df = df[keep + (["id"] if "id" in df.columns and "id" not in keep else [])].copy()
    if "traitement" in df.columns:
        df = df[df["traitement"].astype(str).str.strip() != "non traité"]
    df["classification_parsed"] = df["classification"].map(parse_classification_list)
    df = df[df["classification_parsed"].notna()].copy()
    df["label_fine"] = df["classification_parsed"].map(lambda lst: lst[0])
    return df