from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth import admin as auth_admin
from django.contrib.auth import forms as auth_forms
from django.contrib.auth import models as auth_models
from django.db.models import Count, F
from django.http import HttpResponse

from . import models
from .documents.transfer.exporter import EngagementExporter
from .permissions.models import GroupScope
from .tracking.models import TrackingEvent


class AdminUserCreationForm(auth_forms.AdminUserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["usable_password"].initial = "false"


class LastLoginFilter(admin.SimpleListFilter):
    title = "Dernière connexion"
    parameter_name = "has_last_login"

    def lookups(self, request, model_admin):
        return (
            ("has_last_login", "Non-vide"),
            ("no_last_login", "Vide"),
        )

    def queryset(self, request, queryset):
        if self.value() == "has_last_login":
            return queryset.exclude(last_login__isnull=True)
        elif self.value() == "no_last_login":
            return queryset.filter(last_login__isnull=True)
        return queryset


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
        "full_name",
        "email",
        "last_login",
        "is_active",
        "is_staff",
        "is_superuser",
        "sub",
        "admin_email",
        "created_at",
        "updated_at",
    )
    list_filter = (LastLoginFilter, "is_staff", "is_superuser", "is_active", "groups")
    ordering = [F("last_login").desc(nulls_last=True)]
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


class GroupScopeInline(admin.TabularInline):
    """Inline admin for GroupScope within Group admin"""

    model = GroupScope
    extra = 1
    fields = ("purchase_organization", "purchase_group")
    verbose_name = "Périmètre"
    verbose_name_plural = "Périmètres"


@admin.register(auth_models.Group)
class CustomGroupAdmin(auth_admin.GroupAdmin):
    """Admin class for Group model with inline GroupScope editing"""

    inlines = [GroupScopeInline]
    list_display = ("name", "col_group_scopes")
    search_fields = ("name", "scope__purchase_group", "scope__purchase_organization")
    fields = ("name", "permissions")

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("scope_set")

    def col_group_scopes(self, obj):
        return ", ".join(str(scope) for scope in obj.scope_set.all())

    col_group_scopes.short_description = "Périmètres"


class ActionFilter(admin.SimpleListFilter):
    title = "Action"
    parameter_name = "action"

    def lookups(self, request, model_admin):
        actions = TrackingEvent.objects.values_list("action", flat=True).distinct()
        return [(action, action) for action in sorted(actions) if action]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(action=self.value())
        return queryset


@admin.register(TrackingEvent)
class TrackingEventAdmin(admin.ModelAdmin):
    list_display = ("id", "category", "action", "name", "user", "num_ej", "page_url", "created_at", "updated_at")
    list_filter = (ActionFilter, "category", "action")
    search_fields = ("id", "category", "action", "name", "page_url", "num_ej", "user__email")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")


class EngagementForm(forms.ModelForm):
    scopes = forms.ModelMultipleChoiceField(
        queryset=models.EngagementScope.objects.all(),
        required=False,
        widget=FilteredSelectMultiple("scopes", is_stacked=False),
        label="",
    )

    class Meta:
        model = models.Engagement
        fields = ("num_ej", "external_updated_at", "scopes")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["scopes"].initial = self.instance.scopes.all()

    def _save_m2m(self):
        super()._save_m2m()
        cleaned_data = self.cleaned_data
        scopes = cleaned_data["scopes"]
        self.instance.scopes.set(scopes)


@admin.register(models.Engagement)
class EngagementAdmin(admin.ModelAdmin):
    """Admin class for Engagement model"""

    form = EngagementForm
    list_display = ("num_ej", "col_scopes", "external_updated_at", "updated_at")
    search_fields = ("num_ej", "scopes__purchase_organization", "scopes__purchase_group")
    list_filter = ("external_updated_at",)
    readonly_fields = ("id", "external_updated_at", "created_at", "updated_at")
    actions = ["export_as_json"]

    fieldsets = (
        (None, {"fields": ("id", "num_ej", "scopes")}),
        ("Dates", {"fields": ("external_updated_at", "created_at", "updated_at")}),
    )

    def col_scopes(self, obj):
        return ", ".join(str(scope) for scope in obj.scopes.all())

    col_scopes.short_description = "Périmètres"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("scopes")

    def export_as_json(self, request, queryset):
        """Export selected Engagements as JSON file."""
        num_ejs = list(queryset.values_list("num_ej", flat=True))

        if not num_ejs:
            self.message_user(request, "Aucun engagement sélectionné")
            return

        exporter = EngagementExporter()
        json_bytes = exporter.export_to_json(num_ejs, pretty_print=True)

        # Nom du fichier : num_ej si un seul, sinon engagements.json
        filename = f"{num_ejs[0]}.json" if len(num_ejs) == 1 else "engagements.json"

        response = HttpResponse(json_bytes, content_type="application/json")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    export_as_json.short_description = "Exporter les engagements sélectionnés en JSON"


@admin.register(models.EngagementScope)
class EngagementScopeAdmin(admin.ModelAdmin):
    """Admin class for EngagementScope model"""

    list_display = ("purchase_organization", "purchase_group", "engagement_count")
    search_fields = ("purchase_organization", "purchase_group")
    fields = ("purchase_organization", "purchase_group")

    def engagement_count(self, obj):
        return obj.engagement_count

    engagement_count.short_description = "Engagements"

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(engagement_count=Count("engagements"))
