def pick_primary_num_ej(num_ejs: list[str]) -> str | None:
    if not num_ejs:
        return None
    return sorted(num_ejs)[0]


def ej_stratify_label(classifications: list[str]) -> str:
    if not classifications:
        return "unknown"
    return max(set(classifications), key=classifications.count)