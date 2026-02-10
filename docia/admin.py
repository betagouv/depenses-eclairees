from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth import admin as auth_admin
from django.contrib.auth import forms as auth_forms
from django.contrib.auth import models as auth_models

from . import models


class AdminUserCreationForm(auth_forms.AdminUserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["usable_password"].initial = "false"


@admin.register(models.User)
class UserAdmin(auth_admin.UserAdmin):
    """Admin class for the User model"""

    add_form = AdminUserCreationForm

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "id",
                    "admin_email",
                    "password",
                )
            },
        ),
        (
            "Info personnelles",
            {
                "fields": (
                    "sub",
                    "email",
                    "full_name",
                    "short_name",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Dates important", {"fields": ("created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email",),
            },
        ),
        (
            "Staff",
            {
                "fields": (
                    "is_staff",
                    "admin_email",
                    "usable_password",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    list_display = (
        "id",
        "sub",
        "full_name",
        "admin_email",
        "email",
        "is_active",
        "is_staff",
        "is_superuser",
        "created_at",
        "updated_at",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    ordering = (
        "is_active",
        "-is_superuser",
        "-is_staff",
        "-updated_at",
        "full_name",
    )
    readonly_fields = (
        "id",
        "sub",
        "full_name",
        "short_name",
        "created_at",
        "updated_at",
    )
    search_fields = ("id", "sub", "admin_email", "email", "full_name")


@admin.register(models.Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "filename",
        "dossier",
        "is_ocr",
        "nb_mot",
        "taille",
        "classification",
        "classification_type",
        "date_creation",
    )
    ordering = (
        "-date_creation",
        "dossier",
        "filename",
    )
    search_fields = ("id", "filename", "dossier", "engagements__num_ej", "classification", "classification_type")


# Déregistrer le GroupAdmin par défaut pour le personnaliser
admin.site.unregister(auth_models.Group)


class AdminGroupForm(forms.ModelForm):
    scopes = forms.ModelMultipleChoiceField(
        queryset=models.EngagementScope.objects.all(),
        required=False,
        widget=FilteredSelectMultiple("scopes", is_stacked=False),
        label="",
    )

    class Meta:
        model = auth_models.Group
        fields = ("name", "permissions", "scopes")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["scopes"].initial = self.instance.scopes.all()

    def _save_m2m(self):
        super()._save_m2m()
        cleaned_data = self.cleaned_data
        scopes = cleaned_data["scopes"]
        self.instance.scopes.set(scopes)


@admin.register(auth_models.Group)
class CustomGroupAdmin(auth_admin.GroupAdmin):
    """Admin class for Group model extended with scopes"""

    search_fields = ("name", "scopes__name")
    fields = ("name", "permissions", "scopes")
    form = AdminGroupForm


@admin.register(models.EngagementScope)
class EngagementScopeAdmin(admin.ModelAdmin):
    """Admin class for EngagementScope model"""

    list_display = ("name", "engagement_count", "group_count")
    search_fields = ("name",)
    filter_horizontal = ("groups",)
    fields = ("name", "groups")

    def engagement_count(self, obj):
        return obj.engagements.count()

    engagement_count.short_description = "Engagements"

    def group_count(self, obj):
        return obj.groups.count()

    group_count.short_description = "Groupes"
