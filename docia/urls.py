"""
URL configuration for docia project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from lasuite.oidc_login.urls import urlpatterns as oidc_urls

from . import settings, views
from .tracking.urls import urlpatterns as tracking_urls

urlpatterns = [
    path("", views.home, name="home"),
    path("login", TemplateView.as_view(template_name="docia/auth/login.html"), name="login"),
    path("t/", include(tracking_urls)),
    path("oidc/", include(oidc_urls)),
]

if settings.ADMIN_BASE_URL_PATH:
    urlpatterns.append(path(settings.ADMIN_BASE_URL_PATH, admin.site.urls))
