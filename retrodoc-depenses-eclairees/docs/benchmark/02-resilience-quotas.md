# Résilience, Quotas & Gestion des Erreurs API

!!! abstract "Résumé"
    Le code implémente un mécanisme de retry avec backoff linéaire et jitter, ainsi qu'un rate limiter distribué via PostgreSQL. Cependant, il n'y a pas de circuit breaker, pas d'idempotence garantie, et l'architecture synchrone (boucle Celery) limite la résilience. Verdict global : 🟡 Partiel.

## Références de l'état de l'art

Quand on appelle une API externe des centaines de fois par batch, la question n'est pas "est-ce que ça va tomber en panne" mais "quand". Les patterns de résilience distribués (retry, circuit breaker, idempotence) sont les amortisseurs qui empêchent une panne d'API de se transformer en panne du pipeline entier. C'est d'autant plus critique avec Albert qui n'a pas de SLA public.

- **Exponential backoff + jitter** — augmenter le délai entre chaque retry pour éviter l'effet "troupeau" où tous les workers retentent en même temps.
- **Circuit breaker (pattern Hystrix)** — couper les appels vers un service en panne au lieu de le marteler inutilement.
- **NIST AI RMF MANAGE 2.2** — résilience aux défaillances des dépendances externes.

## Points de contrôle

### Retry avec Exponential Backoff + Jitter

**État de l'art** : Les appels API doivent implémenter un retry avec exponential backoff (délai doublé à chaque tentative) et jitter (variation aléatoire) pour éviter les "thundering herds". La librairie `tenacity` est le standard Python.

**Constat dans le code** :
Le mécanisme de retry est implémenté manuellement dans `docia/file_processing/llm/client.py:121-149` (méthode `_api_call`). La stratégie est :

```python
wait_time = effective_delay * (1 + 0.1 * random.random()) * (attempt + 1)
```

- **429 (rate limit)** : délai de 60s × (attempt+1) × jitter (source : `client.py:139,159`)
- **5xx / erreurs réseau** : délai de 10s × (attempt+1) × jitter (source : `client.py:140-141,160`)
- **4xx (hors 429)** : échec immédiat, pas de retry (source : `client.py:143`)
- **Max retries** : 3 par défaut (source : `client.py:158`)
- **Jitter** : 10% — `(1 + 0.1 * random.random())` (source : `client.py:145`)

Le backoff est **linéaire** (multiplicateur `attempt + 1`), pas exponentiel. Le jitter est faible (10%).

**Verdict** : 🟡 **Partiel** — Retry implémenté avec jitter, mais backoff linéaire au lieu d'exponentiel. Pas d'utilisation de `tenacity`.

**Recommandation** : Migrer vers `tenacity` avec `wait_exponential_jitter(initial=10, max=300)` pour un backoff exponentiel standard. Cela réduit la pression sur l'API Albert lors des pannes prolongées.
**Priorité** : P2 | **Effort** : S

---

### Circuit Breaker

**État de l'art** : Un circuit breaker coupe les appels vers un service défaillant après N échecs consécutifs, et réessaie périodiquement (état "half-open"). Cela évite de marteler une API en panne et permet un fail-fast des documents en attente.

**Constat dans le code** :
[NON IMPLÉMENTÉ] — Aucun pattern circuit breaker n'est présent. Si l'API Albert est en panne, chaque document du batch tentera ses 3 retries (avec des délais de 60s pour les 429), ce qui peut bloquer un worker Celery pendant plusieurs minutes par document.

Le mécanisme `close_and_retry_stuck_batches()` (source : `docia/file_processing/pipeline/pipeline.py:163-172`) détecte les batchs bloqués depuis 30 minutes et les relance, mais ce n'est pas un circuit breaker — c'est un rattrapage tardif.

**Verdict** : 🔴 **Non conforme** — Absence de circuit breaker. En cas de panne Albert, tous les workers Celery seront bloqués en attente.

**Recommandation** : Implémenter un circuit breaker simple (ex: `pybreaker`) sur le `LLMClient`. Après 5 erreurs consécutives, court-circuiter pendant 5 minutes. Logger l'état du circuit pour le monitoring.
**Priorité** : P1 | **Effort** : M

---

### Fallback modèle Mistral Small → Medium

**État de l'art** : Pour les documents complexes qui échouent sur un modèle léger (boucle infinie, timeout, réponse incohérente), un fallback automatique vers un modèle plus puissant est une bonne pratique de résilience. Ce mécanisme doit être documenté, coûté et observable.

