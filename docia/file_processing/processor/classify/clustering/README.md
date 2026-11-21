# Clustering exploratoire (libellé LLM)

Outil **hors prod** : homogénéité du silver LLM par `classification` fine.

## Commande

```bash
python manage.py explore_classify_cluster acte_engagement
python manage.py explore_classify_cluster --all-core-five
```

Artefacts : `data/classify_v2/clustering/<classification>/text_only/` (défaut).

`--features full` aligne filename + nb_mot sur le logreg (souvent dominé par le nom de fichier).

## Lecture

- `01_k_metrics.csv` : comparer k (silhouette sur échantillon si n > 10k).
- `04_cluster_top_terms.csv` : profil lexical par grappe.
- `05_review_sample.csv` : revue humaine par `review_cluster`.

Une grappe peut reflixer une **erreur LLM**, pas un sous-type métier.

## Qualité des grappes

- **text_only** + stop words français (liste locale) + `max_df=0.85` + tokens sans chiffres isolés.
- Choix de **k** : plus le max silhouette brut (favorisait k=14) — plateau + taille min de grappe, cap k≤8.
- Silhouette **faible** (~0.1) sur AE = classe silver **hétérogène** ; le clustering aide l’échantillonnage revue, pas une taxonomie figée.