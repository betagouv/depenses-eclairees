# Tailles réelles

!!! info "Données estimées"

    Les tailles ci-dessous sont estimées à partir des schémas JSON, des consignes de prompts et des types PostgreSQL. Les volumes réels de production n'ont pas été mesurés lors de l'audit. Si des métriques de production sont disponibles, elles devront compléter cette page.

## Taille des données structurées par type de document

### Estimation du `structured_data` (JSON)

| Type | Nb attributs | Attributs complexes (JSON/array) | Taille estimée JSON |
|---|---|---|---|
| `acte_engagement` | ~20 | `forme_marche`, `rib_mandataire`, `cotraitants`, `sous_traitants`, `rib_autres`, `duree`, `montants_en_annexe` | **2–8 Ko** (selon cotraitants) |
| `ccap` | ~10 | `lots`, `forme_marche`, `forme_marche_lots`, `duree_marche`, `montant_maximum_lots` | **1–5 Ko** (selon lots) |
| `rib` | 6 | `adresse_postale_titulaire` | **0.5–1 Ko** |
| `fiche_navette` | 14 | — (tous scalaires) | **0.5–1 Ko** |
| `devis` | 11 | `titulaire`, `montants` | **1–3 Ko** |
| `bon_de_commande` | 10 | — (tous scalaires) | **0.5–1 Ko** |
| `avenant` | 10 | — (tous scalaires) | **0.5–1 Ko** |
| `sous_traitance` | 16 | `adresse_postale_titulaire`, `adresse_postale_sous_traitant`, `duree`, `rib_sous_traitant` | **1–3 Ko** |
| `kbis` | 4 | — | **0.2–0.5 Ko** |
| `att_sirene` | 5 | — | **0.2–0.5 Ko** |

### Estimation du texte extrait (`Document.text`)

| Type de document | Taille texte typique | Cas extrême |
|---|---|---|
| PDF natif (acte engagement) | 5–50 Ko | > 200 Ko (document multi-lots) |
| PDF scanné → OCR | 2–20 Ko | > 100 Ko (OCR bruyant) |
| DOCX | 5–30 Ko | > 100 Ko |
| Excel → markdown | 2–10 Ko | > 50 Ko (gros tableaux) |
| RIB (1 page) | 0.5–2 Ko | — |
| Image → OCR | 0.5–5 Ko | — |

## Taille des prompts envoyés au LLM

### Classification

| Composant | Taille estimée |
|---|---|
| System prompt | ~80 caractères |
| Catalogue catégories (~50) | ~3 000 caractères |
| Texte document (tronqué) | **2 000 caractères max** |
| **Total prompt classification** | **~5 000 caractères (~1 500 tokens)** |

### Extraction (content_analysis)

| Composant | Taille estimée |
|---|---|
| System prompt | ~70 caractères |
| Consignes attributs (variable) | 2 000–8 000 caractères (selon type) |
| Texte document complet | **Variable, non tronqué** |
| **Total prompt extraction** | **2 500 + taille du document** |

!!! danger "Risque de dépassement de contexte"

    Le texte complet est envoyé sans vérification. Un document de 200 Ko (~50 000 tokens) ajouté aux consignes pourrait dépasser la fenêtre de contexte du modèle. La taille de la fenêtre de contexte de `mistral-medium-2508` sur l'infrastructure Albert n'est pas documentée dans le code.

## Estimation volumétrique pour SAP

!!! tip "Template à compléter avec les données de production"

    | Métrique | Valeur estimée | À vérifier |
    |---|---|---|
    | Nombre d'EJ | [NON TROUVÉ DANS LE CODE] | Requête SQL en production |
    | Nombre de documents | [NON TROUVÉ DANS LE CODE] | Requête SQL en production |
    | Taille moyenne `structured_data` | ~1–3 Ko/document | Mesurer `avg(pg_column_size(structured_data))` |
    | Taille moyenne `text` | ~10–30 Ko/document | Mesurer `avg(length(text))` |
    | Taille totale base (données) | [NON TROUVÉ DANS LE CODE] | `pg_database_size()` |
    | Taille totale S3 (fichiers) | [NON TROUVÉ DANS LE CODE] | Métrique S3 |
    | Documents traités/jour | 4 × batch/jour | Logs Celery |
    | Appels LLM/document | 2 (classification + extraction) | Code source |
    | Appels LLM/jour (estimé) | [NON TROUVÉ DANS LE CODE] | 2 × nb_documents/batch × 4 |

**Source** : `docia/file_processing/processor/attributes/*.py`, `docia/file_processing/processor/classifier.py`, schéma PostgreSQL
