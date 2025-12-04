import json
import re
import logging

logger = logging.getLogger("docia." + __name__)

## Fonctions de post-traitement communes
def iban_to_numbers(iban: str) -> str:
    if(len(iban) != 27):
        raise ValueError("L'IBAN doit contenir 27 caractères")
    
    numbers_dict={
        'code_banque': iban[4:9],
        'code_guichet': iban[9:14],
        'numero_compte': iban[14:25],
        'cle_rib': iban[25:27]
    }
    return numbers_dict


def clean_malformed_json(json_string: str) -> str:
    """
    Nettoie et corrige une chaîne JSON mal formatée.
    Essaie d'abord json.loads, et si ça échoue, applique des corrections.
    """
    json_string = json_string.strip()
    
    # Essayer d'abord de parser tel quel
    try:
        json.loads(json_string)
        return json_string
    except json.JSONDecodeError:
        pass
    
    # Corrections à appliquer
    # 1. D'abord, corriger les \' dans les chaînes entre guillemets doubles (non valide en JSON)
    # On remplace \' par ' dans les chaînes entre guillemets doubles
    def fix_single_quote_escaping(text):
        """Remplace les \' par ' dans les chaînes entre guillemets doubles."""
        result = []
        i = 0
        in_double_quotes = False
        while i < len(text):
            if text[i] == '"' and (i == 0 or text[i-1] != '\\'):
                # Toggle: on entre ou on sort d'une chaîne entre guillemets doubles
                in_double_quotes = not in_double_quotes
                result.append(text[i])
                i += 1
            elif in_double_quotes and text[i] == '\\' and i + 1 < len(text) and text[i+1] == "'":
                # On est dans une chaîne entre guillemets doubles et on trouve \'
                # On remplace par simplement ' (car \' n'est pas valide en JSON)
                result.append("'")
                i += 2
            else:
                result.append(text[i])
                i += 1
        return ''.join(result)
    
    json_string = fix_single_quote_escaping(json_string)
    
    # 2. Remplacer les guillemets simples par des guillemets doubles pour les clés et valeurs
    # On utilise une approche qui analyse le contexte pour gérer les apostrophes dans les valeurs
    # Mais on ignore les guillemets simples qui sont dans des chaînes entre guillemets doubles
    
    def replace_single_quotes_with_context(text):
        """Remplace les guillemets simples en analysant le contexte pour gérer les apostrophes."""
        result = []
        i = 0
        in_double_quotes = False
        while i < len(text):
            if text[i] == '"' and (i == 0 or text[i-1] != '\\'):
                # Toggle: on entre ou on sort d'une chaîne entre guillemets doubles
                in_double_quotes = not in_double_quotes
                result.append(text[i])
                i += 1
            elif text[i] == "'" and not in_double_quotes:
                # Trouver la fin de la chaîne entre guillemets simples
                # On cherche jusqu'au prochain guillemet simple suivi de : (clé) ou , ou } (valeur)
                i += 1
                content = []
                
                # Collecter le contenu jusqu'à trouver la fin appropriée
                while i < len(text):
                    if text[i] == "\\" and i + 1 < len(text):
                        # Gérer les échappements
                        content.append(text[i])
                        content.append(text[i + 1])
                        i += 2
                    elif text[i] == "'":
                        # Vérifier si c'est la fin de la chaîne
                        # On regarde les caractères suivants (en ignorant les espaces) pour voir si c'est : , ou }
                        j = i + 1
                        while j < len(text) and text[j] in ' \t\n':
                            j += 1
                        if j < len(text) and text[j] in [':', ',', '}']:
                            # C'est la fin de la chaîne
                            break
                        else:
                            # C'est une apostrophe dans le contenu
                            content.append(text[i])
                            i += 1
                    else:
                        content.append(text[i])
                        i += 1
                
                # Convertir le contenu
                content_str = ''.join(content)
                # Convertir les \' en ' (car dans JSON valide, les guillemets simples n'ont pas besoin d'échappement)
                content_str = content_str.replace("\\'", "'")
                # Échapper les guillemets doubles qui pourraient être dans le contenu
                escaped_content = content_str.replace('"', '\\"')
                result.append(f'"{escaped_content}"')
                i += 1  # Passer le guillemet de fermeture
            else:
                result.append(text[i])
                i += 1
        return ''.join(result)
    
    json_string = replace_single_quotes_with_context(json_string)
    
    # 3. Ajouter des guillemets aux clés sans guillemets
    # Pattern: début de chaîne ou après { ou , suivi d'une clé sans guillemets
    def fix_key(match):
        prefix = match.group(1)  # { ou , ou espace
        key = match.group(2)     # le nom de la clé
        return f'{prefix}"{key}":'
    
    # Remplacer les clés sans guillemets (attention aux cas déjà entre guillemets)
    json_string = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', fix_key, json_string)
    
    return json_string


