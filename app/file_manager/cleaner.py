import logging
import os
import unicodedata
import zipfile
from pathlib import Path
import shutil
import re

import pandas as pd
import hashlib
from tqdm import tqdm
import magic

from django.core.files.storage import default_storage

from docia.file_processing.sync.files_utils import get_corrected_extension
from app.utils import getDate
from app.grist import post_new_data_to_grist, post_data_to_grist_multiple_keys
from app.grist import URL_TABLE_ATTACHMENTS, URL_TABLE_ENGAGEMENTS, URL_TABLE_BATCH, API_KEY_GRIST
from app.data.db import bulk_create_batches, bulk_create_engagements, bulk_create_attachments


logger = logging.getLogger("docia." + __name__)


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


def unzip_all_files(source_dir, target_dir=None):
    """
    Dézippe tous les fichiers ZIP dans le dossier source et les extrait
    dans le dossier cible (ou dans le même dossier si non spécifié).
    
    Args:
        source_dir (str): Chemin du dossier contenant les fichiers ZIP
        target_dir (str, optional): Chemin du dossier où extraire les fichiers

    Return:
        error_count (int): nombre d'erreurs dans le dezippage de fichiers
    """
    # Convertir en objets Path pour une manipulation plus facile
    source_path = Path(source_dir)
    
    # Si aucun dossier cible n'est spécifié, utiliser le dossier source
    if target_dir is None:
        target_path = source_path
    else:
        target_path = Path(target_dir)
        # Créer le dossier cible s'il n'existe pas
        target_path.mkdir(parents=True, exist_ok=True)
    
    # Compteurs pour le rapport
    zip_count = 0
    extracted_count = 0
    error_count = 0
    
    # Parcourir tous les fichiers du dossier source
    print(f"Recherche de fichiers ZIP dans {source_path}...")
    for file_path in source_path.glob('*.zip'):
        zip_count += 1
        try:
            print(f"Extraction de {file_path.name}...")
            
            # Créer un sous-dossier avec le nom du fichier ZIP (sans l'extension)
            extract_dir = target_path / file_path.stem
            extract_dir.mkdir(exist_ok=True)
            
            # Ouvrir et extraire le fichier ZIP
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            os.remove(file_path)

            extracted_count += 1
            print(f"  → Extrait et supprimé avec succès dans {extract_dir}")
        
        except zipfile.BadZipFile:
            print(f"  → ERREUR: {file_path.name} n'est pas un fichier ZIP valide")
            error_count += 1
        except Exception as e:
            print(f"  → ERREUR lors de l'extraction de {file_path.name}: {str(e)}")
            error_count += 1
    
    # Afficher un résumé
    print("\nRésumé de l'opération:")
    print(f"  Fichiers ZIP trouvés: {zip_count}")
    print(f"  Fichiers extraits et supprimés avec succès: {extracted_count}")
    print(f"  Erreurs rencontrées: {error_count}")
    
    if zip_count == 0:
        print("\nAucun fichier ZIP trouvé dans le dossier spécifié.")

    return error_count


