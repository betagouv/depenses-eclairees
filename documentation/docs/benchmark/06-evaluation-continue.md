# Évaluation Continue & Golden Dataset

!!! abstract "Résumé"
    Des tests e2e existent avec un jeu de vérité terrain stocké dans Grist, et des fonctions de comparaison adaptées. Cependant, ces tests ne sont pas exécutés en CI, les métriques F1 ne sont pas calculées formellement, et il n'y a aucun mécanisme de détection de dérive. Verdict global : 🟡 Partiel.

## Références de l'état de l'art

Un prompt qui fonctionne aujourd'hui peut cesser de fonctionner demain — parce qu'on l'a modifié, parce que la DINUM a mis à jour le modèle Mistral, ou simplement parce que les documents ont changé de format. Le Golden Dataset est le filet de sécurité : un échantillon de documents dont on connaît les bonnes réponses, qu'on rejoue automatiquement pour vérifier que la qualité ne se dégrade pas. C'est l'équivalent des tests de non-régression, mais pour un LLM.

- **Frameworks d'évaluation LLM** — Ragas, DeepEval, TruLens pour mesurer Precision, Recall, F1, Faithfulness.
- **Golden Dataset** — jeu de référence versionné, rejoué en CI à chaque changement de prompt ou de modèle.
- **NIST AI RMF MEASURE 2.6** — mesurer les performances IA en continu et comparer à des baselines établies.

## Points de contrôle

### Golden Dataset

**État de l'art** : L'équipe doit maintenir un jeu de données de référence (Golden Dataset) composé de documents représentatifs avec les extractions attendues, validées manuellement par des experts métier.

**Constat dans le code** :
Un jeu de vérité terrain existe dans **Grist** et est utilisé par les tests e2e :

- `tests_e2e/test_quality_classification.py:24` : récupère les données depuis `get_data_from_grist(table="Classif_gt")`
- `tests_e2e/test_quality_acte_engagement.py`, `test_quality_ccap.py`, `test_quality_rib.py`, etc. : utilisent des tables Grist spécifiques par type de document
- Les tests comparent les résultats d'extraction avec les valeurs de référence via des fonctions de comparaison adaptées (exact, normalized, IBAN, durée, comparaison LLM pour les textes libres)

Le jeu de données couvre les types principaux : classification, acte d'engagement, CCAP, RIB, devis, fiche navette, DC4 (sous-traitance).

**Verdict** : 🟡 **Partiel** — Un Golden Dataset existe dans Grist, mais il n'est pas versionné dans Git (dépendance sur un service tiers) et sa maintenance n'est pas formalisée.

**Recommandation** : Exporter le Golden Dataset au format JSON dans le repo Git (`tests_e2e/golden_data/`) pour le versionner. Conserver Grist comme interface d'édition mais synchroniser les données dans Git comme source de vérité.
**Priorité** : P1 | **Effort** : M

---

### Exécution automatique en CI/CD

**État de l'art** : Les tests de qualité doivent être exécutés automatiquement à chaque PR modifiant les prompts, les attributs, ou le post-traitement. Un résultat dégradé doit bloquer le merge.

**Constat dans le code** :
Le workflow GitHub Actions (`.github/workflows/django.yml`) exécute uniquement :
```
pytest tests/
```
Les tests e2e dans `tests_e2e/` **ne sont pas exécutés en CI**. Le fichier de l'analyse le confirme : "Ces tests ne sont pas exécutés en CI (le workflow GitHub ne lance que `pytest tests/`, pas `tests_e2e/`)."

De plus, les tests e2e nécessitent un accès réseau (API Grist + API Albert), ce qui les rend difficiles à exécuter dans un runner CI standard.

**Verdict** : 🔴 **Non conforme** — Les tests de qualité ne sont pas automatisés en CI. Une régression de prompt ne sera pas détectée avant un contrôle humain manuel.

**Recommandation** : (1) Exporter les données Grist en fixtures locales pour exécution offline. (2) Créer un workflow CI dédié "quality-gate" déclenché sur les modifications des fichiers `processor/attributes/`, `classifier.py`, `analyze_content.py`. (3) Utiliser des réponses LLM mockées ou un appel réel Albert en mode CI (si un environnement de test Albert est disponible).
**Priorité** : P0 | **Effort** : L

---

### Métriques Precision / Recall / F1

