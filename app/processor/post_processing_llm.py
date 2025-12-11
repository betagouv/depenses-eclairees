import json
import re
import logging

logger = logging.getLogger("docia." + __name__)


def check_consistency_bank_account(iban: str) -> bool:
    """
    Vérifie la validité d'un IBAN selon la norme ISO 13616.
    Format accepté : Français 27 caractères, ou ''.
    Retourne True si valide, False sinon.
    """

    if iban == '':
        return True

    # Longueur minimale (2 lettres pays + 2 chiffres contrôle + BBAN)
    elif len(iban) != 27:
        return False

    # 2. Déplacer les 4 premiers caractères à la fin
    rearranged = iban[4:] + iban[:4]
    rearranged = rearranged.upper()

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

################################################################################
## Acte d'engagement : post-traitement des informations

def post_processing_bank_account(bank_account_input: dict[str, str]) -> dict[str, str]:
    """
    Post-traitement du RIB pour extraire les informations bancaires.
    """

    if(bank_account_input == {}):
        return {}

    # Vérifie que rib contient la clé 'banque'
    if 'banque' not in bank_account_input:
        raise ValueError("Le paramètre 'rib' doit contenir la clé 'banque'")

    bank_name = bank_account_input.get('banque', '')

    # Si 'iban' est présent, on prend l'iban
    if 'iban' in bank_account_input:
        iban = bank_account_input.get('iban','')

    # Si on a les 4 champs numériques mais pas d'iban, on construit l'iban
    elif all(k in bank_account_input for k in ['code_banque', 'code_guichet', 'numero_compte', 'cle_rib']):
        bank_code = bank_account_input.get('code_banque', '')
        bank_guichet = bank_account_input.get('code_guichet', '')
        account_number = bank_account_input.get('numero_compte', '')
        check_digit = bank_account_input.get('cle_rib', '')
        iban = 'FR76' + bank_code + bank_guichet + account_number + check_digit
    
    # Si pas d'iban et pas les 4 champs, on renvoie une erreur.
    else:
        raise ValueError("Le RIB doit contenir soit un IBAN, soit les champs code_banque, code_guichet, numero_compte et cle_rib.")

    iban = re.sub(r'\s+', '', iban).upper() # Suppression des espaces et mise en majuscule

    if iban == '' and bank_name == '':
        return {}
    elif not check_consistency_bank_account(iban) :
        return {'banque': bank_name, 'iban': ''}
    else:
        return {'banque': bank_name, 'iban': iban}


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
    amount = amount.replace(" ", "")
    # Chercher un nombre avec ou sans partie décimale, séparateur . ou ,
    match = re.search(r'(\d+(?:[.,]\d+)?)', amount)
    if match:
        num = match.group(1)
        # Remplacer la virgule (cas français) par un point pour le float Python
        num = num.replace(',', '.')
        try:
            return str(round(float(num), 2))
        except ValueError:
            return ''
    return ''


def post_processing_co_contractors(co_contractors: list[dict[str, str]]) -> list[dict[str, str]]:
    """
    Post-traitement des cotraitants pour extraire les informations sur les entreprises cotraitantes.
    """
    if co_contractors == []:
        return []
    # On commence par évaluer la chaîne d'entrée comme une liste Python.
    clean_co_contractors_list = []
    # On parcourt chaque cotraitant de la liste
    for co_contractor in co_contractors:
        clean_siret = post_processing_siret(co_contractor['siret'])
            
        # On ajoute à la liste seulement si le nom ou le siret n'est pas vide
        if co_contractor['nom'] != '' and clean_siret != '':
            clean_co_contractors_list.append(
                {
                    'nom': co_contractor['nom'],
                    'siret': clean_siret
                })
    # On retourne la liste nettoyée des cotraitants
    return clean_co_contractors_list


def post_processing_subcontractors(subcontractors_list: list[dict[str, str]]) -> list[dict[str, str]]:
    """
    Post-traitement des sous-traitants pour extraire les informations sur les entreprises sous-traitantes.
    """

    if subcontractors_list == []:
        return []
    
    clean_subcontractors_list = []
    # On parcourt chaque sous-traitant de la liste
    for subcontractor in subcontractors_list:
        # Pour chaque sous-traitant, on nettoie le SIRET et on construit un dictionnaire propre
        clean_siret = post_processing_siret(subcontractor['siret'])

        if subcontractor['nom'] != '' and clean_siret != '':
            clean_subcontractors_list.append(
                {
                    'nom': subcontractor['nom'],
                    'siret': clean_siret
                })
    # On retourne la liste nettoyée des sous-traitants
    return clean_subcontractors_list


