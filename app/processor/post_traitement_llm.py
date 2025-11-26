import json
import re
import logging

logger = logging.getLogger("docia." + __name__)

def iban_to_numeros(iban: str) -> str:
    if(len(iban) != 27):
        raise ValueError("L'IBAN doit contenir 27 caractères")
    
    dict_numeros={
        'code_banque': iban[4:9],
        'code_guichet': iban[9:14],
        'numero_compte': iban[14:25],
        'cle_rib': iban[25:27]
    }
    return dict_numeros

def nettoyer_json_mal_formate(chaine_json: str) -> str:
    """
    Nettoie et corrige une chaîne JSON mal formatée.
    Essaie d'abord json.loads, et si ça échoue, applique des corrections.
    """
    chaine_json = chaine_json.strip()
    
    # Essayer d'abord de parser tel quel
    try:
        json.loads(chaine_json)
        return chaine_json
    except json.JSONDecodeError:
        pass
    
    # Corrections à appliquer
    # 1. D'abord, corriger les \' dans les chaînes entre guillemets doubles (non valide en JSON)
    # On remplace \' par ' dans les chaînes entre guillemets doubles
    def corriger_echappement_guillemets_simples(chaine):
        """Remplace les \' par ' dans les chaînes entre guillemets doubles."""
        result = []
        i = 0
        dans_guillemets_doubles = False
        while i < len(chaine):
            if chaine[i] == '"' and (i == 0 or chaine[i-1] != '\\'):
                # Toggle: on entre ou on sort d'une chaîne entre guillemets doubles
                dans_guillemets_doubles = not dans_guillemets_doubles
                result.append(chaine[i])
                i += 1
            elif dans_guillemets_doubles and chaine[i] == '\\' and i + 1 < len(chaine) and chaine[i+1] == "'":
                # On est dans une chaîne entre guillemets doubles et on trouve \'
                # On remplace par simplement ' (car \' n'est pas valide en JSON)
                result.append("'")
                i += 2
            else:
                result.append(chaine[i])
                i += 1
        return ''.join(result)
    
    chaine_json = corriger_echappement_guillemets_simples(chaine_json)
    
    # 2. Remplacer les guillemets simples par des guillemets doubles pour les clés et valeurs
    # On utilise une approche qui analyse le contexte pour gérer les apostrophes dans les valeurs
    # Mais on ignore les guillemets simples qui sont dans des chaînes entre guillemets doubles
    
    def remplacer_guillemets_simples_avec_contexte(chaine):
        """Remplace les guillemets simples en analysant le contexte pour gérer les apostrophes."""
        result = []
        i = 0
        dans_guillemets_doubles = False
        while i < len(chaine):
            if chaine[i] == '"' and (i == 0 or chaine[i-1] != '\\'):
                # Toggle: on entre ou on sort d'une chaîne entre guillemets doubles
                dans_guillemets_doubles = not dans_guillemets_doubles
                result.append(chaine[i])
                i += 1
            elif chaine[i] == "'" and not dans_guillemets_doubles:
                # Trouver la fin de la chaîne entre guillemets simples
                # On cherche jusqu'au prochain guillemet simple suivi de : (clé) ou , ou } (valeur)
                i += 1
                contenu = []
                
                # Collecter le contenu jusqu'à trouver la fin appropriée
                while i < len(chaine):
                    if chaine[i] == "\\" and i + 1 < len(chaine):
                        # Gérer les échappements
                        contenu.append(chaine[i])
                        contenu.append(chaine[i + 1])
                        i += 2
                    elif chaine[i] == "'":
                        # Vérifier si c'est la fin de la chaîne
                        # On regarde les caractères suivants (en ignorant les espaces) pour voir si c'est : , ou }
                        j = i + 1
                        while j < len(chaine) and chaine[j] in ' \t\n':
                            j += 1
                        if j < len(chaine) and chaine[j] in [':', ',', '}']:
                            # C'est la fin de la chaîne
                            break
                        else:
                            # C'est une apostrophe dans le contenu
                            contenu.append(chaine[i])
                            i += 1
                    else:
                        contenu.append(chaine[i])
                        i += 1
                
                # Convertir le contenu
                contenu_str = ''.join(contenu)
                # Convertir les \' en ' (car dans JSON valide, les guillemets simples n'ont pas besoin d'échappement)
                contenu_str = contenu_str.replace("\\'", "'")
                # Échapper les guillemets doubles qui pourraient être dans le contenu
                contenu_echappe = contenu_str.replace('"', '\\"')
                result.append(f'"{contenu_echappe}"')
                i += 1  # Passer le guillemet de fermeture
            else:
                result.append(chaine[i])
                i += 1
        return ''.join(result)
    
    chaine_json = remplacer_guillemets_simples_avec_contexte(chaine_json)
    
    # 3. Ajouter des guillemets aux clés sans guillemets
    # Pattern: début de chaîne ou après { ou , suivi d'une clé sans guillemets
    def corriger_cle(match):
        prefix = match.group(1)  # { ou , ou espace
        cle = match.group(2)     # le nom de la clé
        return f'{prefix}"{cle}":'
    
    # Remplacer les clés sans guillemets (attention aux cas déjà entre guillemets)
    chaine_json = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', corriger_cle, chaine_json)
    
    return chaine_json

