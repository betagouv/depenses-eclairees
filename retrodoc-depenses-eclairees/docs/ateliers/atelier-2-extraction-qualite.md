# Atelier 2 — Extraction & Qualité

## Informations générales

| | |
|---|---|
| **Titre** | Extraction documentaire & qualité des données |
| **Durée** | 3h |
| **Public** | AIFE (product owner, métier) + Prestataire (développeurs, chef de projet) |
| **Animateur** | Architecte Data/IA |

## Objectifs

1. Passer en revue le contrat d'interface JSON par type de document
2. Remplir la matrice de qualité avec les résultats des tests e2e
3. Identifier les champs critiques pour SAP Chorus
4. Définir les seuils d'acceptation et les cas nécessitant une vérification humaine

## Prérequis

!!! info "Lectures préparatoires"

    - [Contrat d'interface JSON](../modele-donnees/contrat-interface-json.md) — Structure JSON par type
    - [Matrice qualité](../qualite/matrice-qualite.md) — Template à remplir en atelier
    - [Champ objet de la dépense](../modele-donnees/champ-objet-depense.md) — Nommage variable
    - [Scores de confiance](../qualite/scores-confiance.md) — État des lieux et recommandations
    - [Cas d'échec](../qualite/cas-echec.md) — Taxonomie des échecs

## Agenda

| Durée | Sujet | Support |
|---|---|---|
| 20 min | **Tour de table** — Contexte de la migration SAP, attentes qualité | — |
| 30 min | **Contrat JSON** — Revue du `structured_data` par type (acte_engagement, ccap, rib, devis) | [Contrat JSON](../modele-donnees/contrat-interface-json.md) |
| 20 min | **Champ objet** — Nommage variable, règles d'extraction, cas du devis avec raisonnement | [Champ objet](../modele-donnees/champ-objet-depense.md) |
| 10 min | *Pause* | |
| 30 min | **Remplissage matrice qualité** — Résultats tests e2e, précision/rappel par attribut | [Matrice qualité](../qualite/matrice-qualite.md) |
| 20 min | **Cas d'échec** — Taxonomie, propagation, perte de données post-traitement | [Cas d'échec](../qualite/cas-echec.md) |
| 20 min | **Score de confiance** — État des lieux, recommandations pour SAP | [Scores confiance](../qualite/scores-confiance.md) |
| 15 min | **Discussion** — Seuils d'acceptation, workflow de vérification humaine | — |
| 15 min | **Conclusions & actions** | — |

## Questions clés à traiter

- [ ] Quels champs sont **bloquants** pour la saisie Chorus ? (champs obligatoires SAP)
- [ ] Quel taux d'erreur est acceptable par champ ? (ex. SIRET : 0% ; objet : 5% ?)
- [ ] Faut-il un workflow de validation humaine pour certains types de documents ?
- [ ] Les types `bon_de_commande`, `avenant`, `kbis`, `att_sirene` sans test e2e : est-ce un risque ?
- [ ] Le champ `sources_et_conflits` de `DataEngagement` est-il utilisé pour l'agrégation ?

## Livrables attendus

- [ ] Matrice qualité remplie (précision/rappel mesurés)
- [ ] Liste des champs critiques SAP par type de document
- [ ] Seuils d'acceptation par champ
- [ ] Décision : score de confiance ou non ?
- [ ] Spécification du workflow de vérification humaine