def check_consistency_bank_account(bank_account_input: str) -> bool:
    """
    Vérifie la validité d'un IBAN selon la norme ISO 13616.
    Retourne True si valide, False sinon.
    """
    # Longueur minimale (2 lettres pays + 2 chiffres contrôle + BBAN)
    if len(bank_account_input) < 5:
        return False

    # 2. Déplacer les 4 premiers caractères à la fin
    rearranged = bank_account_input[4:] + bank_account_input[:4]

    # 3. Remplacer chaque lettre par sa valeur numérique A=10, B=11, ...
    converted = ""
    for char in rearranged:
        if char.isdigit():
            converted += char
        elif char.isalpha():
            # A -> 10, ..., Z -> 35
            converted += str(ord(char) - 55)
        else:
            return False  # caractère invalide

    # 4. Calcul mod 97 sur un nombre potentiellement très grand
    # On calcule le modulo progressivement (méthode standard IBAN)
    remainder = 0
    for digit in converted:
        remainder = (remainder * 10 + int(digit)) % 97

    # 5. Un IBAN est valide si le résultat = 1
    return remainder == 1


## Acte d'engagement : post-traitement des informations

def post_processing_bank_account(bank_account_input: str) -> str:
    """
    Post-traitement du RIB pour extraire les informations bancaires.
    """

    clean_bank_account = clean_malformed_json(bank_account_input)

    if(clean_bank_account is None or clean_bank_account == '' or clean_bank_account == 'nan'):
        return ''

    json_bank_account = json.loads(clean_bank_account)

    # Vérifie que rib contient la clé 'banque'
    if 'banque' not in json_bank_account:
        raise ValueError("Le paramètre 'rib' doit contenir la clé 'banque'")

    # Si 'iban' est présent, on renvoie la banque et l'iban
    if 'iban' in json_bank_account:
        json_bank_account['iban'] = re.sub(r'\s+', '', json_bank_account['iban']).upper()
        if((len(json_bank_account['iban']) != 27 and len(json_bank_account['iban'])) != 0):
            return json.dumps({'banque': json_bank_account.get('banque', ''), 'iban': ''})
            # raise ValueError("L'IBAN doit contenir 27 caractères")
        if(not check_consistency_bank_account(json_bank_account['iban']) and len(json_bank_account['iban']) != 0):
            return json.dumps({'banque': json_bank_account.get('banque', ''), 'iban': ''})
            # raise ValueError("L'IBAN n'est pas cohérent")
        return json.dumps({'banque': json_bank_account.get('banque', ''), 'iban': json_bank_account['iban'].upper()})
    
    # Si on a les 4 champs numériques mais pas d'iban, on construit l'iban
    elif all(k in json_bank_account for k in ['code_banque', 'code_guichet', 'numero_compte', 'cle_rib']):
        iban = 'FR76' + json_bank_account['code_banque'] + json_bank_account['code_guichet'] + json_bank_account['numero_compte'] + json_bank_account['cle_rib']
        if(len(iban) != 27 and len(iban) != 0):
            return json.dumps({'banque': json_bank_account.get('banque', ''), 'iban': ''})
            # raise ValueError("L'IBAN doit contenir 27 caractères")
        if(not check_consistency_bank_account(iban) and len(iban) != 0):
            return json.dumps({'banque': json_bank_account.get('banque', ''), 'iban': ''})
            # raise ValueError("L'IBAN n'est pas cohérent")
        return json.dumps({'banque': json_bank_account.get('banque', ''), 'iban': iban})
    
    # Si ni l'une ni l'autre condition n'est validée, on retourne une erreur explicite
    else:
        raise ValueError("Le 'rib' doit contenir soit un IBAN, soit les champs code_banque, code_guichet, numero_compte et cle_rib.")


