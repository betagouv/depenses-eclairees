# Prompts LLM

!!! info "Reproduction verbatim"

    Tous les prompts ci-dessous sont reproduits **verbatim** depuis le code source. Les variables de template sont indiquées entre accolades `{variable}`.

## Versionnement des prompts

Les prompts sont **définis en dur dans le code Python** :

| Prompt | Fichier source |
|---|---|
| System prompt classification | `docia/file_processing/processor/classifier.py` |
| User prompt classification | `docia/file_processing/processor/classifier.py` |
| System prompt extraction | `docia/file_processing/processor/analyze_content.py` |
| User prompt extraction | `docia/file_processing/processor/analyze_content.py` |
| Consignes par attribut | `docia/file_processing/processor/attributes/*.py` |

Il n'y a **pas de fichier séparé** pour les prompts, **pas de versionnement dédié**, et **pas de mécanisme de rollback**. Les prompts évoluent avec les commits Git ordinaires.

---

## Prompt de classification

### System prompt

```
Vous êtes un assistant qui aide à classer des fichiers en fonction de leur contenu.
```

**Source** : `docia/file_processing/processor/classifier.py`, fonction `create_classification_prompt()`

### User prompt

```
A partir du contenu du fichier, vous devez déterminer à quelles catégories le document appartient 
parmi les catégories suivantes. La réponse est une liste de catégories possibles, classée par ordre 
de correspondance avec le contenu du document.

Voici la liste des catégories possibles :
{categories_str}

Le titre du document est un élément essentiel pour la classification.
Si le type de document ne correspond à aucune des catégories, répondez "Non classifié".

Voici le nom du document (attention celui-ci peut être trompeur, il faut aussi regarder le contenu) : '{filename}'

Voici la première page du document :
<DEBUT PAGE>
'{text[:2000]}'
<FIN PAGE>

Format : répondez par une liste de catégories possibles (sans autre texte ni ponctuation).
```

**Variables** :

- `{categories_str}` : jointure des ~50 catégories avec descriptions (voir catalogue ci-dessous)
- `{filename}` : nom du fichier
- `{text[:2000]}` : les **2000 premiers caractères** du texte extrait

### Response format (JSON Schema)

```json
{
  "type": "json_schema",
  "json_schema": {
    "name": "ClassificationList",
    "strict": true,
    "schema": {"type": "array", "items": {"type": "string"}}
  }
}
```

### Modèle utilisé

`openweight-medium`, température `0.0`

---

## Prompt d'extraction d'informations structurées

### System prompt

```
Vous êtes un assistant IA qui analyse des documents juridiques.
```

**Source** : `docia/file_processing/processor/analyze_content.py`, fonction `analyze_file_text_llm()`

### User prompt (template)

```
Analyse le contexte suivant et réponds à la question : {question}

Contexte : {text}
```

Où `{question}` est construit dynamiquement par `get_prompt_from_attributes()` :

```
Extrait les informations clés et renvoie-les uniquement au format 
JSON spécifié, sans texte supplémentaire.

Format de réponse (commence par "{" et termine par "}") :
{
  "{attribut_1}": "", 
  "{attribut_2}": "", 
  ...
}

Instructions d'extraction :

{consigne_attribut_1}
{consigne_attribut_2}
...
```

**Variables** :

