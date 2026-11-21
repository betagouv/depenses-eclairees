# Corpus profile (classify V2)

Exploration **hors prod** : courbe de croissance du vocabulaire TF-IDF texte (réglages logreg) en fonction du nombre de documents.

## Commande

```bash
python manage.py explore_classify_corpus
python manage.py explore_classify_corpus --scope all --by-class
python manage.py explore_classify_corpus --n-grid 5000 10000 50000
```

Artefacts : `data/classify_v2/corpus_profile/`.

## Lecture

- `01_vocab_vs_n.csv` : `vocab_size`, `hit_max_features`, `new_types_vs_prev` pour chaque taille N (échantillons imbriqués stratifiés par `label_train`).
- **Saturation** : `hit_max_features` vrai sur les derniers points **et** `new_types_vs_prev` faible → le cap 50k domine ; plus de docs n’enrichit presque plus le texte.
- **Pas saturé** : vocab &lt; 50k au train complet → marge avant de toucher à `max_features`.
- `02_*` (option `--by-class`) : classes rares peuvent avoir peu de types (effet `min_df=2`).

Plafond caractères / troncature : **hors scope** de ce module.