import logging

from django.shortcuts import render

from . import forms
from .file_processing.processor.classifier import DIC_CLASS_FILE_BY_NAME
from .models import Document
from .permissions.checks import user_can_view_ej
from .ratelimit.services import check_rate_limit_for_user

logger = logging.getLogger(__name__)

# Classifications traitées mais non affichées dans la catégorie analysée (pas encore prêtes)
CLASSIFICATIONS_AFFICHEES = frozenset({"acte_engagement", "ccap", "rib", "fiche_navette", "sous_traitance"})

# Ordre d'affichage des catégories (chaque catégorie triée par taux de remplissage décroissant)
ORDER_CLASSIFICATIONS = ("acte_engagement", "ccap", "sous_traitance", "rib", "fiche_navette")


def sort_by_order_and_field(
    items: list[dict],
    order_values: tuple | list,
    order_key: str,
    *,
    then_by_field: str | None = None,
    then_descending: bool = True,
) -> None:
    """
    Trie une liste de dictionnaires en place.

    - Premier critère : ordre défini par order_values (valeur de order_key dans chaque item).
      Les valeurs absentes de order_values sont placées à la fin.
    - Second critère (optionnel) : champ then_by_field, décroissant si then_descending=True.

    :param items: Liste de dicts à trier (modifiée en place).
    :param order_values: Liste ou tuple définissant l'ordre des valeurs pour order_key.
    :param order_key: Clé du dict utilisée pour le tri principal.
    :param then_by_field: Clé optionnelle pour le tri secondaire.
    :param then_descending: Si True, tri secondaire décroissant ; sinon croissant.
    """
    order_index = {v: i for i, v in enumerate(order_values)}
    default_index = len(order_values)

    def sort_key(item):
        primary = order_index.get(item.get(order_key), default_index)
        if then_by_field is None:
            return (primary,)
        secondary = item.get(then_by_field)
        if secondary is not None and isinstance(secondary, (int, float)):
            secondary = -secondary if then_descending else secondary
        elif then_descending:
            secondary = float("inf")  # valeurs manquantes en fin de groupe
        return (primary, secondary)

    items.sort(key=sort_key)


def home(request):
    documents = []
    unprocessed = []
    is_form_processed = False
    is_ratelimited = False
    num_ej = None
    if request.user.is_authenticated and request.GET:
        is_form_processed = True
        # create a form instance and populate it with data from the request:
        form = forms.GetEJDetailsForm(request.GET)
        # check rate limit, 200 per day
        ratelimit_result = check_rate_limit_for_user(request.user, 200, 3600 * 24)
        is_ratelimited = ratelimit_result.limited
        if is_ratelimited:
            logger.info(f"Rate limit for user {request.user.id} exceeded")
        else:
            # check whether it's valid:
            if form.is_valid():
                num_ej = form.cleaned_data["num_ej"]
                if not user_can_view_ej(request.user, num_ej):
                    logger.warning(f"PermissionDenied: User {request.user.email} cannot view EJ {num_ej}")
                else:
                    db_docs = Document.objects.filter(engagements__num_ej=form.cleaned_data["num_ej"])
                    db_docs = db_docs.order_by("classification")
                    for db_doc in db_docs:
                        document_data_raw = db_doc.structured_data or {}
                        ratio_extracted = compute_ratio_data_extraction(document_data_raw)
                        short_classification = get_short_classification(db_doc.classification)
                        if db_doc.classification == "acte_engagement":
                            document_data = enrich_acte_engagement_display(document_data_raw)
                        else:
                            document_data = document_data_raw
                        doc = {
                            "id": db_doc.id,
                            "classification": db_doc.classification,
                            "short_classification": short_classification,
                            "filename": db_doc.filename[11:],
                            "data_as_list": sorted([[key, value] for key, value in document_data_raw.items()]),
                            "data": document_data,
                            "url": db_doc.file.url if db_doc.file else "",
                            "percent_data_extraction": format_ratio_to_percent(ratio_extracted),
                            "ratio_extracted": ratio_extracted,
                        }
                        if document_data and db_doc.classification in CLASSIFICATIONS_AFFICHEES:
                            documents.append(doc)
                        else:
                            unprocessed.append(doc)
                    # Trier par catégorie puis par taux de remplissage décroissant
                    sort_by_order_and_field(
                        documents,
                        ORDER_CLASSIFICATIONS,
                        "classification",
                        then_by_field="ratio_extracted",
                        then_descending=True,
                    )
    else:
        # Create empty form
        form = forms.GetEJDetailsForm()

    return render(
        request,
        "docia/home.html",
        {
            "form": form,
            "is_form_processed": is_form_processed,
            "documents": documents,
            "unprocessed": unprocessed,
            "num_ej": num_ej,
            "is_ratelimited": is_ratelimited,
            "formatting_data": {
                "cotraitants": {
                    "table_columns": (
                        ("nom", "Nom"),
                        ("siret", "SIRET"),
                    ),
                },
                "sous_traitants": {
                    "table_columns": (
                        ("nom", "Nom"),
                        ("siret", "SIRET"),
                    ),
                },
                "rib_autres": {
                    "table_columns": (
                        ("societe", "Société"),
                        ("rib.banque", "Banque"),
                        ("rib.iban", "IBAN"),
                    ),
                },
            },
        },
    )


def compute_ratio_data_extraction(document_data: dict) -> float:
    total_keys = len(document_data.keys())
    total_extracted = len([x for x in document_data.values() if x])
    if total_keys == 0:
        return 0
    return total_extracted / total_keys


def get_short_classification(classification: str) -> str:
    try:
        return DIC_CLASS_FILE_BY_NAME[classification]["short_name"]
    except KeyError:
        return classification


def format_ratio_to_percent(value: float) -> str:
    return f"{value * 100:.0f}%"


def enrich_acte_engagement_display(data: dict) -> dict:
    """
    Enrichit les données d'un acte d'engagement avec des valeurs précalculées pour l'affichage.
    Modifie data en place (montant_tva_euros).
    """
    if not data:
        return data
    montant_tva = data.get("montant_tva")
    montant_ht = data.get("montant_ht")
    if montant_ht is not None and montant_tva is not None and montant_tva != "":
        data["montant_tva_euros"] = float(montant_ht or 0) * float(montant_tva or 0)
    return data