- `{text}` : texte complet du document (ou `relevant_content` s'il existe — **jamais peuplé dans le pipeline actuel**)
- `{question}` : prompt construit à partir des attributs du type de document

### Modèle utilisé

`mistral-medium-2508`, température `0.0`

### Response format

JSON Schema spécifique par type de document, généré dynamiquement par `create_response_format()`. Chaque propriété correspond à un attribut avec son propre schéma (string, object, array…).

---

## Consignes par type de document (verbatim)

### acte_engagement

**Fichier** : `docia/file_processing/processor/attributes/acte_engagement.py`

**24 attributs extraits** : `objet_marche`, `forme_marche`, `administration_beneficiaire`, `societe_principale`, `siret_mandataire`, `siren_mandataire`, `rib_mandataire`, `cotraitants`, `sous_traitants`, `rib_autres`, `montant_ht`, `montant_ttc`, `montant_tva`, `duree`, `date_signature_mandataire`, `date_signature_administration`, `date_notification`, `conserve_avance`, `montants_en_annexe`, `code_cpv`, `mode_consultation`, `mode_reconduction`, `ligne_imputation_budgetaire`, `remise_catalogue`

??? note "Consignes verbatim — acte_engagement (cliquer pour déplier)"

    **OBJET**
    ```
    OBJET
       Définition : l'objet du marché, c'est-à-dire ce qui a été acheté, ou le service fourni.
       Indices :
       - Chercher après les mentions "Objet :", ou autre mention similaire.
       - Généralement en début de document ou après les coordonnées.
       - Dans tous les cas, l'objet du marché doit avoir du sens pour une personne extérieure, et permettre de comprendre l'achat.
       - Ne rien renvoyer si aucun objet trouvé
       Format : 
       - En bon Français
       - Attention, ne pas inclure le type de document dans l'objet : "Devis pour ..." enlever "Devis pour" / "Avenant pour ..." enlever "Avenant pour".
       - Si l'objet de la commande est incompréhensible, proposer un objet simple qui reflète le contenu de la commande.
    ```

    **FORME MARCHE**
    ```
    FORME MARCHE
       Définition : Informations sur la forme du marché concernant les lots, les marchés subséquents et les marchés parents.
       Indices :
       - Chercher après les mentions "Objet", "Lot", "marché subséquent", "marché parent", ou autres mentions similaires, en particulier en début du document.
       - Pour le champ lot_concerne :
         * Si le marché concerne un lot spécifique, identifier le numéro du lot (chercher "Lot X", "Lot n°X", etc.) et son titre. Si pas de titre explicite trouvée, renvoyer null pour titre_lot.
         * Si le marché n'est pas un lot, renvoyer null pour numero_lot et titre_lot.
       - Pour le champ marche_subsequent :
         * Rechercher les mentions explicites de "marché subséquent", "marchés subséquents", ou formulations équivalentes.
         * Si le document précise que ce marché est un marché subséquent ou fait partie d'un marché à marchés subséquents, renvoyer true.
         * Sinon, renvoyer false.
       - Pour le champ marche_parent :
         * Rechercher l'identifiant du marché parent (souvent mentionné comme "accord-cadre", "contrat-cadre", "marché global", etc.).
         * L'identifiant peut être un numéro de marché, un code, un numéro de consultation ou toute référence unique au marché parent.
         * Si aucun marché parent n'est mentionné ou si son identifiant n'est pas disponible, renvoyer null.
       Format : 
       - Un objet JSON avec les trois champs suivants au même niveau :
         * "lot_concerne" : objet avec "numero_lot" (entier ou null) et "titre_lot" (chaîne ou null)
         * "marche_subsequent" : booléen (true ou false)
         * "marche_parent" : chaîne (identifiant du marché parent) ou null
    ```

    **ADMINISTRATION_BENEFICIAIRE**
    ```
    ADMINISTRATION_BENEFICIAIRE 
         Définition : Structure administrative ou publique qui bénéficie de la commande, ou qui achète la prestation.
         Indices :
         - Rechercher les mentions d'achateurs, de pouvoir adjudicateur, ou d'autorité contractante. Le résultat est souvent une direction ou un service au sein d'une administration.
         - Si aucune information n'est trouvée sur l'administration bénéficiaire : renvoyer ''.
         - Si possible, inclure le nom de l'administration jusqu'à deux sous-niveaux organisationnels.
            * Exemple de bon résultat : Ministère de la culture (MDC) - Secrétariat général (SG) - Direction des musées de France (DMF)
            * Exemple de résultat trop général : Ministère de la culture (MC)
            * Exemple de résultat insuffisant : Direction des musées de France (DMF)
            * Exemple de résultat trop détaillé : Ministère de la culture (MC) - Secrétariat général (SG) - Direction des musées de France (DMF) - Service des musées d'artisanat (SMA)
         - S'il est seulement précisé les rôles ou les postes de persones, déduire la direction / le service / l'administration bénéficiaire.
            * Exemple : le préfet de la région Île-de-France -> Préfecture de la région Île-de-France
         Format : les différents niveaux de l'administration bénéficiaire en minuscule correctement écrit (et leurs acronymes entre parenthèses si disponibles), séparés par des tirets, . 
    ```

    **SOCIETE_PRINCIPALE**
    ```
    SOCIETE_PRINCIPALE  
         Définition : Société principale contractante (titulaire). Si un groupement est mentionné, extraire la société mandataire ou représentante.  
         Indices : 
         - Rechercher les mentions de société, entreprise, titulaire, mandataire, contractant.
         - En général, l'autre nom de personne morale que l'administration acheteuse.
         - Les noms de domaine des adresses mails peuvent donner des indices sur la bonne orthographe.
         Format : renvoyer le nom de la société.
    ```

    **SIRET_MANDATAIRE**
    ```
    SIRET_MANDATAIRE  
       Définition : Numéro SIRET de la société principale, composé de 14 chiffres.  
       Indices :
       - Peut être mentionné comme "SIRET", ou "numéro d'immatriculation".
       - Favoriser les numéros de SIRET indiqués dans l'identification du titulaire, plutôt qu'en signature du document.
       - Si plusieurs SIRET sont disponibles pour une même entreprise, avec différentes terminaisons (5 derniers chiffres) :
            * Prendre le numéro de l'établissement concerné (pas le siège social) pour renvoyer le SIRET.
            * S'il n'y a pas de précisions sur l'établissement concerné, renvoyer le SIRET le plus élevé.
                -> Exemple : 123 456 789 00001 et 123 456 789 00020, renvoyer 12345678900020 (car 00020 > 00001).
       - Si le numéro de SIRET ne contient pas suffisamment de caractères, ne pas compléter : renvoyer tel quel.
       Format : un numéro composé de 14 chiffres, sans espaces.  
    ```

    **SIREN_MANDATAIRE**
    ```
    SIREN_MANDATAIRE
       Définition : numéro de SIREN du prestataire / du titulaire principal, composé de 9 chiffres
       Indices :
       - Après la mention SIREN au début ou à la fin du document.
       - A partir d'un numéro de SIRET : les 9 premiers chiffres d'un SIRET de 14 chiffres.
       - A partir d'un numéro RCS : les 9 chiffres du numéro RCS (après "RCS" ou "N° RCS")
       - A partir d'un numéro de TVA : les 9 derniers chiffres du numéro de TVA (après l'identifiant du pays et du département ex : FR12)
       - Ne rien renvoyer si aucun SIREN trouvé
       Format : un numéro composé de 9 chiffres, sans espaces ni caractères spéciaux
    ```

    **COTRAITANTS**
    ```
    COTRAITANTS
    Objectif : Extraire uniquement les entreprises réellement mentionnées comme cotraitantes (hors mandataire).
    Règles d'extraction :
    - Ne retenir qu'une entreprise explicitement décrite comme cotraitante dans le texte.
    - Ignorer totalement les entreprises mentionnées comme sous-traitantes.
    - Ignorer toute mention générique contenant le mot "cotraitant" (ex. "Cotraitant", "cotraitant1", "cotraitant2") : ce ne sont pas des entreprises.
    - Une entreprise n'est retenue que si au moins l'un des éléments suivants apparaît dans le texte : un nom réel d'entreprise, un numéro SIRET (14 chiffres) ou SIREN (9 chiffres) valide.
    - Pour le nom (champ "nom") : en cas de choix, préférer la raison sociale plutôt que le nom commercial.
    - Pour le SIRET (champ "siret") : si plusieurs SIRET sont disponibles pour une même entreprise :
        * Prendre le numéro de l'établissement concerné (pas le siège social) pour renvoyer le SIRET.
        * S'il n'y a pas de précisions sur l'établissement concerné, renvoyer le SIRET le plus élevé.
    - Si aucun cotraitant réel n'est identifié dans le texte, renvoyer []
    - Format attendu : 
        * une liste JSON : [{"nom": "...", "siret": "..."}]
        * Si aucun cotraitant valide n'est trouvé, renvoyer exactement : []
    ```

    **MONTANT_HT**
    ```
    MONTANT_HT  
         Définition : Montant du marché hors taxes (également hors TVA).  
         Indices : 
         - Rechercher les mentions "hors taxes", "HT", "sans TVA", "hors TVA" ou équivalent. 
         - Extraire le montant exprimé en euros ou en écriture littérale, et mets le en chiffres en euros.
         - Cas particuliers :
            * Pour un marché en plusieurs lots (cf champ lot_concerne), ne renvoyer que le montant du lot concerné.
            * Pour un marché en plusieurs tranches, renvoyer la somme des montants de toutes les tranches.
         - Ne rien envoyer si aucun montant HT trouvé.
         Format : en "XXXX.XX€" (sans séparateur de milliers, avec 2 décimales)
    ```

    **MONTANT_TTC**
    ```
    MONTANT_TTC  
     Définition : Montant du marché toutes taxes comprises (avec TVA incluse).  
     Indices : 
     - Rechercher les expressions "TTC", "TVA incluse", "TVA comprise".
     - Ignorer les montants HT (hors taxes) et le montant de TVA seule
     - Le montant TTC peut être le même que le montant HT, s'il n'y a pas de TVA.
     - Cas particuliers :
        * Pour un marché en plusieurs lots (cf champ lot_concerne), ne renvoyer que le montant du lot concerné.
        * Pour un marché en plusieurs tranches, renvoyer la somme des montants de toutes les tranches.
     - Ne rien envoyer si aucun montant TTC trouvé, ou si le montant a plus de chance d'être en HT que en TTC.
     Format : en "XXXX.XX€" (sans séparateur de milliers, avec 2 décimales)
    ```

    **MONTANT_TVA**
    ```
    MONTANT_TVA
        Définition : Montant de la TVA.
        Indices :
        - Rechercher la mention de TVA ou de "taux de TVA". Le montant est souvent sous la forme d'un pourcentage.
        - Convertir le pourcentage en chiffre décimal entre 0 et 1.
        - Ne rien renvoyer si aucun montant de TVA trouvé.
        Format : en "0.XX" avec deux décimales (ex. 0.20 pour 20%).
    ```

    **DUREE**
    ```
    DUREE
        Définition : Durée du marché totale exprimée en mois et extension possible.
        Indices :
        - Chercher dans le paragraphe indiquant la durée du marché ou le délai d'exécution des prestations.
        - Durée initiale : la durée du marché ferme (sans reconduction ou tranches optionnelles), en nombre de mois.
            * En l'absence de précisions sur la durée ferme, renvoyer duree_initiale: null
            * Exemple : une durée de 1 an, renvoyer 12.
            * Pour une durée entre des dates clés, par exemple "jusqu'à la réunion de conclusion 6 mois après le lancement" : renvoyer 6 mois.
                -> Attention : si ces dates clés sont insuffisamment documentées, renvoyer duree_initiale: null
        - Extension de durée possible : extenion maximale en nombre de mois.
            * En l'absence d'informations claires, renvoyer duree_reconduction: null
            * Si des reconductions sont précisées (ne pas confondre avec des tranches optionnelles) :
                1. duree_reconduction : Trouver la durée d'une reconduction (en nombre de mois).
                2. nb_reconductions : Trouver le nombre de reconductions possibles.
            * Si des tranches optionnelles sont précisées : renvoyer la durée de l'ensemble des tranches optionnelles.
                1. delai_tranche_optionnelle
        Format : {"duree_initiale": ..., "duree_reconduction": ..., "nb_reconductions": ..., "delai_tranche_optionnelle": ...}
    ```

---

### ccap

**Fichier** : `docia/file_processing/processor/attributes/ccap.py`

**10 attributs extraits** : `intro` (null — contexte), `objet_marche`, `id_marche`, `lots`, `forme_marche`, `forme_marche_lots`, `duree_marche`, `montant_maximum`, `montant_maximum_lots`, `ccag_reference`

??? note "Consignes verbatim — ccap (cliquer pour déplier)"

    **INTRODUCTION** (champ `intro` — pas de réponse attendue, contexte pour le LLM)
    ```
    INTRODUCTION
        Ce paragraphe donne des précisions et des définitions sur le document à analyser. Le champ introduction n'appelle pas de réponse, renvoyer null.
        Définitions : 
        - LOT : l'acheteur peut décomposer un besoin en lots séparés, chacun constituant une marché à part entière lors de l'attribution.
        - TRANCHE : un marché à tranches est un marché unique composé de plusieurs phases. La tranche ferme est celle pour laquelle l'acheteur s'engage contractuellement, les tranches optionnelles sont des parties supplementaires que l'acheteur peut faire exécuter plus tard.
    ```

    **OBJET_MARCHE**
    ```
    OBJET_MARCHE
        Définition : Formulation synthétique de l'objet du marché.
        Indices : 
        - L'objet du marché peut être dans le titre directement, ou plus généralement dans une section dédiée.
        - Identifier les formules comme "Objet du marché", "Le marché a pour objet", ou toute expression indiquant l'intitulé de la mission.
        Format : 
        - En bon Français
        - Ne pas inclure le type de document dans l'objet.
        - Si l'objet de la commande est incompréhensible, proposer un objet simple qui reflète le contenu de la commande.
    ```

    **LOTS**
    ```
    LOTS
         Définition : Liste des lots du marché (si le marché est alloti)
         Indices : 
         - Le marché est alloti si plusieurs lots sont décrits dans le CCAP : il faut que les lots soient explicitement citées avec la mention "Lot" et le titre de chaque lot.
         - Pour chaque lot : identifier le numéro du lot et le titre du lot.
         - Ne pas inclure les tranches dans la liste des lots.
         Format : une liste de json [{'numero_lot': numéro du lot, 'titre_lot': l'intitulé du lot }, {...}]
    ```

    **FORME_MARCHE** (CCAP — logique conditionnelle complexe)
    ```
    FORME_MARCHE
        Définition : Identifier la forme de passation du marché.
        Indices :
        - SI le marché comporte des lots, renvoyer : structure = "allotie", tranches = null, forme_prix = null, attributaires = null
        - OU ALORS si le marché ne comprend pas de lots :
            (1) structure : "simple" ou "à marchés subséquents"
            (2) tranches : nombre de tranches ou null
            (3) forme_prix : "unitaires", "forfaitaires" ou "mixtes" (par défaut forfaitaire)
            (4) attributaires : nombre d'attributaires ou null
        Format : {'structure': ..., 'tranches': ..., 'forme_prix': ..., 'attributaires': ...}
    ```

---

### rib

**Fichier** : `docia/file_processing/processor/attributes/rib.py`

**6 attributs extraits** : `iban`, `bic`, `titulaire_compte`, `adresse_postale_titulaire`, `domiciliation`, `banque`

??? note "Consignes verbatim — rib (cliquer pour déplier)"

    **IBAN**
    ```
    IBAN
         Définition : Identifiant international de compte bancaire (IBAN)
         Indices : 
         - Généralement composé de 27 caractères (pour un RIB Français), commençant souvent par "FR" pour un IBAN en France (souvent "FR76 ...", "FR09 ..." ou autres)
         - Souvent 6 groupes de 4 caractères, puis 3 caractères.
         - Si aucun IBAN trouvé, renvoyer ''
         Format : l'IBAN d'entre 21 et 27 caractères avec espaces tous les 4 caractères
    ```

    **BIC**
    ```
    BIC
         Définition : Code d'identification bancaire (BIC), généralement composé de 8 ou 11 caractères alphanumériques.
         Indices : 
         - Repérer les codes sous la forme "BIC" ou "Code BIC", souvent présents dans un RIB.
         - Chercher dans la section du RIB ou dans un tableau récapitulatif des coordonnées bancaires.
         Format : le BIC de 8 ou 11 caractères avec espaces tous les 4 caractères
    ```

    **TITULAIRE_COMPTE**
    ```
    TITULAIRE_COMPTE
         Définition : Nom du titulaire du compte bancaire (personne physique ou morale).
         Indices : 
         - Rechercher le nom du titulaire du compte bancaire dans la section du RIB.
         - S'il s'agit d'une personne morale, renvoyer le nom de la société ou de l'établissement.
         - Pas besoin d'inclure informations sur la direction ou le service interne.
    ```

    **ADRESSE_POSTALE_TITULAIRE**
    ```
    ADRESSE_POSTALE_TITULAIRE  
         Définition : Adresse postale de la société titulaire principale du marché (json).
         Format : {'numero_voie': ..., 'nom_voie': ..., 'complement_adresse': ..., 'code_postal': ..., 'ville': ..., 'pays': ...}
    ```

---

### fiche_navette

**Fichier** : `docia/file_processing/processor/attributes/fiche_navette.py`

**14 attributs extraits** : `administration_beneficiaire`, `objet`, `societe_principale`, `accord_cadre`, `id_accord_cadre`, `montant_ht`, `reconduction`, `taux_tva`, `centre_cout`, `centre_financier`, `activite`, `domaine_fonctionnel`, `localisation_interministerielle`, `groupe_marchandise`

---

### devis

**Fichier** : `docia/file_processing/processor/attributes/devis.py`

**11 attributs extraits** : `numero_devis`, `objet`, `raisonnement`, `date_emission`, `titulaire` (JSON : raison_sociale, siren, siret, adresse), `administration_beneficiaire`, `prestations`, `montants` (JSON : ht, taux_tva, tva, ttc), `duree_validite`, `date_signature`, `dernier_signataire`

??? note "Consignes verbatim — devis (cliquer pour déplier)"

    **OBJET** (avec raisonnement)
    ```
    OBJET
       Définition : Objet métier du devis (ce qui est acheté ou réalisé).
       - Si l'objet est explicitement présent dans le document, l'extraire tel quel.
       - Si aucun libellé objet clair n'est trouvé : tenter de déduire un objet court en synthétisant les descriptions des lignes de prestations.
       - Renvoyer null si l'inférence n'aboutit pas.
    ```

    **RAISONNEMENT_OBJET**
    ```
    RAISONNEMENT_OBJET
       Définition : Indiquer comment l'objet a été obtenu.
       - Si trouvé explicitement : "Objet présent dans le document (extrait de la mention ...)"
       - Si inféré : "Objet inféré à partir des prestations / lignes du tableau : ..."
       - Si null : "Objet non trouvé ; inférence impossible ou trop vague"
    ```

    **TITULAIRE**
    ```
    TITULAIRE
       Définition : Informations d'identification du prestataire principal du devis.
       Format : objet JSON {"raison_sociale": ..., "siren": ..., "siret": ..., "adresse": ...}.
    ```

    **MONTANTS**
    ```
    MONTANTS
       Définition : Synthèse financière du devis.
       - taux_tva en pourcentage (ex: 20, 8.5), pas en ratio.
       Format : {"ht": ..., "taux_tva": ..., "tva": ..., "ttc": ...}
    ```

---

### bon_de_commande

**Fichier** : `docia/file_processing/processor/attributes/bon_de_commande.py`

**10 attributs extraits** : `objet`, `type_document`, `montant_ht`, `montant_ttc`, `administration_beneficiaire`, `description_prestations`, `date_signature`, `societe_principale`, `siren`, `siret`

---

### avenant

**Fichier** : `docia/file_processing/processor/attributes/avenant.py`

**10 attributs extraits** : `objet`, `type_document`, `montant_ht`, `montant_ttc`, `administration_beneficiaire`, `description_prestations`, `societe_principale`, `siret`, `siren`, `date_signature`

---

### sous_traitance

**Fichier** : `docia/file_processing/processor/attributes/sous_traitance.py`

**16 attributs extraits** : `administration_beneficiaire`, `objet_marche`, `societe_principale`, `adresse_postale_titulaire`, `siret_titulaire`, `societe_sous_traitant`, `adresse_postale_sous_traitant`, `siret_sous_traitant`, `montant_sous_traitance_ht`, `montant_sous_traitance_ttc`, `description_prestations`, `date_signature`, `montant_tva`, `paiement_direct`, `duree`, `rib_sous_traitant`

---

### kbis

**Fichier** : `docia/file_processing/processor/attributes/kbis.py`

**4 attributs extraits** : `denomination_insee`, `siren_kbis`, `activite_principale`, `adresse_postale_insee`

---

### att_sirene

**Fichier** : `docia/file_processing/processor/attributes/att_sirene.py`

**5 attributs extraits** : `siret`, `siren`, `denomination_insee`, `activite_principale`, `adresse_postale_insee`

---

## Catalogue de classification (~50 catégories)

Défini dans `DIC_CLASS_FILE_BY_NAME` dans `docia/file_processing/processor/classifier.py`.

Seuls **10 types** ont une extraction structurée (`SUPPORTED_DOCUMENT_TYPES`) :

| Type | Extraction structurée ? |
|---|---|
| `acte_engagement` | ✅ |
| `ccap` | ✅ |
| `rib` | ✅ |
| `fiche_navette` | ✅ |
| `devis` | ✅ |
| `bon_de_commande` | ✅ |
| `avenant` | ✅ |
| `sous_traitance` | ✅ |
| `kbis` | ✅ |
| `att_sirene` | ✅ |
| `cctp` | ❌ (attributs définis mais absent de `SUPPORTED_DOCUMENT_TYPES`) |
| Tous les autres (~40) | ❌ (classifiés mais non analysés) |

**Source** : `docia/file_processing/processor/attributes/*.py`, `docia/file_processing/processor/classifier.py`, `docia/file_processing/processor/analyze_content.py`