def post_processing_duration(duration: dict[str, int]) -> dict[str, int]:
    """
    Post-traitement de la durée pour extraire les informations sur la durée du marché.
    """
    if duration == {}:
        return {}

    # Vérification, ajout et format des clés pour qu'elles soient des entiers ou None
    fields = ['duree_initiale', 'duree_reconduction', 'nb_reconductions', 'delai_tranche_optionnelle']
    for field in fields:
        value = duration.get(field, None)
        # Vérifier le format : doit être un entier ou None
        if not isinstance(value, int) and value is not None:
            raise ValueError(f"Dans post_processing_duratiion : Le champ {field} n'est pas un entier ou None")
        else:
            duration[field] = value

    # Ajouter un test : si tous les champs de duration sont None ou 0, renvoyer {}
    if all(duration.get(field, None) in (None, 0) for field in fields):
        return {}

    return duration


def post_processing_siret(siret: str) -> str:
    """
    Post-traitement du SIRET pour le nettoyer.
    """

    if siret == '':
        return ''

    # Retirer les espaces
    siret = siret.replace(' ', '').replace('\xa0', '').replace(u'\u202f', '')

    # Si chaine de float valide (ex: "12345678901234.0"), transformer en int/str
    if re.fullmatch(r"\d{14}\.0+", siret):
        siret = siret.split('.')[0]

    # Si il reste seulement des chiffres et longueur 14, c'est ok
    if (siret.isdigit() and len(siret) == 14) or siret == '':
        return siret
    else:
        return ''


def post_processing_other_bank_accounts(other_bank_accounts: list[dict[str, dict[str, str]]]) -> list[dict[str, dict[str, str]]]:
    """
    Post-traitement des RIB autres pour extraire les informations bancaires de chaque RIB.
    Prend en entrée un string JSON contenant une liste de dictionnaires RIB (format rib_mandataire).
    """
    if other_bank_accounts == []:
        return []

    clean_bank_accounts = []
    
    # Parcourir chaque compte bancaire de la liste
    for account_entry in other_bank_accounts:
        partner_name = account_entry.get('societe', '')
        account_data = account_entry.get('rib', {})
        
        processed_account = post_processing_bank_account(account_data)
        
        # Ajouter à la liste seulement si le compte est valide (non vide)
        if processed_account.get('iban', '') != '' or processed_account.get('banque', '') != '':
            clean_bank_accounts.append({'societe': partner_name,'rib': processed_account})
    
    # Retourner la liste nettoyée des comptes bancaires
    return clean_bank_accounts



################################################################################
## RIB : post-traitement des informations

def post_processing_iban(iban: str) -> str:
    """
    Post-traitement de l'IBAN pour extraire les informations bancaires.
    """
    clean_iban = re.sub(r'\s+', '', iban).upper()
    if(not check_consistency_bank_account(clean_iban)):
        return ''
    return clean_iban


def post_processing_bic(bic: str) -> str:
    """
    Post-traitement du BIC pour extraire les informations bancaires.
    """
    clean_bic = re.sub(r'\s+', '', bic).upper()
    if len(clean_bic) != 8 and len(clean_bic) != 11:
        return ''
    return clean_bic
    

def normalize_text(text:str) -> str:
    """Normalise un texte : trim et capitalisation appropriée."""
    if text == '':
        return ''
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


def post_processing_postal_address(postal_address: dict[str, str]) -> dict[str, str]:
    """
    Post-traitement de l'adresse postale pour normaliser et valider les champs.
    Format attendu : JSON avec les champs numero_voie, nom_voie, complement_adresse, code_postal, ville, pays.
    """
    if postal_address == {}:
        return {}
     
    # Normaliser les champs
    normalized_address = {
        'numero_voie': normalize_text(postal_address.get('numero_voie', '')),
        'nom_voie': normalize_text(postal_address.get('nom_voie', '')),
        'complement_adresse': normalize_text(postal_address.get('complement_adresse', '')),
        'code_postal': normalize_text(postal_address.get('code_postal', '')),
        'ville': normalize_ville(postal_address.get('ville', '')),
        'pays': normalize_text(postal_address.get('pays', ''))
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
        return {}

    return normalized_address