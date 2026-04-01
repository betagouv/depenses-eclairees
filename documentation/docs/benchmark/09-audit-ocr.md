# Audit de la Brique OCR

!!! abstract "Résumé"
    Le pipeline utilise un double moteur OCR : Tesseract (local, souverain) pour les images et Mistral OCR (via Albert) pour les PDF scannés. La distinction PDF natif/scanné est implémentée mais les métriques de qualité OCR (CER, WER) sont absentes, il n'y a pas de prétraitement d'image, et le rejet précoce des documents de mauvaise qualité OCR n'existe pas. Verdict global : 🟡 Partiel.

## Références de l'état de l'art

L'OCR est le maillon d'entrée de toute la chaîne : si le texte extrait est de mauvaise qualité, le LLM travaillera sur des données bruitées et produira des extractions dégradées — "garbage in, garbage out". Un SIRET mal lu (un "8" confondu avec un "3") ne sera pas corrigé par le LLM, il sera halluciné avec confiance. C'est pourquoi les bonnes pratiques imposent de mesurer la qualité OCR (CER/WER), de prétraiter les images (redressement, contraste), et de rejeter les documents illisibles avant d'appeler le LLM (coûteux et inutile sur du bruit).

- **CER / WER** — Character Error Rate et Word Error Rate, les métriques standard pour évaluer la qualité OCR.
- **LayoutLM / Document AI** — analyse de layout (tableaux, colonnes, en-têtes) avant extraction textuelle.
- **Prétraitement** — deskewing (redressement), binarisation (contraste), denoising (réduction du bruit), résolution minimale 300 DPI.

## Points de contrôle

### Choix technologique & souveraineté

#### Moteur OCR

**État de l'art** : Le moteur OCR doit être choisi en fonction du besoin (précision, vitesse, types de documents) et des contraintes de souveraineté (hébergement on-premise ou cloud souverain).

**Constat dans le code** :
Le pipeline utilise **deux moteurs OCR** :

1. **Tesseract** (via `tesserocr`, source : `text_extract_document.py:17,57-63,137`) :
    - Utilisé pour les **images** (PNG, JPG, TIFF) : `tesserocr.image_to_text(image, lang="fra")`
    - Utilisé comme fallback pour les **PDF scannés** si `ocr_tool="tesseract"` (source : `text_extract_document.py:56-63`)
    - Moteur OCR open-source, hébergé localement sur le serveur Scalingo
    - Installé via Aptfile : `tesseract-ocr`, `tesseract-ocr-fra` (pack langue française)

2. **Mistral OCR** (`mistral-ocr-2512`, source : `client.py:208-257`) :
    - Utilisé par défaut pour les **PDF scannés** (source : `text_extract_document.py:64-66`)
    - Appel REST à l'API Albert (DINUM), infrastructure souveraine française
    - Le PDF est envoyé en base64 et la réponse contient du markdown par page

Le choix du moteur OCR pour les PDF est paramétrable via `ocr_tool` (défaut : `"mistral-ocr"`, source : `text_extraction.py:44`).

**Verdict** : 🟢 **Conforme** — Double moteur OCR (local + souverain). Tesseract est open-source et local, Mistral OCR est sur infrastructure souveraine DINUM. Bonne architecture avec fallback.

**Recommandation** : Aucune action immédiate. Documenter le choix de moteur par défaut et les critères de bascule.
**Priorité** : — | **Effort** : —

---

#### Dimensionnement GPU

**État de l'art** : L'infrastructure GPU doit être dimensionnée pour absorber le pic de charge des batchs de nuit sans dégradation de latence.

**Constat dans le code** :
[NON VÉRIFIABLE DEPUIS LE CODE] — Tesseract utilise le CPU (pas de GPU). Mistral OCR est appelé via API (infrastructure gérée par la DINUM). Le dimensionnement n'est pas contrôlable depuis le code.

Le worker `heavy_cpu` est configuré avec concurrency=1 (source : `Procfile`), ce qui limite la charge OCR locale.

**Verdict** : ⚪ **Non applicable** — Le dimensionnement GPU relève de l'infrastructure Albert (DINUM), pas du code applicatif.

