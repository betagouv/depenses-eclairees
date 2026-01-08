from pathlib import Path

from docia.models import DataBatch

ALLOWED_EJ_NUMBERS = []
ALLOWED_BATCHES = [
    "EJ_CBCM_0129",
]

BASE_DIR = Path(__file__).resolve().parent


with open(BASE_DIR / "permissions.txt") as f:
    ALLOWED_EJ_NUMBERS.clear()
    ALLOWED_EJ_NUMBERS.extend([x.strip() for x in f.read().split("\n") if x.strip()])


def user_can_view_ej(user, num_ej: str):
    """
    Check if a user has permission to view a specific EJ (Engagement Juridique) number.

    Args:
        user: The user object containing email information
        num_ej (str): The EJ number to check permissions for

    Returns:
        bool: True if user has permission to view the EJ, False otherwise
    """
    qs_batch = DataBatch.objects.filter(batch__in=ALLOWED_BATCHES, ej_id=num_ej)
    user_has_perm = user.has_perm("docia.view_document")
    if user.is_superuser:
        return True
    elif user_has_perm and (num_ej in ALLOWED_EJ_NUMBERS or qs_batch.exists()):
        return True
    else:
        return False
