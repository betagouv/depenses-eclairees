# Atelier 1 — Connexion LLM

## Informations générales

| | |
|---|---|
| **Titre** | Connexion LLM Albert → SAP Chorus |
| **Durée** | 2h |
| **Public** | Équipe SAP / Prestataire (développeurs), architecte AIFE |
| **Animateur** | Architecte Data/IA |

## Objectifs

1. Comprendre comment l'application actuelle se connecte à l'API Albert (DINUM)
2. Identifier les paramètres de configuration à transposer côté SAP
3. Valider la faisabilité d'un remplacement ou proxy LLM dans l'architecture SAP
4. Documenter les contraintes (rate limiting, timeout, fenêtre de contexte)

## Prérequis

!!! info "Lectures préparatoires"

    - [Appel LLM (Albert)](../pipeline/appel-llm.md) — Client, modèles, gestion d'erreurs
    - [Prompts](../pipeline/prompts.md) — Tous les prompts verbatim
    - [Parsing réponse](../pipeline/parsing-reponse.md) — JSON Schema, post-traitement

## Agenda

| Durée | Sujet | Support |
|---|---|---|
| 15 min | **Présentation du client LLM** — SDK OpenAI, configuration, 3 modèles | [Appel LLM](../pipeline/appel-llm.md) |
| 20 min | **Démonstration live** — Classification + extraction sur un document type | Environnement de démo |
| 15 min | **Prompts verbatim** — Classification (system + user), extraction (par type de document) | [Prompts](../pipeline/prompts.md) |
| 10 min | *Pause* | |
| 20 min | **JSON Schema & post-traitement** — Response format, fonctions de nettoyage | [Parsing réponse](../pipeline/parsing-reponse.md) |
| 15 min | **Gestion d'erreurs & rate limiting** — Retry, backoff, RateGate PostgreSQL | [Appel LLM](../pipeline/appel-llm.md) |
| 15 min | **Discussion** — Transposition SAP : quel LLM ? Quel endpoint ? Quelles contraintes ? | — |
| 10 min | **Conclusions & actions** | — |

## Questions clés à traiter

- [ ] Le LLM SAP supportera-t-il `response_format` (JSON Schema) ?
- [ ] Quelle est la fenêtre de contexte disponible côté SAP ?
- [ ] Le rate limiting sera-t-il géré côté application ou côté infra ?
- [ ] Les prompts seront-ils versionnés séparément du code ?
- [ ] Le modèle OCR (Mistral OCR) a-t-il un équivalent SAP ?

## Livrables attendus

- [x] Inventaire des paramètres de configuration LLM
- [ ] Matrice de correspondance Albert → LLM SAP
- [ ] Décision : proxy Albert ou remplacement direct ?
- [ ] Spécification du contrat d'interface LLM côté SAP