def post_processing_amount(amount: str) -> str:
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
    if not isinstance(amount, str):
        amount = str(amount)
    # Retirer espaces insécables et normaux
    amount = amount.replace('\xa0', ' ').replace(u'\u202f', ' ').replace(" ", "")
    # Chercher un nombre avec ou sans partie décimale, séparateur . ou ,
    match = re.search(r'(\d+(?:[.,]\d{1,2})?)', amount)
    if match:
        num = match.group(1)
        # Remplacer la virgule (cas français) par un point pour le float Python
        num = num.replace(',', '.')
        try:
            return json.dumps(round(float(num), 2))
        except (ValueError, TypeError):
            return ''
    return ''


def post_processing_co_contractors(co_contractors: str) -> str:
    """
    Post-traitement des cotraitants pour extraire les informations sur les entreprises cotraitantes.
    """
    try:
        # On commence par évaluer la chaîne d'entrée comme une liste Python.
        co_contractors_list = json.loads(co_contractors)
        clean_co_contractors_list = []
        # On parcourt chaque cotraitant de la liste
        for co_contractor in co_contractors_list:
            try: 
                # Pour chaque cotraitant, on nettoie le SIRET
                clean_siret = co_contractor['siret']
            except Exception as e:
                clean_siret = ''
                logger.error(f"Error in post_processing_co_contractors for co-contractor: {e}")
                
            clean_co_contractor = {
                'nom': co_contractor['nom'],
                'siret': clean_siret
            }
            # On ajoute à la liste seulement si le nom ou le siret n'est pas vide
            if clean_co_contractor['nom'] or clean_co_contractor['siret']:
                clean_co_contractors_list.append(clean_co_contractor)
            
        # On retourne la liste nettoyée des cotraitants
        return json.dumps(clean_co_contractors_list)
    except Exception as e:
        # Si une erreur globale apparaît (exemple : eval échoue), on loggue et renvoie une liste vide
        logger.error(f"Error in post_processing_co_contractors when evaluating input string of co-contractors: {e}")
        return json.dumps([])


def post_processing_subcontractors(subcontractors: str) -> str:
    """
    Post-traitement des cotraitants pour extraire les informations sur les entreprises sous-traitantes.
    """
    try:
        # On commence par évaluer la chaîne d'entrée comme une liste Python.
        subcontractors_list = json.loads(subcontractors)
        clean_subcontractors_list = []
        # On parcourt chaque sous-traitant de la liste
        for subcontractor in subcontractors_list:
            try: 
                # Pour chaque sous-traitant, on nettoie le SIRET et on construit un dictionnaire propre
                clean_subcontractor = {
                    'nom': subcontractor['nom'],
                    'siret': post_traitement_siret(subcontractor['siret'])
                }
                clean_subcontractors_list.append(clean_subcontractor)
            except Exception as e:
                # Si une erreur survient lors du nettoyage du SIRET, on loggue un warning et met un SIRET vide
                logger.error(f"Erreur dans post_traitement_sous_traitants pour le sous-traitant {subcontractor['nom']} : {e}")
                clean_subcontractor = {'nom': subcontractor['nom'], 'siret': ''}
                clean_subcontractors_list.append(clean_subcontractor)
        # On retourne la liste nettoyée des sous-traitants
        return json.dumps(clean_subcontractors_list)
    except Exception as e:
        # Si une erreur globale apparaît (exemple : eval échoue), on loggue et renvoie une liste vide
        logger.error(f"Erreur dans post_traitement_sous_traitants lors de l'évaluation de la chaîne d'entrée des sous-traitants : {e}")
        return json.dumps([])


