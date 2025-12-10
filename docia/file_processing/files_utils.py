import logging
import mimetypes
import os

from django.core.files.storage import default_storage

import magic
import olefile

logger = logging.getLogger(__name__)


def detect_file_extension_from_content(file_path: str) -> str:
    with default_storage.open(file_path, "rb") as f:
        header = f.read(1024)
        mime = magic.from_buffer(header, mime=True)
        if mime == "application/octet-stream":
            header += f.read(4096)
            mime = magic.from_buffer(header, mime=True)

    # Handle ole files (old Microsoft Office formats)
    if mime == "application/x-ole-storage":
        ext = guess_office_type(file_path)
    else:
        ext = mimetypes.guess_extension(mime, strict=False)

    # Replace .bin with .unknown extension
    if ext == ".bin":
        ext = ".unknown"

    if ext:
        return ext.strip(".")
    else:
        logger.warning("Could not guess extension for mime %r (file=%s)", mime, file_path)
        return "unknown"


def guess_office_type(file_path: str) -> str:
    with default_storage.open(file_path, "rb") as f:
        ole = olefile.OleFileIO(f)
        names = {".".join(e) for e in ole.listdir()}

    if "WordDocument" in names:
        return "doc"
    if "Workbook" in names or "Book" in names:
        return "xls"
    if "PowerPoint Document" in names:
        return "ppt"
    if "__properties_version1.0" in names or any(n.startswith("__substg1.0_") for n in names):
        return "msg"

    return "unknown"


def get_corrected_extension(filename: str, file_path: str) -> str:
    """
    Obtient l'extension correcte d'un fichier en comparant l'extension du nom
    avec l'extension détectée par le contenu

    Args:
        filename (str): Nom du fichier
        file_path (str): Chemin complet vers le fichier

    Returns:
        str: Extension correcte (sans le point)
    """
    # Extension du nom de fichier
    name_ext = os.path.splitext(filename)[1].strip(".").lower()

    # Extension détectée par le contenu
    content_ext = detect_file_extension_from_content(file_path)

    # Si les deux correspondent, retourner l'extension
    if name_ext == content_ext:
        return name_ext

    # Si l'extension du nom est vide ou inconnue, utiliser celle du contenu
    if not name_ext or name_ext == "":
        return content_ext

    # Si l'extension du contenu est inconnue, utiliser celle du nom
    if content_ext == "unknown":
        return name_ext

    # Si les deux sont différentes, prioriser celle du contenu
    logger.info(
        "Extension mismatch %(filename)s: %(name_ext)r vs %(content_ext)r -> use %(content_ext)r",
        dict(
            filename=filename,
            name_ext=name_ext,
            content_ext=content_ext,
        ),
    )

    return content_ext
