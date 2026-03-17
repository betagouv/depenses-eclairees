"""
Définitions des attributs à extraire pour les documents de type "devis".
"""

DEVIS_ATTRIBUTES = {
    "numero_devis": {
        "consigne": """NUMERO_DEVIS
   Définition : Numéro ou référence propre au devis.
   Indices :
   - Chercher les mentions "N° devis", "Devis n°", "Réf. devis", "Référence", N° Dossier.
   - La valeur peut être alphanumérique, avec tirets, slashs ou points.
   - Si plusieurs références sont présentes, privilégier celle explicitement liée au devis.
   - Si aucune référence n'est trouvée, renvoyer null.
   Format : chaîne de caractères, conserver exactement la forme trouvée.
""",
        "search": "",
        "output_field": "numero_devis",
        "schema": {"type": ["string"]},
    },
    "objet": {
        "consigne": """OBJET
   Définition : Objet métier du devis (ce qui est acheté ou réalisé).
   Indices :
   - Chercher après les mentions "Objet", "Intitulé", "Sujet", ou dans le titre.
   - Formuler un objet compréhensible par un tiers.
   - Retirer les préfixes de type de document ("Devis pour", "Avenant pour", etc.).
   - Si l'objet est explicitement présent dans le document, l'extraire tel quel (après nettoyage des préfixes).
   - Si aucun libellé objet clair n'est trouvé : tenter de déduire un objet court en synthétisant les descriptions
     des lignes de prestations / du tableau des lignes (thème commun, nature du service ou des fournitures).
   - Renvoyer null si l'inférence n'aboutit pas à une description de l'objet suffisamment explicite (prestations
     trop vagues, absentes ou inexploitables pour formuler un objet compréhensible par un tiers).
   Format : phrase courte en français, ou null.
""",
        "search": "",
        "output_field": "objet",
        "schema": {"type": ["string", "null"]},
    },
    "raisonnement": {
        "consigne": """RAISONNEMENT_OBJET
   Définition : Indiquer comment l'objet a été obtenu (champ objet ci-dessus).
   Règles :
   - Si l'objet a été trouvé explicitement dans le document (mention "Objet", "Intitulé", etc.) :
     renvoyer une phrase du type : "Objet présent dans le document (extrait de la mention ...)".
   - Si l'objet a été inféré à partir des prestations / lignes du tableau et est suffisamment explicite :
     renvoyer une phrase du type : "Objet inféré à partir des prestations / lignes du tableau : ..."
     en résumant brièvement sur quoi s'appuie l'inférence.
   - Si l'objet est null car l'inférence n'a pas abouti à une description suffisamment explicite :
     renvoyer une phrase du type : "Objet non trouvé ; inférence impossible ou trop vague (prestations absentes ou inexploitables)".
   Format : une ou deux phrases en français.
""",
        "search": "",
        "output_field": "raisonnement",
        "schema": {"type": ["string"]},
    },
    "date_emission": {
        "consigne": """DATE_EMISSION
   Définition : Date d'émission / édition / création du devis.
   Indices :
   - Repérer "Émis le", "Date du devis", "Date d'édition", "Fait le" en en-tête.
   - En cas de plusieurs dates, privilégier la date d'émission du devis.
   - Ignorer les dates de signature.
   - Si aucune date d'émission claire n'est trouvée, renvoyer null.
   Format : "JJ/MM/AAAA".
""",
        "search": "",
        "output_field": "date_emission",
        "schema": {"type": ["string", "null"]},
    },
    "titulaire": {
        "consigne": """TITULAIRE
   Définition : Informations d'identification du prestataire principal du devis.
   Indices :
   - Rechercher la société émettrice : raison sociale, SIREN, SIRET, adresse postale.
   - Privilégier la société contractante principale (pas les sous-traitants).
   - SIREN : composé de 9 chiffres. Exemple : 437813287.
      * le SIREN peut être extrait à partir d'un numéro RCS, il s'agit des 9 chiffres du numéro RCS (après "RCS" ou "N° RCS")
      * le SIREN peut également être extrait à partir d'un numéro de TVA, il s'agit des 9 derniers chiffres du numéro de TVA (après l'identifiant du pays et du département ex : FR12)
      * le SIREN peut également être extrait à partir du SIRET, il s'agit des 9 premiers chiffres d'un SIRET de 14 chiffres.
   - SIRET : composé de 14 chiffres. Exemple : 43781328700001.
   - Si une information est absente, renvoyer null pour cette clé.
   - Si aucun titulaire identifiable, renvoyer {"raison_sociale": null, "siren": null, "siret": null, "adresse": null}.
   Format : objet JSON {"raison_sociale": ..., "siren": ..., "siret": ..., "adresse": ...}.
""",
        "search": "",
        "output_field": "titulaire",
        "schema": {
            "type": "object",
            "properties": {
                "raison_sociale": {"type": ["string"]},
                "siren": {"type": ["string"]},
                "siret": {"type": ["string"]},
                "adresse": {"type": ["string"]},
            },
            "required": ["raison_sociale", "siren", "siret", "adresse"],
        },
    },
    "administration_beneficiaire": {
        "consigne": """ADMINISTRATION_BENEFICIAIRE
   Définition : Entité publique bénéficiaire de la prestation.
   Indices :
   - Rechercher "acheteur", "pouvoir adjudicateur", "autorité contractante", "bénéficiaire", ou simplement à qui s'adresse le devis.
   - Inclure, si possible, le ministère puis le niveau direction/service.
   - Si seul un rôle est mentionné (ex: préfet), déduire l'administration correspondante.
   - Si aucune administration identifiable n'est trouvée, renvoyer null.
   Format : nom de l'administration en toutes lettres.
""",
        "search": "",
        "output_field": "administration_beneficiaire",
        "schema": {"type": ["string", "null"]},
    },
    "prestations": {
        "consigne": """PRESTATIONS
   Définition : Liste détaillée des lignes de prestations du devis.
   Indices :
   - Extraire les lignes de tableau / poste avec code, description, prix unitaire (si présent), quantité (si présente) et montant total.
   - Les champs attendus par ligne sont :
     * "code" : code de ligne (ex: UO 2) ou null si absent
     * "description" : description de la prestation ou null si absente
     * "prix_unitaire" : prix unitaire en nombre décimal ; à remplir uniquement si la ligne a un prix unitaire (ligne en unitaire). Sinon renvoyer null (ex: ligne forfaitaire).
     * "quantite" : quantité en nombre décimal ; à remplir uniquement si elle est indiquée pour la ligne. Sinon renvoyer null.
     * "montant_total" : montant total de la ligne en nombre décimal ; à remplir dans tous les cas pour chaque ligne.
   - Ne pas ajouter de ligne vide.
   - Si aucune ligne exploitable n'est trouvée, renvoyer [].
   Format : tableau JSON d'objets homogènes.
""",
        "search": "",
        "output_field": "prestations",
        "schema": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": ["string", "null"]},
                    "description": {"type": ["string", "null"]},
                    "prix_unitaire": {"type": ["number", "null"]},
                    "quantite": {"type": ["number", "null"]},
                    "montant_total": {"type": ["number"]},
                },
                "required": ["code", "description", "prix_unitaire", "quantite", "montant_total"],
            },
        },
    },
    "montants": {
        "consigne": """MONTANTS
   Définition : Synthèse financière du devis.
   Indices :
   - Extraire les montants HT, TVA, TTC et le taux de TVA.
   - Convertir en nombres décimaux (sans symbole euro).
   - "taux_tva" doit être exprimé en pourcentage (ex: 20, 8.5), pas en ratio.
   - Si une composante est absente, renvoyer null pour cette clé.
   - Si aucun montant n'est trouvé, renvoyer {"ht": null, "taux_tva": null, "tva": null, "ttc": null}.
   Format : objet JSON {"ht": ..., "taux_tva": ..., "tva": ..., "ttc": ...}.
""",
        "search": "",
        "output_field": "montants",
        "schema": {
            "type": "object",
            "properties": {
                "ht": {"type": ["number"]},
                "taux_tva": {"type": ["number"]},
                "tva": {"type": ["number"]},
                "ttc": {"type": ["number"]},
            },
            "required": ["ht", "taux_tva", "tva", "ttc"],
        },
    },
    "duree_validite": {
        "consigne": """DUREE_VALIDITE
   Définition : Durée de validité de l'offre/devis.
   Indices :
   - Rechercher "durée de validité", "devis valable", "offre valable jusqu'au", "validité".
   - Peut être exprimée en nombre de jours, de mois (convertir en jours si possible) ou sous forme de date limite (calculer le nombre de jours si la date limite est lisible et déduite d'une date de référence, sinon ignorer).
   - Retourner uniquement le nombre de jours de validité, sous forme de nombre entier.
   - Si aucune information n'est trouvée, renvoyer null.
   Format : nombre de jours (ex : 90). 
""",
        "search": "",
        "output_field": "duree_validite",
        "schema": {"type": ["string", "null"]},
    },
    "date_signature": {
        "consigne": """DATE_SIGNATURE
   Définition : Date de signature effective du devis.
   Indices :
   - Repérer les mentions "Signé le", "Bon pour accord", "Fait à ... le ...", signature électronique.
   - En cas de plusieurs dates de signature, retenir la plus tardive.
   - Ignorer la date d'émission.
   - Si aucune signature datée n'est présente, renvoyer null.
   Format : "JJ/MM/AAAA".
""",
        "search": "",
        "output_field": "date_signature",
        "schema": {"type": ["string", "null"]},
    },
    "dernier_signataire": {
        "consigne": """DERNIER_SIGNATAIRE
   Définition : Nom du dernier signataire identifié sur le devis.
   Indices :
   - Chercher les noms proches de blocs de signature, cachets ou signatures électroniques.
   - En cas de signatures multiples, renvoyer la personne associée à la dernière date de signature.
   - Si seul un signataire est trouvé, renvoyer ce signataire.
   - Si aucun nom de signataire n'est identifiable, renvoyer null.
   Format : nom et prénom sous forme texte.
""",
        "search": "",
        "output_field": "dernier_signataire",
        "schema": {"type": ["string", "null"]},
    },
}