def flatten(root_dir):
    """
    Aplatit les dossiers du root qui commencent par num_EJ_compteur_.
    Récupère tous les fichiers dans ces dossiers et les fait remonter d'un cran
    en gardant le préfixe num_EJ_compteur_ suivi du nom du fichier.
    
    Args:
        root_dir (str): Chemin du dossier racine à aplatir
    """
    root_path = Path(root_dir).resolve()
    print(f"Aplatissement du dossier: {root_path}")
    
    # Pattern pour identifier les dossiers avec le format num_EJ_compteur_
    pattern = re.compile(r'^(\d{10}_\d+_)(.+)$')
    
    # Liste pour stocker les chemins de fichiers à déplacer
    files_to_move = []
    dirs_to_remove = set()
    
    # Parcourir tous les éléments du dossier racine
    for item in root_path.iterdir():
        if item.is_dir():
            # Vérifier si le dossier correspond au pattern num_EJ_compteur_
            match = pattern.match(item.name)
            if match:
                prefix = match.group(1)  # num_EJ_compteur_
                print(f"Traitement du dossier: {item.name}")
                
                # Parcourir récursivement tous les fichiers dans ce dossier
                for file_path in item.rglob('*'):
                    if file_path.is_file():
                        # Construire le nouveau nom avec le préfixe
                        new_filename = prefix + file_path.name
                        new_path = root_path / new_filename
                        
                        # En cas de conflit de nom, ajouter un numéro
                        counter = 1
                        original_new_filename = new_filename
                        while new_path.exists():
                            name_parts = original_new_filename.rsplit('.', 1)
                            if len(name_parts) > 1:
                                new_filename = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                            else:
                                new_filename = f"{original_new_filename}_{counter}"
                            new_path = root_path / new_filename
                            counter += 1
                        
                        files_to_move.append((file_path, new_path))
                
                # Ajouter le dossier à la liste des dossiers à supprimer
                dirs_to_remove.add(item)
    
    # Déplacer tous les fichiers
    moved_count = 0
    error_count = 0
    
    for old_path, new_path in files_to_move:
        try:
            print(f"Déplacement de {old_path.name} → {new_path.name}")
            shutil.move(old_path, new_path)
            moved_count += 1
        except Exception as e:
            print(f"ERREUR lors du déplacement de {old_path}: {str(e)}")
            error_count += 1
    
    # Supprimer tous les dossiers traités
    removed_dirs = 0
    for dir_path in sorted(dirs_to_remove, key=lambda x: len(str(x)), reverse=True):
        try:
            shutil.rmtree(dir_path)
            removed_dirs += 1
            print(f"Dossier supprimé: {dir_path.name}")
        except Exception as e:
            print(f"ERREUR lors de la suppression du dossier {dir_path}: {str(e)}")
    
    # Afficher un résumé
    print("\nRésumé de l'opération:")
    print(f"  Fichiers déplacés: {moved_count}")
    print(f"  Erreurs de déplacement: {error_count}")
    print(f"  Dossiers supprimés: {removed_dirs}")


def remove_counter_from_filenames(root_dir):
    """
    Parcourt tous les fichiers du root et supprime le compteur du nom de fichier.
    Transforme 'num_EJ_compteur_filename' en 'num_EJ_filename'.
    
    Args:
        root_dir (str): Chemin du dossier racine à traiter
    """
    root_path = Path(root_dir).resolve()
    print(f"Suppression des compteurs dans les noms de fichiers: {root_path}")
    
    # Pattern pour identifier les fichiers avec le format num_EJ_compteur_filename
    pattern = re.compile(r'^(\d{10})_\d+_(.+)$')
    
    # Liste pour stocker les chemins de fichiers à renommer
    files_to_rename = []
    
    # Parcourir tous les fichiers du dossier racine
    for item in root_path.iterdir():
        if item.is_file():
            # Vérifier si le fichier correspond au pattern num_EJ_compteur_filename
            match = pattern.match(item.name)
            if match:
                num_EJ = match.group(1)  # num_EJ
                filename = match.group(2)  # filename
                new_name = f"{num_EJ}_{filename}"
                new_path = root_path / new_name
                
                files_to_rename.append((item, new_path))
    
    # Renommer tous les fichiers
    renamed_count = 0
    error_count = 0
    
    for old_path, new_path in files_to_rename:
        try:
            # En cas de conflit de nom, ajouter un numéro
            counter = 1
            original_new_path = new_path
            while new_path.exists():
                name_parts = original_new_path.stem, original_new_path.suffix
                new_name = f"{name_parts[0]}_{counter}{name_parts[1]}"
                new_path = root_path / new_name
                counter += 1
            
            print(f"Renommage de {old_path.name} → {new_path.name}")
            shutil.move(old_path, new_path)
            renamed_count += 1
        except Exception as e:
            print(f"ERREUR lors du renommage de {old_path}: {str(e)}")
            error_count += 1
    
    # Afficher un résumé
    print("\nRésumé de l'opération:")
    print(f"  Fichiers renommés: {renamed_count}")
    print(f"  Erreurs de renommage: {error_count}")


