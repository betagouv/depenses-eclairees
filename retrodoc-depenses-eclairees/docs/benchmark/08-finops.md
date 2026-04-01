# FinOps & Optimisation des Coûts LLM

!!! abstract "Résumé"
    Le pipeline ne collecte aucune métrique de consommation de tokens, n'utilise pas le prompt caching, et ne ventile pas les coûts par type de document. Le texte complet est envoyé au LLM sans optimisation de tokens. Verdict global : 🔴 Non conforme.

## Références de l'état de l'art

Même si Albert est "gratuit" pour l'AIFE (coût porté par la DINUM), les tokens ne sont pas une ressource infinie : les quotas existent, et chaque token inutile ralentit le batch et occupe de la capacité qu'un autre service de l'État pourrait utiliser. Le FinOps LLM, c'est mesurer ce qu'on consomme (combien de tokens par document ? quel coût par type de pièce jointe ?) et optimiser les prompts pour ne pas envoyer 50 pages au LLM quand les 3 premières suffisent.

- **FinOps LLM** — mesurer le coût par unité de valeur (document, num_ej), optimiser les tokens input.
- **Prompt caching** — ne pas repayer le system prompt identique à chaque appel si l'API le supporte.
- **Routage intelligent** — modèle léger pour les cas simples, modèle lourd pour les cas complexes.

## Points de contrôle

### Ventilation des coûts par type de document

**État de l'art** : La télémétrie doit permettre de calculer le coût API par type de document, par flux métier, et par unité de valeur SAP (num_ej). Cela permet d'identifier les types de documents les plus coûteux et d'optimiser en priorité.

**Constat dans le code** :
[NON IMPLÉMENTÉ] — La consommation de tokens n'est pas collectée (cf. Thème 5). L'objet `response.usage` retourné par l'API est ignoré dans `client.py:189-195`. Sans données de tokens, aucune ventilation de coûts n'est possible.

Le `ProcessDocumentStep` enregistre `duration` mais pas la consommation de tokens.

**Verdict** : 🔴 **Non conforme** — Impossible de calculer le coût de traitement d'un document.

**Recommandation** : Capturer `response.usage.prompt_tokens` et `response.usage.completion_tokens` dans `ask_llm()`. Stocker dans `ProcessDocumentStep.llm_usage`. Créer une vue admin ou un script qui agrège les tokens par classification et par num_ej.
**Priorité** : P1 | **Effort** : S

---

### Prompt Caching

**État de l'art** : Si l'API supporte le prompt caching (Anthropic, OpenAI), le system prompt identique entre appels successifs peut être mis en cache côté serveur, réduisant significativement les tokens facturés et la latence. Mistral/Albert peut supporter cette fonctionnalité via le protocole OpenAI.

**Constat dans le code** :
[NON IMPLÉMENTÉ] — Le code ne fait rien pour exploiter le prompt caching :

- Le system prompt de classification est court et identique pour tous les documents : `"Vous êtes un assistant qui aide à classer des fichiers en fonction de leur contenu."` (source : `classifier.py:15`)
- Le system prompt d'extraction est similairement court : `"Vous êtes un assistant IA qui analyse des documents juridiques."` (source : `analyze_content.py:114`)
- Les user prompts contiennent la liste des catégories (classification) ou les consignes d'attributs (extraction) qui sont identiques pour un même type de document — ces parties seraient éligibles au caching.

**Verdict** : 🟡 **Partiel** — Le prompt caching n'est pas exploité, mais les system prompts sont suffisamment courts pour que l'impact financier soit modéré. L'essentiel des tokens input vient du texte du document, pas du prompt.

**Recommandation** : Vérifier auprès de la DINUM si l'API Albert supporte le prompt caching. Si oui, restructurer les appels pour maximiser le préfixe commun (system prompt + consignes d'extraction avant le texte du document).
**Priorité** : P2 | **Effort** : S

---

### Routage intelligent par modèle

