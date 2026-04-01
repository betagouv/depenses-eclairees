# Fenêtre de Contexte & Stratégie de Chunking

!!! abstract "Résumé"
    Le pipeline envoie le texte intégral des documents au LLM sans aucune vérification du nombre de tokens ni stratégie de chunking. Un document volumineux peut silencieusement dépasser la fenêtre de contexte du modèle, entraînant une extraction tronquée ou une erreur. Verdict global : 🔴 Non conforme.

## Références de l'état de l'art

Un LLM a une "mémoire de travail" limitée : la fenêtre de contexte (32k-128k tokens pour Mistral). Si on envoie un contrat de 80 pages sans vérifier, deux choses peuvent arriver — et aucune n'est bonne : soit l'API tronque silencieusement le texte (et on perd les dernières pages), soit elle retourne une erreur. Pire, même quand le document tient dans la fenêtre, la recherche "Lost in the Middle" (Liu et al., 2023) montre que le LLM prête moins attention aux informations au milieu du texte. Un SIRET mentionné en page 10 d'un contrat de 20 pages a plus de chances d'être ignoré que s'il était en page 1 ou page 20.

- **"Lost in the Middle" (Liu et al., 2023)** — attention dégradée au milieu des contextes longs.
- **Fenêtres de contexte Mistral** — 32k à 128k tokens selon le modèle ; dépassement = troncature silencieuse ou erreur.
- **Chunking sémantique** — découper par sections logiques du document plutôt que par nombre brut de tokens.

## Points de contrôle

### Gestion des documents longs

**État de l'art** : Avant chaque appel LLM, le nombre de tokens du prompt complet (system + user + texte du document) doit être vérifié contre la fenêtre de contexte du modèle. Si le document dépasse, une stratégie de chunking ou de troncature intelligente doit être appliquée.

**Constat dans le code** :
[NON IMPLÉMENTÉ] — Le texte intégral est envoyé au LLM sans aucune vérification :

```python
user_prompt = f"Analyse le contexte suivant et réponds à la question : {question}\n\nContexte : {text}"
```
(source : `docia/file_processing/processor/analyze_content.py:115`)

- `tiktoken` est présent dans les dépendances (`pyproject.toml`) mais **n'est jamais importé ni utilisé** dans le code du pipeline.
- Aucun comptage de tokens n'est effectué avant l'appel API.
- La fenêtre de contexte du modèle n'est pas configurée ni vérifiée.
- Le seul contrôle de taille est `text[:2000]` pour la classification (source : `classifier.py:35`), mais pas pour l'extraction.

Le rétro-doc confirme : "Le texte complet du document est envoyé au LLM sans vérification du nombre de tokens."

**Verdict** : 🔴 **Non conforme** — Absence totale de contrôle de la fenêtre de contexte. Risque critique d'extraction tronquée ou d'erreur silencieuse sur les documents longs.

**Recommandation** : (1) Utiliser `tiktoken` pour compter les tokens du prompt avant l'appel API. (2) Définir une constante `MAX_CONTEXT_TOKENS` par modèle. (3) Si le document dépasse, appliquer une troncature intelligente (garder début + fin, ou chunking sémantique).
**Priorité** : P0 | **Effort** : M

---

### Troncature silencieuse vs chunking

**État de l'art** : La troncature silencieuse (perte de données en fin de document) est inacceptable dans un contexte d'extraction financière. Si le document dépasse la fenêtre, il doit être soit découpé en chunks avec agrégation des résultats, soit routé vers un traitement spécifique.

**Constat dans le code** :
Deux scénarios de troncature sont possibles :

1. **Côté API** : Si le prompt dépasse la fenêtre de contexte, l'API Albert/Mistral peut soit tronquer silencieusement le prompt, soit retourner une erreur HTTP 400. Le comportement exact dépend de la version de l'API et n'est pas documenté.

2. **Côté code** : Aucune troncature n'est implémentée côté applicatif. Le texte complet est envoyé.

Le `timeout=180` secondes (source : `client.py:86`) est le seul garde-fou indirect — un prompt très long pourrait provoquer un timeout.

**Verdict** : 🔴 **Non conforme** — Ni troncature intelligente ni chunking. Le comportement sur les documents longs est imprévisible.

**Recommandation** : Implémenter une stratégie en 3 niveaux : (1) Si tokens < MAX_CONTEXT × 0.8 → envoi direct. (2) Si tokens < MAX_CONTEXT × 1.5 → troncature intelligente (garder les 70% premiers + 30% derniers tokens). (3) Si tokens > MAX_CONTEXT × 1.5 → chunking sémantique par sections du document.
**Priorité** : P0 | **Effort** : L