def flatten_deep_directory(root_dir):
    """
    Cette fonction aplatit récursivement l'arborescence d'un dossier en alternant dézippage et déplacement des fichiers.
    Elle effectue les opérations suivantes :
      1. Tant qu'il reste des fichiers zip dans le dossier racine, elle :
         - Dézippe tous les fichiers zip présents à la racine (et éventuellement dans les sous-dossiers).
         - Déplace tous les fichiers extraits ou présents dans les sous-dossiers vers le dossier racine,
           en préfixant leur nom avec le chemin relatif de leur dossier parent pour éviter les collisions de noms.
      2. Après avoir extrait et déplacé tous les fichiers, elle supprime les compteurs dans les noms de fichiers
         (ex : "1234567890_1_monfichier.pdf" devient "1234567890_monfichier.pdf").
      3. Enfin, elle supprime tous les sous-dossiers vides.

    Args:
        root_dir (str): Chemin du dossier racine à aplatir.
    """

    nb_op = 1  # Compteur d'opérations (itérations)
    # Compte le nombre de fichiers zip à la racine
    nb_zip_to_unzip = sum(1 for f in os.listdir(root_dir) if f.endswith(".zip"))

    # Boucle principale : tant qu'il reste des fichiers zip à traiter
    while nb_zip_to_unzip > 0:
        print(f"\n\nDézippage et déplacement des fichiers dans le dossier principal (opération n° {nb_op})")
        # Dézippe tous les fichiers zip présents à la racine
        error_zip = unzip_all_files(root_dir)
        # Déplace tous les fichiers des sous-dossiers vers la racine, en préfixant leur nom
        flatten(root_dir)
        # Recompte les fichiers zip restants, en tenant compte des erreurs de dézippage
        nb_zip_to_unzip = sum(1 for f in os.listdir(root_dir) if f.endswith(".zip")) - error_zip
        nb_op += 1

    # Nettoie les noms de fichiers en supprimant les compteurs éventuels
    remove_counter_from_filenames(root_dir)


def remove_empty_files(directory_path: str) -> list:
    """
    Supprime les fichiers vides (taille 0 octets) dans le répertoire spécifié.
    
    Args:
        directory_path (str): Chemin du répertoire à analyser
    
    Returns:
        list: Liste des fichiers supprimés
    """
    if not os.path.isdir(directory_path):
        print(f"Erreur: '{directory_path}' n'est pas un dossier valide.")
        return []
    
    print(f"Recherche des fichiers vides dans le dossier: {directory_path}")
    
    deleted_files = []
    error_count = 0
    
    # Parcourir tous les fichiers du répertoire
    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)
        
        # Ignorer les dossiers
        if not os.path.isfile(file_path):
            continue
        
        try:
            # Vérifier si le fichier est vide (taille 0)
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                # Supprimer le fichier vide
                os.remove(file_path)
                deleted_files.append(filename)
                print(f"Fichier vide supprimé: {filename}")
        except OSError as e:
            print(f"Erreur lors de la suppression de {filename}: {e}")
            error_count += 1
    
    # Afficher un résumé
    print(f"\nRésumé: {len(deleted_files)} fichiers vides supprimés.")
    if error_count > 0:
        print(f"Erreurs rencontrées: {error_count}")
    
    return deleted_files


