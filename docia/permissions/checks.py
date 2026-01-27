from docia.models import DataEngagement


def get_user_allowed_ej_qs(user):
    return DataEngagement.objects.filter(scopes__groups__user=user).distinct()


def user_can_view_ej(user, num_ej: str):
    """
    Check if a user has permission to view a specific EJ (Engagement Juridique) number.

    Args:
        user: The user object containing email information
        num_ej (str): The EJ number to check permissions for

    Returns:
        bool: True if user has permission to view the EJ, False otherwise
    """

    if user.is_superuser:
        return True
    else:
        # 1. Check Django permission
        user_has_view_perm = user.has_perm("docia.view_document")
        # 2. Check scope permission
        # Engagement should be in a scope linked to a group of the user
        user_has_scope = get_user_allowed_ej_qs(user).filter(num_ej=num_ej).exists()
        return user_has_view_perm and user_has_scope
