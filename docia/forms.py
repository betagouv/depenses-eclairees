from django import forms

from dsfr.forms import DsfrBaseForm


class GetEJDetailsForm(DsfrBaseForm):
    num_ej = forms.CharField(
        label="Numéro d'EJ",
        max_length=200,
    )
