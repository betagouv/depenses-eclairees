import re
import unicodedata


def extract_num_EJ(filename: str) -> str:
    """
    Extrait les 10 premiers chiffres du nom du fichier et les convertit en int.
    
    Args:
        filename (str): Nom du fichier à analyser
        
    Returns:
        int: Les 10 premiers chiffres trouvés ou NaN si moins de 10 chiffres
    """
    # Extraire tous les chiffres du nom de fichier
    m = re.search(r"^\d{10}", filename)
    if m:
        return m.group(0)
    else:
        raise ValueError(f"num_ej missing in filename {filename}")


def normalize_text(text):
    text = unicodedata.normalize('NFD', text)
    text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
    text = text.lower()
    text = re.sub(r'[_\-]+', ' ', text)         # remplace _ et - par espace
    text = re.sub(r'[^a-z0-9\s]', '', text)     # supprime la ponctuation
    return re.sub(r'\s+', ' ', text)    # espaces multiples