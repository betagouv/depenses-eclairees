# Flux de données

## Séquence complète : de la synchronisation à la vue 360°

```mermaid
sequenceDiagram
    participant CRON as Cron (4×/jour)
    participant DJANGO as Django
    participant API as API Chorus/SAP
    participant S3 as S3 Storage
    participant REDIS as Redis
    participant CELERY as Celery Worker
    participant ALBERT as API Albert (LLM)
    participant PG as PostgreSQL

    CRON->>DJANGO: launch_pipeline --timedelta 7d
    
    rect rgb(230, 240, 255)
        Note over DJANGO,API: Phase 1 — Synchronisation
        DJANGO->>API: sync_engagements() (OAuth2)
        API-->>DJANGO: Liste num_ej modifiés
        DJANGO->>API: sync_documents() (métadonnées PJ)
        API-->>DJANGO: Métadonnées (nom, taille, date)
        DJANGO->>API: download_documents()
        API-->>S3: Fichiers (PDF, DOCX, etc.)
        DJANGO->>PG: init_documents_from_external()
    end

    rect rgb(255, 240, 230)
        Note over DJANGO,CELERY: Phase 2 — Lancement batch
        DJANGO->>REDIS: launch_batch() → group de chains
        REDIS->>CELERY: Dispatch tâches
    end

    rect rgb(230, 255, 230)
        Note over CELERY,ALBERT: Phase 3 — Pipeline par document
        CELERY->>S3: Lecture fichier
        S3-->>CELERY: Contenu binaire
        
        Note over CELERY: Étape 1 : text_extraction
        CELERY->>CELERY: PyMuPDF / Tesseract / LibreOffice
        alt PDF scanné (< 50 mots)
            CELERY->>ALBERT: ocr_pdf (mistral-ocr-2512)
            ALBERT-->>CELERY: Texte OCR (markdown)
        end
        CELERY->>PG: Document.text, is_ocr, nb_mot
        
        Note over CELERY: Étape 2 : classification
        CELERY->>ALBERT: ask_llm (openweight-medium = mistral-small)<br/>filename + text[:2000]
        ALBERT-->>CELERY: JSON array de catégories
        CELERY->>PG: Document.classification
        
        Note over CELERY: Étape 3 : content_analysis
        CELERY->>ALBERT: ask_llm (mistral-medium-2508)<br/>texte complet + prompt attributs
        ALBERT-->>CELERY: JSON structuré
        CELERY->>CELERY: post_processing (IBAN, SIRET, montants...)
        CELERY->>PG: Document.llm_response + structured_data
    end

    Note over DJANGO,PG: Consultation
    DJANGO->>PG: SELECT documents WHERE num_ej = ?
    PG-->>DJANGO: Documents + structured_data
    DJANGO-->>CRON: Vue 360° (DSFR)
```

## Planification cron

Défini dans `cron.json` :

| Heure | Commande | Particularité |
|---|---|---|
| 02:00 | `launch_pipeline --timedelta 7d` | Incrémental (ne ré-analyse pas les documents déjà traités) |
| 06:00 | `launch_pipeline --timedelta 7d` | Incrémental |
| 11:00 | `launch_pipeline --timedelta 7d` | Incrémental |
| 20:00 | `launch_pipeline --timedelta 7d --force-analyze` | Force la ré-analyse de tous les documents |

## Mécanisme de retry des batchs

```mermaid
flowchart TD
    A[Batch en cours] -->|30 min sans MAJ| B{close_and_retry_stuck_batches}
    B -->|Annuler batch| C[Status = CANCELLED]
    B -->|Filtrer jobs| D[Jobs FAILURE ou CANCELLED]
    D -->|Recréer batch| E[Nouveau batch = retry_of ancien]
    E -->|Relancer| F[launch_batch avec les jobs échoués]
```

**Source** : `docia/file_processing/pipeline/pipeline.py`, `cron.json`