def post_traitement_rib(rib_entree: str) -> dict:
    """
    Post-traitement du RIB pour extraire les informations bancaires.
    """

    rib_propre = nettoyer_json_mal_formate(rib_entree)

    if(rib_propre is None or rib_propre == '' or rib_propre == 'nan'):
        return ''

    rib = json.loads(rib_propre)

    # Vérifie que rib contient la clé 'banque'
    if 'banque' not in rib:
        raise ValueError("Le paramètre 'rib' doit contenir la clé 'banque'")

    # Si 'iban' est présent, on renvoie la banque et l'iban
    if 'iban' in rib:
        rib['iban'] = re.sub(r'\s+', '', rib['iban']).upper()
        if(len(rib['iban']) != 27):
            raise ValueError("L'IBAN doit contenir 27 caractères")
        return json.dumps({'banque': rib.get('banque', ''), 'iban': rib['iban'].upper()})
    
    # Si on a les 4 champs numériques mais pas d'iban, on construit l'iban
    elif all(k in rib for k in ['code_banque', 'code_guichet', 'numero_compte', 'cle_rib']):
        iban = 'FR76' + rib['code_banque'] + rib['code_guichet'] + rib['numero_compte'] + rib['cle_rib']
        if(len(iban) != 27):
            raise ValueError("L'IBAN doit contenir 27 caractères")
        return json.dumps({'banque': rib.get('banque', ''), 'iban': iban})
    
    # Si ni l'une ni l'autre condition n'est validée, on retourne une erreur explicite
    else:
        raise ValueError("Le 'rib' doit contenir soit un IBAN, soit les champs code_banque, code_guichet, numero_compte et cle_rib.")

def post_traitement_montant(montant: str) -> str:
    """
    Extrait le montant d'une expression chaîne de caractères.
    Exemples d'entrées possibles :
      - "1234.56€"
      - "1 234,56 €"
      - "1200€"
      - "85.00"
      - "200,00"
      - "2400"
      - "2 400,50"
      - "2300,5€"
    Retourne un float à deux chiffres après la virgule, ou None si rien n'est trouvé.
    """
    if not isinstance(montant, str):
        montant = str(montant)
    # Retirer espaces insécables et normaux
    montant = montant.replace('\xa0', ' ').replace(u'\u202f', ' ').replace(" ", "")
    # Chercher un nombre avec ou sans partie décimale, séparateur . ou ,
    match = re.search(r'(\d+(?:[.,]\d{1,2})?)', montant)
    if match:
        num = match.group(1)
        # Remplacer la virgule (cas français) par un point pour le float Python
        num = num.replace(',', '.')
        try:
            return json.dumps(round(float(num), 2))
        except (ValueError, TypeError):
            return ''
    return ''

def post_traitement_cotraitants(cotraitants: str) -> str:
    """
    Post-traitement des cotraitants pour extraire les informations sur les entreprises cotraitantes.
    """
    try:
        # On commence par évaluer la chaîne d'entrée comme une liste Python.
        list_cotraitants = json.loads(cotraitants)
        list_clean_cotraitants = []
        # On parcourt chaque cotraitant de la liste
        for cotraitant in list_cotraitants:
            try: 
                # Pour chaque cotraitant, on nettoie le SIRET
                clean_siret = cotraitant['siret']
            except Exception as e:
                clean_siret = ''
                logger.error(f"Erreur dans post_traitement_cotraitants pour le cotraitant {cotraitant['nom']} : {e}")
                
            clean_cotraitant = {
                'nom': cotraitant['nom'],
                'siret': clean_siret
            }
            # On ajoute à la liste seulement si le nom ou le siret n'est pas vide
            if clean_cotraitant['nom'] or clean_cotraitant['siret']:
                list_clean_cotraitants.append(clean_cotraitant)
            
        # On retourne la liste nettoyée des cotraitants
        return json.dumps(list_clean_cotraitants)
    except Exception as e:
        # Si une erreur globale apparaît (exemple : eval échoue), on loggue et renvoie une liste vide
        logger.error(f"Erreur dans post_traitement_cotraitants lors de l'évaluation de la chaîne d'entrée des cotraitants : {e}")
        return json.dumps([])

