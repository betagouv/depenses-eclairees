# Schéma de base de données

## Diagramme ER

```mermaid
erDiagram
    User {
        UUID id PK
        string sub "OIDC subject"
        string full_name
        string short_name
        string email UK
        string admin_email
    }

    DataEngagement {
        UUID id PK
        string num_ej UK "max 20 chars"
        string designation
        string descriptif_prestations
        string date "CharField — réponse LLM libre"
        string prestataire
        string administration
        string siret
        json sources_et_conflits
        date date_creation
        datetime external_updated_at
    }

    DataEngagementItems {
        UUID id PK
        string num_ej FK
        string poste_ej
        string num_contrat
        string groupe_marchandise
        string centre_financier
    }

    Document {
        UUID id PK
        string filename
        file file "max 1000 chars"
        string extension
        string dossier
        text text
        bool is_ocr
        int nb_mot
        text relevant_content "NON PEUPLE"
        bool is_embedded
        json llm_response
        json structured_data
        string classification
        string classification_type
        datetime analyzed_at
        string hash UK
        int taille
        string batch
        date date_creation
    }

    DataBatch {
        UUID id PK
        string batch
        string ej FK
    }

    EngagementScope {
        UUID id PK
        string purchase_organization
        string purchase_group
    }

    DataProgrammesMinisteriels {
        UUID id PK
        int programme UK
        string libelle
        string nom_ministere
    }

    ProcessDocumentBatch {
        UUID id PK
        string folder
        array target_classifications
        array steps
        string status
        string celery_task_id
        UUID retry_of FK "self"
    }

    ProcessDocumentJob {
        UUID id PK
        UUID batch FK
        UUID document FK
        string status
        string celery_task_id
    }

    ProcessDocumentStep {
        UUID id PK
        UUID job FK
        string step_type
        int order
        string status
        string error
        text traceback
        string celery_task_id
        datetime started_at
        datetime finished_at
        duration duration
    }

    FileInfo {
        UUID id PK
        string external_id UK
        UUID parent FK "self"
        file file
        string filename
        string folder
        string extension
        int size
        string hash
        date created_date
        string original_filename
    }

    ExternalDocumentMetadata {
        UUID id PK
        string external_id UK
        string name
        int size
        datetime date
    }

    ExternalLinkDocumentOrder {
        UUID id PK
        UUID external_document FK
        string order_id
    }

    DownloadDocumentError {
        UUID id PK
        UUID external_document FK
        string message
    }

    RateGateState {
        string key PK
        datetime next_allowed_at
    }

    RateLimitCount {
        UUID id PK
        string key
        string interval
        int count
        datetime expiry
    }

    TrackingEvent {
        UUID id PK
        string category
        string action
        string name
        string page_url
        string user_agent
        UUID user FK
        string num_ej
    }

    DataEngagement }o--o{ Document : "M2M (docia_document_engagements)"
    DataEngagement ||--o{ DataBatch : "via num_ej"
    DataEngagement ||--o{ DataEngagementItems : "via num_ej"
    EngagementScope }o--o{ DataEngagement : "M2M"
    ProcessDocumentBatch ||--o{ ProcessDocumentJob : "batch"
    ProcessDocumentJob ||--|| Document : "document"
    ProcessDocumentJob ||--o{ ProcessDocumentStep : "job"
    ProcessDocumentBatch ||--o| ProcessDocumentBatch : "retry_of (self)"
    FileInfo ||--o| FileInfo : "parent (self)"
    ExternalDocumentMetadata ||--o{ ExternalLinkDocumentOrder : "external_document"
    ExternalDocumentMetadata ||--o{ DownloadDocumentError : "external_document"
    User ||--o{ TrackingEvent : "user"
```

## Tables par domaine

### Domaine métier (Documents)

| Table Django | Table SQL | Rôle |
|---|---|---|
| `Document` | `docia_document` | Document avec texte extrait, classification et données structurées |
| `DataEngagement` | `engagements` | Engagement juridique (EJ) synchronisé depuis Chorus |
| `DataEngagementItems` | `engagements_items` | Postes d'un EJ (numéro contrat, groupe marchandise, centre financier) |
| `DataBatch` | `batch` | Association batch legacy → EJ |
| `EngagementScope` | `docia_engagementscope` | Périmètre d'accès (purchase org/group) |
| `DataProgrammesMinisteriels` | `programmes_ministeriels` | Référentiel programmes ministériels |

### Domaine pipeline

| Table Django | Table SQL | Rôle |
|---|---|---|
| `ProcessDocumentBatch` | `docia_processdocumentbatch` | Batch de traitement (folder, steps, status) |
| `ProcessDocumentJob` | `docia_processdocumentjob` | Job par document dans un batch |
| `ProcessDocumentStep` | `docia_processdocumentstep` | Étape d'un job (type, status, error, duration) |
| `FileInfo` | `docia_fileinfo` | Métadonnées fichier téléchargé |
| `ExternalDocumentMetadata` | `docia_externaldocumentmetadata` | Métadonnées document API externe |
| `ExternalLinkDocumentOrder` | `docia_externallinkdocumentorder` | Lien document → order ID externe |
| `DownloadDocumentError` | `docia_downloaddocumenterror` | Erreurs de téléchargement |

### Domaine technique

| Table Django | Table SQL | Rôle |
|---|---|---|
| `User` | `docia_user` | Utilisateur OIDC (ProConnect) |
| `TrackingEvent` | `docia_trackingevent` | Événements de suivi UI |
| `RateGateState` | `docia_rategatestate` | État du rate limiter LLM |
| `RateLimitCount` | `docia_ratelimitcount` | Compteurs rate limiting web |

!!! warning "Conventions de nommage mixtes"

    Les tables `engagements`, `engagements_items`, `batch`, `programmes_ministeriels` utilisent des noms personnalisés (`Meta.db_table`), tandis que les autres suivent la convention Django (`docia_*`). Cela reflète l'héritage du code legacy.

**Source** : `docia/documents/models.py`, `docia/file_processing/models.py`, `docia/common/models.py`, migrations
