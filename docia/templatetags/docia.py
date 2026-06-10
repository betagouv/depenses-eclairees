from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def url_replace(request, **kwargs):
    """
    Permet de modifier des paramètres dans l'URL actuelle.
    Exemple : {% url_replace request sort='date' %}
    Conserve tous les paramètres existants et remplace ceux passés en kwargs.
    """
    # Récupère les paramètres GET actuels
    params = request.GET.copy()
    # Remplace les paramètres (écrase les valeurs existantes)
    for key, value in kwargs.items():
        params[key] = value
    # Reconstruit l'URL avec les paramètres
    return f"?{params.urlencode()}"


def _is_nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list)):
        return bool(value)
    return True


@register.filter
def dict_has_values(value):
    """True si dict avec au moins une valeur non vide (None, '', {}, [])."""
    if not value or not isinstance(value, dict):
        return False
    return any(_is_nonempty(v) for v in value.values())


@register.filter
def get_item(dictionary, key):
    if not dictionary:
        return None
    if "." in key:
        key, suffix = key.split(".", 1)
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


def _format_eur_amount(value) -> str | None:
    if not _is_nonempty(value):
        return None
    n = float(value)
    sign = "-" if n < 0 else ""
    n = abs(n)
    integer = int(n)
    cents = int(round((n - integer) * 100))
    if cents == 100:
        integer += 1
        cents = 0
    int_str = f"{integer:,}".replace(",", "\u00a0")
    return f"{sign}{int_str},{cents:02d} €"


@register.filter
def format_money_block_line(block):
    """Bloc monétaire {ht, tva, ttc} sur une seule ligne."""
    if not block or not isinstance(block, dict):
        return ""
    parts = []
    if _is_nonempty(block.get("ht")):
        parts.append(f"{_format_eur_amount(block['ht'])} HT")
    if _is_nonempty(block.get("tva")):
        parts.append(f"{_format_eur_amount(block['tva'])} TVA")
    if _is_nonempty(block.get("ttc")):
        parts.append(f"{_format_eur_amount(block['ttc'])} TTC")
    return " · ".join(parts)


@register.filter
def format_incidence_duree_line(block):
    """Incidence durée {prolongation, date_fin_execution} sur une seule ligne."""
    if not block or not isinstance(block, dict):
        return ""
    parts = []
    if _is_nonempty(block.get("prolongation")):
        parts.append(f"Prolongation {block['prolongation']} mois")
    if _is_nonempty(block.get("date_fin_execution")):
        parts.append(f"Fin {block['date_fin_execution']}")
    return " · ".join(parts)


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
def is_cpv_by_lot(value):
    """True si code_cpv est une liste de dicts par lot (avec numero_lot), False sinon (liste de strings)."""
    if not value or not isinstance(value, list) or len(value) == 0:
        return False
    first = value[0]
    return isinstance(first, dict) and "numero_lot" in first


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
