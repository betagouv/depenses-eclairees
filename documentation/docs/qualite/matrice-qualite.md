# Matrice de qualité

!!! tip "Template — À compléter en atelier 2"

    Cette matrice est un template à remplir lors de l'[Atelier 2 — Extraction & Qualité](../ateliers/atelier-2-extraction-qualite.md). Les colonnes « Précision mesurée » et « Rappel mesuré » doivent être renseignées à partir des résultats des tests e2e.

## Matrice par type de document

### acte_engagement (~20 attributs)

| Attribut | Type | Critique SAP ? | Précision mesurée | Rappel mesuré | Commentaire |
|---|---|---|---|---|---|
| `objet_marche` | string | ✅ | [À MESURER] | [À MESURER] | Comparaison LLM dans tests e2e |
| `forme_marche` | object | ✅ | [À MESURER] | [À MESURER] | Logique conditionnelle complexe |
| `administration_beneficiaire` | string | ✅ | [À MESURER] | [À MESURER] | Comparaison LLM |
| `societe_principale` | string | ✅ | [À MESURER] | [À MESURER] | Post-processing strip nom |
| `siret_mandataire` | string | ✅ | [À MESURER] | [À MESURER] | Validation 14 chiffres |
| `siren_mandataire` | string | ✅ | [À MESURER] | [À MESURER] | Aucun post-traitement — champ passé brut (absent de CLEAN_FUNCTIONS) |
| `rib_mandataire` | object | ✅ | [À MESURER] | [À MESURER] | Validation IBAN schwifty |
| `cotraitants` | array | ⚠️ | [À MESURER] | [À MESURER] | |
| `sous_traitants` | array | ⚠️ | [À MESURER] | [À MESURER] | |
| `montant_ht` | string | ✅ | [À MESURER] | [À MESURER] | Post-processing montant |
| `montant_ttc` | string | ✅ | [À MESURER] | [À MESURER] | Post-processing montant |
| `duree` | object | ✅ | [À MESURER] | [À MESURER] | Structure JSON complexe |

### ccap (~10 attributs)

| Attribut | Type | Critique SAP ? | Précision mesurée | Rappel mesuré | Commentaire |
|---|---|---|---|---|---|
| `objet_marche` | string | ✅ | [À MESURER] | [À MESURER] | |
| `id_marche` | string | ✅ | [À MESURER] | [À MESURER] | Format non standardisé |
| `lots` | array | ✅ | [À MESURER] | [À MESURER] | |
| `forme_marche` | object | ✅ | [À MESURER] | [À MESURER] | Logique oneOf complexe |
| `duree_marche` | object | ✅ | [À MESURER] | [À MESURER] | |

### rib (6 attributs)

| Attribut | Type | Critique SAP ? | Précision mesurée | Rappel mesuré | Commentaire |
|---|---|---|---|---|---|
| `iban` | string | ✅ | [À MESURER] | [À MESURER] | Validation schwifty |
| `bic` | string | ✅ | [À MESURER] | [À MESURER] | |
| `titulaire_compte` | string | ✅ | [À MESURER] | [À MESURER] | |

### devis (11 attributs)

| Attribut | Type | Critique SAP ? | Précision mesurée | Rappel mesuré | Commentaire |
|---|---|---|---|---|---|
| `objet` | string | ✅ | [À MESURER] | [À MESURER] | Avec raisonnement |
| `titulaire` | object | ✅ | [À MESURER] | [À MESURER] | JSON structuré |
| `montants` | object | ✅ | [À MESURER] | [À MESURER] | ht/tva/ttc numériques |

## Résumé par type

| Type | Nb attributs | Attributs critiques SAP | Couverture tests e2e |
|---|---|---|---|
| `acte_engagement` | ~20 | ~12 | ✅ `test_quality_acte_engagement.py` |
| `ccap` | ~10 | ~5 | ✅ `test_quality_ccap.py` |
| `rib` | 6 | 3 | ✅ `test_quality_rib.py` |
| `fiche_navette` | 14 | ~5 | ✅ `test_quality_fiche_navette.py` |
| `devis` | 11 | ~4 | ✅ `test_quality_devis.py` |
| `bon_de_commande` | 10 | ~5 | ❌ Pas de test e2e dédié |
| `avenant` | 10 | ~5 | ❌ Pas de test e2e dédié |
| `sous_traitance` | 16 | ~8 | ✅ `test_quality_dc4.py` |
| `kbis` | 4 | 2 | ❌ Pas de test e2e dédié |
| `att_sirene` | 5 | 3 | ❌ Pas de test e2e dédié |

!!! warning "Types sans test e2e"

    `bon_de_commande`, `avenant`, `kbis`, `att_sirene` n'ont pas de test de qualité dédié. La qualité de l'extraction n'est pas mesurée pour ces types.

**Source** : `tests_e2e/`, `docia/file_processing/processor/attributes/*.py`
