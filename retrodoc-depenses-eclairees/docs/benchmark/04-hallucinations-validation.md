# Prévention des Hallucinations & Validation Déterministe

!!! abstract "Résumé"
    Le pipeline utilise `response_format` JSON Schema pour contraindre la structure de sortie, et implémente un post-traitement déterministe solide (IBAN, SIRET, montants, adresses). Cependant, il n'y a pas d'auto-évaluation LLM, pas de validation Pydantic, et les contrôles de cohérence métier croisés (HT+TVA=TTC) sont absents. Verdict global : 🟡 Partiel.

## Références de l'état de l'art

L'hallucination est le talon d'Achille des LLM : le modèle génère une réponse qui "a l'air" correcte mais qui ne correspond pas au document source. Un SIRET inventé, un montant arrondi, un nom de société déformé — dans un flux financier vers SAP Chorus, chaque hallucination est une bombe à retardement. La parade combine deux approches complémentaires : des validateurs déterministes (Pydantic, regex, schwifty) qui vérifient les formats, et des techniques LLM (Chain-of-Verification) qui vérifient la fidélité au document source.

- **Faithfulness (Ragas/DeepEval)** — mesurer si l'extraction est fidèle au document source, pas inventée.
- **OWASP LLM09 (Overreliance)** — ne pas faire confiance aveuglément aux sorties du LLM, surtout en contexte financier.
- **Validation déterministe** — Pydantic ou JSON Schema côté applicatif pour garantir structure et types avant intégration.

## Points de contrôle

### Auto-évaluation LLM (Chain-of-Verification)

**État de l'art** : Un second appel LLM peut vérifier la fidélité (faithfulness) de l'extraction par rapport au document source. Le LLM évaluateur vérifie que chaque champ extrait est effectivement présent dans le texte d'origine, détectant ainsi les hallucinations.

**Constat dans le code** :
[NON IMPLÉMENTÉ] — Le pipeline effectue un seul appel LLM par document pour l'extraction (`analyze_content.py:103-121`). Il n'y a pas de second appel de vérification.

**Verdict** : 🔴 **Non conforme** — Aucun mécanisme anti-hallucination basé sur LLM.

**Recommandation** : Implémenter un appel LLM de vérification pour les champs critiques (montants, SIRET, IBAN) en production, et pour tous les champs dans les tests e2e. Utiliser un prompt "Vérifie que chaque valeur extraite est fidèle au texte source" avec le JSON extrait et le texte original.
**Priorité** : P1 | **Effort** : L

---

### Validation déterministe (Pydantic / JSON Schema applicatif)

**État de l'art** : Les sorties du LLM doivent être validées par un schéma strict côté applicatif (Pydantic, JSON Schema, Cerberus) avant toute utilisation. Cela garantit la structure, le typage et les contraintes métier.

**Constat dans le code** :
La validation structurelle est assurée **côté API** via le paramètre `response_format` (JSON Schema) :

- Classification : `response_format` avec `json_schema` de type array de strings (source : `classifier.py:65-72`)
- Extraction : `response_format` avec schéma spécifique par type de document, construit dynamiquement depuis les attributs (source : `analyze_content.py:43-78`)

Cependant, **côté applicatif**, il n'y a pas de validation Pydantic ou JSON Schema après réception de la réponse. Le `json.loads(content)` dans `client.py:206` parse le JSON mais ne le valide pas contre un schéma.

Le post-traitement (`post_processing_llm.py`) agit comme une validation implicite : les fonctions de nettoyage lèvent des `ValueError` si les champs attendus sont manquants (ex: `post_processing_duration` à la ligne 227, `post_processing_postal_address` à la ligne 427). Mais ces erreurs font crasher le step entier au lieu de marquer les champs individuels comme invalides.

**Verdict** : 🟡 **Partiel** — Validation structurelle via `response_format` côté API, mais pas de validation Pydantic côté applicatif. Les erreurs de post-traitement sont fatales au lieu d'être gracieuses.

**Recommandation** : Ajouter des modèles Pydantic par type de document pour valider la réponse LLM avant le post-traitement. Catch les `ValueError` du post-traitement au niveau du champ (pas du document) pour préserver les champs valides.
**Priorité** : P1 | **Effort** : M

---

### Utilisation de response_format JSON

**État de l'art** : L'option `response_format: {"type": "json_object"}` ou mieux `{"type": "json_schema"}` force le LLM à produire du JSON valide, éliminant le risque de texte conversationnel parasite.

