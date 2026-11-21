# Classify V2

Supervised document classification (TF-IDF + logistic regression) for 8 target classes.

## Commands

```bash
python manage.py build_classify_v2_dataset
python manage.py import_annotation_audit data/classify_v2/reports/01_annotation_audit_sample.csv
python manage.py train_classify_v2
python manage.py train_classify_v2 --merge-financial \
  --disagreement-review-csv data/classify_v2/reports/06_disagreement_review_train_val_calib.csv \
  --write-patched-parquet
```

Offline training (no database) — depuis `data/classify_v2/documents_raw.parquet` :

```bash
python -m docia.file_processing.processor.classify.train_from_parquet \
  --coarse-hierarchy \
  --disagreement-review-csv data/classify_v2/reports/11_silver_corrections_for_train.csv \
  --write-patched-parquet
```

En mode coarse, le train **re-map** les `label_train` puis **re-split** (les splits V1 8-classes
ne couvraient pas les 19 parents au train).

Artifacts live under `data/classify_v2/` (gitignored).

## Golden test set (Grist, hors train V2)

Le jeu **test final** (`data/classify_test_final/`) fusionne `Classif_gt` et les tables `*_gt` des tests e2e.
Il sert d’évaluation / référence qualité, pas d’entraînement silver V2 par défaut.

```bash
python manage.py build_classify_test_final
python manage.py build_classify_test_final --dry-run
```

Enrichissement prod via `hash` → `Document` par défaut (`--skip-db-enrich` pour exporter sans DB).
Le parquet golden reprend le schéma **`documents_raw.parquet`** (`text_2000`, `filename_normalized`, …) ;
jointure silver par `hash` quand disponible.

Voir `data/classify_test_final/README.md`.

## Label hierarchy (evolving)

Business taxonomy and LLM-fine → coarse mapping live in `label_hierarchy.py`
(`HIERARCHY_REVISION`, `map_llm_to_coarse`). Update mappings there when document
classes change; use `list_unmapped_llm_labels()` on prod counts to spot gaps before training.

### Réentraînement avec parents coarse (17 classes)

### Métriques : classifieur vs routage LLM

- **Prod (KPI principal)** : **`macro_f1`** sur `pred_with_reject` (rejet compte dans le F1).
  `min_routing_f1` = pire F1 par classe ; `macro_recall` / `routing_recall_per_class` en diagnostic.
- **Classifieur (diagnostic)** : `macro_f1_classifier` sur `pred` sans seuils.
- **Séparation modèle (sans seuils)** : `auc_macro_ovr`, `auc_acte_engagement` — comparer modèles /
  calibration ; **ne remplace pas** le recall prod quand tau/margin envoient une part des docs au LLM.
- **Routage** : `llm_fallback_rate` = part confiée au LLM ;
  `labeled_accuracy_on_accepted` = précision sur les accepts uniquement.

Rapports train : `data/classify_v2/reports/05_test_summary.md` (sections séparées).

**KPI produit** : ne pas rater `acte_engagement`, `ccap`, `sous_traitance`, `rib`,
`avenant`, `devis` (`PRIORITY_COARSE_LABELS`). Les libellés LLM `ccp_simple` / `ccp_vae`
sont mappés vers `ccap` / `acte_engagement` (finesse CCP hors logreg). En mode coarse,
optionnels : poids priorité et seuils capture (`optimize_priority`, hors défaut). **Premier
retrain : macro-F1 sur le classifieur ; `choose_thresholds` avec **plafond**
`DEFAULT_MAX_LLM_FALLBACK_RATE` (40 % → LLM) sur le split calib**, plancher
`DEFAULT_MIN_ROUTING_F1` (plancher F1 minimal par classe au calib), objectif seuils =
**macro-F1 routage** (65 % global + 35 % macro-F1 classes prioritaires si `optimize_priority`).

```bash
python manage.py retune_classify_v2_thresholds
python manage.py retune_classify_v2_thresholds --max-llm-fallback-rate 0.35
python manage.py retune_classify_v2_thresholds --min-routing-f1 0.35
python manage.py retune_classify_v2_thresholds --no-routing-f1-floor
```

```bash
python manage.py prepare_classify_retrain
python manage.py build_classify_v2_dataset --coarse-hierarchy   # optionnel : rescan DB
python manage.py train_classify_v2 --coarse-hierarchy \
  --disagreement-review-csv data/classify_v2/reports/11_silver_corrections_for_train.csv \
  --write-patched-parquet
```

Avant retrain : désaccords **train** LLM vs logreg (parquet, coarse) :

```bash
python manage.py export_classify_v2_train_disagreement_review --rescore
python manage.py export_classify_v2_train_disagreement_review \
  --pool priority-agree-low-conf --per-class 40 --max-total 400
python manage.py prepare_classify_retrain
```

Parents : `acte_engagement`, `annexe`, `catalogue_prix`, `devis`, `ccap`, `cctp`,
`avenant`, `sous_traitance`, `rib`, `contrats_mixte`,
`messagerie`, `fiche_navette`, `outil_gestion`, `execution_commande`,
`certificats_administratifs`, `dossier_candidature`, `consultation_marche`.
En mode `--coarse-hierarchy`, le flux ratio-médiane utilise `CLASSES_RATIO_MEDIAN`
(affichées + devis, incl. navette et CCP). Révision : `label_hierarchy.HIERARCHY_REVISION`.

Dataset build streams the DB in small batches (`ROW_BATCH_SIZE=150`, text fetched 100 ids at a time) and
never materializes full tables in memory. Only selected rows (after hash dedup) are held until export.