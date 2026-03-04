import hashlib
import io
import logging
import os
import posixpath
import re
import zipfile

from django.core.files.storage import default_storage
from django.utils import timezone

from unidecode import unidecode

from docia.file_processing.models import FileInfo
from docia.file_processing.sync.client import SyncClient
from docia.file_processing.sync.files_utils import get_corrected_extension

logger = logging.getLogger(__name__)


class DocumentDownloader:
    def __init__(self):
        self.client = SyncClient.from_settings()

    def download_document(self, external_id: str, name: str):
        """Download a document from the API and store it in S3 + database (metadata)."""

        assert not name.startswith("."), f"File name invalid {name!r}"

        if not self.client.is_authenticated:
            self.client.authenticate()

        # Check if download has already been done
        if FileInfo.objects.filter(external_id=external_id).exists():
            logger.info("Skip file %s / %s: Already exists", external_id, name)
            return

        # Download the document
        file_content = self.client.download_document(external_id)

        self._store_file(external_id, name, file_content=file_content, folder=f"docs/{external_id}")

    def _compute_hash(self, file_content: bytes):
        hash_sha256 = hashlib.sha256()
        hash_sha256.update(file_content)
        hash_hex = hash_sha256.hexdigest()
        return hash_hex

    def _store_file(
        self,
        external_id: str | None,
        name: str,
        file_content: bytes,
        folder: str,
        db_save: bool = True,
        parent: FileInfo | None = None,
    ):
        """Store the file in s3, if it's a zip, unzip and store sub files aswell.

        The function will first store the file on s3, then if it's a zip, unzip it and store the sub files,
        and finally store the metadata (external_id, s3 path, hash, ...) in the database.

        This process ensures that a file in the database has an existing file in s3, but not the opposite.
        Errors during processing can lead to files in s3 without a row in the database.
        """

        # Store original name
        original_filename = name

        name = self.clean_filename(name)

        if name.endswith(".zip"):
            extension = "zip"
            filename = name
        else:
            extension = get_corrected_extension(name, file_content)
            # If extension mismatch, correct file extension
            if name.lower().endswith(extension):
                filename = name
            else:
                filename = name + "." + extension

        filepath = f"{folder}/{filename}"
        with default_storage.open(filepath, "wb") as f:
            f.write(file_content)

        hash = self._compute_hash(file_content)

        size = len(file_content)

        file_info = FileInfo(
            external_id=external_id,
            parent=parent,
            file=filepath,
            filename=filename,
            folder=folder,
            extension=extension,
            size=size,
            hash=hash,
            created_date=timezone.now().date(),
            original_filename=original_filename,
        )

        # Unzip files recursively and store them with the original_name as prefix
        if extension == "zip":
            sub_files_info = self._store_sub_zip_file(f"{folder}/{filename}_", file_content, parent=file_info)
        else:
            sub_files_info = []

        files_info = [file_info, *sub_files_info]
        if db_save:
            FileInfo.objects.bulk_create(files_info, batch_size=100)

        return files_info

    def _store_sub_zip_file(self, folder: str, file_content: bytes, parent: FileInfo):
        """
        Extract the files inside a zip and store them, works reccursively in case of nested zips.

        File/folder structure is preserved.

        Exemple:
        archive.zip with hello1.txt and sub/hello2.txt inside :
        + archive.zip
        + archive.zip_/hello1.txt
        + archive.zip_/sub/hello2.txt
        """

        files_info = []
        # Extract and store each file from the zip archive
        try:
            with zipfile.ZipFile(io.BytesIO(file_content), "r") as zip_ref:
                for zip_info in zip_ref.infolist():
                    if not zip_info.is_dir():  # Skip directories
                        # Get the file content from the zip
                        file_content = zip_ref.read(zip_info.filename)

                        subfolder, filename = posixpath.split(zip_info.filename)
                        filename = self.clean_filename(filename)
                        filefolder = posixpath.join(folder, subfolder).rstrip("/")

                        # Store the inner file
                        sub_files_info = self._store_file(
                            external_id=None,
                            name=filename,
                            folder=filefolder,
                            file_content=file_content,
                            db_save=False,
                            parent=parent,
                        )
                        files_info.extend(sub_files_info)

        except zipfile.BadZipFile as ex:
            logger.error("File is not a valid zip file: %s", ex)
            raise

        return files_info

    def clean_filename(self, filename):
        """
        AWS only support ISO-8859-1 (latin-1) in headers.
        Windows only support 255 filename length.

        We use unidecode to transform everything to ascii characters.
        Unidecode the whole string would remove accents, but we can keep accents since they
        are compatible with latin-1.
        To keep accents, we iterate over the string character by character, keeping accents
        and using unidecode on the rest.
        Also lower string the extension.
        """
        filename = re.sub(r"[/\\]", "_", filename)
        filename, ext = os.path.splitext(filename)
        ext = ext.lower()

        clean = ""
        for char in filename:
            if char in "éèêà":
                clean += char
            else:
                clean += unidecode(char)
        # Truncate exceeding characters
        max_filename_len = 250 - len(ext)
        if len(clean) > max_filename_len:
            trunc_str = "[trunc]"
            clean = clean[: max_filename_len - len(trunc_str)] + trunc_str
        # Return result
        return clean + ext