**Constat dans le code** :
L'équipe a décrit l'existence d'un fallback automatique Small → Medium pour ~3–4% des documents complexes. **Cette affirmation n'est pas confirmée par le code.**

L'analyse du pipeline montre deux routages statiques par type de tâche :

- **Classification** → `openweight-medium` (alias Albert pour `mistral-small`, source : `classifier.py:45`)
- **Extraction** → `mistral-medium-2508` (défaut, source : `analyze_content.py:81,104`)

Le step d'analyse (`content_analysis.py:38-41`) appelle `processor.analyze_file_text(document.relevant_content or document.text, document.classification)` **sans passer de paramètre `llm_model`** — il utilise donc toujours `mistral-medium-2508`, sans aucun switch conditionnel.

```python
# content_analysis.py:38-41 — aucun paramètre llm_model passé
result = processor.analyze_file_text(
    document.relevant_content or document.text,
    document.classification,
)
```

Il n'existe **aucune logique de switch** dans `client.py`, `content_analysis.py` ou ailleurs permettant de détecter un comportement anormal (boucle infinie, timeout) sur un premier modèle et de relancer sur un second modèle. Les scripts `tests_e2e/` (ex : `test_quality_acte_engagement.py:262`) qui utilisent `mistral-medium-2508` sont des **benchmarks manuels**, pas de la logique de production.

!!! danger "Fallback automatique non confirmé dans le code — hypothèse : déjà corrigé en amont"
    L'équipe a décrit un scénario où ~3-4% des documents provoquaient une boucle infinie sur `mistral-small` (`openweight-medium`), résolue par un switch vers `mistral-medium-2508`. **Aucune logique de switch conditionnel n'existe dans le code actuel.** L'hypothèse la plus probable : la solution a été de fixer `mistral-medium-2508` comme modèle **par défaut permanent** pour l'extraction (`analyze_content.py:81`), abandonnant l'usage de Small pour cette étape. Ce qui reste vrai : il n'existe aucun filet de sécurité si le modèle par défaut lui-même échoue.

**Verdict** : 🔴 **Non conforme** — Aucun fallback automatique implémenté. L'affirmation de l'équipe n'est pas reflétée dans le code source.

**Recommandation** : Si un fallback est souhaité, implémenter une détection d'échec (timeout > N s, `FAILURE` sur 3 retries) suivie d'un deuxième appel avec `llm_model="mistral-medium-2508"`. Ajouter un champ `llm_fallback_used` dans `ProcessDocumentStep` pour la traçabilité.
**Priorité** : P2 | **Effort** : M

---

### Gestion des cas d'erreur API

**État de l'art** : Chaque type d'erreur API doit être géré explicitement : timeout, 429, 500, réponse vide, JSON malformé. Les erreurs doivent être journalisées avec contexte (document_id, tentative, code HTTP).

**Constat dans le code** :

| Cas d'erreur | Gestion | Source |
|---|---|---|
| Timeout | Retry (erreur réseau) | `client.py:140-141` |
| HTTP 429 | Retry avec délai 60s × attempt | `client.py:138-139` |
| HTTP 5xx | Retry avec délai 10s × attempt | `client.py:140-141` |
| HTTP 4xx (hors 429) | Échec immédiat | `client.py:143` |
| Réponse vide | Non géré — `response.choices[0]` lèverait `IndexError` | `client.py:195` |
| JSON malformé | Non géré — `json.loads(content)` lèverait `JSONDecodeError` | `client.py:206` |

Les erreurs réseau/timeout de l'appel OCR (`httpx`) sont gérées séparément (source : `client.py:237-242`).

L'`AbstractStepRunner` (source : `docia/file_processing/pipeline/steps/base.py:49-53`) capture toutes les exceptions, les journalise avec `logger.exception`, enregistre l'erreur et le traceback dans le step, et annule les étapes suivantes du job.

**Verdict** : 🟡 **Partiel** — Bonne gestion des erreurs HTTP classiques. Réponse vide et JSON malformé non gérés explicitement.

**Recommandation** : Ajouter un try/catch autour de `json.loads(content)` avec fallback vers `FAILURE` et journalisation de la réponse brute. Vérifier que `response.choices` n'est pas vide avant accès.
**Priorité** : P1 | **Effort** : S

---

### Remontée d'alertes

**État de l'art** : Les erreurs critiques (taux d'échec anormal, panne API prolongée, batch échoué) doivent déclencher des alertes exploitables (Slack, PagerDuty, email).