def get_file_hash(file_path: str) -> str:
    """
    Calcule le hash SHA-256 d'un fichier.
    
    Args:
        file_path (str): Chemin vers le fichier
        
    Returns:
        str: Hash SHA-256 du fichier ou "ERROR" en cas d'erreur
    """
    try:
        hash_sha256 = hashlib.sha256()
        with default_storage.open(file_path, "rb") as f:
            # Lire le fichier par chunks pour optimiser la mémoire
            for chunk in iter(lambda: f.read(65536), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        print(f"Erreur lors du calcul du hash pour {file_path}: {e}")
        return "ERROR"



def remove_duplicate(directory_path: str) -> list:
    """
    Supprime les fichiers en doublon basés sur leur hash SHA-256.
    Un document en double est un document ayant le même hash qu'un autre document.
    Ne supprime les doublons que s'ils ont le même numéro EJ (même préfixe).
    Dans ce cas, garde le fichier avec le premier nom (ordre alphabétique) et supprime les autres.
    
    Args:
        directory_path (str): Chemin du répertoire à analyser
    
    Returns:
        list: Liste des fichiers supprimés
    """
    if not os.path.isdir(directory_path):
        print(f"Erreur: '{directory_path}' n'est pas un dossier valide.")
        return []
    
    print(f"Recherche des doublons dans le dossier: {directory_path}")
    
    # Première étape : identification des fichiers à supprimer
    hash_to_files = {}
    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)
        if not os.path.isfile(file_path):
            continue
        file_hash = get_file_hash(file_path)
        if file_hash == "ERROR":
            print(f"Impossible de calculer le hash pour {filename}, ignoré.")
            continue
        if file_hash not in hash_to_files:
            hash_to_files[file_hash] = []
        hash_to_files[file_hash].append(filename)
    
    fichiers_a_supprimer = []
    for file_hash, filenames in hash_to_files.items():
        if len(filenames) > 1:
            # Grouper les fichiers par numéro EJ
            ej_groups = {}
            for filename in filenames:
                num_ej = extract_num_EJ(filename)
                if num_ej not in ej_groups:
                    ej_groups[num_ej] = []
                ej_groups[num_ej].append(filename)
            
            # Pour chaque groupe EJ, supprimer les doublons
            for num_ej, ej_filenames in ej_groups.items():
                if len(ej_filenames) > 1:
                    # Trier les fichiers par ordre alphabétique
                    ej_filenames_sorted = sorted(ej_filenames)
                    # Garder le premier, marquer les autres pour suppression
                    for filename_to_delete in ej_filenames_sorted[1:]:
                        fichiers_a_supprimer.append({
                            'filename': filename_to_delete,
                            'kept_file': ej_filenames_sorted[0],
                            'num_ej': num_ej
                        })
    
    # Deuxième étape : suppression des fichiers identifiés
    deleted_files = []
    for file_info in fichiers_a_supprimer:
        filename = file_info['filename']
        kept_file = file_info['kept_file']
        num_ej = file_info['num_ej']
        
        file_path = os.path.join(directory_path, filename)
        try:
            os.remove(file_path)
            deleted_files.append(filename)
            print(f"Doublon supprimé: {filename} (EJ: {num_ej}, conservé: {kept_file})")
        except OSError as e:
            print(f"Erreur lors de la suppression de {filename}: {e}")
    
    print(f"\nRésumé: {len(deleted_files)} fichiers dupliqués supprimés.")
    return deleted_files


# Magic bytes pour les formats de fichiers courants
MAGIC_BYTES: dict[bytes, str] = {
    b'\x25\x50\x44\x46': 'pdf',  # %PDF
    b'\x50\x4B\x03\x04': 'zip',  # ZIP (aussi docx, xlsx, pptx, odt, ods, odp)
    b'\x50\x4B\x05\x06': 'zip',  # ZIP (fichier vide)
    b'\x50\x4B\x07\x08': 'zip',  # ZIP (spanned)
    b'\xFF\xD8\xFF': 'jpg',      # JPEG
    b'\x89\x50\x4E\x47': 'png',  # PNG
    b'\x47\x49\x46\x38': 'gif',  # GIF
    b'\x42\x4D': 'bmp',          # BMP
    b'\xD0\xCF\x11\xE0': 'ole2',  # OLE2/Compound Document (DOC, XLS, PPT, etc.)
    b'\x00\x00\x01\x00': 'ico',  # ICO
    b'\x52\x49\x46\x46': 'avi',  # AVI
    b'\x4F\x67\x67\x53': 'ogg',  # OGG
    b'\x49\x44\x33': 'mp3',      # MP3
    b'\xFF\xFB': 'mp3',          # MP3 (autre signature)
    b'\x52\x61\x72\x21': 'rar',  # RAR
    b'\x37\x7A\xBC\xAF': '7z',   # 7-Zip
    b'\x1F\x8B\x08': 'gz',       # GZIP
    b'\x42\x5A\x68': 'bz2',      # BZIP2
}

