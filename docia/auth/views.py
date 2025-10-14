from django.conf import settings
from django.contrib.auth import get_user_model

from magicauth import views as magicauth_views
from mozilla_django_oidc.views import OIDCAuthenticationCallbackView

from docia.auth.forms import LoginForm

User = get_user_model()


class LoginView(magicauth_views.LoginView):
    template_name = "docia/auth/login.html"
    form_class = LoginForm


def logout(request):
    return settings.OIDC_RP_LOGOUT_ENDPOINT


class CustomOIDCAuthenticationCallbackView(OIDCAuthenticationCallbackView):
    pass
