import uuid
from typing import override

from django.contrib.auth import models as auth_models
from django.db import models
from django.utils.translation import gettext_lazy as _


class BaseModel(models.Model):
    """
    Serves as an abstract base model for other models.

    Includes fields common to all models: a UUID primary key and creation/update timestamps.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        editable=False,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        editable=False,
    )

    class Meta:
        abstract = True

    def save(
        self,
        *,
        force_insert = False,
        force_update = False,
        using = None,
        update_fields = None,
    ):
        """
        Overrides the default save method to ensure the 'updated_at' field is always updated
        unless explicitly excluded.

        Args:
            force_insert (bool): If True, forces the creation of a new record.
            force_update (bool): If True, forces the update of an existing record.
            using (str): The database alias to use for the query.
            update_fields (list): The list of fields to update. If provided, only these fields
                                 will be updated. If 'updated_at' is not in the list, it will
                                 be added unless explicitly excluded with '-updated_at'.

        Returns:
            None
        """
        if update_fields:
            # Remove '-updated_at' from update_fields if present to allow updating 'updated_at'
            if "-updated_at" in update_fields:
                update_fields.remove("-updated_at")
            # Add 'updated_at' to update_fields if not already present to ensure it's updated
            elif "updated_at" not in update_fields:
                update_fields.append("updated_at")
        return super().save(
            force_insert = force_insert,
            force_update = force_update,
            using = None,
            update_fields = update_fields,
        )


class UserManager(auth_models.UserManager):
    """Custom manager for User model with additional methods."""

    @override
    def get_by_natural_key(self, username):
        """Make sure we dont return user if username is falsy."""
        if not username:
            return self.none()
        return super().get_by_natural_key(username=username)


class User(auth_models.AbstractBaseUser, auth_models.PermissionsMixin, BaseModel):
    sub = models.CharField(
        "sub",
        max_length=255,
        unique=True,
        blank=True,
        null=True,
    )

    full_name = models.CharField("nom complet", max_length=100, null=True, blank=True)  # noqa: DJ001
    short_name = models.CharField("nom court", max_length=20, null=True, blank=True)  # noqa: DJ001

    email = models.EmailField(unique=True, blank=True, null=True)  # noqa: DJ001

    # Unlike the "email" field which stores the email coming from the OIDC token, this field
    # stores the email used by staff users to login to the admin site
    admin_email = models.EmailField("adresse e-mail de connection à l'admin", unique=True, blank=True, null=True)

    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin site."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. Unselect this instead of deleting accounts."
        ),
    )

    objects = UserManager()

    USERNAME_FIELD = "admin_email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email or self.admin_email or str(self.id)
