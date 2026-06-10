from django import forms

from dsfr.forms import DsfrBaseForm


class GetEJDetailsForm(DsfrBaseForm):
    num_ej = forms.CharField(
        label="Numéro d'EJ",
        max_length=200,
    )
    sort = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
    )
