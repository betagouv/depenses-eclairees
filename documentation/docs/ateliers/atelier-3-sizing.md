# Atelier 3 — Sizing

## Informations générales

| | |
|---|---|
| **Titre** | Dimensionnement et architecture SAP |
| **Durée** | 2h |
| **Public** | Architectes SAP (Prestataire), architecte infra AIFE |
| **Animateur** | Architecte Data/IA |

## Objectifs

1. Dimensionner l'infrastructure SAP pour le pipeline d'extraction
2. Estimer les volumes de données et les flux LLM
3. Valider le modèle de déploiement (batch vs temps réel, queues, workers)
4. Identifier les composants à remplacer ou adapter

## Prérequis

!!! info "Lectures préparatoires"

    - [Déploiement](../architecture/deploiement.md) — Infrastructure Scalingo actuelle
    - [Tailles réelles](../modele-donnees/tailles-reelles.md) — Estimations volumétriques
    - [Vue d'ensemble](../architecture/vue-ensemble.md) — Stack technique complète
    - [Flux de données](../architecture/flux-donnees.md) — Séquence bout en bout

## Agenda

| Durée | Sujet | Support |
|---|---|---|
| 15 min | **Architecture actuelle** — Scalingo, Celery, Redis, PostgreSQL, S3 | [Déploiement](../architecture/deploiement.md) |
| 20 min | **Volumes de données** — Tailles JSON, texte, prompts, estimations | [Tailles réelles](../modele-donnees/tailles-reelles.md) |
| 15 min | **Flux LLM** — 2 appels/document, rate limiting, timeout 180s | [Appel LLM](../pipeline/appel-llm.md) |
| 10 min | *Pause* | |
| 20 min | **Modèle d'exécution** — Batch 4×/jour vs temps réel, concurrency workers | [Flux de données](../architecture/flux-donnees.md) |
| 15 min | **Composants à transposer** — Celery → ?, Redis → ?, Tesseract → ?, LibreOffice → ? | [Composants](../architecture/composants.md) |
| 15 min | **Discussion** — Sizing SAP, choix d'architecture, risques identifiés | — |
| 10 min | **Conclusions & actions** | — |

## Données de sizing (à compléter)

!!! tip "Template — À remplir avec les données de production"

    | Paramètre | Valeur actuelle | Valeur cible SAP |
    |---|---|---|
    | Documents/jour | [À MESURER] | [À DÉFINIR] |
    | Appels LLM/jour | [À MESURER] | [À DÉFINIR] |
    | Taille moyenne fichier | [À MESURER] | [À DÉFINIR] |
    | Temps moyen/document | [À MESURER] | [À DÉFINIR] |
    | Workers Celery | 2 + 1 heavy_cpu | [À DÉFINIR] |
    | RAM par worker | [À MESURER] | [À DÉFINIR] |
    | Taille base PostgreSQL | [À MESURER] | [À DÉFINIR] |
    | Taille stockage S3 | [À MESURER] | [À DÉFINIR] |
    | Bande passante LLM (tokens/min) | 98 req/min (rate limit) | [À DÉFINIR] |

## Questions clés à traiter

- [ ] SAP BTP ou on-premise ? Impact sur le choix du broker de messages
- [ ] Celery/Redis → quel équivalent SAP ? (SAP BTP Job Scheduling ? Cloud Foundry Tasks ?)
- [ ] Tesseract et LibreOffice en production : containers ou services managés ?
- [ ] PostgreSQL → SAP HANA ? Impact sur le rate limiter distribué (basé sur `clock_timestamp()`)
- [ ] S3 → SAP Document Management Service ?
- [ ] Le cron 4×/jour est-il suffisant pour SAP, ou faut-il du quasi temps réel ?

## Correspondance composants

| Composant actuel | Rôle | Équivalent SAP potentiel |
|---|---|---|
| Celery + Redis | Queue de tâches async | SAP BTP Job Scheduling / ABAP BGD |
| PostgreSQL 16 | Base relationnelle | SAP HANA |
| S3 (Scalingo) | Object storage | SAP Document Management |
| Tesseract (local) | OCR images | SAP Document Information Extraction |
| LibreOffice (local) | Conversion .doc | [À DÉFINIR] |
| Django (web) | UI, API | SAP Fiori / SAP CAP |
| API Albert (DINUM) | LLM | SAP AI Core / Azure OpenAI |
| Scalingo | PaaS | SAP BTP Cloud Foundry |

## Livrables attendus

- [ ] Tableau de sizing rempli avec données de production
- [ ] Matrice de correspondance composants actuels → SAP
- [ ] Architecture cible SAP (diagramme)
- [ ] Plan de migration technique (phases)
- [ ] Liste des risques de migration identifiés
