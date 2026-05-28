import logging
import os

from django.core.files.storage import default_storage
from django.db import connection
from django.db.transaction import atomic

from celery import group, shared_task

from docia.file_processing.models import ExternalLinkDocumentOrder, FileInfo
from docia.file_processing.processor.cleaner import extract_num_EJ, get_file_initial_info
from docia.models import Document, Engagement, EngagementTag

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
            info = get_file_initial_info(filename, folder)
            # Rename some fields
            info = dict(**info)
            info["folder"] = info.pop("dossier")
            info["size"] = info.pop("taille")
            info["date"] = info.pop("date_creation")
            file_info = FileInfo(**info)
            file_info.file = os.path.join(folder, filename)
            to_create.append(file_info)
        files_info.append(file_info)

    # Save
    FileInfo.objects.bulk_create([info for info in to_create], batch_size=200, ignore_conflicts=True)

    return files_info


def bulk_create_engagements(num_ejs):
    engagements = [
        Engagement(
            num_ej=num_ej,
        )
        for num_ej in num_ejs
    ]
    Engagement.objects.bulk_create(engagements, batch_size=200, ignore_conflicts=True)


def bulk_create_documents(file_infos: list[FileInfo]):
    """
    Creates Documents from FileInfos, propagating the date field.
    Handles conflicts by keeping the most recent date when the same hash appears
    multiple times in file_infos or already exists in the database.
    """
    # Get all unique hashes from file_infos
    all_hashes = list({info.hash for info in file_infos})
    
    # Get existing documents' hash -> Document mapping, only loading hash and date fields
    existing_docs = Document.objects.filter(hash__in=all_hashes).only("hash", "date")
    existing_by_hash = {d.hash: d for d in existing_docs}
    
    # Deduplicate file_infos: group by hash, keep the one with most recent date
    items_by_hash = {}
    for info in file_infos:
        existing_info = items_by_hash.get(info.hash)
        if existing_info is None:
            items_by_hash[info.hash] = info
        else:
            # Keep the one with the most recent date
            if info.date and (not existing_info.date or info.date > existing_info.date):
                items_by_hash[info.hash] = info
    
    # Separate into documents to create and documents to update
    docs_to_create = []
    docs_to_update = []
    
    for hash, info in items_by_hash.items():
        existing_doc = existing_by_hash.get(hash)
        if existing_doc is not None:
            # Existing document - update date if new date is more recent
            new_date = info.date
            if existing_doc.date is None or (new_date and new_date > existing_doc.date):
                existing_doc.date = new_date
                docs_to_update.append(existing_doc)
        else:
            # New document
            doc = Document(
                filename=info.filename,
                extension=info.extension,
                dossier=info.folder,
                taille=info.size,
                hash=info.hash,
                file=info.file,
                date=info.date,
            )
            docs_to_create.append(doc)
    
    # Bulk create new documents
    if docs_to_create:
        Document.objects.bulk_create(docs_to_create, batch_size=200, ignore_conflicts=True)
    
    # Bulk update existing documents with newer dates
    if docs_to_update:
        Document.objects.bulk_update(docs_to_update, fields=["date"], batch_size=200)


def bulk_create_links_document_engagement_using_filenames(files_info: list[FileInfo]):
    """Create Links between documents and engagements"""

    # Use through model for efficient bulk creation of M2M relationships
    DocumentEngagement = Document.engagements.through
    # Get doc id by hash
    hashes = [fi.hash for fi in files_info]
    doc_id_by_hash = dict(Document.objects.filter(hash__in=hashes).values_list("hash", "id"))
    # Get engagements by num_ej
    num_ejs = set(extract_num_EJ(file_info.filename) for file_info in files_info)
    engagements_by_num_ej = dict(Engagement.objects.filter(num_ej__in=num_ejs).values_list("num_ej", "id"))

    # Build the links
    links_doc_engagement = [
        DocumentEngagement(
            document_id=doc_id_by_hash[fi.hash],
            engagement_id=engagements_by_num_ej[extract_num_EJ(fi.filename)],
        )
        for fi in files_info
    ]

    # Insert in database
    DocumentEngagement.objects.bulk_create(links_doc_engagement, batch_size=200, ignore_conflicts=True)


def bulk_create_links_document_engagement_using_external_data(file_infos: list[FileInfo]):
    """Create Links between documents and engagements"""

    # Use through model for efficient bulk creation of M2M relationships
    DocumentEngagement = Document.engagements.through
    # Get relations
    hashes = [info.hash for info in file_infos]
    SQL_QUERY = """
    SELECT doc.id, ej.id
    FROM docia_document doc
    INNER JOIN docia_fileinfo fi ON fi.hash = doc.hash
    INNER JOIN docia_externallinkdocumentorder link ON link.external_document_id = fi.root_external_id
    INNER JOIN docia_engagement ej ON ej.num_ej = link.order_id
    WHERE doc.hash = ANY(%s)
    """
    with connection.cursor() as cursor:
        cursor.execute(SQL_QUERY, [hashes])
        links = cursor.fetchall()

    # Build the links
    links_doc_engagement = [
        DocumentEngagement(
            document_id=doc_id,
            engagement_id=ej_id,
        )
        for doc_id, ej_id in links
    ]

    # Insert in database
    DocumentEngagement.objects.bulk_create(links_doc_engagement, batch_size=200, ignore_conflicts=True)


def bulk_create_ej_tags(num_ejs, tag):
    tags = [
        EngagementTag(
            name=tag,
            ej_id=num_ej,
        )
        for num_ej in num_ejs
    ]
    EngagementTag.objects.bulk_create(tags, batch_size=200, ignore_conflicts=True)


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


def init_documents_from_external_filter_by_num_ejs(num_ejs: list[str], batch_name: str):
    """Init documents using data from files imported using External API."""
    qs_links = ExternalLinkDocumentOrder.objects.filter(order_id__in=num_ejs).values_list(
        "external_document_id", flat=True
    )
    fileinfos = list(FileInfo.objects.filter(root_external_id__in=qs_links))
    num_ejs = sorted(num_ejs)
    with atomic():
        bulk_create_engagements(num_ejs)
        bulk_create_ej_tags(num_ejs, batch_name)
        bulk_create_documents(fileinfos)
        bulk_create_links_document_engagement_using_external_data(fileinfos)


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
        bulk_create_ej_tags(num_ejs, batch)
        bulk_create_documents(files_info)
        bulk_create_links_document_engagement_using_filenames(files_info)
