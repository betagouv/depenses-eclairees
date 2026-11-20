# Classify V2

Supervised document classification (TF-IDF + logistic regression) for 8 target classes.

## Commands

```bash
python manage.py build_classify_v2_dataset
python manage.py import_annotation_audit data/classify_v2/reports/01_annotation_audit_sample.csv
python manage.py train_classify_v2
```

Offline training (no database):

```bash
python -m docia.file_processing.processor.classify.train_from_parquet --output-dir data/classify_v2
```

Artifacts live under `data/classify_v2/` (gitignored).

Dataset build streams the DB in small batches (`ROW_BATCH_SIZE=150`, text fetched 100 ids at a time) and
never materializes full tables in memory. Only selected rows (after hash dedup) are held until export.