**Constat dans le code** :
Le code utilise `response_format` avec `json_schema` strict pour les deux appels LLM :

- **Classification** (source : `classifier.py:65-72`) :
```python
response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "ClassificationList",
        "strict": True,
        "schema": {"type": "array", "items": {"type": "string"}},
    },
}
```

- **Extraction** (source : `analyze_content.py:71-78`) : schéma dynamique avec `properties` et `required` construits depuis les attributs du type de document.

L'utilisation de `"strict": True` dans le schéma de classification est une bonne pratique. Le schéma d'extraction ne spécifie pas `"strict": True` mais utilise `required` pour tous les champs.

**Verdict** : 🟢 **Conforme** — Le `response_format` JSON Schema est correctement utilisé pour les deux appels LLM.

**Recommandation** : Ajouter `"strict": True` au schéma d'extraction pour renforcer la conformité.
**Priorité** : P2 | **Effort** : S

---

### Contrôles de cohérence métier

**État de l'art** : Des règles métier déterministes doivent vérifier la cohérence des données extraites : HT + TVA = TTC, date facture < date échéance, SIRET au format 14 chiffres, montants dans des fourchettes plausibles.

**Constat dans le code** :
Le post-traitement (`docia/file_processing/processor/post_processing_llm.py`) implémente :

| Contrôle | Implémenté | Source |
|---|---|---|
| SIRET 14 chiffres | 🟢 Oui | `post_processing_siret` (L311-330) |
| IBAN valide (ISO 13616) | 🟢 Oui | `check_consistency_iban` via schwifty (L13-25) |
| Correction IBAN 1 caractère | 🟢 Oui | `try_correct_false_iban` (L28-53) |
| BIC 8 ou 11 caractères | 🟢 Oui | `post_processing_bic` (L375-382) |
| Code postal 5 chiffres | 🟢 Oui | `post_processing_postal_address` (L443-449) |
| Montants : extraction numérique | 🟢 Oui | `post_processing_amount` (L125-150) |
| HT + TVA = TTC | 🔴 Non | — |
| Date facturation < date échéance | 🔴 Non | — |
| Montants dans fourchettes plausibles | 🔴 Non | — |
| SIREN = 9 premiers chiffres du SIRET | 🔴 Non | — |

Les validations existantes sont solides et bien testées (17 fichiers de tests dans `tests/docia/file_processing/processor/post_processing_llm/`). Mais les contrôles croisés (cohérence inter-champs) sont absents.

**Verdict** : 🟡 **Partiel** — Excellente validation unitaire par champ (IBAN, SIRET, montants, adresses). Absence de contrôles de cohérence croisés.

**Recommandation** : Ajouter des validations croisées : (1) vérifier HT × (1 + TVA) ≈ TTC avec une tolérance de 1%, (2) vérifier SIREN cohérent avec SIRET, (3) ajouter des fourchettes de montants plausibles (> 0, < 1 milliard €).
**Priorité** : P1 | **Effort** : M

---

### Nettoyage du texte conversationnel LLM

**État de l'art** : Même avec `response_format`, certains modèles ou configurations peuvent produire du texte parasite avant ou après le JSON. Le parseur doit gérer ce cas.

**Constat dans le code** :
Le code utilise `response_format` JSON Schema, ce qui élimine ce risque côté API. Le `json.loads(content)` dans `client.py:206` échouera si la réponse n'est pas du JSON valide, ce qui déclenchera un `FAILURE` du step.

Le `content.strip()` appliqué à `client.py:195` retire les espaces et retours à la ligne en tête/fin.

**Verdict** : 🟢 **Conforme** — Le `response_format` JSON Schema élimine le risque de pollution textuelle.

**Recommandation** : Aucune action immédiate. Le risque est correctement couvert.
**Priorité** : — | **Effort** : —

---

## Synthèse du thème

| Critère | Verdict | Priorité | Effort |
|---------|---------|----------|--------|
| Auto-évaluation LLM | 🔴 Non conforme | P1 | L |
| Validation Pydantic/JSON Schema applicatif | 🟡 Partiel | P1 | M |
| response_format JSON | 🟢 Conforme | P2 | S |
| Contrôles de cohérence métier | 🟡 Partiel | P1 | M |
| Nettoyage texte conversationnel | 🟢 Conforme | — | — |