**État de l'art** : Les métriques d'évaluation standard (Precision, Recall, F1) doivent être calculées par type de document et par champ, avec suivi de tendance dans le temps.

**Constat dans le code** :
Les tests e2e calculent des statistiques de qualité (nombre de correspondances exactes, comparaisons normalisées), mais :

- [NON IMPLÉMENTÉ] — Les métriques Precision, Recall et F1 ne sont pas calculées formellement.
- La classification e2e (`test_quality_classification.py:58`) calcule un `is_correct` binaire par document.
- Les tests d'extraction comparent champ par champ avec des fonctions adaptées, mais ne produisent pas de métriques agrégées standardisées.

**Verdict** : 🟡 **Partiel** — Des comparaisons existent mais les métriques standard ne sont pas calculées ni suivies.

**Recommandation** : Ajouter le calcul de Precision/Recall/F1 par type de document et par champ dans les tests e2e. Stocker les résultats dans un fichier de référence (`tests_e2e/metrics_baseline.json`) pour détecter les régressions.
**Priorité** : P1 | **Effort** : M

---

### Détection de dérive (Model Drift)

**État de l'art** : Quand la DINUM met à jour le modèle Mistral derrière Albert, la qualité des extractions peut changer sans modification du code. Un mécanisme de détection de dérive doit alerter quand les métriques se dégradent.

**Constat dans le code** :
[NON IMPLÉMENTÉ] — Aucun mécanisme de détection de dérive n'existe. Il n'y a pas de baseline de qualité stockée, pas de comparaison automatique entre les résultats actuels et les résultats précédents, pas d'alerte sur la dégradation.

Le seul indicateur indirect serait une augmentation des erreurs de post-traitement (SIRET invalides, IBAN non corrigeables), mais cela n'est pas monitoré.

**Verdict** : 🔴 **Non conforme** — Aucune détection de dérive. Un changement de modèle côté DINUM peut dégrader silencieusement la qualité.

**Recommandation** : Exécuter automatiquement (cron hebdomadaire) le Golden Dataset contre l'API Albert en production. Comparer les métriques F1 avec la baseline. Alerter si le F1 chute de plus de 5 points sur un type de document.
**Priorité** : P1 | **Effort** : M

---

### Échantillonnage en production

**État de l'art** : Un pourcentage des extractions en production (ex: 2% des documents à confiance élevée) doit être routé vers un contrôle humain aléatoire pour valider en continu la qualité réelle.

**Constat dans le code** :
[NON IMPLÉMENTÉ] — Aucun échantillonnage aléatoire, aucun workflow de revue humaine en production.

**Verdict** : 🔴 **Non conforme** — Pas de contrôle qualité continu en production.

**Recommandation** : Implémenter un flag aléatoire `Document.sampled_for_review = True` sur 2% des documents traités. Ajouter une vue admin Django listant les documents échantillonnés avec leur extraction pour revue.
**Priorité** : P2 | **Effort** : M

---

### Taux de correction manuelle

**État de l'art** : Le taux de corrections manuelles appliquées par les utilisateurs (si un workflow de correction existe) doit être mesuré et tracé dans le temps. C'est un indicateur de qualité réelle en production.

**Constat dans le code** :
[NON IMPLÉMENTÉ] — Il n'y a pas de workflow de correction manuelle. La vue 360° est en lecture seule. Le module `tracking` (source : `docia/tracking/`) enregistre des événements UI mais pas de corrections de données.

**Verdict** : 🔴 **Non conforme** — Prérequis : implémenter d'abord un workflow de correction.

**Recommandation** : Ce point est lié à l'implémentation du circuit de validation humaine (Thème 3). Une fois en place, mesurer le taux de correction par type de document et par champ.
**Priorité** : P2 | **Effort** : S (une fois le workflow en place)

---

## Synthèse du thème

| Critère | Verdict | Priorité | Effort |
|---------|---------|----------|--------|
| Golden Dataset | 🟡 Partiel | P1 | M |
| Exécution en CI/CD | 🔴 Non conforme | P0 | L |
| Métriques Precision/Recall/F1 | 🟡 Partiel | P1 | M |
| Détection de dérive | 🔴 Non conforme | P1 | M |
| Échantillonnage en production | 🔴 Non conforme | P2 | M |
| Taux de correction manuelle | 🔴 Non conforme | P2 | S |
