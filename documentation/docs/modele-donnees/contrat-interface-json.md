# Contrat d'interface JSON

Le champ `Document.structured_data` (`JSONField`) contient les informations extraites et post-traitées. La structure varie selon la `classification` du document.

!!! warning "Pas de schéma JSON validé côté base"

    Le `structured_data` est un `JSONField` libre. Aucune validation JSON Schema côté base de données ni côté application (au-delà de ce que la réponse du LLM retourne via `response_format`).

---

## acte_engagement

```json
{
  "objet_marche": "string — Objet du marché",
  "forme_marche": {
    "lot_concerne": {"numero_lot": "integer|null", "titre_lot": "string|null"},
    "marche_subsequent": "boolean",
    "marche_parent": "string|null"
  },
  "administration_beneficiaire": "string — Nom administration (2 niveaux max)",
  "societe_principale": "string — Nom société titulaire",
  "siret_mandataire": "string — 14 chiffres, sans espaces",
  "siren_mandataire": "string — 9 chiffres, sans espaces",
  "rib_mandataire": {
    "banque": "string|null",
    "iban": "string|null — FR76 XXXX XXXX ... (espaces tous les 4 chars)",
    "code_banque": "string|null — 5 chiffres (si pas d'IBAN)",
    "code_guichet": "string|null — 5 chiffres (si pas d'IBAN)",
    "numero_compte": "string|null — 11 chiffres (si pas d'IBAN)",
    "cle_rib": "string|null — 2 chiffres (si pas d'IBAN)"
  },
  "cotraitants": [
    {"nom": "string", "siret": "string — 14 chiffres"}
  ],
  "sous_traitants": [
    {"nom": "string", "siret": "string — 14 chiffres"}
  ],
  "rib_autres": [
    {"societe": "string", "rib": {"banque": "...", "iban": "..."}}
  ],
  "montant_ht": "string — XXXX.XX€",
  "montant_ttc": "string — XXXX.XX€",
  "montant_tva": "string — ex: 0.20",
  "duree": {
    "duree_initiale": "integer|null — mois",
    "duree_reconduction": "integer|null — mois",
    "nb_reconductions": "integer|null",
    "delai_tranche_optionnelle": "integer|null — mois"
  },
  "date_signature_mandataire": "string — JJ/MM/AAAA",
  "date_signature_administration": "string — JJ/MM/AAAA",
  "date_notification": "string — JJ/MM/AAAA",
  "conserve_avance": "string — conserve|renonce",
  "montants_en_annexe": {
    "annexe_financière": "boolean",
    "classification": "string|null"
  },
  "code_cpv": "string — Code CPV + description",
  "mode_consultation": "string",
  "mode_reconduction": "string — tacite|expresse",
  "ligne_imputation_budgetaire": "string",
  "remise_catalogue": "string|null"
}
```

---

## ccap

```json
{
  "intro": null,
  "objet_marche": "string",
  "id_marche": "string — identifiant unique consultation",
  "lots": [
    {"numero_lot": "integer", "titre_lot": "string"}
  ],
  "forme_marche": {
    "structure": "string — allotie|simple|à marchés subséquents",
    "tranches": "integer|null",
    "forme_prix": "string|null — unitaires|forfaitaires|mixtes",
    "attributaires": "integer|null"
  },
  "forme_marche_lots": [
    {
      "numero_lot": "integer",
      "structure": "string — simple|à marchés subséquents",
      "tranches": "integer|null",
      "forme_prix": "string — mixtes|unitaires|forfaitaires",
      "attributaires": "integer|null"
    }
  ],
  "duree_marche": {
    "duree_initiale": "integer",
    "duree_reconduction": "integer",
    "nb_reconductions": "integer",
    "delai_tranche_optionnelle": "integer"
  },
  "montant_maximum": "string|null — XXXX.XX€",
  "montant_maximum_lots": ["..."],
  "ccag_reference": "string — ex: CCAG-FCS"
}
```

---

## rib

```json
{
  "iban": "string — 21 à 27 chars, espaces tous les 4 chars",
  "bic": "string — 8 ou 11 chars",
  "titulaire_compte": "string",
  "adresse_postale_titulaire": {
    "numero_voie": "string",
    "nom_voie": "string",
    "complement_adresse": "string",
    "code_postal": "string",
    "ville": "string",
    "pays": "string"
  },
  "domiciliation": "string",
  "banque": "string"
}
```

