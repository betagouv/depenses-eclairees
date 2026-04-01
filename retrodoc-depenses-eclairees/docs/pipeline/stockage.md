# Stockage

## Architecture de stockage

```mermaid
flowchart LR
    subgraph Fichiers
        S3["S3 (Scalingo)<br/>ou Filesystem local"]
    end
    
    subgraph Base de données
        PG["PostgreSQL 16"]
    end
    
    CELERY["Celery Workers"] -->|Fichiers binaires<br/>(PDF, DOCX, etc.)| S3
    CELERY -->|Texte extrait<br/>Classification<br/>Données structurées| PG
    DJANGO["Django Web"] -->|Lecture| PG
    DJANGO -->|Lecture fichiers| S3
```

## Stockage fichiers (S3)

| Paramètre | Valeur | Source |
|---|---|---|
| Backend | `storages.backends.s3boto3.S3Boto3Storage` ou filesystem | `DEFAULT_FILE_STORAGE` |
| Bucket | Variable `AWS_STORAGE_BUCKET_NAME` | `docia/settings.py` |
| Credentials | `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Variables d'environnement |
| Organisation | Par `folder` (identifiant batch) | `FileInfo.folder` |

Les fichiers sont stockés via le `FileField` Django (`Document.file`, `FileInfo.file`).

## Stockage en base (PostgreSQL)

### Résultats d'extraction

| Champ | Table | Type | Contenu |
|---|---|---|---|
| `text` | `docia_document` | `TextField` | Texte brut extrait (illimité) |
| `is_ocr` | `docia_document` | `BooleanField` | OCR utilisé ? |
| `nb_mot` | `docia_document` | `IntegerField` | Nombre de mots |
| `classification` | `docia_document` | `CharField` | Type de document (ex. `acte_engagement`) |
| `classification_type` | `docia_document` | `CharField` | Méthode (`llm`) |
| `llm_response` | `docia_document` | `JSONField` | Réponse brute du LLM |
| `structured_data` | `docia_document` | `JSONField` | Données post-traitées |
| `analyzed_at` | `docia_document` | `DateTimeField` | Horodatage analyse |
| `relevant_content` | `docia_document` | `TextField` | [NON PEUPLÉ DANS LE PIPELINE ACTUEL] |

### État du pipeline

| Champ | Table | Type | Contenu |
|---|---|---|---|
| `status` | `docia_processdocumentbatch` | `CharField` | `PENDING`, `RUNNING`, `SUCCESS`, `FAILURE`, `CANCELLED` |
| `status` | `docia_processdocumentjob` | `CharField` | Idem par document |
| `status` | `docia_processdocumentstep` | `CharField` | Idem par étape |
| `error` | `docia_processdocumentstep` | `TextField` | Message d'erreur |
| `traceback` | `docia_processdocumentstep` | `TextField` | Stack trace |
| `duration` | `docia_processdocumentstep` | `DurationField` | Durée d'exécution |

### Dédoublonnage

| Mécanisme | Table | Champ | Description |
|---|---|---|---|
| Hash document | `docia_document` | `hash` (unique) | SHA256 du contenu fichier |
| Hash fichier | `docia_fileinfo` | `hash` | SHA256 du fichier téléchargé |
| ID externe | `docia_fileinfo` | `external_id` (unique) | Identifiant API externe |
| ID externe | `docia_externaldocumentmetadata` | `external_id` (unique) | Identifiant API externe |

!!! warning "Double chemin de dédoublonnage"

    Le `Document.hash` et `FileInfo.hash` servent tous deux au dédoublonnage mais passent par des chemins différents. Le lien entre `Document` et `FileInfo` n'est pas direct (pas de FK visible).

!!! info "Pas de contrainte de taille"

    Les champs `Document.text` et `Document.structured_data` n'ont pas de limite de taille. En PostgreSQL, `TextField` et `JSONField` sont illimités. Un document très volumineux produira un `text` très long stocké en base.

**Source** : `docia/documents/models.py`, `docia/file_processing/models.py`, `docia/settings.py`
