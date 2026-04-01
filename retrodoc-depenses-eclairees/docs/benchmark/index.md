# Benchmark LLMOps — Synthèse de l'audit

!!! abstract "Audit technique du projet Dépenses Éclairées"
    Date : 1er avril 2026 | Périmètre : Repository `depenses-eclairees` (branche `main`, commit [`278138d`](https://github.com/betagouv/depenses-eclairees/commit/278138dc2372c886093875bbfff6090aad1f49a8))

## Tableau de synthèse

| # | Thème | Nb critères | 🟢 | 🟡 | 🔴 | ⚪ | Priorité max | Effort total estimé |
|---|-------|-------------|-----|-----|-----|-----|-------------|-------------------|
| 1 | [PromptOps & Versionnement](01-promptops.md) | 5 | 0 | 1 | 4 | 0 | P0 | M |
| 2 | [Résilience & Quotas](02-resilience-quotas.md) | 6 | 1 | 3 | 2 | 0 | P1 | M |
| 3 | [Confiance & Logprobs](03-confiance-logprobs.md) | 5 | 0 | 0 | 5 | 0 | P0 | L |
| 4 | [Hallucinations & Validation](04-hallucinations-validation.md) | 5 | 2 | 2 | 1 | 0 | P1 | L |
| 5 | [Observabilité & Télémétrie](05-observabilite.md) | 6 | 0 | 3 | 3 | 0 | P1 | L |
| 6 | [Évaluation Continue](06-evaluation-continue.md) | 6 | 0 | 2 | 4 | 0 | P0 | L |
| 7 | [Sécurité & Conformité](07-securite-conformite.md) | 9 | 0 | 3 | 4 | 2 | P0 | XL |
| 8 | [FinOps & Coûts](08-finops.md) | 5 | 0 | 2 | 3 | 0 | P1 | M |
| 9 | [Audit OCR](09-audit-ocr.md) | 8 | 2 | 2 | 3 | 1 | P1 | L |
| 10 | [Contexte & Chunking](10-contexte-chunking.md) | 6 | 0 | 0 | 6 | 0 | P0 | L |
| | **TOTAL** | **61** | **5** | **18** | **35** | **3** | | |

## Résumé exécutif

Le projet Dépenses Éclairées présente une **architecture technique solide** (Django + Celery, double moteur OCR, séparation des modèles LLM par tâche, post-traitement déterministe des IBAN/SIRET/montants) mais accuse un **déficit critique en matière de LLMOps, d'observabilité et de conformité réglementaire**. Sur 61 critères audités, **35 sont non conformes (57%)**, 18 partiels (30%), et seulement 5 conformes (8%).

**Top 3 des risques** :

1. **Absence de score de confiance et de circuit de validation humaine** — Les extractions LLM sont injectées sans qualification dans la base de données. Dans un flux financier étatique connecté à SAP Chorus, une hallucination non détectée peut avoir des conséquences budgétaires et juridiques graves.

2. **Absence de gestion de la fenêtre de contexte** — Le texte intégral des documents est envoyé au LLM sans comptage de tokens ni stratégie de chunking. Un document long peut produire une extraction tronquée ou erronée sans aucune alerte.

3. **Non-conformité EU AI Act** — Aucune analyse de risque, aucun registre des traitements IA, aucun plan de supervision humaine n'est documenté. L'EU AI Act entre en application stricte en août 2026 et ce système a de fortes probabilités d'être qualifié "haut risque".

**Top 3 des actions prioritaires** :

1. **[P0] Implémenter le contrôle de la fenêtre de contexte et la troncature intelligente** — Utiliser `tiktoken` pour compter les tokens, définir des limites, et ajouter une troncature/chunking pour les documents longs. Effort : M.

2. **[P0] Ajouter des délimiteurs anti-injection et une directive système** — Protéger les prompts contre les injections indirectes via le texte OCRisé. Effort : S.

3. **[P0] Lancer la mise en conformité EU AI Act** — Commander l'analyse de risque, créer le registre des traitements IA, et formaliser le plan de supervision humaine. Effort : XL mais incontournable.

## Répartition des verdicts par priorité

| Priorité | Description | Nb critères 🔴 |
|----------|-------------|----------------|
| **P0** | Bloquant MEP / Conformité | 12 |
| **P1** | À traiter avant recette | 17 |
| **P2** | Backlog post-MEP | 6 |

## Points forts du projet

Malgré le nombre élevé de non-conformités, le projet présente des bases solides :

- Architecture Celery/Redis bien conçue pour le traitement batch distribué
- Double moteur OCR (Tesseract local + Mistral OCR souverain) avec bascule automatique
- Utilisation de `response_format` JSON Schema pour contraindre les sorties LLM
- Post-traitement déterministe robuste et bien testé (IBAN via schwifty, SIRET, montants, adresses)
- Séparation classification/extraction sur des modèles différents
- Rate limiter distribué via PostgreSQL (RateGate)
- Bonne distinction PDF natif/scanné avec seuil paramétrable
