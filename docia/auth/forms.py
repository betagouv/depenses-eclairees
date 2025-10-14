from dsfr.forms import DsfrBaseForm
from magicauth import forms as magicauth_forms


class LoginForm(magicauth_forms.EmailForm, DsfrBaseForm):
    pass