# Patterns pour les formats ZIP-based (par ordre de priorité)
ZIP_BASED_FORMATS = [
    # Microsoft Office formats (priorité haute) - patterns spécifiques
    ('word/document.xml', 'docx'),
    ('xl/workbook.xml', 'xlsx'),
    ('ppt/presentation.xml', 'pptx'),
]

def detect_ole2_by_streams(file_path: str) -> str:
    """
    Détecte le type OLE2 en analysant les noms des streams
    """
    try:
        # Vérifier d'abord l'extension du nom de fichier pour les formats OLE2 connus
        filename = os.path.basename(file_path).lower()
        if filename.endswith('.msg'):
            # Vérifier si c'est un PDF dans un MSG
            with default_storage.open(file_path, 'rb') as f:
                content = f.read(1000)  # Lire seulement les premiers octets
                if b'%PDF' in content:
                    return 'pdf'
                else:
                    return 'msg'
        elif filename.endswith('.xls'):
            return 'xls'
        elif filename.endswith('.doc'):
            return 'doc'
        elif filename.endswith('.ppt'):
            return 'ppt'
        elif filename.endswith('.db') or 'thumbs.db' in filename:
            return 'db'
        
        with default_storage.open(file_path, 'rb') as f:
            # Lire tout le fichier et chercher des patterns caractéristiques
            content = f.read()
            
            # Patterns spécifiques pour Excel (plus précis et avec poids)
            excel_patterns = [
                (b'Workbook', 10),  # Très spécifique à Excel
                (b'Book', 5),
                (b'Excel', 8),
                (b'Worksheet', 10),
                (b'xl/', 5),
                (b'xl/workbook', 15),
                (b'Microsoft Excel', 12),
                (b'BIFF', 8),  # Binary Interchange File Format d'Excel
                (b'BOUNDSHEET', 15),  # Feuille de calcul Excel
                (b'EXTERNBOOK', 10),  # Référence externe Excel
                (b'FONT', 3),  # Police Excel
                (b'FORMAT', 3),  # Format Excel
                (b'LABEL', 5),  # Étiquette Excel
                (b'NUMBER', 3),  # Nombre Excel
                (b'STRING', 3),  # Chaîne Excel
                (b'XLS', 5),  # Extension Excel
                (b'Sheet', 8),  # Feuille Excel
                (b'Cell', 5),  # Cellule Excel
                (b'Row', 3),  # Ligne Excel
                (b'Column', 3),  # Colonne Excel
            ]
            
            # Patterns spécifiques pour MSG (fichiers Outlook) - à exclure
            msg_patterns = [
                (b'Message', 10),
                (b'Outlook', 8),
                (b'MSG', 5),
                (b'Mail', 5),
                (b'Email', 5),
                (b'Attachment', 3),
                (b'Recipient', 3),
                (b'Sender', 3),
                (b'Subject', 3),
            ]
            
            # Patterns spécifiques pour Word (plus précis et avec poids)
            word_patterns = [
                (b'WordDocument', 15),  # Très spécifique à Word
                (b'Document', 5),
                (b'Microsoft Word', 12),
                (b'word/', 5),
                (b'word/document', 15),
                (b'DOC', 5),  # Extension Word
                (b'FIB', 10),  # File Information Block de Word
                (b'Table', 3),  # Table Word
                (b'1Table', 8),  # Table Word
                (b'0Table', 8),  # Table Word
                (b'Paragraph', 5),  # Paragraphe Word
                (b'Character', 3),  # Caractère Word
                (b'Section', 3),  # Section Word
            ]
            
            # Patterns spécifiques pour PowerPoint (avec poids)
            ppt_patterns = [
                (b'PowerPoint', 12),
                (b'Presentation', 10),
                (b'ppt/', 5),
                (b'ppt/presentation', 15),
                (b'PPT', 5),  # Extension PowerPoint
                (b'Current User', 3),  # Utilisateur PowerPoint
                (b'Pictures', 3),  # Images PowerPoint
                (b'Slide', 8),  # Diapositive PowerPoint
            ]
            
            # Compter les occurrences de chaque pattern avec poids
            excel_score = sum(content.count(pattern) * weight for pattern, weight in excel_patterns)
            word_score = sum(content.count(pattern) * weight for pattern, weight in word_patterns)
            ppt_score = sum(content.count(pattern) * weight for pattern, weight in ppt_patterns)
            msg_score = sum(content.count(pattern) * weight for pattern, weight in msg_patterns)
            
            # Si c'est un fichier MSG, ne pas le traiter comme Excel
            if msg_score > 5:  # Seuil pour identifier un fichier MSG
                # Vérifier si c'est un PDF dans un MSG
                if b'%PDF' in content:
                    return 'pdf'
                else:
                    return 'msg'
            
            # Retourner le type avec le score le plus élevé
            if excel_score > word_score and excel_score > ppt_score:
                return 'xls'
            elif word_score > ppt_score:
                return 'doc'
            elif ppt_score > 0:
                return 'ppt'
            else:
                # Si aucun pattern n'est trouvé, essayer de deviner par l'extension du nom
                filename = os.path.basename(file_path).lower()
                if filename.endswith('.xls'):
                    return 'xls'
                elif filename.endswith('.doc'):
                    return 'doc'
                elif filename.endswith('.ppt'):
                    return 'ppt'
                else:
                    # Par défaut, considérer comme DOC si on ne peut pas déterminer
                    return 'doc'
                
    except Exception as e:
        print(f"Erreur dans detect_ole2_by_streams: {e}")
        return 'doc'  # Fallback par défaut

