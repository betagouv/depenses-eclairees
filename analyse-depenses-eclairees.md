# Rétro-documentation — Dépenses Éclairées

**Date** : 31 mars 2026  
**Auteur** : Audit automatisé du code source  
**Périmètre** : Repository `depenses-eclairees` (branche courante)

---

## Phase 1 : Cartographie du repo

### 1.1 Langages, frameworks et dépendances

| Catégorie | Technologie | Version |
|---|---|---|
| Langage | Python | ~3.13 |
| Framework web | Django | ~5.2 |
| API REST | Django REST Framework | ~3.16 |
| File d'attente | Celery + Redis | ≥5.5.3 |
| Base de données | PostgreSQL | 16 (CI) |
| OCR local | Tesseract (tesserocr) | ≥2.9.1 |
| OCR distant | Mistral OCR via Albert API | mistral-ocr-2512 |
| LLM | OpenAI SDK → Albert (Mistral) | openweight-medium, mistral-medium-2508 |
| PDF | PyMuPDF (pymupdf) | — |
| Auth | mozilla-django-oidc + django-lasuite | — |
| Stockage fichiers | django-storages (S3) ou FileSystem | — |
| UI | Django DSFR (Design Système de l'État) | ≥3.2 |
| Gestion dépendances | Poetry | — |

**Dépendances notables** (`pyproject.toml`) :
- `openai` — client SDK pour appeler l'API Albert via le protocole OpenAI
- `schwifty` — validation IBAN (ISO 13616)
- `tesserocr` + `Pillow` — OCR local Tesseract pour images
- `pymupdf` — extraction texte PDF natif + rendu pixmap pour OCR
- `docx2txt`, `openpyxl`, `xlrd`, `olefile` — extraction texte doc/xls/ods
- `faiss-cpu`, `scikit-learn`, `tiktoken` — présents dans les dépendances mais non utilisés dans le pipeline actuel (probablement hérité de l'ancienne approche RAG/embedding)
- `pandas` — utilisée dans le legacy code (`app/`) et les tests e2e
- `moto` — mock AWS S3 pour les tests

### 1.2 Structure du repo

```
├── app/                          # Code legacy (pré-Django), partiellement encore utilisé
│   ├── ai_models/config_albert.py
│   ├── data/sql/
│   ├── file_manager/             # Nettoyage fichiers, extraction num_EJ, stats (legacy)
│   ├── grist/grist_api.py        # API Grist pour métriques/exports
│   ├── models/                   # Modèles SQLAlchemy legacy (marche.py, tiers.py)
│   └── processor/                # Prompts legacy (select_relevant_content, synthesis)
├── docia/                        # Application Django principale
│   ├── auth/                     # OIDC backend (ProConnect / LaSuite)
│   ├── common/models.py          # BaseModel, User
│   ├── documents/models.py       # DataEngagement, Document, EngagementScope, etc.
│   ├── file_processing/
│   │   ├── llm/client.py         # Client LLM (ask_llm + ocr_pdf)
│   │   ├── llm/rategate/         # Rate limiting distribué via PostgreSQL
│   │   ├── models.py             # ProcessDocumentBatch/Job/Step, FileInfo, etc.
│   │   ├── pipeline/             # Orchestration batch Celery
│   │   │   ├── pipeline.py       # launch_batch, sync_and_analyze, etc.
│   │   │   ├── steps/            # Étapes : text_extraction, classification, content_analysis
│   │   │   └── utils.py          # Suivi progression batch
│   │   ├── processor/
│   │   │   ├── analyze_content.py     # Extraction d'info structurée via LLM
│   │   │   ├── attributes/            # Définitions des champs à extraire par type doc
│   │   │   ├── attributes_query.py    # DataFrame des attributs
│   │   │   ├── classifier.py          # Classification LLM + catalogue catégories
│   │   │   ├── post_processing_llm.py # Post-traitement (IBAN, SIRET, montants, etc.)
│   │   │   ├── pdf_drawings.py        # Détection cases cochées dans PDF
│   │   │   └── text_extraction/       # Dispatch extraction texte par format
│   │   └── sync/                 # Synchronisation avec API externe (Chorus/SAP)
│   │       ├── client.py         # Client API externe (OAuth2 client_credentials)
│   │       ├── downloader.py     # Téléchargement documents + stockage S3
│   │       ├── sync_engagements.py
│   │       ├── sync_metadata.py
│   │       └── workflow.py       # Orchestration sync
│   ├── management/commands/
│   │   ├── launch_pipeline.py    # Commande Django pour lancer le pipeline
│   │   ├── display_batch_progress.py
│   │   ├── shell.py
│   │   └── sync_engagement_items.py
│   ├── migrations/               # ~30 migrations Django
│   ├── permissions/              # Vérification droits utilisateur sur EJ
│   ├── ratelimit/                # Rate limiting utilisateur web (200 requêtes/jour)
│   ├── templates/                # Templates DSFR (vue 360°)
│   └── tracking/                 # Évènements de suivi (Matomo-like)
├── tests/                        # Tests unitaires pytest
├── tests_e2e/                    # Tests de qualité extraction sur données réelles (Grist)
├── docker/
│   ├── Dockerfile-scalingo       # Image basée sur scalingo-24
│   └── Dockerfile-githubactions
├── scripts/                      # Scripts utilitaires (export SQL, MAJ Grist)
└── static/                       # CSS/JS frontend
```

### 1.3 Points d'entrée

| Point d'entrée | Fichier | Rôle |
|---|---|---|
| Serveur web | `Procfile` → `gunicorn docia.wsgi` | Application Django / vue 360° |
| Worker Celery (normal) | `Procfile` → `celery -Q celery` (concurrency=2) | Tâches pipeline standard |
| Worker Celery (heavy CPU) | `Procfile` → `celery -Q heavy_cpu` (concurrency=1) | Tâches gourmandes (OCR) |
| Cron pipeline | `cron.json` → `launch_pipeline --timedelta 7d` | 3×/jour (02h, 06h, 11h) + 1×/jour forcé (20h) |
| Post-deploy | `Procfile` → `python manage.py migrate` | Migration auto au déploiement |
| CI/CD | `.github/workflows/django.yml` | Tests pytest + ruff (lint) sur PR/push main |

### 1.4 Déploiement

- **Plateforme** : **Scalingo** (PaaS français, compatible 12-factor)
- **Docker** : Dockerfile basé sur `scalingo/scalingo-24`, Python 3.13, Poetry
- **Dépendances système** (Aptfile) : `tesseract-ocr`, `tesseract-ocr-fra`, `libtesseract-dev`, `libreoffice-core-nogui`, `libreoffice-writer-nogui`, `libreoffice-java-common`
- **Stockage fichiers** : S3 (configurable) ou filesystem local
- **Broker Celery** : Redis
- **Base de données** : PostgreSQL (variable `DATABASE_URL`)

### ⚠️ Points d'attention

- **Dépendances inutilisées** : `faiss-cpu`, `scikit-learn`, `tiktoken`, `ipykernel`, `jupyter` sont dans les dépendances de production mais semblent être des vestiges de l'ancienne approche RAG/embedding.
- **Double code legacy** : Le dossier `app/` contient du code pré-Django (SQLAlchemy, pandas) encore partiellement importé (`app.file_manager.cleaner`, `app.file_manager.extract_num_EJ`, `app.utils`).
- **LibreOffice en production** : Nécessaire pour convertir les fichiers `.doc` anciens. Ajoute ~200 Mo à l'image Docker.

### ❓ Questions ouvertes

- Quels workers Celery utilisent la queue `heavy_cpu` vs `celery` ? Le code ne semble pas router explicitement les tâches vers `heavy_cpu`.
- Le `docker-compose.yml` ne définit qu'un service `web` (pas de worker, pas de Redis, pas de PostgreSQL). Il semble incomplet pour le développement local.

---

## Phase 2 : Analyse du pipeline d'extraction

### 2.1 Flux de données de bout en bout

Le pipeline est déclenché par la commande `launch_pipeline` (cron ou manuelle) qui appelle `sync_and_analyze()` :

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        sync_and_analyze()                              │
│  docia/file_processing/pipeline/pipeline.py                            │
│                                                                        │
│  1. SYNC : Récupère les EJ modifiés depuis N jours via l'API externe  │
│     ├── sync_engagements() → liste num_ejs                            │
│     ├── sync_documents()   → récupère métadonnées PJ                  │
│     └── download_documents() → télécharge fichiers dans S3            │
│                                                                        │
│  2. INIT : Créer les enregistrements Document en base                 │
│     └── init_documents_from_external_filter_by_num_ejs()              │
│                                                                        │
│  3. BATCH : Lance un batch Celery de traitement                       │
│     └── launch_batch() → group de chains Celery                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Étapes du batch (par document)

Chaque document passe par 3 étapes **séquentielles** (Celery `chain`). Tous les documents d'un batch sont traités **en parallèle** (Celery `group`).

```python
DEFAULT_PROCESS_STEPS = [
    ProcessDocumentStepType.TEXT_EXTRACTION,
    ProcessDocumentStepType.CLASSIFICATION,
    ProcessDocumentStepType.CONTENT_ANALYSIS,
]
```

#### Étape 1 : Extraction de texte (`task_extract_text`)

**Fichier** : `docia/file_processing/pipeline/steps/text_extraction.py` → `docia/file_processing/processor/text_extraction/text_extraction.py`

- Dispatch selon l'extension du fichier :
  - **PDF** : extraction texte natif via PyMuPDF. Si < 50 mots → fallback OCR (Mistral OCR par défaut, ou Tesseract)
  - **DOCX** : `docx2txt`
  - **DOC** : conversion LibreOffice → txt, fallback docx2txt
  - **ODT** : parsing XML du zip
  - **TXT** : lecture directe UTF-8
  - **Images (PNG, JPG, TIFF)** : OCR Tesseract local (`tesserocr`)
  - **Excel (XLSX, XLS, ODS)** : extraction en format markdown (tables avec `|`)
- Stocke le résultat dans `Document.text`, `Document.is_ocr`, `Document.nb_mot`
- **Cas spécial PDF** : si le PDF est natif (> 50 mots), une étape supplémentaire d'enrichissement via `add_drawings_to_pdf` détecte les cases cochées (☒) dans les dessins vectoriels du PDF et les ajoute au texte extrait.

#### Étape 2 : Classification (`task_classify_document`)

**Fichier** : `docia/file_processing/pipeline/steps/classification.py` → `docia/file_processing/processor/classifier.py`

- Appelle le LLM (`openweight-medium`) avec le nom du fichier + les 2000 premiers caractères du texte
- Le LLM classe le document parmi **~50 catégories** définies dans `DIC_CLASS_FILE_BY_NAME`
- Utilise un `response_format` JSON Schema → la réponse est une liste ordonnée de catégories
- Prend la première catégorie retournée qui correspond à une clé connue
- Stocke dans `Document.classification` et `Document.classification_type = "llm"`

#### Étape 3 : Extraction d'informations structurées (`task_analyze_content`)

**Fichier** : `docia/file_processing/pipeline/steps/content_analysis.py` → `docia/file_processing/processor/analyze_content.py`

- **Condition** : uniquement pour les types de documents supportés (voir § 2.3)
- Utilise le contenu pertinent (`Document.relevant_content`) s'il existe, sinon le texte complet
- Appelle le LLM (`mistral-medium-2508`) avec un prompt construit dynamiquement depuis la définition des attributs du type de document
- Chaque type de document a sa propre liste d'attributs avec des consignes détaillées (`docia/file_processing/processor/attributes/`)
- Le format de sortie est spécifié via JSON Schema (`response_format`)
- **Post-traitement** (`post_processing_llm.py`) : nettoyage et validation des valeurs extraites (IBAN, SIRET, montants, adresses, noms de sociétés, etc.)
- Stocke le résultat dans `Document.llm_response` (réponse brute) et `Document.structured_data` (données nettoyées)

### 2.3 Types de documents supportés pour l'extraction d'informations

```python
SUPPORTED_DOCUMENT_TYPES = [
    "devis", "fiche_navette", "acte_engagement", "bon_de_commande",
    "avenant", "sous_traitance", "rib", "att_sirene", "kbis", "ccap",
]
```

Chaque type a sa définition d'attributs dans `docia/file_processing/processor/attributes/` :

| Type | Fichier | Attributs extraits (résumé) |
|---|---|---|
| `acte_engagement` | `acte_engagement.py` | objet_marche, forme_marche, administration, société, SIRET, SIREN, RIB, cotraitants, sous-traitants, montants HT/TTC/TVA, durée, dates signature/notification, CPV, avance, annexes financières |
| `ccap` | `ccap.py` | objet, ID marché, lots, forme marché, durée, montants par lot, CCAG référence, modalités reconduction |
| `rib` | `rib.py` | IBAN, BIC, titulaire, adresse postale, domiciliation, banque |
| `fiche_navette` | `fiche_navette.py` | administration, objet, société, accord-cadre, montant HT, TVA, centres de coût/financier, domaine fonctionnel, etc. |
| `sous_traitance` | `sous_traitance.py` | titulaire, sous-traitant, adresses, SIRET, montants, durée, RIB sous-traitant |
| `devis` | `devis.py` | (non lu intégralement) |
| `avenant` | `avenant.py` | (non lu intégralement) |
| `bon_de_commande` | `bon_de_commande.py` | (non lu intégralement) |
| `kbis` | `kbis.py` | (non lu intégralement) |
| `att_sirene` | `att_sirene.py` | (non lu intégralement) |
| `cctp` | `cctp.py` | Déclaré dans les attributs mais **absent de SUPPORTED_DOCUMENT_TYPES** |

### 2.4 Formats de fichiers traités

```python
SUPPORTED_FILES_TYPE = [
    "doc", "docx", "odt", "pdf", "txt",
    "jpg", "jpeg", "png", "tiff", "tif",
    "xlsx", "xls", "ods",
]
```

Les fichiers avec une extension non supportée sont **ignorés** (`SkipStepException`).

### 2.5 Mécanisme d'orchestration

- **Orchestration** : Celery avec Redis comme broker
- **Parallélisme** : Chaque document = 1 `chain` de 3 tâches séquentielles. L'ensemble des documents d'un batch = 1 `group`.
- **Concurrency** : Worker `celery` = 2 ; Worker `heavy_cpu` = 1
- **Cron** : 4 exécutions/jour — 3 incrémentales (documents des 7 derniers jours, pas de re-analyse) + 1 avec `--force-analyze` à 20h
- **Gestion des batchs bloqués** : `close_and_retry_stuck_batches()` détecte les batchs sans mise à jour depuis 30 min, les annule et relance les tâches échouées/annulées

### ⚠️ Points d'attention

- **Pas de limite de taille fichier explicite** dans le code pipeline. Le téléchargement utilise `max_retries = 2 if doc.size_mo < 21 else 0` (aucune retry au-dessus de 21 Mo, mais le téléchargement est quand même tenté).
- **Texte complet envoyé au LLM** : Si `relevant_content` est null (ce qui semble être le cas par défaut dans le pipeline actuel), c'est **tout le texte extrait** qui est envoyé au LLM. Pas de troncature explicite pour l'étape d'analyse.
- **La classification n'utilise que les 2000 premiers caractères** : suffisant pour la plupart des documents, mais peut poser problème pour les documents dont les informations discriminantes sont plus loin.
- **Le champ `relevant_content` n'est jamais peuplé** dans le pipeline actuel (pas d'appel visible à `select_relevant_content`). C'est probablement un vestige de l'ancienne approche RAG.

### ❓ Questions ouvertes

- Les tests e2e (`tests_e2e/`) sont-ils exécutés en CI ? Le workflow GitHub n'exécute que `pytest tests/`, pas `tests_e2e/`.
- Quelle est la taille typique des documents traités (en nombre de tokens) ? Y a-t-il un risque de dépasser la fenêtre de contexte du modèle ?

---

## Phase 3 : Analyse de la connexion Albert / LLM

### 3.1 Client LLM

**Fichier principal** : `docia/file_processing/llm/client.py`

Le client utilise le **SDK OpenAI** (`openai.OpenAI`) configuré pour pointer vers l'API Albert :

```python
self.client = OpenAI(
    api_key=self.api_key,       # settings.ALBERT_API_KEY
    base_url=self.base_url,     # settings.ALBERT_BASE_URL
    timeout=timeout,            # 180s par défaut
    max_retries=0,              # Retry géré manuellement
)
```

### 3.2 Configuration API

| Paramètre | Source | Valeur |
|---|---|---|
| URL de base | `ALBERT_BASE_URL` (env) | Non en dur dans le code (définie dans l'environnement) |
| API Key | `ALBERT_API_KEY` (env) | ⚠️ Secret — présence signalée, non reproduit |
| Protocole | Compatibilité OpenAI | `chat.completions.create()` + endpoint OCR spécifique |
| Timeout | Codé en dur | 180 secondes |
| Rate limiting | `ALBERT_USE_RATE_LIMITER` | Optionnel, basé sur PostgreSQL (`RateGateState`) |

### 3.3 Modèles utilisés

| Modèle | Usage | Temperature | Rate limit |
|---|---|---|---|
| `openweight-medium` | Classification des documents | 0.0 | 98 req/min |
| `mistral-medium-2508` | Extraction d'informations structurées | 0.0 | 98 req/min |
| `mistral-ocr-2512` | OCR de PDF scannés | — | 98 req/min |

### 3.4 Appels API — deux méthodes

#### `ask_llm()` — pour classification et extraction

```python
response = self.client.chat.completions.create(
    model=model,
    messages=messages,
    temperature=temperature,
    response_format=response_format,  # JSON Schema
)
return response.choices[0].message.content.strip()
```

Si `response_format` est fourni, la réponse est parsée en JSON : `json.loads(content)`.

#### `ocr_pdf()` — pour OCR

Appel REST direct (pas via SDK OpenAI) :

```python
url = urljoin(self.base_url, "/ocr")
headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
payload = {
    "model": "mistral-ocr-2512",
    "document": {"type": "document_url", "document_url": "data:application/pdf;base64,..."},
    "include_image_base64": False,
}
```

La réponse est structurée avec des pages, chaque page contenant du markdown. Le client reconstruit le texte avec des marqueurs `[[PAGE i / N]]`.

### 3.5 Prompts — Verbatim

#### Prompt de classification

**System prompt** :
```
Vous êtes un assistant qui aide à classer des fichiers en fonction de leur contenu.
```

**User prompt** (template) :
```
A partir du contenu du fichier, vous devez déterminer à quelles catégories le document appartient 
parmi les catégories suivantes. La réponse est une liste de catégories possibles, classée par ordre 
de correspondance avec le contenu du document.

Voici la liste des catégories possibles :
{categories_str}    ← jointure des ~50 catégories avec descriptions

Le titre du document est un élément essentiel pour la classification.
Si le type de document ne correspond à aucune des catégories, répondez "Non classifié".

Voici le nom du document (attention celui-ci peut être trompeur, il faut aussi regarder le contenu) : '{filename}'

Voici la première page du document :
<DEBUT PAGE>
'{text[:2000]}'
<FIN PAGE>

Format : répondez par une liste de catégories possibles (sans autre texte ni ponctuation).
```

**Response format** : JSON Schema → `{"type": "array", "items": {"type": "string"}}`

#### Prompt d'extraction d'informations

**System prompt** :
```
Vous êtes un assistant IA qui analyse des documents juridiques.
```

**User prompt** (template) :
```
Analyse le contexte suivant et réponds à la question : {question}

Contexte : {text}
```

Où `{question}` est construit dynamiquement à partir des attributs du type de document :

```
Extrait les informations clés et renvoie-les uniquement au format 
JSON spécifié, sans texte supplémentaire.

Format de réponse (commence par "{" et termine par "}") :
{
  "objet_marche": "", 
  "forme_marche": "", 
  ...
}

Instructions d'extraction :

OBJET
   Définition : l'objet du marché, c'est-à-dire ce qui a été acheté...
   [consignes détaillées par attribut]
```

**Response format** : JSON Schema spécifique par type de document, avec des `properties` correspondant aux attributs à extraire. Chaque propriété a son propre schéma (string, object, array, etc.).

### 3.6 Versionnement des prompts

Les prompts sont **définis en dur dans le code Python** :
- Prompt de classification : `docia/file_processing/processor/classifier.py` (fonctions `create_classification_prompt`)
- Prompts d'extraction : `docia/file_processing/processor/attributes/*.py` (champ `"consigne"` de chaque attribut)
- System prompts : en dur dans `classifier.py` et `analyze_content.py`

Il n'y a **pas de fichier séparé** pour les prompts, **pas de versionnement dédié**, et **pas de mécanisme de rollback**. Les prompts évoluent avec les commits Git ordinaires.

### 3.7 Format de sortie du LLM

- **Classification** : JSON array de strings (noms de catégories)
- **Extraction** : JSON object avec les attributs comme clés. Spécifié via `response_format` (JSON Schema strict). Le LLM est contraint de produire du JSON valide par l'API.

### 3.8 Gestion d'erreurs LLM

**Fichier** : `docia/file_processing/llm/client.py`, méthode `_api_call()`

```
Stratégie de retry (max_retries=3 par défaut) :
├── HTTP 429 (rate limit) → attente 60s × (attempt+1) × jitter → retry
├── HTTP 5xx (erreur serveur) → attente 10s × (attempt+1) × jitter → retry
├── Erreurs réseau/timeout → attente 10s × (attempt+1) × jitter → retry
└── HTTP 4xx (hors 429) → échec immédiat, pas de retry
```

Si toutes les tentatives échouent, l'exception `LLMApiError` remonte. L'`AbstractStepRunner` la capture, marque le step en `FAILURE`, enregistre l'erreur et le traceback, et **annule les étapes suivantes** du même job. Le batch continue pour les autres documents.

**Rate limiting distribué** : Si `ALBERT_USE_RATE_LIMITER=True`, un `RateGate` basé sur PostgreSQL (`SELECT ... FOR UPDATE`) assure un espacement minimum entre les requêtes. Utilise `clock_timestamp()` de PostgreSQL pour éviter les dérives d'horloge entre workers.

### ⚠️ Points d'attention

- **Pas de gestion de fenêtre de contexte** : Le texte complet du document est envoyé au LLM sans vérification du nombre de tokens. Un document long pourrait dépasser la fenêtre de contexte du modèle et produire une réponse tronquée ou une erreur.
- **Timeout de 180s** : Peut être insuffisant pour des documents très longs envoyés au LLM.
- **Le post-traitement peut lever des exceptions** (ex. `ValueError` dans `post_processing_duration` pour des champs manquants). Ces exceptions ne sont pas catchées au niveau du step, ce qui causerait un `FAILURE` de l'étape d'analyse et une perte de la réponse brute du LLM (la `llm_response` n'est pas sauvée en cas d'erreur de post-traitement car le `save()` n'est pas atteint).
- **L'API OCR (Mistral OCR) n'utilise pas le SDK OpenAI** : elle fait un appel HTTP direct (`httpx.post`). Ce n'est pas un problème fonctionnel mais complexifie la maintenance.

### ❓ Questions ouvertes

- Quelle est la taille de la fenêtre de contexte des modèles `openweight-medium` et `mistral-medium-2508` sur l'infrastructure Albert ?
- Le rate limiting distribué est-il activé en production (`ALBERT_USE_RATE_LIMITER`) ?
- Quelle est la disponibilité SLA de l'API Albert ?

---

## Phase 4 : Analyse du modèle de données

### 4.1 Base de données

**PostgreSQL** (configurable via `DATABASE_URL`). ORM Django avec migrations. Environ 30 fichiers de migration.

### 4.2 Schéma principal (ORM Django)

#### Tables métier — Documents

| Table | Modèle Django | Champs clés |
|---|---|---|
| `docia_document` | `Document` | `id` (UUID), `filename`, `file` (FileField, max 1000 chars), `extension`, `dossier`, `text` (TextField), `is_ocr` (bool), `nb_mot` (int), `relevant_content` (TextField), `llm_response` (JSON), `structured_data` (JSON), `classification`, `classification_type`, `analyzed_at`, `hash` (unique), `taille` |
| `engagements` | `DataEngagement` | `id` (UUID), `num_ej` (unique, max 20), `designation`, `descriptif_prestations`, `date`, `prestataire`, `administration`, `siret`, `sources_et_conflits` (JSON), `date_creation`, `external_updated_at` |
| `docia_document_engagements` | M2M through | `document_id`, `dataengagement_id` |
| `engagements_items` | `DataEngagementItems` | `num_ej`, `poste_ej`, `num_contrat`, `groupe_marchandise`, `centre_financier` |
| `batch` | `DataBatch` | `batch` (str), `ej` (FK → DataEngagement via num_ej) |
| `docia_engagementscope` | `EngagementScope` | `purchase_organization`, `purchase_group` + M2M vers DataEngagement et Group |
| `programmes_ministeriels` | `DataProgrammesMinisteriels` | `programme` (int unique), `libelle`, `nom_ministere` |

#### Tables pipeline

| Table | Modèle Django | Champs clés |
|---|---|---|
| `docia_processdocumentbatch` | `ProcessDocumentBatch` | `folder`, `target_classifications` (ArrayField), `steps` (ArrayField), `status`, `celery_task_id`, `retry_of` (self FK) |
| `docia_processdocumentjob` | `ProcessDocumentJob` | `batch` (FK), `document` (FK), `status`, `celery_task_id` |
| `docia_processdocumentstep` | `ProcessDocumentStep` | `job` (FK), `step_type`, `order`, `status`, `error`, `traceback`, `started_at`, `finished_at`, `duration` |
| `docia_fileinfo` | `FileInfo` | `external_id` (unique), `parent` (self FK), `file`, `filename`, `folder`, `extension`, `size`, `hash`, `created_date`, `original_filename` |
| `docia_externaldocumentmetadata` | `ExternalDocumentMetadata` | `external_id` (unique), `name`, `size`, `date` |
| `docia_externallinkdocumentorder` | `ExternalLinkDocumentOrder` | `external_document` (FK), `order_id` |
| `docia_downloaddocumenterror` | `DownloadDocumentError` | `external_document` (FK), `message` |
| `docia_rategatestate` | `RateGateState` | `key` (PK), `next_allowed_at` |
| `docia_ratelimitcount` | `RateLimitCount` | `key`, `interval`, `count`, `expiry` |

#### Tables auth et tracking

| Table | Modèle | Champs clés |
|---|---|---|
| `docia_user` | `User` | `sub` (OIDC), `full_name`, `short_name`, `email` (unique), `admin_email` |
| `docia_trackingevent` | `TrackingEvent` | `category`, `action`, `name`, `page_url`, `user_agent`, `user` (FK), `num_ej` |

### 4.3 Structure JSON de `structured_data`

Le champ `Document.structured_data` est un `JSONField` qui contient les informations extraites par le LLM puis post-traitées. La structure varie selon la classification :

**Exemple pour `acte_engagement`** :
```json
{
  "objet_marche": "Prestations de maintenance informatique",
  "forme_marche": {
    "lot_concerne": {"numero_lot": 2, "titre_lot": "Maintenance applicative"},
    "marche_subsequent": false,
    "marche_parent": "2024-AC-001"
  },
  "administration_beneficiaire": "Ministère de l'économie - Direction générale des finances publiques",
  "societe_principale": "Accenture",
  "siret_mandataire": "12345678901234",
  "siren_mandataire": "123456789",
  "rib_mandataire": {"banque": "BNP Paribas", "iban": "FR76 1234 5678 9012 3456 7890 123"},
  "cotraitants": [{"nom": "Capgemini", "siret": "98765432109876"}],
  "sous_traitants": [],
  "rib_autres": [],
  "montant_ht": "150000.00",
  "montant_ttc": "180000.00",
  "montant_tva": "0.20",
  "duree": {
    "duree_initiale": 36,
    "duree_reconduction": 12,
    "nb_reconductions": 2,
    "delai_tranche_optionnelle": null
  },
  "date_signature_mandataire": "01/01/2025",
  "date_signature_administration": "15/01/2025",
  "date_notification": "20/01/2025",
  "conserve_avance": "conserve",
  "montants_en_annexe": {"annexe_financière": false, "classification": null},
  "code_cpv": "72611000-6 Services de support informatique",
  "mode_consultation": "Procédure adaptée",
  "mode_reconduction": "tacite",
  "ligne_imputation_budgetaire": "0723-CDIE",
  "remise_catalogue": null
}
```

### 4.4 Le champ "objet de la dépense"

L'objet de la dépense est extrait sous différents noms selon le type de document :

| Type document | Champ | Source |
|---|---|---|
| `acte_engagement` | `objet_marche` | `docia/file_processing/processor/attributes/acte_engagement.py` |
| `ccap` | `objet_marche` | `docia/file_processing/processor/attributes/ccap.py` |
| `fiche_navette` | `objet` | `docia/file_processing/processor/attributes/fiche_navette.py` |
| `devis` | (non vérifié) | `docia/file_processing/processor/attributes/devis.py` |
| `bon_de_commande` | (non vérifié) | `docia/file_processing/processor/attributes/bon_de_commande.py` |

Le champ global `DataEngagement.designation` et `DataEngagement.descriptif_prestations` existent sur le modèle mais leur peuplement n'a pas été observé dans le pipeline actuel (les champs sont `null=True`). Le champ `sources_et_conflits` (JSON) pourrait servir à tracer les conflits de données entre documents.

### 4.5 Grist

**Fichier** : `app/grist/grist_api.py`

L'API Grist est utilisée pour :
1. **Exporter des données** vers une base Grist (métriques, suivi de production)
2. **Importer des données de référence** pour les tests e2e (données de vérité terrain)

Fonctions clés :
- `get_data_from_grist(table)` — récupère le contenu d'une table Grist
- `post_new_data_to_grist()` / `post_data_to_grist_multiple_keys()` — insère ou met à jour des données

Le script `scripts/maj_grist_from_scalingo.py` permet de pousser les données de production vers Grist.

### ⚠️ Points d'attention

- **Pas de schéma JSON validé** : Le `structured_data` est un `JSONField` libre. Pas de validation JSON Schema côté base de données, ni côté application (au-delà de ce que la réponse du LLM retourne).
- **Duplication de données** : Le `Document.hash` est utilisé pour dédupliquer, mais la table `FileInfo` contient aussi un `hash`. La relation document ↔ hash passe par deux chemins différents.
- **Tables legacy** : Les tables `engagements_items`, `batch`, `programmes_ministeriels` utilisent des noms de tables personnalisés (`db_table`) et des conventions de nommage différentes du reste du code Django.
- **Pas de contrainte de taille** sur `Document.text` et `Document.structured_data` : en production PostgreSQL, pas de limite technique, mais risque de documents très volumineux.

### ❓ Questions ouvertes

- Les champs `DataEngagement.designation`, `descriptif_prestations`, `prestataire`, `administration`, `siret` sont-ils peuplés par agrégation des `structured_data` des documents rattachés ? Ou manuellement ?
- Quel est le volume de données actuel (nombre d'EJ, de documents, taille de la base) ?

---

## Phase 5 : Analyse qualité & métriques

### 5.1 Score de confiance

Il **n'existe pas de score de confiance** explicite dans le pipeline. Le LLM est appelé avec `temperature=0.0` (déterministe) mais aucun score de probabilité ou de certitude n'est stocké.

Le seul proxy de qualité est le **taux de remplissage** calculé dans la vue web :

```python
# docia/views.py
def compute_ratio_data_extraction(document_data: dict) -> float:
    total_keys = len(document_data.keys())
    total_extracted = len([x for x in document_data.values() if x])
    return total_extracted / total_keys if total_keys > 0 else 0
```

Ce ratio est affiché sous forme de pourcentage dans l'interface.

### 5.2 Tests de qualité (e2e)

**Dossier** : `tests_e2e/`

Des tests de qualité existent pour les types principaux :
- `test_quality_acte_engagement.py`
- `test_quality_ccap.py`
- `test_quality_classification.py`
- `test_quality_dc4.py` (sous-traitance)
- `test_quality_devis.py`
- `test_quality_fiche_navette.py`
- `test_quality_pipeline_ae.py`
- `test_quality_rib.py`

Ces tests :
1. Récupèrent des données de référence depuis **Grist** (vérité terrain labellisée manuellement)
2. Passent les documents dans le pipeline d'extraction
3. Comparent les résultats avec des fonctions de comparaison adaptées (exact string, normalized string, IBAN, durée, et même **comparaison via LLM** pour les champs textuels libres comme l'objet ou l'administration)
4. Calculent des statistiques globales de qualité

**Important** : Ces tests ne sont **pas exécutés en CI** (le workflow GitHub ne lance que `pytest tests/`). Ils semblent être exécutés manuellement.

### 5.3 Métriques et suivi

| Mécanisme | Fichier | Description |
|---|---|---|
| Logs structurés | `docia/logging.py` | request_id, session_id, celery_task_id dans chaque log |
| Progression batch | `docia/file_processing/pipeline/utils.py` | Compteurs par étape (success, failure, skipped) |
| Tracking événements | `docia/tracking/` | API REST pour enregistrer des événements UI (Matomo-like) |
| Rate limiting | `docia/ratelimit/` | Compteurs par utilisateur pour la vue web (200 requêtes/jour) |
| Erreurs de téléchargement | `docia/file_processing/models.py` (`DownloadDocumentError`) | Enregistrement des erreurs de téléchargement de documents |
| Grist | `app/grist/grist_api.py` | Export des résultats vers Grist pour suivi (script manuel) |

### 5.4 Cas d'échec connus

1. **Extension non supportée** → `SkipStepException`, le document est marqué `SKIPPED`
2. **Texte vide après extraction** → `Exception("Failed to extract text - empty result")` → `FAILURE`
3. **LLM timeout / erreur 5xx** → 3 retries puis `FAILURE`
4. **LLM erreur 4xx (hors 429)** → `FAILURE` immédiate
5. **Post-traitement** : `ValueError` si champs manquants dans la durée, l'adresse postale → `FAILURE`
6. **Batch bloqué** : Détecté après 30 min d'inactivité, annulé et relancé automatiquement
7. **Document > 21 Mo** : Pas de retry au téléchargement, mais le document est quand même téléchargé une fois

### ⚠️ Points d'attention

- **Pas de score de confiance** : Impossible de filtrer les extractions de mauvaise qualité sans vérification humaine.
- **Tests e2e manuels** : Le jeu de vérité terrain dans Grist est le seul moyen de mesurer la qualité. S'il n'est plus maintenu, la qualité ne sera plus mesurable.
- **Pas de dashboard de suivi** : Les métriques sont dans les logs et dans Grist, mais il n'y a pas de dashboard centralisé visible.
- **Pas de mécanisme de validation humaine** : Pas de workflow de revue/correction des données extraites.

### ❓ Questions ouvertes

- À quelle fréquence les tests e2e sont-ils exécutés et par qui ?
- Quel est le taux d'exactitude mesuré par les tests e2e (derniers résultats) ?
- Le script `scripts/maj_grist_from_scalingo.py` est-il exécuté régulièrement ?

---

## Phase 6 : Identification du hors-scope et des risques

### 6.1 Types de documents non gérés pour l'extraction

Les **~50 catégories** de classification sont définies dans `DIC_CLASS_FILE_BY_NAME`, mais seuls **10 types** ont une extraction structurée (`SUPPORTED_DOCUMENT_TYPES`). Les types suivants sont classifiés mais **pas analysés** :

`abondement`, `ae_annexe`, `application_revision_prix`, `att_etrangers`, `att_fiscale`, `att_handicap`, `att_honneur`, `att_resp_civile`, `att_sociale`, `avis_boamp`, `bordereau_prix`, `ca_chgt_denomination`, `ca_chgt_ej`, `ca_chgt_siret`, `ca_chgt_revision_prix`, `ca_chgt_rib`, `ccag`, `ccap_annexe`, `ccap_annexe_beneficiaires`, `ccc`, `ccp_simple`, `ccp_vae`, `cctp`, `cctp_annexe`, `cga`, `commentaire`, `conv_financement`, `cv`, `reconduction`, `decomposition_prix`, `delegation_pouvoir`, `detail_quantitatif_estimatif`, `ej_complexe`, `facture`, `fiche_achat`, `fiche_communication`, `fiche_engagement`, `fiche_modificative`, `lettre_candidature_dc1`, `lettre_candidature_dc2`, `lettre_consultation`, `mail`, `memoire_technique`, `mise_au_point`, `notification`, `ordre_service`, `pv_cao`, `question_reponse`, `rapport_affermissement_tranche`, `rapport_analyse_offre`, `rapport_signature`, `reglement_consultation`, `service_fait`

### 6.2 Formats de fichiers non gérés

Les extensions suivantes sont **explicitement non supportées** et provoquent un `SkipStepException` :
- **Tout format hors** : `doc, docx, odt, pdf, txt, jpg, jpeg, png, tiff, tif, xlsx, xls, ods`
- En particulier : **BPU Excel** (s'il est au format `.csv`), **fichiers `.msg`** (Outlook), **fichiers `.eml`**, **fichiers `.ppt`/`.pptx`**, **fichiers `.rtf`**

### 6.3 TODO, FIXME, et dette technique

| Fichier | Commentaire |
|---|---|
| `tests/docia/file_processing/sync/test_client.py:14` | `# TODO` (commentaire isolé, pas de description) |

La dette technique est surtout **structurelle** :
1. **Code legacy `app/`** : Le dossier `app/` contient du code pré-Django (SQLAlchemy, pandas, fonctions standalone). Certaines fonctions sont encore importées (`app.file_manager.cleaner`, `app.utils`). L'exclusion de ces fichiers par ruff (`ruff.exclude`) confirme que le code n'est pas maintenu aux mêmes standards.
2. **Fichiers exclus de ruff** : `app/file_manager/__init__.py`, `app/file_manager/cleaner.py`, `app/file_manager/statistics.py`, `app/grist/__init__.py`, `app/grist/grist_api.py`, `app/processor/select_relevant_content.py`, `app/processor/synthesis.py`, `scripts/maj_grist_from_scalingo.py`
3. **`cctp` défini dans les attributs mais absent de `SUPPORTED_DOCUMENT_TYPES`** : Les attributs CCTP sont définis mais le type n'est jamais analysé.
4. **`relevant_content` jamais peuplé** : Le champ existe dans le modèle et est utilisé dans `AnalyzeContentStepRunner` (`document.relevant_content or document.text`), mais aucun code du pipeline actuel ne le remplit.

### 6.4 Dépendances externes fragiles

| Dépendance | Risque |
|---|---|
| **API Albert (Mistral/DINUM)** | Service managé par la DINUM, pas de SLA public connu. Tout le pipeline est bloqué si Albert est indisponible. |
| **API externe (Chorus/SAP)** | Client OAuth2 `SyncClient` pour récupérer les EJ et PJ. Authentification client_credentials. Format OData. |
| **Grist** | Utilisé pour les tests e2e et le suivi. Service tiers, pas critique pour le pipeline. |
| **Scalingo** | PaaS de déploiement. Migration vers un autre hébergeur nécessiterait d'adapter Procfile et Aptfile. |
| **Redis** | Broker Celery. Scalingo fournit une add-on Redis managé. |

### ⚠️ Points d'attention

- **Dépendance monopoint sur Albert** : Il n'y a pas de fallback si l'API Albert est indisponible. Le modèle `openweight-medium` et `mistral-medium-2508` sont spécifiques à cette infrastructure.
- **API de synchronisation OData** : Le client de synchronisation utilise un format de date propriétaire (`/Date(<timestamp>)/`) et des filtres OData. La documentation de cette API n'est pas dans le repo.
- **Pas de pagination** dans l'appel API `list_documents_for_ej` : Pourrait poser un problème si un EJ a beaucoup de PJ.
- **Le code Grist utilise `requests` avec des `except:` nues** (bare except) et des `print()` au lieu de logging.

### ❓ Questions ouvertes

- Quels sont les formats de documents les plus fréquents qui sont actuellement skippés ?
- Y a-t-il un plan pour ajouter le support BPU (Excel), DPGF, et les documents P530 ?
- L'API de synchronisation (export_pj_ej) est-elle l'API SAP Chorus standard ou un développement spécifique ?

---

## Synthèse architecturale

### Diagramme ASCII du flux de données

```
                                    ┌─────────────────────┐
                                    │   API Externe        │
                                    │ (Chorus/SAP OData)   │
                                    └─────────┬───────────┘
                                              │ OAuth2 client_credentials
                                              ▼
┌──────────────┐          ┌──────────────────────────────────┐
│   CRON       │──────────│      sync_and_analyze()          │
│ 4x/jour      │          │  docia/file_processing/pipeline  │
└──────────────┘          │                                  │
                          │  1. sync_engagements()           │
                          │     → liste des num_ej modifiés  │
                          │                                  │
                          │  2. sync_documents()             │
                          │     → métadonnées des PJ         │
                          │                                  │
                          │  3. download_documents()         │
                          │     → fichiers dans S3    ───────┼──► ┌─────────┐
                          │                                  │    │   S3    │
                          │  4. init_documents()             │    │(Scalingo)│
                          │     → enregistrements en base    │    └─────────┘
                          │                                  │
                          │  5. launch_batch()               │
                          └──────────┬───────────────────────┘
                                     │ Celery group
                                     ▼
                          ┌──────────────────────────┐
                          │   Par document (chain)   │
                          │                          │
                          │  ┌────────────────────┐  │
                          │  │ 1. TEXT EXTRACTION  │  │
                          │  │ PyMuPDF / Tesseract │  │
                          │  │ / Mistral OCR       │──┼──► API Albert (OCR)
                          │  └────────┬───────────┘  │
                          │           ▼              │
                          │  ┌────────────────────┐  │
                          │  │ 2. CLASSIFICATION  │  │
                          │  │ LLM openweight-med │──┼──► API Albert (LLM)
                          │  └────────┬───────────┘  │
                          │           ▼              │
                          │  ┌────────────────────┐  │
                          │  │ 3. CONTENT ANALYSIS│  │
                          │  │ LLM mistral-med    │──┼──► API Albert (LLM)
                          │  │ + post-processing  │  │
                          │  └────────┬───────────┘  │
                          │           ▼              │
                          │  Document.structured_data│
                          └──────────┬───────────────┘
                                     │
                                     ▼
                          ┌──────────────────────┐
                          │    PostgreSQL         │
                          │  (Document, EJ, etc.) │
                          └──────────┬───────────┘
                                     │
                          ┌──────────▼───────────┐
                          │   Vue 360° Web       │
                          │  Django + DSFR        │
                          │  (recherche par EJ)   │
                          └──────────────────────┘
```

### Liste des composants et leur rôle

| Composant | Rôle |
|---|---|
| **Django (docia)** | Application web (vue 360°, admin, auth OIDC), ORM, commandes de gestion |
| **Celery workers** | Exécution parallèle du pipeline de traitement documentaire |
| **Redis** | Broker de messages pour Celery |
| **PostgreSQL** | Base de données relationnelle (documents, EJ, résultats d'extraction, état du pipeline) |
| **S3 (Scalingo)** | Stockage des fichiers documents (PDF, DOCX, etc.) |
| **API Albert (DINUM)** | LLM Mistral (classification, extraction structurée) + OCR Mistral |
| **Tesseract** | OCR local pour images (fallback) |
| **LibreOffice** | Conversion .doc → .txt |
| **API externe Chorus/SAP** | Source des EJ et des pièces jointes (synchronisation) |
| **Grist** | Base de données collaborative pour métriques et données de test |
| **GitHub Actions** | CI (tests, lint) |
| **Scalingo** | PaaS de déploiement (web + workers + cron) |

### Les 5 risques principaux identifiés

1. **Dépendance monopoint sur l'API Albert (critique)** — L'intégralité du pipeline (OCR, classification, extraction) dépend d'une seule API LLM sans fallback ni mode dégradé. Une indisponibilité d'Albert bloque totalement le traitement des documents.

2. **Absence de score de confiance (élevé)** — Aucun mécanisme de score ou d'incertitude n'est associé aux données extraites. Dans le contexte SAP Chorus (données financières), il est impossible de distinguer automatiquement une extraction correcte d'une hallucination du LLM.

3. **Pas de contrôle de la taille du contexte LLM (élevé)** — Le texte intégral des documents est envoyé au LLM sans troncature ni vérification du nombre de tokens. Un document volumineux peut silencieusement produire une extraction partielle ou erronée.

4. **Code legacy non migré (modéré)** — Le dossier `app/` contient du code pré-Django encore importé (`extract_num_EJ`, `get_file_initial_info`, `clean_nul_bytes`). Ce code bypass le framework Django (print au lieu de logging, pas de gestion d'erreurs standard) et complexifie la maintenance et la migration SAP.

5. **Tests de qualité non automatisés (modéré)** — Les tests e2e mesurant la qualité de l'extraction ne sont pas exécutés en CI. Le jeu de vérité terrain Grist peut devenir obsolète sans qu'on le détecte. La régression de qualité des prompts ou des modèles n'est pas détectée automatiquement.
