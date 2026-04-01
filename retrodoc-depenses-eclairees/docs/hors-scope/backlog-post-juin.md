# Backlog post-juin

## Éléments identifiés lors de l'audit

Les éléments ci-dessous ne sont **pas dans le périmètre actuel** de la migration mais constituent des améliorations identifiées pour une phase ultérieure.

### Haute priorité

| # | Sujet | Justification | Effort estimé |
|---|---|---|---|
| 1 | **Score de confiance** | Aucun mécanisme de scoring n'existe. Critique pour SAP Chorus (données financières). | M |
| 2 | **Contrôle fenêtre de contexte LLM** | Le texte complet est envoyé sans troncature. Risque de réponse tronquée sur gros documents. | S |
| 3 | **Sauvegarde `llm_response` avant post-traitement** | Actuellement, la réponse brute est perdue si le post-traitement échoue. | S |
| 4 | **Intégration tests e2e en CI** | Les tests de qualité ne sont pas exécutés automatiquement. Régression non détectée. | S |
| 5 | **Ajout extraction `cctp`** | Attributs déjà définis dans le code, juste à ajouter dans `SUPPORTED_DOCUMENT_TYPES`. | XS |

### Priorité moyenne

| # | Sujet | Justification | Effort estimé |
|---|---|---|---|
| 6 | **Suppression code legacy `app/`** | Remplacer les imports restants par du code Django natif. | M |
| 7 | **Nettoyage dépendances** | Supprimer `faiss-cpu`, `scikit-learn`, `tiktoken`, `jupyter` des dépendances prod. | XS |
| 8 | **Extraction pour types manquants** | `bordereau_prix`, `facture`, `cctp` — parmi les types les plus fréquents classifiés mais non analysés. | L |
| 9 | **Versionnement des prompts** | Déplacer les prompts hors du code Python, permettre un rollback indépendant. | M |
| 10 | **Dashboard de suivi qualité** | Centraliser les métriques (logs, Grist, batch progress) dans un dashboard. | M |

### Basse priorité

| # | Sujet | Justification | Effort estimé |
|---|---|---|---|
| 11 | **Validation croisée inter-documents** | Comparer SIRET, société entre acte d'engagement, Kbis, attestation SIRENE. | L |
| 12 | **Gestion multi-langue** | Détection de langue + prompts adaptés pour documents non francophones. | L |
| 13 | **Support formats manquants** | `.csv`, `.msg`, `.ppt`, `.rtf` | M |
| 14 | **Workflow de validation humaine** | Interface pour corriger les extractions douteuses avant injection SAP. | L |
| 15 | **Pagination API sync** | `list_documents_for_ej` ne pagine pas. Risque si un EJ a beaucoup de PJ. | S |

## Légende effort

| Code | Signification |
|---|---|
| XS | < 1 jour |
| S | 1–3 jours |
| M | 1–2 semaines |
| L | > 2 semaines |

## Questions ouvertes (non résolues par l'audit)

| # | Question |
|---|---|
| Q1 | Quelle est la taille de la fenêtre de contexte des modèles Albert (`openweight-medium` = `mistral-small`, `mistral-medium-2508`) ? |
| Q2 | Le rate limiting distribué (`ALBERT_USE_RATE_LIMITER`) est-il activé en production ? |
| Q3 | Quel est le volume réel de données en production (nombre d'EJ, de documents, taille base) ? |
| Q4 | Les champs `DataEngagement.designation`, `descriptif_prestations` sont-ils peuplés ? Par quel processus ? |
| Q5 | L'API de synchronisation (`export_pj_ej`) est-elle l'API SAP Chorus standard ou un développement spécifique ? |
| Q6 | À quelle fréquence les tests e2e sont-ils exécutés et les données Grist mises à jour ? |
| Q7 | Quels sont les formats de documents les plus fréquents actuellement skippés ? |
| Q8 | Quel est le SLA de l'API Albert (disponibilité, temps de réponse garanti) ? |

**Source** : analyse complète du code source, `analyse-depenses-eclairees.md`
