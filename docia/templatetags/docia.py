from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def get_item(dictionary, key):
    if not dictionary:
        return None
    if "." in key:
        key, suffix = key.split(".")
        return get_item(dictionary.get(key), suffix)
    else:
        return dictionary.get(key)


def _get_dotted(dictionnary: dict[str, any], key: str) -> any:
    while "." in key:
        if not dictionnary:
            return ""
        prefix, key = key.split(".", 1)
        dictionnary = dictionnary.get(prefix)
    return dictionnary.get(key, "")


@register.filter
def iban_spaces(value):
    """Format IBAN with a space every 4 characters."""
    if not value:
        return ""
    s = str(value).replace(" ", "")
    return " ".join(s[i : i + 4] for i in range(0, len(s), 4))


@register.filter
def format_siren_siret(value):
    """Format SIREN / SIRET avec un espace tous les 3 caractères (chiffres uniquement)."""
    if not value:
        return ""
    s = "".join(c for c in str(value))
    if not s:
        return ""
    return " ".join(s[i : i + 3] for i in range(0, len(s), 3))


@register.filter
def format_postal_address(adresse):
    """
    Formate un dictionnaire d'adresse postale (numero_voie, nom_voie, complement_adresse,
    code_postal, ville, pays) en une chaîne cohérente, ordre français.
    """
    if not adresse or not isinstance(adresse, dict):
        return ""
    numero = (adresse.get("numero_voie") or "").strip()
    voie = (adresse.get("nom_voie") or "").strip()
    complement = (adresse.get("complement_adresse") or "").strip()
    code_postal = (adresse.get("code_postal") or "").strip()
    ville = (adresse.get("ville") or "").strip()
    pays = (adresse.get("pays") or "").strip()
    ligne1 = " ".join(filter(None, [numero, voie]))
    if complement:
        ligne1 = f"{ligne1}, {complement}" if ligne1 else complement
    ligne2 = " ".join(filter(None, [code_postal, ville]))
    parts = [p for p in [ligne1, ligne2, pays] if p]
    return ", ".join(parts)


@register.filter
def as_percentage(value):
    """
    Convertit un taux décimal (ex. 0.20, 0.055) en pourcentage affichable (ex. 20 %, 5.5 %).
    """
    if not value:
        return None
    rate = float(value)
    pct = rate * 100
    if pct == int(pct):
        return mark_safe(f"{int(pct)}&nbsp;%")
    return mark_safe(f"{pct:.1f}&nbsp;%")


@register.filter
def list_of_dicts_as_table(list_of_dicts: list[dict], columns):
    rows = []
    headers = [label for key, label in columns]
    for dict_row in list_of_dicts:
        row = []
        for key, _label in columns:
            row.append(_get_dotted(dict_row, key))
        rows.append(row)
    return {
        "headers": headers,
        "rows": rows,
    }
