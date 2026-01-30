from django import template

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
def first_n_words(value, n=10):
    """
    Garde les n premiers mots (séparés par des espaces) et ajoute « ... » si le texte est tronqué.
    """
    if not value:
        return ""
    words = str(value).strip().split()
    if len(words) <= n:
        return " ".join(words)
    return " ".join(words[:n]) + " ..."


@register.filter
def format_siren_siret(value):
    """Format SIREN / SIRET avec un espace tous les 3 caractères (chiffres uniquement)."""
    if not value:
        return ""
    s = "".join(c for c in str(value) if c.isdigit())
    if not s:
        return ""
    return " ".join(s[i : i + 3] for i in range(0, len(s), 3))


@register.filter
def format_montant(value):
    """
    Formate un montant pour l'affichage : séparateurs de milliers (espace),
    virgule décimale, symbole €.
    La valeur attendue est celle standardisée par post_processing_amount
    (chaîne "1234.56" ou None). Retourne '' si vide (template affiche [Non trouvé]).
    """
    if value is None or value == "":
        return ""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return ""
    # Format US puis conversion style français : 1 234,56
    s = f"{n:,.2f}"
    if "." in s:
        parts = s.rsplit(".", 1)
        formatted = parts[0].replace(",", " ") + "," + parts[1]
    else:
        formatted = s.replace(",", " ")
    return f"{formatted} €"


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
