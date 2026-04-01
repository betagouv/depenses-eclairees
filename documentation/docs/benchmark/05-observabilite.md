# Observabilité & Télémétrie LLM

!!! abstract "Résumé"
    Le pipeline dispose de logs structurés avec request_id, session_id et celery_task_id. Cependant, il n'y a pas de télémétrie spécifique LLM (tokens, latence, TTFT), pas d'OpenTelemetry, pas de corrélation avec SAP, et pas de dashboard de monitoring. Verdict global : 🟡 Partiel.

## Références de l'état de l'art

Monitorer un pipeline LLM, ce n'est pas seulement surveiller le CPU et la RAM. C'est savoir combien de tokens chaque appel consomme (et combien ça coûte), quelle est la latence par document, quel est le taux d'erreur par modèle, et pouvoir remonter d'une extraction douteuse dans SAP jusqu'à l'appel Albert qui l'a produite. Sans cette visibilité, on pilote à l'aveugle — et quand Albert a un coup de mou à 2h du matin, personne ne le sait avant le lendemain.

- **OpenTelemetry / OpenLLMetry** — standard d'observabilité distribué, avec une extension spécifique pour tracer les appels LLM (tokens, latence, modèle).
- **NIST AI RMF MEASURE 2.8** — collecter des métriques opérationnelles pour détecter les dégradations avant qu'elles n'aient un impact.
- **Corrélation cross-système** — pouvoir relier un Trace ID Albert à un num_ej SAP pour le débogage de bout en bout.

## Points de contrôle

### Traçage OpenTelemetry

**État de l'art** : Les appels LLM doivent être instrumentés via OpenTelemetry (spans avec attributs : model, prompt_tokens, completion_tokens, latency). Les librairies comme `openllmetry-sdk` automatisent cette instrumentation pour le SDK OpenAI.

**Constat dans le code** :
[NON IMPLÉMENTÉ] — Aucune dépendance OpenTelemetry dans `pyproject.toml`. Aucune instrumentation de tracing dans le code. Le `LLMClient` ne produit pas de spans.

**Verdict** : 🔴 **Non conforme** — Pas d'OpenTelemetry ni de tracing distribué.

**Recommandation** : Intégrer `opentelemetry-sdk` + `opentelemetry-instrumentation-openai` (ou `openllmetry-sdk`). Exporter les traces vers un backend compatible (Jaeger, Grafana Tempo). Cela fournira automatiquement les métriques de tokens, latence et erreurs.
**Priorité** : P1 | **Effort** : M

---

### Journalisation des métriques LLM

**État de l'art** : Chaque appel LLM doit journaliser : Time To First Token (TTFT), tokens input/output, latence totale, modèle utilisé, code d'erreur, finish_reason.

**Constat dans le code** :
L'objet `response` retourné par `client.chat.completions.create()` contient un attribut `usage` (prompt_tokens, completion_tokens, total_tokens) et `finish_reason`, mais le code ne les exploite pas (source : `docia/file_processing/llm/client.py:189-195`).

Le `ProcessDocumentStep` enregistre `started_at`, `finished_at`, `duration` (source : `docia/file_processing/pipeline/steps/base.py:39,57-58`), mais cette durée inclut le pré/post-traitement, pas uniquement l'appel API.

Les seuls logs LLM sont les warnings de retry (source : `client.py:146`) :
```python
logger.warning("%s, wait %.1fs before retry (%d/%d)", e.code, wait_time, attempt + 1, max_retries)
```

**Verdict** : 🔴 **Non conforme** — Les métriques spécifiques LLM (tokens, TTFT, finish_reason) ne sont ni journalisées ni stockées.

**Recommandation** : Dans `ask_llm()`, extraire `response.usage` et `response.choices[0].finish_reason` et les journaliser via `logger.info`. Stocker les tokens consommés dans un champ `ProcessDocumentStep.llm_usage` (JSONField).
**Priorité** : P1 | **Effort** : S

---

### Corrélation ID SAP ↔ Trace ID Albert

**État de l'art** : Pour le débogage cross-système, chaque appel Albert doit être corrélé à l'identifiant de la transaction SAP (num_ej, document_id). Cela permet de tracer une extraction erronée dans SAP jusqu'à l'appel LLM qui l'a produite.

**Constat dans le code** :
Le `ProcessDocumentStep` est lié au `ProcessDocumentJob` qui est lié au `Document` qui est lié aux `DataEngagement` (via M2M). La chaîne de traçabilité existe en base de données :

`ProcessDocumentStep` → `Job` → `Document` → `DataEngagement.num_ej`

