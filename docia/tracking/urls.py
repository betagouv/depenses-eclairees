from django.urls import path

from docia.tracking.views import tracking_event_view

urlpatterns = [
    path("events", tracking_event_view, name="tracking-event-create"),
]