**Recommandation** : Vérifier avec la DINUM les SLA de l'API OCR et les limites de débit en pic de charge.
**Priorité** : P2 | **Effort** : S

---

### Préservation du layout et ordre de lecture

#### Analyse de layout

**État de l'art** : Les moteurs OCR modernes (LayoutLM, DocTR) effectuent une analyse de layout avant extraction textuelle pour préserver la structure logique du document (tableaux, colonnes, en-têtes, pieds de page).

**Constat dans le code** :
- **PDF natif** (PyMuPDF) : `page.get_text(sort=True)` (source : `text_extract_document.py:42`) — le paramètre `sort=True` ordonne les blocs de texte par position verticale puis horizontale. C'est un tri géométrique basique, pas une analyse de layout sémantique.
- **Mistral OCR** : retourne du **markdown structuré** (source : `client.py:29-36`), ce qui préserve une partie de la structure (titres, listes, tableaux).
- **Tesseract** : `tesserocr.image_to_text()` sans configuration de layout analysis — mode par défaut (source : `text_extract_document.py:62,137`).
- **Excel** : extraction en format **markdown tabulaire** avec `|` (source : `text_extract_excel.py`). Bonne pratique.

**Verdict** : 🟡 **Partiel** — Mistral OCR préserve la structure en markdown. PyMuPDF fait un tri géométrique. Tesseract utilise le mode par défaut sans analyse de layout explicite.

**Recommandation** : Pour Tesseract, configurer le PSM (Page Segmentation Mode) approprié selon le type de document. Pour PyMuPDF, envisager `page.get_text("dict")` pour une extraction structurée par blocs avec positions.
**Priorité** : P2 | **Effort** : M

---

#### Restitution des tableaux

**État de l'art** : Les tableaux doivent être restitués en format structuré (Markdown, HTML, CSV) et non en texte brut linéaire pour préserver la relation colonnes/lignes.

**Constat dans le code** :
- **Excel** : les tableaux sont restitués en markdown (séparateurs `|`) — bonne pratique (source : `text_extract_excel.py`).
- **PDF natif** : `page.get_text(sort=True)` ne distingue pas les tableaux du texte courant. Les cellules de tableaux sont extraites comme du texte linéaire.
- **Mistral OCR** : le markdown retourné peut contenir des tableaux formatés, dépendant de la qualité du modèle.

**Verdict** : 🟡 **Partiel** — Bonne restitution pour Excel. PDF natif : pas de détection de tableaux. Mistral OCR : dépend du modèle.

**Recommandation** : Pour les PDF contenant des tableaux critiques (BPU, annexes financières), envisager l'utilisation de `camelot-py` ou `tabula-py` pour une extraction tabulaire dédiée.
**Priorité** : P2 | **Effort** : L

---

### Prétraitement des images

#### Deskewing, binarisation, denoising

**État de l'art** : Avant l'OCR, les images doivent être prétraitées : redressement (deskew), binarisation (contraste noir/blanc), réduction du bruit (denoising). Cela améliore significativement le CER/WER.

**Constat dans le code** :
[NON IMPLÉMENTÉ] — Aucun prétraitement d'image n'est appliqué :

- **PDF → pixmap** (Tesseract) : `doc.load_page(i).get_pixmap(matrix=pymupdf.Matrix(2, 2))` (source : `text_extract_document.py:60`) — le `Matrix(2, 2)` double la résolution (bon), mais pas de deskewing, binarisation ou denoising.
- **Images** : `Image.open(io.BytesIO(file_content))` (source : `text_extract_document.py:136`) — aucun prétraitement avant `tesserocr.image_to_text()`.

**Verdict** : 🔴 **Non conforme** — Aucun prétraitement OCR. La qualité d'extraction sur les documents scannés de mauvaise qualité sera dégradée.

**Recommandation** : Ajouter une fonction `preprocess_image()` utilisant Pillow ou OpenCV : (1) conversion en niveaux de gris, (2) binarisation adaptative (Otsu), (3) deskewing via détection de lignes, (4) denoising. Appliquer avant chaque appel Tesseract.
**Priorité** : P1 | **Effort** : M

---

#### Résolution minimale et distinction PDF natif/scanné

**État de l'art** : La résolution minimale recommandée est 300 DPI. Les PDF natifs (texte extractible) doivent être distingués des PDF scannés (image) pour éviter un OCR inutile.

