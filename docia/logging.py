import logging
import threading
import uuid

from django.conf import settings

from celery import current_task

local = threading.local()


def get_request_id(request):
    header = getattr(settings, "REQUEST_ID_HEADER", "HTTP_X_REQUEST_ID")
    if hasattr(request, "request_id"):
        return request.request_id
    elif header in request.META:
        return request.META[header]
    else:
        return uuid.uuid4().hex


class RequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        local.request = request
        request.request_id = get_request_id(request)
        response = self.get_response(request)
        return response


class SessionIdFilter(logging.Filter):
    def filter(self, record):
        try:
            record.session_id = local.request.session.session_key
        except AttributeError:
            record.session_id = ""
        return True


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        try:
            record.request_id = local.request.request_id
        except AttributeError:
            record.request_id = ""
        return True


class CeleryTaskFilter(logging.Filter):
    """Add `task_id` to log record."""

    def filter(self, record):
        if current_task:
            try:
                record.task_id = current_task.request.id
                record.task_name = current_task.name
            except AttributeError as ex:
                print("Error in CeleryTaskFilter", ex)
                record.task_id = ""
                record.task_name = ""
        else:
            record.task_id = ""
            record.task_name = ""
        return True