def detect_ole2_format(file_path: str) -> str:
    """
    Détecte le format spécifique pour les fichiers OLE2/Compound Document (DOC, XLS, PPT, etc.)
    
    Args:
        file_path (str): Chemin vers le fichier
        
    Returns:
        str: Extension détectée
    """
    # Utiliser directement la méthode par analyse du contenu qui est plus robuste
    return detect_ole2_by_streams(file_path)


def detect_zip_based_format(file_path: str) -> str:
    """
    Détecte le format spécifique pour les fichiers ZIP-based (docx, xlsx, pptx, odt, etc.)
    
    Args:
        file_path (str): Chemin vers le fichier
        
    Returns:
        str: Extension détectée
    """
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_file:
            file_list = zip_file.namelist()
            
            # 1. Vérifier d'abord les formats Microsoft Office (patterns spécifiques)
            for pattern, ext in ZIP_BASED_FORMATS:
                if any(pattern in f for f in file_list):
                    return ext
            
            # 2. Vérification spéciale pour les formats OpenDocument via mimetype
            try:
                if 'mimetype' in file_list:
                    mimetype_content = zip_file.read('mimetype').decode('utf-8').strip()
                    if 'application/vnd.oasis.opendocument.text' in mimetype_content:
                        return 'odt'
                    elif 'application/vnd.oasis.opendocument.spreadsheet' in mimetype_content:
                        return 'ods'
                    elif 'application/vnd.oasis.opendocument.presentation' in mimetype_content:
                        return 'odp'
            except:
                pass
            
            # 3. Fallback: vérifier les patterns OpenDocument génériques
            # (seulement si aucun format Microsoft n'a été trouvé)
            if any('META-INF/manifest.xml' in f for f in file_list):
                # C'est probablement un OpenDocument, mais on ne peut pas distinguer le type
                # sans le mimetype, donc on retourne 'odt' par défaut
                return 'odt'
                    
        return 'zip'
    except (zipfile.BadZipFile, Exception):
        return 'zip'

