import logging

from django.shortcuts import render

from . import forms
from .models import Document
from .permissions import user_can_view_ej
from .ratelimit.services import check_rate_limit_for_user

logger = logging.getLogger(__name__)


def home(request):
    documents = []
    unprocessed = []
    is_form_processed = False
    is_ratelimited = False
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
                    db_docs = Document.objects.filter(ej_id=form.cleaned_data["num_ej"])
                    db_docs = db_docs.order_by("classification")
                    for db_doc in db_docs:
                        document_data = db_doc.structured_data or {}
                        ratio_extracted = compute_ratio_data_extraction(document_data)
                        doc = {
                            "id": db_doc.id,
                            "title": f"[{db_doc.classification}] {db_doc.filename}",
                            "data_as_list": sorted([[key, value] for key, value in document_data.items()]),
                            "data": document_data,
                            "url": db_doc.file.url if db_doc.file else "",
                            "percent_data_extraction": format_ratio_to_percent(ratio_extracted),
                            "classification": db_doc.classification,
                        }
                        if document_data:
                            documents.append(doc)
                        else:
                            unprocessed.append(doc)
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


def format_ratio_to_percent(value: float) -> str:
    return f"{value * 100:.0f}%"
