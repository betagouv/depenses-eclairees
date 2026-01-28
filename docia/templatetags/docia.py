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
