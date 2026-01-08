import pandas as pd

from docia.models import DataBatch, DataEngagement, Document


def bulk_create_batches(df: pd.DataFrame, batch_size=100):
    """
    Bulk insert records into the batch table in batches.

    Args:
        df (pd.DataFrame): DataFrame containing Batch and num_EJ columns
        batch_size (int): Number of records to insert in each batch
    """
    batches = [
        DataBatch(
            batch=row["Batch"],
            ej_id=row["num_EJ"],
        )
        for row in df.to_dict(orient="records")
    ]
    DataBatch.objects.bulk_create(batches, batch_size=batch_size, ignore_conflicts=True)


def bulk_create_engagements(df: pd.DataFrame, batch_size=100):
    engagements = [
        DataEngagement(
            num_ej=row["num_EJ"],
            date_creation=row["date_creation"],
        )
        for row in df.to_dict(orient="records")
    ]
    DataEngagement.objects.bulk_create(engagements, batch_size=batch_size, ignore_conflicts=True)


def bulk_create_attachments(df: pd.DataFrame, batch_size=100):
    attachments = [
        Document(
            filename=row["filename"],
            extension=row["extension"],
            dossier=row["dossier"],
            ej_id=row["num_EJ"],
            date_creation=row["date_creation"],
            taille=row["taille"],
            hash=row["hash"],
            file=row["dossier"] + "/" + row["filename"],
        )
        for row in df.to_dict(orient="records")
    ]
    Document.objects.bulk_create(attachments, batch_size=batch_size, ignore_conflicts=True)
