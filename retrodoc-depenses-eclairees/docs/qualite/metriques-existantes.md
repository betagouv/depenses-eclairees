# Métriques existantes

## Score de confiance

!!! danger "Pas de score de confiance"

    Il **n'existe pas de score de confiance** explicite dans le pipeline. Le LLM est appelé avec `temperature=0.0` (déterministe) mais aucun score de probabilité ou de certitude n'est stocké.

### Proxy existant : taux de remplissage

Le seul proxy de qualité est calculé dans la vue web :

```python
# docia/views.py (verbatim)
def compute_ratio_data_extraction(document_data: dict) -> float:
    total_keys = len(document_data.keys())
    total_extracted = len([x for x in document_data.values() if x])
    return total_extracted / total_keys if total_keys > 0 else 0
```

Ce ratio est affiché sous forme de **pourcentage** dans l'interface 360° : il mesure la proportion de champs non vides dans `structured_data`.

**Limites** : un champ rempli par une hallucination du LLM est compté comme « extrait ». Ce ratio ne mesure pas la justesse.

## Mécanismes de suivi existants

| Mécanisme | Fichier | Description |
|---|---|---|
| Logs structurés | `docia/logging.py` | `request_id`, `session_id`, `celery_task_id` dans chaque log |
| Progression batch | `docia/file_processing/pipeline/utils.py` | Compteurs par étape (success, failure, skipped) |
| Tracking événements | `docia/tracking/` | API REST pour enregistrer des événements UI (Matomo-like) |
| Rate limiting web | `docia/ratelimit/` | Compteurs par utilisateur (200 requêtes/jour) |
| Erreurs de téléchargement | `DownloadDocumentError` | Enregistrement des erreurs de téléchargement |
| Grist | `app/grist/grist_api.py` | Export des résultats vers Grist (script `scripts/maj_grist_from_scalingo.py`) |

## Tests de qualité (e2e)

**Dossier** : `tests_e2e/`

| Test | Fichier | Type document |
|---|---|---|
| Classification | `test_quality_classification.py` | Tous |
| Acte d'engagement | `test_quality_acte_engagement.py` | `acte_engagement` |
| CCAP | `test_quality_ccap.py` | `ccap` |
| RIB | `test_quality_rib.py` | `rib` |
| Devis | `test_quality_devis.py` | `devis` |
| Fiche navette | `test_quality_fiche_navette.py` | `fiche_navette` |
| Sous-traitance (DC4) | `test_quality_dc4.py` | `sous_traitance` |
| Pipeline AE complet | `test_quality_pipeline_ae.py` | `acte_engagement` (pipeline intégral) |

### Fonctionnement des tests e2e

1. **Import** des données de référence depuis **Grist** (vérité terrain labellisée manuellement)
2. **Exécution** du pipeline d'extraction sur les documents de test
3. **Comparaison** avec des fonctions adaptées :
    - Comparaison exacte (string)
    - Comparaison normalisée (accents, casse)
    - Validation IBAN
    - Comparaison durée (JSON structuré)
    - **Comparaison via LLM** pour les champs textuels libres (objet, administration)
4. **Calcul** de statistiques globales de qualité

!!! warning "Tests e2e non exécutés en CI"

    Le workflow GitHub (`django.yml`) n'exécute que `pytest tests/`, pas `tests_e2e/`. Ces tests sont exécutés **manuellement** par l'équipe. L'équipe confirme effectuer des re-tests périodiques du pipeline complet avec des documents types pour détecter les régressions — notamment les performances de Mistral OCR sur des textes spécifiques — sans protocole d'évaluation formel.

**Source** : `docia/views.py`, `docia/logging.py`, `tests_e2e/`, `app/grist/grist_api.py`
