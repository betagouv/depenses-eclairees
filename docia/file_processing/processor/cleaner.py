import hashlib
import logging
import os
import re

from django.core.files.storage import default_storage
from django.utils import timezone

from docia.file_processing.sync.files_utils import get_corrected_extension

logger = logging.getLogger(__name__)


def get_file_initial_info(filename, directory_path: str) -> dict:
    """
    Analyse un fichier et crée un dictionnaire avec les informations sur le fichier.

    Args:
        filename (str): Nom du fichier à analyser
        directory_path (str): Chemin vers le dossier contenant le fichier

    Returns:
        dict: Dictionnaire contenant les informations sur le fichier
    """
    file_path = os.path.join(directory_path, filename)

    # Calculer le hash et l'extension
    file_hash = get_file_hash(file_path)
    extension = get_corrected_extension(filename, file_path)

    return {
        "filename": filename,
        "num_EJ": extract_num_EJ(filename),
        "dossier": directory_path,
        "extension": extension,
        "date_creation": timezone.now().date(),
        "taille": default_storage.size(file_path),
        "hash": file_hash,
    }


def get_file_hash(file_path: str, use_local_fs: bool = False) -> str:
    """
    Calcule le hash SHA-256 d'un fichier.

    Args:
        file_path (str): Chemin vers le fichier

    Returns:
        str: Hash SHA-256 du fichier ou "ERROR" en cas d'erreur
    """
    _open = open if use_local_fs else default_storage.open
    hash_sha256 = hashlib.sha256()
    with _open(file_path, "rb") as f:
        # Lire le fichier par chunks pour optimiser la mémoire
        for chunk in iter(lambda: f.read(65536), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()


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
