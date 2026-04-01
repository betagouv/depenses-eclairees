# Appel LLM (Albert)

## Client LLM

**Fichier** : `docia/file_processing/llm/client.py`

Le client utilise le **SDK OpenAI** configuré pour pointer vers l'API Albert (DINUM) :

```python
# docia/file_processing/llm/client.py (verbatim)
self.client = OpenAI(
    api_key=self.api_key,       # settings.ALBERT_API_KEY
    base_url=self.base_url,     # settings.ALBERT_BASE_URL
    timeout=timeout,            # 180s par défaut
    max_retries=0,              # Retry géré manuellement
)
```

## Configuration API

| Paramètre | Source | Valeur |
|---|---|---|
| URL de base | `ALBERT_BASE_URL` (env) | Définie dans l'environnement (non en dur) |
| API Key | `ALBERT_API_KEY` (env) | Secret — non reproduit ici |
| Protocole | Compatibilité OpenAI | `chat.completions.create()` + endpoint OCR spécifique |
| Timeout | Codé en dur | **180 secondes** |
| Rate limiting | `ALBERT_USE_RATE_LIMITER` (env) | Optionnel, basé sur PostgreSQL |

## Modèles utilisés

| Modèle | Usage | Température | Rate limit |
|---|---|---|---|
| `openweight-medium` | Classification des documents | 0.0 | 98 req/min |
| `mistral-medium-2508` | Extraction d'informations structurées | 0.0 | 98 req/min |
| `mistral-ocr-2512` | OCR de PDF scannés | — | 98 req/min |

## Deux méthodes d'appel

### `ask_llm()` — Classification et extraction

Utilise le SDK OpenAI :

```python
# docia/file_processing/llm/client.py (verbatim)
response = self.client.chat.completions.create(
    model=model,
    messages=messages,
    temperature=temperature,
    response_format=response_format,  # JSON Schema
)
return response.choices[0].message.content.strip()
```

Si `response_format` est fourni, la réponse est parsée en JSON : `json.loads(content)`.

### `ocr_pdf()` — OCR de PDF scannés

Appel REST direct (pas via SDK OpenAI) avec `httpx.post` :

```python
# docia/file_processing/llm/client.py (verbatim, simplifié)
url = urljoin(self.base_url, "/ocr")
headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
payload = {
    "model": "mistral-ocr-2512",
    "document": {"type": "document_url", "document_url": "data:application/pdf;base64,..."},
    "include_image_base64": False,
}
```

La réponse contient des pages, chaque page avec du markdown. Le client reconstruit le texte avec des marqueurs `[[PAGE i / N]]`.

## Gestion d'erreurs et retry

**Fichier** : `docia/file_processing/llm/client.py`, méthode `_api_call()`

```mermaid
flowchart TD
    A["Appel API Albert"] --> B{Réponse ?}
    B -->|HTTP 200| C["Succès"]
    B -->|HTTP 429| D["Rate limit<br/>Attente : 60s × (attempt+1) × jitter"]
    B -->|HTTP 5xx| E["Erreur serveur<br/>Attente : 10s × (attempt+1) × jitter"]
    B -->|Timeout / réseau| F["Erreur réseau<br/>Attente : 10s × (attempt+1) × jitter"]
    B -->|HTTP 4xx (hors 429)| G["Échec immédiat<br/>Pas de retry"]
    D --> H{attempt < 3 ?}
    E --> H
    F --> H
    H -->|Oui| A
    H -->|Non| I["LLMApiError<br/>→ Step FAILURE"]
    G --> I
```

| Scénario | Comportement | Délai |
|---|---|---|
| HTTP 429 (rate limit) | Retry | 60s × (attempt+1) × jitter |
| HTTP 5xx (erreur serveur) | Retry | 10s × (attempt+1) × jitter |
| Timeout / erreur réseau | Retry | 10s × (attempt+1) × jitter |
| HTTP 4xx (hors 429) | Échec immédiat | — |
| Toutes tentatives épuisées | `LLMApiError` → Step `FAILURE` | — |

## Rate limiting distribué

Si `ALBERT_USE_RATE_LIMITER=True`, un `RateGate` basé sur PostgreSQL assure un espacement minimum entre les requêtes :

- Utilise `SELECT ... FOR UPDATE` sur la table `docia_rategatestate`
- Emploie `clock_timestamp()` PostgreSQL pour éviter les dérives d'horloge entre workers
- Rate limit : **98 requêtes/minute** par défaut

!!! danger "Pas de gestion de fenêtre de contexte"

    Le texte complet du document est envoyé au LLM sans vérification du nombre de tokens. Un document long pourrait dépasser la fenêtre de contexte et produire une réponse tronquée ou une erreur.

!!! warning "Timeout de 180 secondes"

    Codé en dur. Peut être insuffisant pour des documents très volumineux.

**Source** : `docia/file_processing/llm/client.py`, `docia/file_processing/llm/rategate/`
