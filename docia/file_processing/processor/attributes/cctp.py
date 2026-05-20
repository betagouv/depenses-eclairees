"""
Définitions des attributs à extraire pour les documents de type "cctp".
"""

from .common import OBJET_MARCHE

CCTP_ATTRIBUTES = {
    "titre": {
        "consigne": """
   - Identifie UNIQUEMENT le titre principal du document.
   - Le titre est généralement en début de document, souvent mis en évidence (majuscules, gras, grande taille).
   - Ne donne que le titre exact, sans commentaire ni explication.
   - Si tu ne trouves pas de titre clair, extrait ce qui ressemble le plus à un titre.
   - Ne commence pas ta réponse par "Le titre est" ou "Titre:".        
""",
    },
    "objet_marche": OBJET_MARCHE,
    "prestations": {
        "consigne": """
   - Crée un résumé CONCIS des prestations techniques attendues dans le cadre de ce marché.
   - Concentre-toi uniquement sur les actions concrètes à réaliser ou les livrables attendus.
   - Le résumé doit être direct et descriptif, sans contexte ni introduction.
   - Utilise un style factuel et synthétique en une seule phrase complète.
   - N'utilise pas de formulations comme "Ce marché concerne..." ou "Les prestations comprennent...".   
""",
    },
    "lots": {
        "consigne": """
   - Vérifie la présence d'informations indiquant que le marché est divisé en plusieurs lots distincts.
   - Identifie et liste TOUS les intitulés/titres des différents lots du marché.
   - Présente-les sous forme d'une liste séparée par des points-virgules (;).
   - Chaque titre de lot doit être précédé par "Lot N°X: " ou son équivalent si le numéro est mentionné.
   - Si le numéro n'est pas mentionné, liste simplement le titre du lot.
   - Réponds uniquement si le marché est alloti.
   - Ne donne aucune explication ou commentaire supplémentaire.
   - Exemple de format attendu: "Lot N°1: Gros œuvre; Lot N°2: Peinture; Lot N°3: Électricité"
""",
    },
}
