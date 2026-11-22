# Démo classify V2 (Streamlit)

Interface locale pour tester la **régression logistique** classify_v2 sur un PDF :

- upload en mémoire (rien n'est écrit sur disque) ;
- **Pipeline 1** : PyMuPDF4LLM (3 pages, OCR hybride Tesseract) → logreg ;
- option **Comparer pipeline prod** : **mistral-ocr sur tout le PDF** (même code que prod) → `openweight-medium` ;
- affichage TOP5, routage, temps des deux pipelines en parallèle.

## Prérequis

- Artefacts : `data/classify_v2/classify_v2_pipeline.joblib` et `classify_v2_thresholds.json`
- `.env` : `ALBERT_API_KEY`, `ALBERT_BASE_URL` pour le pipeline prod (OCR + LLM)

## Lancement

```bash
cd /chemin/vers/depenses-eclairees
source .venv/bin/activate
streamlit run docia/demo/classify_app.py --server.address localhost
```

## Pipelines

| | Extraction | Classification |
|---|------------|----------------|
| **P1** (comparaison) | **3 pages** → logreg → doc entier : **mistral** (AE, sous-traitance) ou **Tesseract** (autres `CONTENT_ANALYSIS`) | logreg |
| **P2** (prod) | mistral-ocr **document entier** | LLM openweight-medium |

Étape 3 P1 (logreg **accepté**) : `acte_engagement` / `sous_traitance` → mistral-ocr ; `ccap`, `rib`, etc. → Tesseract PyMuPDF4LLM sur tout le PDF.

Pas de RapidOCR dans l'interface : OCR local limité au routage PyMuPDF/Tesseract sur P1.