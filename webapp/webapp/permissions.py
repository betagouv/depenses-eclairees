import os
from pathlib import Path


ALLOWED_EJ_NUMBERS = []

BASE_DIR = Path(__file__).resolve().parent


with open(BASE_DIR / "permissions.txt") as f:
    ALLOWED_EJ_NUMBERS.clear()
    ALLOWED_EJ_NUMBERS.extend([x.strip() for x in f.read().split('\n') if x.strip()])


def user_can_view_ej(user, ej_number: str):
    """
    Check if a user has permission to view a specific EJ (Engagement Juridique) number.

    Args:
        user: The user object containing email information
        ej_number (str): The EJ number to check permissions for

    Returns:
        bool: True if user has permission to view the EJ, False otherwise
    """
    admin_emails = [x.strip() for x in os.getenv('ADMIN_EMAILS', '').split(',') if x.strip()]
    if user.email in admin_emails:
        return True
    elif ej_number in ALLOWED_EJ_NUMBERS:
        return True
    else:
        return False
