# Formats non gérés

## Types de documents classifiés mais non analysés

Le catalogue de classification contient **~50 catégories** (`DIC_CLASS_FILE_BY_NAME`), mais seuls **10 types** ont une extraction structurée (`SUPPORTED_DOCUMENT_TYPES`).

Les types suivants sont **classifiés par le LLM** mais **aucune donnée structurée n'est extraite** :

| Catégorie | Description estimée |
|---|---|
| `abondement` | Décision d'abondement |
| `ae_annexe` | Annexe à l'acte d'engagement |
| `application_revision_prix` | Application de la clause de révision de prix |
| `att_etrangers` | Attestation pour entreprises étrangères |
| `att_fiscale` | Attestation fiscale |
| `att_handicap` | Attestation emploi travailleurs handicapés |
| `att_honneur` | Attestation sur l'honneur |
| `att_resp_civile` | Attestation responsabilité civile |
| `att_sociale` | Attestation sociale (URSSAF) |
| `avis_boamp` | Avis BOAMP |
| `bordereau_prix` | Bordereau de prix unitaires (BPU) |
| `ca_chgt_denomination` | Courrier administratif — changement de dénomination |
| `ca_chgt_ej` | Courrier administratif — changement d'EJ |
| `ca_chgt_siret` | Courrier administratif — changement de SIRET |
| `ca_chgt_revision_prix` | Courrier administratif — révision de prix |
| `ca_chgt_rib` | Courrier administratif — changement de RIB |
| `ccag` | CCAG |
| `ccap_annexe` | Annexe au CCAP |
| `ccap_annexe_beneficiaires` | Annexe bénéficiaires du CCAP |
| `ccc` | CCC |
| `ccp_simple` | CCP simple |
| `ccp_vae` | CCP VAE |
| `cctp` | CCTP (attributs définis mais type non activé) |
| `cctp_annexe` | Annexe au CCTP |
| `cga` | Conditions générales d'achat |
| `commentaire` | Commentaire |
| `conv_financement` | Convention de financement |
| `cv` | CV |
| `reconduction` | Reconduction |
| `decomposition_prix` | Décomposition du prix global et forfaitaire (DPGF) |
| `delegation_pouvoir` | Délégation de pouvoir |
| `detail_quantitatif_estimatif` | DQE |
| `ej_complexe` | EJ complexe |
| `facture` | Facture |
| `fiche_achat` | Fiche d'achat |
| `fiche_communication` | Fiche de communication |
| `fiche_engagement` | Fiche d'engagement |
| `fiche_modificative` | Fiche modificative |
| `lettre_candidature_dc1` | DC1 |
| `lettre_candidature_dc2` | DC2 |
| `lettre_consultation` | Lettre de consultation |
| `mail` | Mail |
| `memoire_technique` | Mémoire technique |
| `mise_au_point` | Mise au point |
| `notification` | Notification |
| `ordre_service` | Ordre de service |
| `pv_cao` | PV de la CAO |
| `question_reponse` | Questions/réponses |
| `rapport_affermissement_tranche` | Rapport d'affermissement de tranche |
| `rapport_analyse_offre` | Rapport d'analyse des offres |
| `rapport_signature` | Rapport de signature |
| `reglement_consultation` | Règlement de consultation |
| `service_fait` | Service fait |

## Formats de fichiers non supportés

Les extensions suivantes provoquent un `SkipStepException` :

| Extension | Usage typique |
|---|---|
| `.csv` | BPU, tableaux de données |
| `.msg` | Mails Outlook |
| `.eml` | Mails |
| `.ppt` / `.pptx` | Présentations |
| `.rtf` | Texte enrichi |
| `.zip` | Archives |
| `.html` | Pages web |

## Impact pour SAP

!!! tip "Recommandation"

    Avant la migration, il serait utile de mesurer le volume de documents par catégorie pour prioriser l'ajout d'extraction structurée sur les types les plus fréquents (ex. `bordereau_prix`, `facture`, `cctp`).

**Source** : `docia/file_processing/processor/classifier.py` (`DIC_CLASS_FILE_BY_NAME`), `docia/file_processing/processor/text_extraction/text_extraction.py` (`SUPPORTED_FILES_TYPE`)
