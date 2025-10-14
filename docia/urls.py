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

from lasuite.oidc_login.urls import urlpatterns as oidc_urls
from magicauth.urls import urlpatterns as magicauth_urls
from mozilla_django_oidc.urls import OIDCCallbackClass

from . import views
from .auth import views as auth_views
from .tracking.urls import urlpatterns as tracking_urls

urlpatterns = [
    path("", views.home, name="home"),
    path("login", auth_views.LoginView.as_view(), name="login"),
    path("t/", include(tracking_urls)),
    path("oauth2callback", OIDCCallbackClass.as_view(), name="oidc_authentication_callback_custom"),
    path("oidc/", include(oidc_urls)),
    path("magicauth/", include(magicauth_urls)),
    path("admin/", admin.site.urls),
]