**Constat dans le code** :
La distinction PDF natif/scanné est bien implémentée :

```python
word_count = count_words(text)
if word_count >= word_threshold:  # 50 mots par défaut
    # PDF natif → extraction directe
else:
    # PDF scanné → OCR
```
(source : `text_extract_document.py:46-54`)

Le seuil de 50 mots est paramétrable. Le doublement de résolution pour Tesseract (`Matrix(2, 2)`) est présent.

Cependant, il n'y a pas de vérification de la résolution minimale du document avant OCR.

**Verdict** : 🟢 **Conforme** — Bonne distinction PDF natif/scanné avec seuil paramétrable. Le doublement de résolution pour Tesseract est une bonne pratique.

**Recommandation** : Ajouter un check de résolution avant OCR Tesseract. Si la résolution est < 150 DPI, logger un warning et upscaler l'image.
**Priorité** : P2 | **Effort** : S

---

### Métriques de qualité OCR

#### CER et WER

**État de l'art** : Le Character Error Rate (CER) et le Word Error Rate (WER) doivent être mesurés régulièrement sur un échantillon de documents avec ground truth. Un CER pondéré sur les zones numériques critiques (SIRET, IBAN, montants) est particulièrement important.

**Constat dans le code** :
[NON IMPLÉMENTÉ] — Aucune métrique CER/WER n'est calculée. Il n'y a pas de ground truth OCR. Le test e2e `tests_e2e/text_extraction/test_ocr_api.py` teste l'appel API OCR mais ne mesure pas la qualité de l'extraction.

**Verdict** : 🔴 **Non conforme** — Aucune métrique de qualité OCR mesurée.

**Recommandation** : Créer un jeu de test OCR (10-20 documents scannés avec transcription manuelle). Mesurer CER/WER global et CER pondéré sur les zones numériques. Intégrer dans les tests e2e.
**Priorité** : P1 | **Effort** : M

---

### Rejet précoce (Early Rejection)

#### Score de confiance OCR et court-circuit LLM

**État de l'art** : Le moteur OCR doit produire un score de confiance par page. Si le score tombe sous un seuil, le document doit être rejeté avant l'appel LLM (coûteux) et routé vers une file d'exception humaine.

**Constat dans le code** :
Le seul proxy de qualité OCR est le comptage de mots :
```python
word_count = count_words(text)
```
(source : `text_extract_document.py:47`)

- Si `word_count < 50` pour un PDF → bascule vers OCR (pas rejet).
- Si le texte extrait est vide après OCR → `Exception("Failed to extract text - empty result")` → `FAILURE` (source : `text_extraction.py:24`).
- Tesseract peut fournir des scores de confiance par mot (`tesserocr` a la méthode `AllWordConfidences()`), mais elle n'est pas utilisée.
- Mistral OCR ne retourne pas de score de confiance dans sa réponse.

Il n'y a pas de seuil de qualité OCR en dessous duquel le LLM serait court-circuité.

**Verdict** : 🔴 **Non conforme** — Pas de score de confiance OCR, pas de rejet précoce, pas de file d'exception.

**Recommandation** : (1) Utiliser `tesserocr.AllWordConfidences()` pour calculer un score de confiance moyen par page. (2) Définir un seuil (ex: confiance moyenne < 60%) en dessous duquel le document est marqué "OCR_LOW_QUALITY" et le LLM n'est pas appelé. (3) Router ces documents vers une file d'exception.
**Priorité** : P1 | **Effort** : M

---

## Synthèse du thème

| Critère | Verdict | Priorité | Effort |
|---------|---------|----------|--------|
| Choix technologique OCR | 🟢 Conforme | — | — |
| Dimensionnement GPU | ⚪ Non applicable | P2 | S |
| Analyse de layout | 🟡 Partiel | P2 | M |
| Restitution des tableaux | 🟡 Partiel | P2 | L |
| Prétraitement des images | 🔴 Non conforme | P1 | M |
| Distinction PDF natif/scanné | 🟢 Conforme | P2 | S |
| Métriques CER/WER | 🔴 Non conforme | P1 | M |
| Rejet précoce | 🔴 Non conforme | P1 | M |