---

### Stratégie de chunking

**État de l'art** : Le chunking doit être sémantique (par sections logiques du document : en-tête, articles, annexes) plutôt que mécanique (par nombre de tokens). Les chunks doivent se chevaucher (overlap) pour éviter de couper une information critique en deux.

**Constat dans le code** :
[NON IMPLÉMENTÉ] — Aucun mécanisme de chunking n'existe.

Le module `app/processor/select_relevant_content.py` (code legacy) contient potentiellement une logique de sélection de contenu pertinent, mais il est exclu de ruff (non maintenu) et le champ `Document.relevant_content` n'est jamais peuplé dans le pipeline actuel (source : analyse rétro-doc).

**Verdict** : 🔴 **Non conforme** — Pas de chunking implémenté.

**Recommandation** : Pour un MVP, implémenter un chunking mécanique par nombre de tokens (chunks de 80% de la fenêtre, overlap de 10%). À terme, implémenter un chunking sémantique basé sur les marqueurs de section du document (titres, articles, numéros de page).
**Priorité** : P1 | **Effort** : L

---

### Agrégation des résultats multi-chunks

**État de l'art** : Si un document est découpé en chunks, les résultats d'extraction de chaque chunk doivent être agrégés intelligemment : fusion des champs complémentaires, résolution des conflits (valeurs différentes pour le même champ), vérification de cohérence.

**Constat dans le code** :
[NON IMPLÉMENTÉ] — Prérequis : implémenter le chunking.

**Verdict** : 🔴 **Non conforme** — Prérequis non rempli.

**Recommandation** : Lors de l'implémentation du chunking, prévoir une fonction d'agrégation qui : (1) fusionne les champs non-null de chaque chunk, (2) en cas de conflit, prend la valeur la plus fréquente ou celle du premier chunk, (3) logue les conflits pour analyse.
**Priorité** : P1 | **Effort** : M

---

### Effet "Lost in the Middle"

**État de l'art** : Les LLM prêtent moins attention aux informations situées au milieu d'un long contexte (Liu et al., 2023). Pour l'extraction, cela signifie que les informations critiques en milieu de document peuvent être ignorées.

**Constat dans le code** :
[NON IMPLÉMENTÉ] — Aucune mitigation de l'effet "Lost in the Middle" n'est implémentée. Le texte est envoyé dans l'ordre séquentiel du document.

**Verdict** : 🔴 **Non conforme** — Pas de mitigation. Risque accru pour les documents longs avec informations critiques en milieu de texte (ex: SIRET mentionné uniquement en page 5 d'un contrat de 20 pages).

**Recommandation** : Pour les documents longs, restructurer le prompt pour placer les informations de contexte les plus critiques (premières pages, dernières pages) en début et fin de prompt. Le "milieu" peut contenir le corps du document, moins critique pour l'extraction de métadonnées.
**Priorité** : P2 | **Effort** : S

---

### Documents hors-normes

**État de l'art** : Les documents hors-normes (> 20 Mo, > 500 pages) doivent être détectés en amont et routés vers un traitement spécifique (extraction partielle, file d'exception humaine, rejet).

**Constat dans le code** :
Le code gère partiellement les gros documents au niveau du téléchargement :

```python
max_retries = 2 if doc.size_mo < 21 else 0
```
(source : analyse rétro-doc — le code de téléchargement réduit les retries pour les documents > 21 Mo)

Cependant, une fois téléchargé, **aucune vérification de taille n'est faite avant le traitement** :
- Pas de limite de taille sur `Document.text` (source : modèle Django `Document`)
- Pas de limite de nombre de pages avant OCR
- Pas de detection de documents anormalement longs avant l'appel LLM

**Verdict** : 🔴 **Non conforme** — Les documents hors-normes ne sont pas détectés ni routés.

**Recommandation** : Ajouter des gardes-fous : (1) rejeter les documents > 50 Mo avec un message d'erreur explicite, (2) limiter l'OCR à 100 pages maximum, (3) logger un warning pour les documents dont le texte dépasse 100k tokens.
**Priorité** : P0 | **Effort** : S

---

## Synthèse du thème

| Critère | Verdict | Priorité | Effort |
|---------|---------|----------|--------|
| Gestion des documents longs | 🔴 Non conforme | P0 | M |
| Troncature vs chunking | 🔴 Non conforme | P0 | L |
| Stratégie de chunking | 🔴 Non conforme | P1 | L |
| Agrégation multi-chunks | 🔴 Non conforme | P1 | M |
| Lost in the Middle | 🔴 Non conforme | P2 | S |
| Documents hors-normes | 🔴 Non conforme | P0 | S |