def post_processing_duration(duration: str) -> str:
    """
    Post-traitement de la durée pour extraire les informations sur la durée du marché.
    """
    if duration is None or duration == '' or duration == 'nan':
        return json.dumps('')
    try:
        # On commence par évaluer la chaîne d'entrée comme un json.
        duration_json = json.loads(duration)
        # Vérification, ajout et format des clés pour qu'elles soient des str d'entier ou ''
        fields = ['duree_initiale', 'duree_reconduction', 'nb_reconductions', 'delai_tranche_optionnelle']
        for field in fields:
            value = duration_json.get(field, '')
            # Vérifier le format : doit être un str représentant un entier ou ''
            if isinstance(value, int):
                duration_json[field] = str(value)
            elif isinstance(value, str):
                value = value.replace(' ', '').replace('\xa0', '').replace(u'\u202f', '')
                # Si string vide ou string d'un entier positif
                if value == '' or (value.isdigit() and value != '0'):
                    duration_json[field] = value
                else:
                    # Format incorrect, on met ''
                    duration_json[field] = ''
            else:
                # Si ce n'est ni un int ni un str (float, bool, list, None, etc.), on remplace par ''
                duration_json[field] = ''
        
        # Si toutes les valeurs sont vides, on renvoie '' au lieu d'un dictionnaire avec des champs vides
        if all(value == '' for value in duration_json.values()):
            return json.dumps('')
        
        return json.dumps(duration_json)
    except Exception as e:
        # Si une erreur globale apparaît (exemple : eval échoue), on loggue et renvoie une durée vide
        logger.error(f"Erreur dans post_traitement_duree lors de l'évaluation de la chaîne d'entrée de la durée : {e}")
        return json.dumps('')


def post_processing_siret(siret: str) -> str:
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


def post_processing_other_bank_accounts(other_bank_accounts: str) -> str:
    """
    Post-traitement des RIB autres pour extraire les informations bancaires de chaque RIB.
    Prend en entrée un string JSON contenant une liste de dictionnaires RIB (format rib_mandataire).
    """
    if other_bank_accounts is None or other_bank_accounts == '' or other_bank_accounts == 'nan':
        return json.dumps([])

    try:
        # Parser la chaîne JSON en liste de dictionnaires de comptes bancaires
        bank_accounts_list = json.loads(other_bank_accounts)
        
        # Vérifier que c'est bien une liste
        if not isinstance(bank_accounts_list, list):
            logger.error(f"Erreur dans post_processing_other_bank_accounts : l'entrée n'est pas une liste")
            return json.dumps([])
        
        clean_bank_accounts = []
        
        # Parcourir chaque compte bancaire de la liste
        for account_entry in bank_accounts_list:
            try:
                partner_name = account_entry.get('societe', '')
                account_data = account_entry.get('rib', {})
                
                # Convertir le dictionnaire de compte en string JSON pour post_processing_bank_account
                account_str = json.dumps(account_data) if isinstance(account_data, dict) else str(account_data)
                
                # Appliquer le post-traitement à chaque compte
                processed_account = post_processing_bank_account(account_str)
                
                # Parser le résultat pour vérifier qu'il est valide
                account_dict = json.loads(processed_account)
                
                # Ajouter à la liste seulement si le compte est valide (non vide)
                if account_dict and (account_dict.get('iban', '') != '' or account_dict.get('banque', '') != ''):
                    clean_bank_accounts.append({'societe': partner_name,'rib': account_dict})
                    
            except Exception as e:
                # Si une erreur survient lors du traitement d'un compte, on loggue et on continue
                logger.warning(f"Erreur dans post_processing_other_bank_accounts pour un compte bancaire : {e}")
                # On n'ajoute pas ce compte à la liste nettoyée
                continue
        
        # Retourner la liste nettoyée des comptes bancaires
        return json.dumps(clean_bank_accounts)

    except json.JSONDecodeError as e:
        # Si une erreur globale apparaît lors du parsing JSON, on loggue et renvoie une liste vide
        logger.error(f"Erreur dans post_processing_other_bank_accounts lors du parsing JSON : {e}")
        return json.dumps([])
    except Exception as e:
        # Si une autre erreur globale apparaît, on loggue et renvoie une liste vide
        logger.error(f"Erreur dans post_processing_other_bank_accounts : {e}")
        return json.dumps([])


## RIB : post-traitement des informations

