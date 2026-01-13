"""
Définitions des attributs à extraire pour les documents de type "cctp".
"""

CCTP_ATTRIBUTES = {
    "titre": {
        "consigne": """TITRE
   - Identifie UNIQUEMENT le titre principal du document.
   - Le titre est généralement en début de document, souvent mis en évidence (majuscules, gras, grande taille).
   - Ne donne que le titre exact, sans commentaire ni explication.
   - Si tu ne trouves pas de titre clair, extrait ce qui ressemble le plus à un titre.
   - Ne commence pas ta réponse par "Le titre est" ou "Titre:".        
""",
        "search": "titre principal du document en-tête première page",
        "output_field": "titre",
    },
    "objet_marche": {
        "consigne": """OBJET_MARCHE
     Définition : Formulation synthétique de l'objet du marché.
     Indices : 
     - L'objet du marché peut être dans le titre directement, ou plus généralement dans une section dédiée.
     - Identifier les formules comme "Objet du marché", "Le marché a pour objet", ou toute expression indiquant l'intitulé de la mission.  
""",
        "search": "Section du document qui décrit l'objet du marché ou le contexte général de la consultation.",
        "output_field": "objet_marche",
    },
    "prestations": {
        "consigne": """PRESTATIONS
   - Crée un résumé CONCIS des prestations techniques attendues dans le cadre de ce marché.
   - Concentre-toi uniquement sur les actions concrètes à réaliser ou les livrables attendus.
   - Le résumé doit être direct et descriptif, sans contexte ni introduction.
   - Utilise un style factuel et synthétique en une seule phrase complète.
   - N'utilise pas de formulations comme "Ce marché concerne..." ou "Les prestations comprennent...".   
""",
        "search": "description des prestations, liste des livrables, contenu du marché, spécifications",
        "output_field": "prestations",
    },
    "lots": {
        "consigne": """LOTS:
   - Vérifie la présence d'informations indiquant que le marché est divisé en plusieurs lots distincts.
   - Identifie et liste TOUS les intitulés/titres des différents lots du marché.
   - Présente-les sous forme d'une liste séparée par des points-virgules (;).
   - Chaque titre de lot doit être précédé par "Lot N°X: " ou son équivalent si le numéro est mentionné.
   - Si le numéro n'est pas mentionné, liste simplement le titre du lot.
   - Réponds uniquement si le marché est alloti.
   - Ne donne aucune explication ou commentaire supplémentaire.
   - Exemple de format attendu: "Lot N°1: Gros œuvre; Lot N°2: Peinture; Lot N°3: Électricité"
""",
        "search": "La décomposition du marché en plusieurs lots, la liste des lots et de leurs principales prestations.",
        "output_field": "lots",
    },
}