def detect_file_type_by_magic_bytes(file_path: str) -> str:
    """
    Détecte le type de fichier par magic bytes
    
    Args:
        file_path (str): Chemin vers le fichier
        
    Returns:
        str: Extension détectée ou 'unknown'
    """
    with default_storage.open(file_path, 'rb') as f:
        # Lire les premiers 16 octets
        header = f.read(16)

        # Vérifier les magic bytes
        for magic, ext in MAGIC_BYTES.items():
            if header.startswith(magic):
                # Vérifications spéciales pour les formats ZIP-based
                if ext == 'zip':
                    return detect_zip_based_format(file_path)
                # Vérifications spéciales pour les formats OLE2
                elif ext == 'ole2':
                    return detect_ole2_format(file_path)
                return ext

        return "unknown"


def detect_file_extension_from_content_old(file_path: str) -> str:
    """
    Détecte l'extension d'un fichier à partir de son contenu brut
    
    Args:
        file_path (str): Chemin vers le fichier
        
    Returns:
        str: Extension détectée (sans le point)
    """

    with default_storage.open(file_path, "rb") as f:
        mime = magic.from_buffer(f.read(1024), mime=True)

    mime_to_ext = {
        'application/pdf': 'pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
        'application/vnd.oasis.opendocument.text': 'odt',
        'application/vnd.oasis.opendocument.spreadsheet': 'ods',
        'application/vnd.oasis.opendocument.presentation': 'odp',
        'image/jpeg': 'jpg',
        'image/png': 'png',
        'image/gif': 'gif',
        'image/bmp': 'bmp',
        'text/plain': 'txt',
        'application/zip': 'zip',
        'application/x-rar-compressed': 'rar',
        'application/x-7z-compressed': '7z',
        'application/gzip': 'gz',
        'application/x-bzip2': 'bz2',
    }
    detected_ext = mime_to_ext.get(mime, 'unknown')
    if detected_ext != "unknown":
        return detected_ext
    
    # Fallback sur les magic bytes
    return detect_file_type_by_magic_bytes(file_path)



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
        'filename': filename,
        'num_EJ': extract_num_EJ(filename),
        'dossier': directory_path,
        'extension': extension,
        'date_creation': getDate(),
        'taille': default_storage.size(file_path),
        'hash': file_hash
    }

def get_files_initial_infos(directory_path: str, save_path = None, save_grist = False, batch_grist = "") -> pd.DataFrame:
    """
    Analyse un dossier et crée un DataFrame avec les informations sur les fichiers.
    
    Args:
        directory_path (str): Chemin vers le dossier à analyser
        
    Returns:
        pd.DataFrame: DataFrame contenant les informations sur les fichiers
    """
    files_data = []

    files = default_storage.listdir(directory_path)[1]
    for filename in tqdm(files, desc="Analyse des fichiers"):
        file_infos = get_file_initial_info(filename, directory_path)

        files_data.append(file_infos)
    
    dfFiles = pd.DataFrame(files_data).astype(str)

    if(save_path != None):
        dfFiles.to_excel(f'{save_path}/dfFichiers_{directory_path.split("/")[-1]}_{getDate()}.xlsx', index = False)
        print(f"Liste des fichiers sauvegardées dans {save_path}/dfFichiers_{directory_path.split("/")[-1]}_{getDate()}.xlsx")

    if(save_grist):
        if(batch_grist != "" and isinstance(batch_grist, str)):
            dfBatch = dfFiles[["num_EJ"]].drop_duplicates("num_EJ")
            dfBatch["Batch"] = batch_grist

            post_data_to_grist_multiple_keys(dfToSend=dfBatch,
                                            list_keys=["num_EJ", "Batch"],
                                            table_url=URL_TABLE_BATCH,
                                            api_key=API_KEY_GRIST,
                                            columns_to_send=[],
                                            batch_size=100)

        post_new_data_to_grist(dfFiles,
                               key_column="num_EJ",
                               table_url=URL_TABLE_ENGAGEMENTS,
                               api_key=API_KEY_GRIST,
                               columns_to_send=["num_EJ", "date_creation"])
        
        post_new_data_to_grist(dfFiles,
                               key_column="filename", 
                               table_url=URL_TABLE_ATTACHMENTS,
                               api_key=API_KEY_GRIST,
                               columns_to_send=["filename", "extension", "dossier", "date_creation", "taille", "hash"])
        
        # if(batch_name != None):
        #     dfFiles["Batch"] = batch_name
        #     dfToSend = dfFiles.drop_duplicates("num_EJ", inplace=True)
        #     post_new_data_to_grist(dfToSend,"Batch", URL_TABLE_BATCH, API_KEY_GRIST, columns_to_send=["num_EJ", "Batch"])

    return dfFiles.sort_values(by=["filename","extension","hash"])