def post_traitement_sous_traitants(sous_traitants: str) -> str:
    """
    Post-traitement des cotraitants pour extraire les informations sur les entreprises sous-traitantes.
    """
    try:
        # On commence par évaluer la chaîne d'entrée comme une liste Python.
        list_sous_traitants = json.loads(sous_traitants)
        list_clean_sous_traitants = []
        # On parcourt chaque sous-traitant de la liste
        for sous_traitant in list_sous_traitants:
            try: 
                # Pour chaque sous-traitant, on nettoie le SIRET et on construit un dictionnaire propre
                clean_sous_traitant = {
                    'nom': sous_traitant['nom'],
                    'siret': post_traitement_siret(sous_traitant['siret'])
                }
                list_clean_sous_traitants.append(clean_sous_traitant)
            except Exception as e:
                # Si une erreur survient lors du nettoyage du SIRET, on loggue un warning et met un SIRET vide
                logger.error(f"Erreur dans post_traitement_sous_traitants pour le sous-traitant {sous_traitant['nom']} : {e}")
                clean_sous_traitant = {'nom': sous_traitant['nom'], 'siret': ''}
                list_clean_sous_traitants.append(clean_sous_traitant)
        # On retourne la liste nettoyée des sous-traitants
        return json.dumps(list_clean_sous_traitants)
    except Exception as e:
        # Si une erreur globale apparaît (exemple : eval échoue), on loggue et renvoie une liste vide
        logger.error(f"Erreur dans post_traitement_sous_traitants lors de l'évaluation de la chaîne d'entrée des sous-traitants : {e}")
        return json.dumps([])

def post_traitement_duree(duree: str) -> str:
    """
    Post-traitement de la durée pour extraire les informations sur la durée du marché.
    """
    if duree is None or duree == '' or duree == 'nan':
        return json.dumps('')
    try:
        # On commence par évaluer la chaîne d'entrée comme un json.
        duree_json = json.loads(duree)
        # Vérification, ajout et format des clés pour qu'elles soient des str d'entier ou ''
        champs = ['duree_initiale', 'duree_reconduction', 'nb_reconductions', 'delai_tranche_optionnelle']
        for champ in champs:
            valeur = duree_json.get(champ, '')
            # Vérifier le format : doit être un str représentant un entier ou ''
            if isinstance(valeur, int):
                duree_json[champ] = str(valeur)
            elif isinstance(valeur, str):
                valeur = valeur.replace(' ', '').replace('\xa0', '').replace(u'\u202f', '')
                # Si string vide ou string d'un entier positif
                if valeur == '' or (valeur.isdigit() and valeur != '0'):
                    duree_json[champ] = valeur
                else:
                    # Format incorrect, on met ''
                    duree_json[champ] = ''
            else:
                # Si ce n'est ni un int ni un str (float, bool, list, None, etc.), on remplace par ''
                duree_json[champ] = ''
        
        # Si toutes les valeurs sont vides, on renvoie '' au lieu d'un dictionnaire avec des champs vides
        if all(valeur == '' for valeur in duree_json.values()):
            return json.dumps('')
        
        return json.dumps(duree_json)
    except Exception as e:
        # Si une erreur globale apparaît (exemple : eval échoue), on loggue et renvoie une durée vide
        logger.error(f"Erreur dans post_traitement_duree lors de l'évaluation de la chaîne d'entrée de la durée : {e}")
        return json.dumps('')

def post_traitement_siret(siret: str) -> str:
    """
    Post-traitement du SIRET pour le nettoyer.
    """
    # Le post-traitement du SIRET : on attend un string de 14 chiffres.
    # On corrige éventuellement si possible : (float en string, espaces...)
    if not isinstance(siret, str):
        siret = str(siret)

    # Retirer les espaces
    siret = siret.replace(' ', '').replace('\xa0', '').replace(u'\u202f', '')

    # Si chaine de float valide (ex: "12345678901234.0"), transformer en int/str
    if re.fullmatch(r"\d{14}\.0+", siret):
        siret = siret.split('.')[0]

    # Si restent seulement des chiffres et longueur 14, c'est ok
    if siret.isdigit() and len(siret) == 14:
        return siret

    # Si pas corrigible, on lève une erreur ValueError
    raise ValueError("Le SIRET fourni n'est pas corrigible.")