def post_processing_iban(iban: str) -> str:
    """
    Post-traitement de l'IBAN pour extraire les informations bancaires.
    """
    clean_iban = re.sub(r'\s+', '', iban).upper()
    if(len(clean_iban) != 27):
        raise ValueError("L'IBAN doit contenir 27 caractères")
    if(not check_consistency_bank_account(clean_iban)):
        raise ValueError("L'IBAN est incohérent")
    return clean_iban

def post_processing_bic(bic: str) -> str:
    """
    Post-traitement du BIC pour extraire les informations bancaires.
    """
    clean_bic = re.sub(r'\s+', '', bic).upper()
    if(len(clean_bic) != 8 and len(clean_bic) != 11):
        raise ValueError("Le BIC doit contenir 8 ou 11 caractères")
    return clean_bic
    
def post_processing_postal_address(postal_address: str) -> str:
    """
    Post-traitement de l'adresse postale pour normaliser et valider les champs.
    Format attendu : JSON avec les champs numero_voie, nom_voie, complement_adresse, code_postal, ville, pays.
    """
    if postal_address is None or postal_address == '' or postal_address == 'nan':
        return ''
    
    try:
        # Nettoyer le JSON malformé
        clean_postal_address = clean_malformed_json(postal_address)
        
        # Parser le JSON
        address_dict = json.loads(clean_postal_address)
        
        # Normaliser chaque champ
        def normalize_text(text):
            """Normalise un texte : trim et capitalisation appropriée."""
            if not isinstance(text, str):
                text = str(text) if text is not None else ''
            # Retirer les espaces en début et fin
            text = text.strip()
            # Retirer les espaces multiples
            text = re.sub(r'\s+', ' ', text)
            return text
        
        def normalize_ville(text):
            """Normalise une ville : première lettre en majuscule, reste en minuscule."""
            text = normalize_text(text)
            if text:
                # Gérer les cas spéciaux (Saint-, Le, La, etc.)
                parts = text.split('-')
                normalized_parts = []
                for part in parts:
                    if part:
                        # Première lettre en majuscule, reste en minuscule
                        normalized_parts.append(part[0].upper() + part[1:].lower() if len(part) > 1 else part.upper())
                    else:
                        normalized_parts.append(part)
                return '-'.join(normalized_parts)
            return text
        
        # Normaliser les champs
        normalized_address = {
            'numero_voie': normalize_text(address_dict.get('numero_voie', '')),
            'nom_voie': normalize_text(address_dict.get('nom_voie', '')),
            'complement_adresse': normalize_text(address_dict.get('complement_adresse', '')),
            'code_postal': normalize_text(address_dict.get('code_postal', '')),
            'ville': normalize_ville(address_dict.get('ville', '')),
            'pays': normalize_text(address_dict.get('pays', ''))
        }
        
        # Validation du code postal (5 chiffres pour la France)
        code_postal = normalized_address['code_postal']
        if code_postal:
            # Retirer les espaces et caractères non numériques
            code_postal_clean = re.sub(r'[^\d]', '', code_postal)
            if len(code_postal_clean) == 5 and code_postal_clean.isdigit():
                normalized_address['code_postal'] = code_postal_clean
            else:
                # Code postal invalide, on le vide
                normalized_address['code_postal'] = ''
        
        # Normalisation du pays : France par défaut si vide ou si code postal français présent
        pays = normalized_address['pays']
        if not pays:
            if normalized_address['code_postal']:
                # Si on a un code postal français, on suppose que c'est la France
                normalized_address['pays'] = 'France'
            else:
                normalized_address['pays'] = ''
        else:
            # Normaliser le nom du pays (première lettre en majuscule)
            pays_normalized = normalize_text(pays)
            if pays_normalized.lower() in ['france', 'fr']:
                normalized_address['pays'] = 'France'
            else:
                normalized_address['pays'] = pays_normalized
        
        # Vérifier si tous les champs importants sont vides
        important_fields = ['numero_voie', 'nom_voie', 'code_postal', 'ville']
        if all(not normalized_address[field] for field in important_fields):
            return ''
        
        return json.dumps(normalized_address)
        
    except:
        raise
