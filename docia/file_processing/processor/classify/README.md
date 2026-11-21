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

## Label hierarchy (evolving)

Business taxonomy and LLM-fine → coarse mapping live in `label_hierarchy.py`
(`HIERARCHY_REVISION`, `map_llm_to_coarse`). Update mappings there when document
classes change; use `list_unmapped_llm_labels()` on prod counts to spot gaps before training.

### Réentraînement avec parents coarse (19 classes)

**KPI produit** : ne pas rater `acte_engagement`, `ccap`, `sous_traitance`, `rib`,
`ccp_simple`, `ccp_vae`, `avenant`, `devis` (`PRIORITY_COARSE_LABELS`). En mode coarse,
optionnels : poids priorité et seuils capture (`optimize_priority`, hors défaut). **Premier
retrain : macro-F1 / `choose_thresholds` classique** (`acc - false_accept`).

```bash
python manage.py prepare_classify_retrain
python manage.py build_classify_v2_dataset --coarse-hierarchy   # optionnel : rescan DB
python manage.py train_classify_v2 --coarse-hierarchy \
  --disagreement-review-csv data/classify_v2/reports/11_silver_corrections_for_train.csv \
  --write-patched-parquet
```

Parents : `acte_engagement`, `annexe`, `catalogue_prix`, `devis`, `ccap`, `cctp`,
`ccp_simple`, `ccp_vae`, `avenant`, `sous_traitance`, `rib`, `contrats_mixte`,
`messagerie`, `fiche_navette`, `outil_gestion`, `execution_commande`,
`certificats_administratifs`, `dossier_candidature`, `consultation_marche`.
En mode `--coarse-hierarchy`, le flux ratio-médiane utilise `CLASSES_RATIO_MEDIAN`
(affichées + devis, incl. navette et CCP). Révision : `label_hierarchy.HIERARCHY_REVISION`.

Dataset build streams the DB in small batches (`ROW_BATCH_SIZE=150`, text fetched 100 ids at a time) and
never materializes full tables in memory. Only selected rows (after hash dedup) are held until export.