---

## fiche_navette

```json
{
  "administration_beneficiaire": "string",
  "objet": "string",
  "societe_principale": "string",
  "accord_cadre": "string|null",
  "id_accord_cadre": "string|null — ex: 2022AMO0538402",
  "montant_ht": "string — XXXX.XX€",
  "reconduction": "string — Oui|Non",
  "taux_tva": "string — 0.20 (pas 20%)",
  "centre_cout": "string — ex: DRIEETR075",
  "centre_financier": "string — ex: 0174-CLIM-SCEE",
  "activite": "string — ex: 020304DGTUCT",
  "domaine_fonctionnel": "string — ex: 0203-04-02",
  "localisation_interministerielle": "string — ex: N, N11, S1200594",
  "groupe_marchandise": "string — ex: 40.01.02"
}
```

---

## devis

```json
{
  "numero_devis": "string|null",
  "objet": "string|null",
  "raisonnement": "string — comment l'objet a été obtenu",
  "date_emission": "string|null — JJ/MM/AAAA",
  "titulaire": {
    "raison_sociale": "string",
    "siren": "string — 9 chiffres",
    "siret": "string — 14 chiffres",
    "adresse": "string"
  },
  "administration_beneficiaire": "string|null",
  "prestations": "string|null — résumé synthétique",
  "montants": {
    "ht": "number",
    "taux_tva": "number — ex: 20, 8.5 (pourcentage)",
    "tva": "number",
    "ttc": "number"
  },
  "duree_validite": "string|null — nombre de jours",
  "date_signature": "string|null — JJ/MM/AAAA",
  "dernier_signataire": "string|null"
}
```

---

## bon_de_commande

```json
{
  "objet": "string",
  "type_document": "string — ex: bon_de_commande",
  "montant_ht": "string — XXXX.XX€",
  "montant_ttc": "string — XXXX.XX€",
  "administration_bénéficiaire": "string",
  "description_prestations": "string",
  "date_signature": "string — JJ/MM/AAAA",
  "societe_principale": "string",
  "siren": "string — 9 chiffres",
  "siret": "string — 14 chiffres"
}
```

---

## avenant

```json
{
  "objet": "string",
  "type_document": "string",
  "montant_ht": "string — XXXX.XX€",
  "montant_ttc": "string — XXXX.XX€",
  "administration_bénéficiaire": "string",
  "description_prestations": "string",
  "societe_principale": "string",
  "siret": "string — 14 chiffres",
  "siren": "string — 9 chiffres",
  "date_signature": "string — JJ/MM/AAAA"
}
```

---

## sous_traitance

```json
{
  "administration_beneficiaire": "string",
  "objet_marche": "string",
  "societe_principale": "string",
  "adresse_postale_titulaire": {
    "numero_voie": "string", "nom_voie": "string",
    "complement_adresse": "string", "code_postal": "string",
    "ville": "string", "pays": "string"
  },
  "siret_titulaire": "string — 14 chiffres",
  "societe_sous_traitant": "string",
  "adresse_postale_sous_traitant": {"...même structure..."},
  "siret_sous_traitant": "string — 14 chiffres",
  "montant_sous_traitance_ht": "string — XXXX.XX€",
  "montant_sous_traitance_ttc": "string — XXXX.XX€",
  "description_prestations": "string",
  "date_signature": "string — JJ/MM/AAAA",
  "montant_tva": "string — 0.20 (pas 20%)",
  "paiement_direct": "string — Oui|Non",
  "duree": {"...même structure que acte_engagement..."},
  "rib_sous_traitant": {"...même structure que rib_mandataire..."}
}
```

---

## kbis

```json
{
  "denomination": "string — raison sociale",
  "siren": "string — 9 chiffres",
  "activite_principale": "string — APE",
  "adresse_postale_insee": "string"
}
```

---

## att_sirene

```json
{
  "siret": "string — 14 chiffres",
  "siren": "string — 9 chiffres",
  "denomination": "string",
  "activite_principale": "string — APE",
  "adresse_postale_insee": "string"
}
```

!!! tip "Template pour l'équipe SAP"

    Ces contrats JSON constituent la spécification d'interface pour mapper les données extraites vers les champs SAP Chorus. Chaque type de document a une structure fixe ; les champs absents renvoient `null` ou `""`.

**Source** : `docia/file_processing/processor/attributes/*.py`, `docia/file_processing/processor/analyze_content.py`