def save_files_initial_infos_result(df: pd.DataFrame, batch: str):
    if not batch:
        raise ValueError(f"Batch cannot be empty (got: {batch!r})")

    bulk_create_engagements(df)
    bulk_create_attachments(df)

    dfBatch = df[["num_EJ"]].drop_duplicates("num_EJ")
    dfBatch["Batch"] = batch
    bulk_create_batches(df=dfBatch)


def get_files_chorus_infos(dfFiles: pd.DataFrame, df_ground_truth: pd.DataFrame, directory_path: str, save_path = None) -> pd.DataFrame:
    df_ground_truth[["Marché"]] = df_ground_truth[["Marché"]].astype(str)
    df_ground_truth[["n° EJ"]] = df_ground_truth[["n° EJ"]].astype(str)
    dfFiles = dfFiles.astype(str)

    # Récupération des informaitions pour les fichiers rattachés à un achat (n° EJ)
    dfFilesFromAchats = pd.merge( 
        dfFiles,
        df_ground_truth,
        left_on='num_EJ',
        right_on='n° EJ', 
        how='inner',
        suffixes=('_PJ', '_Chorus')
    )

    # Récupération des informations pour les fichiers rattachés à un marché (Marché, et n° Marché différent de l'EJ)
    dfFilesFromMarches = pd.merge( 
            dfFiles,
            df_ground_truth.query("Marché != `n° EJ` and Marché != '#' and Marché.notna()")[["Marché"]].drop_duplicates(),
            left_on='num_EJ',
            right_on='Marché', 
            how='inner',
            suffixes=('_PJ', '_Chorus')
        )

    dfFilesUnknown = dfFiles.query("num_EJ not in @df_ground_truth['n° EJ'].values and num_EJ not in @df_ground_truth['Marché'].values")

    dfFilesFromAchats.insert(3,"Type EJ", "Achat")
    dfFilesFromMarches.insert(3,"Type EJ", "Marché")
    dfFilesUnknown.insert(3,"Type EJ", "Inconnu")

    dfResult = pd.concat([dfFilesFromAchats, dfFilesFromMarches, dfFilesUnknown], ignore_index=True)

    try:
        if(save_path != None):
            dfResult.to_excel(f'{save_path}/dfFichiersInfosChorus_{directory_path.split("/")[-1]}_{getDate()}.xlsx', index = False)
            print(f"Liste des fichiers sauvegardées dans {save_path}/dfFichiersInfosChorus_{directory_path.split("/")[-1]}_{getDate()}.xlsx")
    except Exception as e:
        print(f"Erreur lors de la sauvegarde du fichier : {e}")

    return dfResult


def clean_filenames_unicode(dirpath: str):
    paths = [p for p in os.listdir(dirpath)]
    path_join = os.path.join
    rename = os.rename
    files = [p for p in paths if os.path.isfile(path_join(dirpath, p))]
    directories = [p for p in paths if os.path.isdir(path_join(dirpath, p))]

    renamed_files = []

    for f in files:
        file_path = path_join(dirpath, f)
        file_path_nfc = unicodedata.normalize("NFC", file_path)
        if file_path != file_path_nfc:
            rename(file_path, file_path_nfc)
            renamed_files.append((file_path, file_path_nfc))

    for d in directories:
        dir_path = path_join(dirpath, d)
        r = clean_filenames_unicode(dir_path)
        renamed_files.extend(r)

    return renamed_files
