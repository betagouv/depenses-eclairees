# Scores de Confiance & Logprobs

!!! abstract "Résumé"
    Le pipeline ne récupère pas les logprobs, ne calcule aucun score de confiance et n'implémente aucun seuil de rejet. Les extractions sont injectées tel quel sans circuit de validation gradué. Verdict global : 🔴 Non conforme.

## Références de l'état de l'art

Un LLM ne dit jamais "je ne sais pas" — il produit toujours une réponse, même quand il invente. Les logprobs (log-probabilités des tokens générés) sont le principal signal disponible pour mesurer à quel point le modèle est "sûr de lui". Concrètement, si le LLM hésite entre "12345678901234" et "12345678901235" pour un SIRET, les logprobs le révèlent. Sans ce signal, on ne peut pas distinguer une extraction fiable d'une hallucination.

- **API Mistral logprobs** — paramètre `logprobs=True` pour obtenir les probabilités token par token.
- **Human-in-the-Loop** — router les extractions à faible confiance vers une revue humaine plutôt que de tout accepter aveuglément.
- **NIST AI RMF MEASURE 2.5** — les systèmes IA doivent quantifier et communiquer leur incertitude.

## Points de contrôle

### Récupération des logprobs

**État de l'art** : L'appel API doit activer `logprobs=True` pour obtenir les probabilités token par token. Ces logprobs sont la base de tout calcul de confiance.

**Constat dans le code** :
L'appel `chat.completions.create()` dans `docia/file_processing/llm/client.py:189-194` ne passe pas le paramètre `logprobs` :

```python
response = self.client.chat.completions.create(
    model=model,
    messages=messages,
    temperature=temperature,
    response_format=response_format if response_format else None,
)
```

Seul le contenu textuel est extrait : `response.choices[0].message.content.strip()` (source : `client.py:195`). Les métadonnées de la réponse (usage, logprobs, finish_reason) sont ignorées.

**Verdict** : 🔴 **Non conforme** — Les logprobs ne sont pas demandés ni exploités.

**Recommandation** : Ajouter `logprobs=True, top_logprobs=5` à l'appel API. Stocker les logprobs dans un champ dédié du modèle `ProcessDocumentStep` ou `Document`. Vérifier au préalable que l'API Albert supporte ce paramètre (non garanti sur OpenGateLLM).
**Priorité** : P1 | **Effort** : M

---

### Exploitation des logprobs en score de confiance

**État de l'art** : Les logprobs doivent être agrégés en un score de confiance global (moyenne des log-probabilités des tokens structurants) et/ou par champ (logprobs des tokens correspondant à chaque valeur extraite). Un score par champ permet un circuit de validation plus fin.

**Constat dans le code** :
[NON IMPLÉMENTÉ] — Aucun calcul de score de confiance n'existe. Le seul proxy est le "taux de remplissage" calculé dans la vue web :

```python
def compute_ratio_data_extraction(document_data: dict) -> float:
    total_keys = len(document_data.keys())
    total_extracted = len([x for x in document_data.values() if x])
    return total_extracted / total_keys if total_keys > 0 else 0
```
(source : `docia/views.py`)

Ce ratio mesure la complétude (combien de champs sont non-vides), pas la confiance (probabilité que les valeurs soient correctes).

**Verdict** : 🔴 **Non conforme** — Aucun score de confiance calculé.

**Recommandation** : Implémenter un score de confiance en 3 niveaux : (1) confiance globale basée sur les logprobs moyens, (2) confiance par champ basée sur les logprobs des tokens de la valeur, (3) heuristique de validation post-traitement (IBAN valide = bonus, SIRET invalide = malus).
**Priorité** : P1 | **Effort** : L

---
Seuil de confiance et human-in-the-loop
### 

**État de l'art** : Un seuil de confiance paramétrable doit router les extractions sous le seuil vers une file de revue humaine (Human-in-the-Loop). C'est une exigence critique pour un système financier automatisé.

**Constat dans le code** :
[NON IMPLÉMENTÉ] — Aucun seuil de confiance, aucune file d'exception humaine, aucun workflow de revue n'existe dans le code. Toutes les extractions qui ne lèvent pas d'erreur technique sont stockées directement dans `Document.structured_data`.

**Verdict** : 🔴 **Non conforme** — Absence de circuit de validation humaine. Critique dans le contexte d'un flux financier étatique.

**Recommandation** : Ajouter un champ `confidence_level` (HIGH/MEDIUM/LOW) au modèle `Document`. Les extractions LOW sont marquées comme "à vérifier". Implémenter une vue d'administration Django permettant aux agents de valider/corriger les extractions.
**Priorité** : P0 | **Effort** : L

---

### Circuit de validation gradué

**État de l'art** : L'intégration avec un ERP comme SAP ne doit pas être binaire (tout ou rien). Un circuit gradué permet : (1) intégration automatique si confiance haute, (2) revue humaine si confiance moyenne, (3) rejet si confiance basse ou données incohérentes.

**Constat dans le code** :
L'approche actuelle est binaire : si l'extraction technique réussit (pas d'exception), les données sont stockées dans `Document.structured_data` sans aucune qualification. Il n'y a pas de distinction entre une extraction de haute qualité et une extraction douteuse.

La vue 360° (`docia/views.py`) affiche les données extraites avec le taux de remplissage, mais sans indication de confiance.

**Verdict** : 🔴 **Non conforme** — Pas de circuit de validation gradué.

**Recommandation** : Concevoir un workflow à 3 niveaux de confiance avec des règles de routage claires. Commencer par un MVP : flag binaire "à vérifier" basé sur les échecs de post-traitement (IBAN invalide, SIRET absent, montants incohérents).
**Priorité** : P0 | **Effort** : L

---

### Journalisation des scores de confiance

**État de l'art** : Les scores de confiance doivent être journalisés et stockés pour permettre une analyse a posteriori de la distribution de confiance, la calibration du seuil, et la détection de dérive.

**Constat dans le code** :
[NON IMPLÉMENTÉ] — En l'absence de scores de confiance, il n'y a rien à journaliser.

**Verdict** : 🔴 **Non conforme** — Prérequis : implémenter d'abord les scores de confiance.

**Recommandation** : Une fois les scores implémentés, les stocker dans la base (champ JSON sur `Document`) et les exporter vers un outil de monitoring pour suivre l'évolution de la distribution.
**Priorité** : P1 | **Effort** : S (une fois les scores implémentés)

---

## Synthèse du thème

| Critère | Verdict | Priorité | Effort |
|---------|---------|----------|--------|
| Récupération des logprobs | 🔴 Non conforme | P1 | M |
| Score de confiance | 🔴 Non conforme | P1 | L |
| Seuil et file d'exception humaine | 🔴 Non conforme | P0 | L |
| Circuit de validation gradué | 🔴 Non conforme | P0 | L |
| Journalisation des scores | 🔴 Non conforme | P1 | S |