Cependant, cette corrélation n'est pas propagée dans les logs. Le celery_task_id est logué (source : `docia/logging.py:53-69`), mais pas le document_id ni le num_ej.

**Verdict** : 🟡 **Partiel** — Corrélation présente en base de données, mais absente des logs. Le débogage cross-système nécessite des requêtes SQL manuelles.

**Recommandation** : Ajouter `document_id` et `num_ej` au contexte de logging des tâches Celery. Utiliser un structured logging filter qui enrichit chaque log avec ces identifiants pendant le traitement d'un step.
**Priorité** : P1 | **Effort** : S

---

### Logs structurés

**État de l'art** : Les logs doivent être en format structuré (JSON) pour être exploitables par des outils d'agrégation (ELK, Loki, Datadog).

**Constat dans le code** :
Les logs utilisent un format texte structuré (mais pas JSON) :

```python
# Console handler (source : settings.py:257-258)
"format": "[%(asctime)s] %(levelname)s sid=%(session_id)s rid=%(request_id)s %(name)s %(message)s"

# Celery handler (source : settings.py:267)
"format": "[%(asctime)s] %(levelname)s %(worker_name)s/%(processName)s task=%(task_name)s[%(task_id)s] %(name)s %(message)s"
```

Les logs incluent `session_id`, `request_id`, `worker_name`, `task_id`, `task_name` — bonne couverture de contexte. Mais le format est texte libre, pas JSON.

Le `MultiLineFormatter` (source : `docia/logging.py:72-97`) reformate les messages multilignes (tracebacks) pour inclure le préfixe structuré sur chaque ligne.

**Verdict** : 🟡 **Partiel** — Logs semi-structurés avec bons identifiants de contexte, mais format texte au lieu de JSON.

**Recommandation** : Ajouter un formatter JSON (ex: `python-json-logger`) optionnel via variable d'environnement. En production Scalingo, les logs JSON sont mieux exploitables par les outils d'agrégation.
**Priorité** : P2 | **Effort** : S

---

### Dashboard et alertes

**État de l'art** : Un dashboard opérationnel doit afficher en temps réel : taux d'erreur des batchs, latence moyenne des appels LLM, consommation de tokens, nombre de documents traités/en erreur. Des alertes doivent se déclencher sur les anomalies.

**Constat dans le code** :
[NON IMPLÉMENTÉ] — Aucun dashboard de monitoring n'est configuré. La commande `display_batch_progress` (source : `docia/management/commands/display_batch_progress.py`) affiche la progression d'un batch en ligne de commande, mais ce n'est pas un monitoring continu.

Le suivi de production se fait via Grist (export manuel via `scripts/maj_grist_from_scalingo.py`).

**Verdict** : 🔴 **Non conforme** — Pas de dashboard ni d'alertes automatiques.

**Recommandation** : Déployer un dashboard simple (Grafana + Loki pour les logs Scalingo, ou un dashboard Django admin custom). Au minimum, exposer des métriques Prometheus via `django-prometheus` : compteurs de documents traités, taux d'erreur, latence LLM.
**Priorité** : P1 | **Effort** : L

---

### Journalisation des prompts et réponses

**État de l'art** : Les prompts envoyés et les réponses reçues doivent être journalisés, au moins en mode debug, pour permettre le débogage et l'amélioration des prompts.

**Constat dans le code** :
Les prompts ne sont pas journalisés. La réponse brute du LLM est stockée dans `Document.llm_response` (source : `content_analysis.py:42`), ce qui est une bonne pratique pour la traçabilité a posteriori.

Cependant, le prompt exact envoyé n'est pas stocké ni journalisé. En mode debug, aucun log n'affiche le contenu des messages envoyés au LLM.

**Verdict** : 🟡 **Partiel** — Réponse brute stockée en base (bonne pratique), mais prompt non journalisé.

**Recommandation** : Ajouter un `logger.debug("LLM request: model=%s tokens_estimate=%d", model, len(messages[1]["content"]))` dans `ask_llm()`. En mode debug, journaliser le prompt complet (attention : ne pas journaliser en production les données sensibles).
**Priorité** : P2 | **Effort** : S

---

## Synthèse du thème

| Critère | Verdict | Priorité | Effort |
|---------|---------|----------|--------|
| Traçage OpenTelemetry | 🔴 Non conforme | P1 | M |
| Métriques LLM (tokens, latence) | 🔴 Non conforme | P1 | S |
| Corrélation SAP ↔ Albert | 🟡 Partiel | P1 | S |
| Logs structurés | 🟡 Partiel | P2 | S |
| Dashboard et alertes | 🔴 Non conforme | P1 | L |
| Journalisation prompts/réponses | 🟡 Partiel | P2 | S |
