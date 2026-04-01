# Vue d'ensemble de l'architecture

## Diagramme C4 — Niveau Contexte

```mermaid
C4Context
    title Dépenses Éclairées — Diagramme de contexte

    Person(user, "Agent AIFE", "Utilisateur de la vue 360°")
    System(docia, "Dépenses Éclairées", "Application Django + Celery<br/>Extraction documentaire IA")
    System_Ext(chorus, "API Chorus / SAP", "Source des EJ et PJ<br/>Protocole OData, OAuth2")
    System_Ext(albert, "API Albert (DINUM)", "LLM Mistral<br/>Classification, extraction, OCR")
    System_Ext(grist, "Grist", "Base collaborative<br/>Métriques et données de test")

    Rel(user, docia, "Consulte la vue 360°<br/>Recherche par num_ej")
    Rel(docia, chorus, "Synchronise EJ + PJ<br/>OAuth2 client_credentials")
    Rel(docia, albert, "Classification, extraction,<br/>OCR PDF scannés")
    Rel(docia, grist, "Export métriques<br/>Import données de test")
```

## Diagramme C4 — Niveau Conteneur

```mermaid
C4Container
    title Dépenses Éclairées — Conteneurs

    Person(user, "Agent AIFE")

    Container_Boundary(scalingo, "Scalingo PaaS") {
        Container(web, "Django 5.2", "Python 3.13", "Vue 360°, admin, auth OIDC,<br/>commandes de gestion")
        Container(celery, "Celery Workers", "Python 3.13", "Pipeline extraction :<br/>text_extraction → classification<br/>→ content_analysis")
        Container(redis, "Redis", "Broker", "File de messages Celery")
        ContainerDb(pg, "PostgreSQL 16", "SQL", "EJ, documents,<br/>résultats d'extraction,<br/>état du pipeline")
        Container(s3, "S3", "Object Storage", "Fichiers PDF, DOCX, etc.")
    }

    System_Ext(chorus, "API Chorus / SAP")
    System_Ext(albert, "API Albert (DINUM)")

    Rel(user, web, "HTTPS")
    Rel(web, redis, "Enqueue tasks")
    Rel(redis, celery, "Dispatch tasks")
    Rel(celery, pg, "Read/Write")
    Rel(celery, s3, "Read fichiers")
    Rel(celery, albert, "HTTPS — LLM + OCR")
    Rel(web, pg, "ORM Django")
    Rel(web, chorus, "Sync EJ + PJ")
```

## Stack technique

| Couche | Technologie | Version | Source |
|---|---|---|---|
| Langage | Python | ~3.13 | `pyproject.toml` |
| Framework web | Django | ~5.2 | `pyproject.toml` |
| API REST | Django REST Framework | ~3.16 | `pyproject.toml` |
| File d'attente | Celery + Redis | ≥5.5.3 | `pyproject.toml`, `Procfile` |
| Base de données | PostgreSQL | 16 (CI) | `ci.env` |
| OCR local | Tesseract (tesserocr) | ≥2.9.1 | `pyproject.toml`, `Aptfile` |
| OCR distant | Mistral OCR via Albert API | mistral-ocr-2512 | `docia/file_processing/llm/client.py` |
| LLM | OpenAI SDK → Albert (Mistral) | openweight-medium (alias: mistral-small), mistral-medium-2508 | `docia/file_processing/llm/client.py` |
| PDF | PyMuPDF (pymupdf) | — | `pyproject.toml` |
| Auth | mozilla-django-oidc + django-lasuite | — | `pyproject.toml` |
| Stockage fichiers | django-storages (S3) ou FileSystem | — | `pyproject.toml`, `docia/settings.py` |
| UI | Django DSFR | ≥3.2 | `pyproject.toml` |
| Gestion dépendances | Poetry | — | `pyproject.toml` |

## Dépendances notables

| Paquet | Usage |
|---|---|
| `openai` | Client SDK pour appeler l'API Albert via le protocole OpenAI |
| `schwifty` | Validation IBAN (ISO 13616) |
| `tesserocr` + `Pillow` | OCR local Tesseract pour images |
| `pymupdf` | Extraction texte PDF natif + rendu pixmap pour OCR |
| `docx2txt`, `openpyxl`, `xlrd`, `olefile` | Extraction texte doc/xls/ods |

!!! warning "Dépendances inutilisées en production"

    `faiss-cpu`, `scikit-learn`, `tiktoken`, `ipykernel`, `jupyter` sont dans les dépendances de production mais semblent être des vestiges de l'ancienne approche RAG/embedding. Elles ne sont pas utilisées dans le pipeline actuel.

**Source** : `pyproject.toml`, `Aptfile`, `docia/settings.py`
