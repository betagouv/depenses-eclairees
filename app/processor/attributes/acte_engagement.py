"""
Définitions des attributs à extraire pour les documents de type "acte_engagement".
"""

ACTE_ENGAGEMENT_ATTRIBUTES = {
    "objet_marche": {
        "consigne": """OBJET
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
""",
        "search": "",
        "output_field": "objet_marche"
    },

    "lot_concerne": {
        "consigne": """LOT_CONCERNE
   Définition : le lot du marché concerné par le contrat.
   Indices :
   - Chercher après les mentions "Objet" et "Lot", ou autre mention similaire, en particulier en début du document.
   - Renvoyer le numéro du lot, ainsi que le titre du lot s'il est disponible : "Lot X : [titre du lot]"
   - Ne rien renvoyer si aucun lot trouvé.
   Format : 
   - La chaîne de caractères"Lot X : [titre du lot]", où le titre du lot est écrit en minuscule correctement.
   - Si aucun lot trouvé, renvoyer ''
""",
        "search": "",
        "output_field": "lot_concerne"
    },

    "administration_beneficiaire": {
        "consigne": """ADMINISTRATION_BENEFICIAIRE 
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
""",
        "search": "",
        "output_field": "administration_beneficiaire"
    },

    "societe_principale": {
        "consigne": """SOCIETE_PRINCIPALE  
     Définition : Société principale contractante (titulaire). Si un groupement est mentionné, extraire la société mandataire ou représentante.  
     Indices : 
     - Rechercher les mentions de société, entreprise, titulaire, mandataire, contractant.
     - En général, l'autre nom de personne morale que l'administration acheteuse.
     - Les noms de domaine des adresses mails peuvent donner des indices sur la bonne orthographe.
     Format : renvoyer le nom de la société.
""",
        "search": "",
        "output_field": "societe_principale"
    },

    "siret_mandataire": {
        "consigne": """SIRET_MANDATAIRE  
   Définition : Numéro SIRET de la société principale, composé de 14 chiffres.  
   Indices :
   - Peut être mentionné comme "SIRET", ou "numéro d'immatriculation".
   - Si plusieurs SIRET sont disponibles pour une même entreprise, avec différentes terminaisons (5 derniers chiffres), prendre le numéro le plus élevé.
        * Exemple : 123 456 789 00001 et 123 456 789 00020, renvoyer 12345678900020 (car 00020 > 00001).
   - Si le numéro de SIRET ne contient pas suffisamment de caractères, ne pas compléter : renvoyer tel quel.
   Format : un numéro composé de 14 chiffres, sans espaces.  
""",
        "search": "",
        "output_field": "siret_mandataire"
    },

    "siren_mandataire": {
        "consigne": """SIREN_MANDATAIRE
   Définition : numéro de SIREN du prestataire / du titulaire principal, composé de 9 chiffres
   Indices :
   - Après la mention SIREN au début ou à la fin du document.
   - A partir d'un numéro de SIRET : les 9 premiers chiffres d'un SIRET de 14 chiffres.
   - A partir d'un numéro RCS : les 9 chiffres du numéro RCS (après "RCS" ou "N° RCS")
   - A partir d'un numéro de TVA : les 9 derniers chiffres du numéro de TVA (après l'identifiant du pays et du département ex : FR12)
   - Ne rien renvoyer si aucun SIREN trouvé
   Format : un numéro composé de 9 chiffres, sans espaces ni caractères spéciaux
""",
        "search": "",
        "output_field": "siren_mandataire"
    },

    "rib_mandataire": {
        "consigne": """RIB_MANDATAIRE
     Définition : Informations bancaires (IBAN en priorité) du compte à créditer indiqué dans l'acte d'engagement.
     Indices : 
     - Rechercher dans les informations bancaires, en priorité près des mentions "RIB" ou "IBAN".
     - 1er cas (prioritaire) : l'IBAN est fourni (27 caractères commençant par "FR76"). Renvoyer :
        * 'banque' : Nom de la banque (sans la mention "Banque")
        * 'iban' : IBAN du compte à créditer (souvent 6 groupes de 4 caractères, puis 3 caractères)
     - 2ème cas (uniquement s'il n'y a pas d'IBAN) : l'IBAN n'est pas fourni, mais les autres informations bancaires sont fournies. Renvoyer :
        * 'banque' : Nom de la banque (sans la mention "Banque")
        * 'code_banque' : code de la banque à 5 chiffres (espaces non compris)
        * 'code_guichet' : code du guichet à 5 chiffres (espaces non compris)
        * 'numero_compte' : numéro de compte français à 11 chiffres (espaces non compris)
        * 'cle_rib' : clé du RIB à 2 chiffres (espaces non compris)
     - Si aucune information bancaire trouvée pour le mandataire (ni IBAN, ni informations seules), renvoyer {}
     Format : 
     - 1er cas (prioritaire) : un json sous format suivant {"banque": "nom de la banque", "iban": "IBAN avec espaces tous les 4 caractères"}
     - 2ème cas (secondaire - uniquement s'il n'y a pas d'IBAN) : un json sous format suivant {"banque": "nom de la banque", "code_banque": "code de la banque à 5 chiffres", "code_guichet": "code du guichet à 5 chiffres", "numero_compte": "numéro de compte à 11 chiffres", "cle_rib": "clé du RIB à 2 chiffres"}
""",
        "search": "",
        "output_field": "rib_mandataire",
        "schema":
            {
                "type": "object",
                "oneOf": [
                    {
                        "type": "object",
                        "properties": {
                            "banque": {"type": "string"},
                            "iban": {"type": "string"}
                        },
                        "required": ["banque", "iban"]
                    },
                    {
                        "type": "object",
                        "properties": {
                            "banque": {"type": "string"},
                            "code_banque": {"type": "string"},
                            "code_guichet": {"type": "string"},
                            "numero_compte": {"type": "string"},
                            "cle_rib": {"type": "string"}
                        },
                        "required": [
                            "banque",
                            "code_banque",
                            "code_guichet",
                            "numero_compte",
                            "cle_rib"
                        ]
                    },
                    {}
                ]
            }
    },

#     "avance":{
#         "consigne": """AVANCE
#      Définition : Information sur la volonté du titulaire de recevoir ou non une avance.
#      Indices :
#      - Dans un paragraphe dédié au renoncement de l'avance, souvent sous la forme d'une case à cocher à gauche de la mention "Non" ou "Oui".
#      - Attention l'extraction du texte peut être ambiguë, notamment pour les cases à cocher :
#         * si une des cases est devenu 0 ou O, elle n'était probalement pas cochée : "Ef NON O oul", c'était probablement que "Non" était cochée.
#         * si une des cases est devenu x ou X, elle était probablement cochée.
#         * si la coche d'une case n'est pas clairement visible, renvoyer "Information insuffisante".
#      - Ne rien renvoyer sur l'avance si aucune information sur l'avance trouvée.
#      Format : "✓ Conserve le bénéfice de l'avance" ou "✗ Renonce au bénéfice de l'avance" ou "Information insuffisante
# """,
#         "search": "",
#         "output_field": "avance"
#     },

    "citation_avance":{
        "consigne": """CITATION_AVANCE
     Définition : La question (souvent "Je renonce au bénéfice de l'avance :")et les réponses extraites du texte du document concernant l'avance.
     Format : La citation du texte du document telle quelle, sans aucune modification.
""",
        "search": "",
        "output_field": "citation_avance"
    },

    "cotraitants":{
        "consigne": """COTRAITANTS
Objectif : Extraire uniquement les entreprises réellement mentionnées comme cotraitantes (hors mandataire).
Règles d’extraction :
- Ne retenir qu’une entreprise explicitement décrite comme cotraitante dans le texte.
- Ignorer totalement les entreprises mentionnées comme sous-traitantes.
- Ignorer toute mention générique contenant le mot “cotraitant” (ex. “Cotraitant”, “cotraitant1”, “cotraitant2”) : ce ne sont pas des entreprises.
- Une entreprise n’est retenue que si au moins l’un des éléments suivants apparaît dans le texte : un nom réel d’entreprise, un numéro SIRET (14 chiffres) ou SIREN (9 chiffres) valide.
- Si aucun cotraitant réel n’est identifié dans le texte, renvoyer []
- Format attendu : 
    * une liste JSON : [{"nom": "...", "siret": "..."}]
    * Si aucun cotraitant valide n’est trouvé, renvoyer exactement : []
""",
        "search": "",
        "output_field": "cotraitants",
        "schema":
            {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "nom": {"type": "string"},
                        "siret": {"type": "string"}
                    },
                    "required": ["nom", "siret"]
                }
            }
    },

    "sous_traitants":{
        "consigne": """SOUS_TRAITANTS
     Définition : Liste des sous-traitants du mandataire, s'il y en a.
     Indices : 
     - Rechercher dans le paragraphe de description du groupement, s'il y a plusieurs entreprises sous-traitantes (et non pas cotraitantes).
     - S'il n'y a que des cotraitants, ne rien renvoyer.
     - Ne rien renvoyer si aucun sous-traitant trouvé.
     Format : une liste de dictionnaires sous format [{"nom": "nom de la société", "siret": "siret de la société"}]
""",
        "search": "Section du document qui décrit le groupement et les entreprises qui le composent.",
        "output_field": "sous_traitants",
        "schema":
            {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "nom": {"type": "string"},
                        "siret": {"type": "string"}
                    },
                    "required": ["nom", "siret"]
                }
            }
    },

    "rib_autres":{
        "consigne": """RIB_AUTRES
     Définition : RIB des autres entreprises du groupement, s'il y en a.
     Indices : 
     - Rechercher dans le paragraphe des comptes à créditer, s'il y a plusieurs RIB indiqués pour plusieurs entreprises différentes.
        * 'societe' : nom de la société du groupement (si possible cohérent avec le champ cotraitants ci-dessus)
        * 'rib' : informations bancaires du compte à créditer (banque, IBAN, etc.)
            * 'banque' : Nom de la banque (sans la mention "Banque"). Ne rien renvoyer si aucune banque trouvée.
            * 'iban' : IBAN du compte à créditer avec espaces tous les 4 caractères. Ne rien renvoyer si aucun IBAN trouvé.
     - S'il n'y a que le RIB du mandataire, renvoyer [].
     - S'il n'y a pas d'informations sur le compte bancaire d'une entreprise, ne rien renvoyer pour cette entreprise.
     Format : une liste de dictionnaires json sous format [{"societe": "nom de la société du groupement", "rib": {"banque": "nom de la banque", "iban": "IBAN avec espaces tous les 4 caractères"}}]
""",
        "search": "Section du document qui décrit le groupement et les entreprises qui le composent.",
        "output_field": "rib_autres",
        "schema":
            {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "societe": {"type": "string"},
                        "rib": {
                            "type": "object",
                            "properties": {
                                "banque": {"type": "string"},
                                "iban": {"type": "string"}
                            },
                            "required": ["banque", "iban"]
                        }
                    },
                    "required": ["societe", "rib"]
                }
            }
    },

    "montant_ht": {
        "consigne": """MONTANT_HT  
     Définition : Montant du marché hors taxes (également hors TVA).  
     Indices : 
     - Rechercher les mentions "hors taxes", "HT", "sans TVA", "hors TVA" ou équivalent. 
     - Extraire le montant exprimé en euros ou en écriture littérale, et mets le en chiffres en euros.
     - Cas particuliers :
        * Pour un marché en plusieurs lots (cf champ lot_concerne), ne renvoyer que le montant du lot concerné.
        * Pour un marché en plusieurs tranches, renvoyer la somme des montants de toutes les tranches.
     - Ne rien envoyer si aucun montant HT trouvé.
     Format : en "XXXX.XX€" (sans séparateur de milliers, avec 2 décimales)
""",
        "search": "",    
        "output_field": "montant_ht"
    },

    "montant_ttc": {
        "consigne": """MONTANT_TTC  
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
""",
        "search": "",
        "output_field": "montant_ttc"
    },

    "duree": {
        "consigne": """DUREE
        Définition : Durée du marché totale exprimée en mois et extension possible.
        Indices :
        - Chercher dans le paragraphe indiquant la durée du marché ou le délai d'exécution des prestations.
        - Durée initiale : la durée du marché ferme (sans reconduction ou tranches optionnelles), en nombre de mois.
            * En l'absence de précisions sur la durée ferme, renvoyer None
            * Exemple : une durée de 1 an, renvoyer 12.
            * Pour une durée entre des dates clés, par exemple "jusqu'à la réunion de conclusion 6 mois après le lancement" : renvoyer 6 mois.
                -> Attention : si ces dates clés sont insuffisamment documentées, renvoyer None
        - Extension de durée possible : extenion maximale en nombre de mois.
            * En l'absence d'informations claires, renvoyer None
            * Si des reconductions sont précisées (ne pas confondre avec des tranches optionnelles qui sont gérées ci-dessous) :
                1. duree_reconduction : Trouver la durée d'une reconduction (en nombre de mois). Si l'information n'est pas précisée, renvoyer None.
                2. nb_reconductions : Trouver le nombre de reconductions possibles. Si l'information n'est pas précisée, renvoyer None.
            * Si des tranches optionnelles sont précisées : renvoyer la durée de l'ensemble des tranches optionnelles.
                1. delai_tranche_optionnelle : Trouver la durée de l'ensemble des tranches optionnelles.
                    Exemple : 2 tranches optionnelles de 8 mois, renvoyer 8 + 8 = 16.
        Format : un json sous format suivant {"duree_initiale": "nombre entier de mois", "duree_reconduction": "nombre entier de mois", "nb_reconductions": "nombre entier de reconductions possibles", "delai_tranche_optionnelle": "nombre entier de mois"}
    """,
        "search": "Section du document qui décrit la durée du marché ou le délai d'exécution des prestations.",
        "output_field": "duree",
        "schema":
            {"oneOf": [
                {
                    "type": "object",
                    "properties": {
                        "duree_initiale": {"type": "integer"},
                        "duree_reconduction": {"type": "integer"},
                        "nb_reconductions": {"type": "integer"},
                        "delai_tranche_optionnelle": {"type": "integer"}
                    },
                    "required": [
                        "duree_initiale",
                        "duree_reconduction",
                        "nb_reconductions",
                        "delai_tranche_optionnelle"
                    ]
                },
                {}
            ]}
    },

    "duree_explication": {
        "consigne": """DUREE_EXPLICATION
        Définition : Explique comment tu as calculé la durée ci-dessus""",
        "search": "Section du document qui décrit la durée du marché ou le délai d'exécution des prestations.",
        "output_field": "duree_explication"
    },

    "date_signature_mandataire": {
        "consigne": """DATE_SIGNATURE_MANDATAIRE
      Définition : Date de signature du document par le mandataire (entreprise prestataire principale). 
      Indices : 
      - Uniquement la date de signature de l'entreprise mandataire, pas celle de l'administration bénéficiaire.
      - Souvent la première date de signature en cas de plusieurs dates de signature.
      - Repérer les expressions comme "Signé le", "Fait à ...", ou des dates en bas du document associées à une signature.
      - Si le document termine par une date seule, c'est probablement la date de signature de l'administration.
      - Ignorer les dates d'émission ou de création du document, en général en haut du document
      - Ne rien renvoyer si aucune date de signature trouvée pour le mandataire.
     Format : en "JJ/MM/AAAA" quelle que soit la notation d'origine  
""",
        "search": "",
        "output_field": "date_signature_mandataire"
    },

    "date_signature_administration": {
        "consigne": """DATE_SIGNATURE_ADMINISTRATION
      Définition : Date de signature du document par l'administration. 
      Indices : 
      - Uniquement la date de signature de l'acheteur, du pouvoir adjudicateur, ou de l'administration bénéficiaire.
      - Souvent la dernière signature en cas de plusieurs dates de signatures.
      - Repérer les expressions comme "Signé le", "Fait à ...", ou des dates en bas du document associées à une signature.
      - Si le document termine par une date seule, c'est surement la date designature de l'administration.
      - Ignorer les dates d'émission ou de création du document, en général en haut du document
      - Ne rien renvoyer si aucune date de signature trouvée
     Format : en "JJ/MM/AAAA" quelle que soit la notation d'origine  
""",
        "search": "",
        "output_field": "date_signature_administration"
    },

    "date_notification": {
        "consigne": """DATE_NOTIFICATION
      Définition : Date de notification du marché aux mandataires. 
      Indices : 
      - Parfois en début du document, ou en toute fin de document.
      - Après la mention "Date de notification" ou "Date de début du marché".
      - S'il y a un doute sur la lecture de la date, prendre la date la plus proche postérieure à la signature par l'administration si disponible.
      - S'il n'y a pas de date de notification explicite, ne rien renvoyer.
      - Attention à ne pas confondre la date de notification avec la date de signature.
     Format : en "JJ/MM/AAAA" quelle que soit la notation d'origine  
""",
        "search": "",
        "output_field": "date_notification"
    },
}