**Constat dans le code** :
Les erreurs sont journalisées dans les logs structurés (source : `docia/settings.py:241-328`) avec `request_id`, `session_id`, `celery_task_id`. Les erreurs de step sont enregistrées en base dans `ProcessDocumentStep.error` et `ProcessDocumentStep.traceback`.

Cependant :
- [NON IMPLÉMENTÉ] — Aucun mécanisme d'alerte (webhook, email, Slack) n'est configuré.
- [NON IMPLÉMENTÉ] — Pas de dashboard de monitoring des batchs.
- Le suivi de progression (`docia/file_processing/pipeline/utils.py`) fournit des compteurs mais pas d'alertes automatiques.

**Verdict** : 🔴 **Non conforme** — Logs exploitables mais pas d'alertes automatiques. Un batch échoué à 2h du matin ne sera découvert qu'au matin.

**Recommandation** : Configurer un webhook Mattermost/Slack/email déclenché par le handler de logging Django quand le taux d'échec d'un batch dépasse un seuil (ex: > 10%). Ajouter une alerte si le circuit breaker s'ouvre.
**Priorité** : P1 | **Effort** : M

---

### Architecture synchrone vs asynchrone

**État de l'art** : Un pipeline de traitement documentaire batch doit utiliser une architecture asynchrone (queue de messages, workers distribués) pour gérer la charge et la résilience.

**Constat dans le code** :
L'architecture utilise **Celery avec Redis** comme broker (source : `docia/celeryapp.py`, `docia/settings.py:357-358`). Chaque document est traité comme une chaîne de 3 tâches séquentielles (`chain`), et tous les documents d'un batch sont lancés en parallèle (`group`) (source : `pipeline.py:105-133`).

- Worker `celery` : concurrency=2 (source : `Procfile`)
- Worker `heavy_cpu` : concurrency=1 (source : `Procfile`)
- Les tâches sont bien immutées (`.si()`) pour la sérialisation (source : `pipeline.py:123`)

**Verdict** : 🟢 **Conforme** — L'architecture Celery/Redis est appropriée pour un pipeline batch. La séparation en deux queues (standard/heavy_cpu) est une bonne pratique.

**Recommandation** : Aucune action immédiate. À terme, envisager des priorités de queue pour les documents urgents.
**Priorité** : — | **Effort** : —

---

### Idempotence du traitement

**État de l'art** : Un batch doit pouvoir être relancé sans créer de doublons ni retraiter les documents déjà traités avec succès. L'idempotence est critique pour la reprise sur erreur.

**Constat dans le code** :
Le pipeline filtre les documents déjà traités avant de lancer un batch :
```python
qs_docs = qs_docs.filter(structured_data__isnull=True)
```
(source : `pipeline.py:288`)

De plus, `close_and_retry_stuck_batches()` ne relance que les jobs en échec ou annulés (source : `pipeline.py:163-172`). Le mécanisme `retry_batch_failures` filtre par status `FAILURE`/`CANCELLED` (source : `pipeline.py:136-160`).

Cependant, si un document est en cours de traitement quand le batch est relancé (statut `STARTED`), il pourrait être traité en double. Le `select_for_update(nowait=True)` dans `AbstractStepRunner` (source : `base.py:17`) protège contre les exécutions concurrentes d'un même step, mais un nouveau job pourrait être créé pour le même document.

**Verdict** : 🟡 **Partiel** — Bonne protection contre le retraitement des succès. Risque de doublon si un document est encore `STARTED` lors d'un retry.

**Recommandation** : Ajouter une contrainte d'unicité sur `(document_id, batch_step_type)` pour les jobs en cours, ou vérifier le statut des jobs existants avant de créer un nouveau job.
**Priorité** : P2 | **Effort** : S

---

## Synthèse du thème

| Critère | Verdict | Priorité | Effort |
|---------|---------|----------|--------|
| Retry avec Backoff + Jitter | 🟡 Partiel | P2 | S |
| Circuit Breaker | 🔴 Non conforme | P1 | M |
| Fallback modèle Small → Medium | 🔴 Non conforme | P2 | M |
| Gestion des cas d'erreur API | 🟡 Partiel | P1 | S |
| Remontée d'alertes | 🔴 Non conforme | P1 | M |
| Architecture async | 🟢 Conforme | — | — |
| Idempotence | 🟡 Partiel | P2 | S |
