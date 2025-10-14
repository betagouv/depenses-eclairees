import re
import unicodedata

def extract_num_EJ(filename: str) -> int:
    """
    Extrait les 10 premiers chiffres du nom du fichier et les convertit en int.
    
    Args:
        filename (str): Nom du fichier à analyser
        
    Returns:
        int: Les 10 premiers chiffres trouvés ou NaN si moins de 10 chiffres
    """
    # Extraire tous les chiffres du nom de fichier
    digits = ''.join(re.findall(r'\d', filename))
    
    # Vérifier s'il y a au moins 10 chiffres
    if len(digits) >= 10:
        return digits[:10]
    else:
        # Retourner NaN si moins de 10 chiffres
        return "-1"


def normalize_text(text):
    text = unicodedata.normalize('NFD', text)
    text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
    text = text.lower()
    text = re.sub(r'[_\-]+', ' ', text)         # remplace _ et - par espace
    text = re.sub(r'[^a-z0-9\s]', '', text)     # supprime la ponctuation
    return re.sub(r'\s+', ' ', text)    # espaces multiples