**État de l'art** : Utiliser un modèle léger et rapide pour les tâches simples (classification, documents standards) et réserver un modèle plus puissant pour les cas complexes (documents atypiques, extractions difficiles). Cela réduit les coûts et la latence.

**Constat dans le code** :
Le pipeline utilise déjà **deux modèles différents** :

- `openweight-medium` pour la classification (source : `classifier.py:45`)
- `mistral-medium-2508` pour l'extraction (source : `analyze_content.py:81`)

Cependant, il n'y a pas de routage conditionnel : tous les documents passent par le même modèle d'extraction, quel que soit leur complexité ou type.

**Verdict** : 🟡 **Partiel** — Bonne pratique de séparer classification et extraction sur des modèles différents. Pas de routage conditionnel par complexité.

**Recommandation** : À terme, envisager un modèle plus léger pour les types de documents simples (RIB, attestation SIRENE) et réserver `mistral-medium` pour les documents complexes (actes d'engagement, CCAP). Mesurer d'abord la consommation de tokens pour identifier les optimisations à plus fort impact.
**Priorité** : P2 | **Effort** : M

---

### Minimisation des tokens input

**État de l'art** : Le texte OCR doit être nettoyé avant envoi au LLM : supprimer les en-têtes/pieds de page répétitifs, les zones blanches, les artefacts OCR. Si le document est long, ne garder que les sections pertinentes.

**Constat dans le code** :
- **Classification** : seuls les 2000 premiers caractères sont envoyés — `text[:2000]` (source : `classifier.py:35`). Bonne pratique de troncature pour cette étape.
- **Extraction** : le texte **complet** est envoyé — `document.relevant_content or document.text` (source : `content_analysis.py:39`). Le champ `relevant_content` est toujours `None` dans le pipeline actuel, donc c'est `document.text` intégral qui est envoyé.
- Le seul nettoyage du texte est `clean_nul_bytes()` (source : `text_extraction.py:84`), qui supprime uniquement les caractères NUL.
- Aucun nettoyage des en-têtes/pieds de page, aucune détection des zones répétitives, aucune troncature intelligente.

**Verdict** : 🔴 **Non conforme** — Le texte intégral (potentiellement très long) est envoyé au LLM pour l'extraction sans nettoyage ni troncature.

**Recommandation** : (1) Implémenter une troncature intelligente basée sur le nombre de tokens (via `tiktoken`) pour ne pas dépasser la fenêtre de contexte. (2) Supprimer les en-têtes/pieds de page répétitifs. (3) Pour les documents multi-sections, identifier et n'envoyer que les sections pertinentes au type d'extraction demandé.
**Priorité** : P1 | **Effort** : M

---

### Estimation du coût par document

**État de l'art** : L'équipe doit pouvoir estimer le coût moyen de traitement d'un document pour planifier le budget et détecter les anomalies de consommation.

**Constat dans le code** :
[NON IMPLÉMENTÉ] — En l'absence de collecte des tokens consommés, aucune estimation de coût n'est possible.

**Verdict** : 🔴 **Non conforme** — Impossible d'estimer le coût de traitement.

**Recommandation** : Une fois les tokens collectés (cf. critère 1), calculer le coût moyen par type de document en utilisant la grille tarifaire Albert. Ajouter un widget dans l'admin Django affichant le coût estimé du dernier batch.
**Priorité** : P2 | **Effort** : S (une fois les tokens collectés)

---

## Synthèse du thème

| Critère | Verdict | Priorité | Effort |
|---------|---------|----------|--------|
| Ventilation des coûts | 🔴 Non conforme | P1 | S |
| Prompt Caching | 🟡 Partiel | P2 | S |
| Routage intelligent par modèle | 🟡 Partiel | P2 | M |
| Minimisation des tokens input | 🔴 Non conforme | P1 | M |
| Estimation du coût par document | 🔴 Non conforme | P2 | S |
