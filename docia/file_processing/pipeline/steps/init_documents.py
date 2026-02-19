import logging
import os

from django.core.files.storage import default_storage
from django.db.transaction import atomic

from celery import group, shared_task

from app.file_manager import cleaner as processor
from app.file_manager import extract_num_EJ
from docia.file_processing.models import FileInfo
from docia.models import DataBatch, DataEngagement, Document

logger = logging.getLogger(__name__)


def listdir_chunk(folder, chunk_number: int = 0, chunk_size: int | None = None) -> list[str]:
    all_files = default_storage.listdir(folder)[1]
    all_files = sorted(all_files)
    if chunk_size is None:
        chunk_size = len(all_files)
    offset = chunk_number * chunk_size
    limit = offset + chunk_size
    filenames = all_files[offset:limit]
    return filenames


def get_files_info(folder: str, chunk_number: int = 0, chunk_size: int | None = None) -> list[FileInfo]:
    filenames = listdir_chunk(folder, chunk_number, chunk_size)
    file_paths = [os.path.join(folder, filename) for filename in filenames]
    files_info = []

    existing_info_by_path = dict((info.file.name, info) for info in FileInfo.objects.filter(file__in=file_paths))
    to_create = []

    for filename in filenames:
        file_path = os.path.join(folder, filename)
        if file_path in existing_info_by_path:
            logger.info(f"Get file infos {file_path} (existing)")
            file_info = existing_info_by_path[file_path]
        else:
            logger.info(f"Get file infos {file_path}")
            info = processor.get_file_initial_info(filename, folder)
            # Rename some fields
            info = dict(**info)
            info["folder"] = info.pop("dossier")
            info["size"] = info.pop("taille")
            info["created_date"] = info.pop("date_creation")
            file_info = FileInfo(**info)
            file_info.file = os.path.join(folder, filename)
            to_create.append(file_info)
        files_info.append(file_info)

    # Save
    FileInfo.objects.bulk_create([info for info in to_create], batch_size=200, ignore_conflicts=True)

    return files_info


def bulk_create_engagements(num_ejs):
    engagements = [
        DataEngagement(
            num_ej=num_ej,
        )
        for num_ej in num_ejs
    ]
    DataEngagement.objects.bulk_create(engagements, batch_size=200, ignore_conflicts=True)


def bulk_create_documents(file_infos: list[FileInfo]):
    file_infos = remove_duplicates(file_infos)
    # Filters out duplicate files
    attachments = [
        Document(
            filename=row.filename,
            extension=row.extension,
            dossier=row.folder,
            taille=row.size,
            hash=row.hash,
            file=row.file,
        )
        for row in file_infos
    ]
    Document.objects.bulk_create(attachments, batch_size=200, ignore_conflicts=True)


def bulk_create_links_document_engagement_using_filenames(files_info: list[FileInfo]):
    """Create Links between documents and engagements"""

    # Use through model for efficient bulk creation of M2M relationships
    DocumentEngagement = Document.engagements.through
    # Get doc id by hash
    hashes = [fi.hash for fi in files_info]
    doc_id_by_hash = dict(Document.objects.filter(hash__in=hashes).values_list("hash", "id"))
    # Get engagements by num_ej
    num_ejs = set(extract_num_EJ(file_info.filename) for file_info in files_info)
    engagements_by_num_ej = dict(DataEngagement.objects.filter(num_ej__in=num_ejs).values_list("num_ej", "id"))

    # Build the links
    links_doc_engagement = [
        DocumentEngagement(
            document_id=doc_id_by_hash[fi.hash],
            dataengagement_id=engagements_by_num_ej[extract_num_EJ(fi.filename)],
        )
        for fi in files_info
    ]

    # Insert in database
    DocumentEngagement.objects.bulk_create(links_doc_engagement, batch_size=200, ignore_conflicts=True)


def bulk_create_batches(num_ejs, batch):
    batches = [
        DataBatch(
            batch=batch,
            ej_id=num_ej,
        )
        for num_ej in num_ejs
    ]
    DataBatch.objects.bulk_create(batches, batch_size=200, ignore_conflicts=True)


def remove_duplicates(file_infos: list[FileInfo]):
    # First deduplicate from the list
    # Sort to put shortest paths first
    file_infos = sorted(file_infos, key=lambda info: (len(info.file.name.split("/")), info.filename))
    # Group them by hash
    items_by_hash = {}
    for info in file_infos:
        items_by_hash.setdefault(info.hash, []).append(info)

    # Secondly deduplicate from database
    existing_hashes = set(
        Document.objects.filter(hash__in=[info.hash for info in file_infos]).values_list("hash", flat=True)
    )
    to_insert = []
    for hash, infos in items_by_hash.items():
        if hash not in existing_hashes:
            to_insert.append(infos[0])

    return to_insert


def init_documents_in_folder(folder: str, batch: str, on_success=None):
    """Init documents using data from files imported using s3 folder."""
    all_files = default_storage.listdir(folder)[1]
    files_count = len(all_files)
    if files_count < 200:
        chunk_size = 10
    else:
        chunk_size = 100
    group_task = group(
        [
            task_chunk_init_documents.s(batch, folder, chunk_number=i, chunk_size=chunk_size)
            for i in range(files_count // chunk_size + 1)
        ],
    )
    if on_success:
        r = (group_task | on_success)()
        gr = r.parent
    else:
        gr = group_task()
    gr.save()
    return gr


@shared_task
def task_chunk_init_documents(batch: str, folder: str, *, chunk_number: int = 0, chunk_size: int | None = None):
    files_info = get_files_info(folder, chunk_number, chunk_size)
    num_ejs = sorted(set(extract_num_EJ(info.filename) for info in files_info))
    with atomic():
        bulk_create_engagements(num_ejs)
        bulk_create_batches(num_ejs, batch)
        bulk_create_documents(files_info)
        bulk_create_links_document_engagement_using_filenames(files_info)
