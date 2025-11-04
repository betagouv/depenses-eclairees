import logging

from django.shortcuts import render

from . import forms
from .models import DataAttachments
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
                    db_docs = DataAttachments.objects.filter(ej_id=form.cleaned_data["num_ej"])
                    db_docs = db_docs.order_by("classification")
                    for db_doc in db_docs:
                        llm_response = db_doc.llm_response or {}
                        doc = {
                            "id": db_doc.id,
                            "title": f"[{db_doc.classification}] {db_doc.filename}",
                            "content": sorted([[key, value] for key, value in llm_response.items()]),
                            "url": db_doc.file.url if db_doc.file else "",
                        }
                        if db_doc.llm_response:
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
        },
    )
