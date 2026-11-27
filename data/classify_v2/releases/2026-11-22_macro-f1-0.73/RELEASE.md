# Classify v2 release `2026-11-22_macro-f1-0.73`

- **Date (UTC)** : 2026-11-22T01:21:10+00:00
- **Git** : `f076878620b4`
- **HIERARCHY_REVISION** : `2026-11-21f-merge_ccp_ae_ccap`
- **Seuils** : tau=0.8500000000000001, margin=0.0
- **macro_f1 (test prod)** : 0.7297542538237907
- **macro_f1_classifier** : 0.9199267347365275

**Note** : Retrain C=100; KPI prod macro_f1~0.73; baseline avant campagne ccap/AE/ST

## Fichiers

- `classify_v2_pipeline.joblib`
- `classify_v2_thresholds.json`
- `reports/05_metrics.json`, `05_test_summary.md`, `RUN_SUMMARY.md`, `05_confusion_matrix.csv`

Charger : `load_pipeline(Path('.../releases/<tag>'))` + lire `classify_v2_thresholds.json`.
