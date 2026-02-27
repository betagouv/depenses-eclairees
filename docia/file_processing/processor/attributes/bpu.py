"""
Définitions des attributs à extraire pour les documents de type "devis".
Le LLM renvoie une liste plate (clé "prestations") ; le postprocessing produit
prestations_flat (liste plate, sans guid) et prestations (arborescence récursive).
"""

import hashlib
import json


def _guid_for_flat_item(item: dict) -> str:
    """Génère un guid déterministe à partir de id, label, parent et pricing (hors LLM, pour fusion chunks)."""
    key = "|".join(
        [
            str(item.get("id") or ""),
            str(item.get("label") or ""),
            str(item.get("parent") if item.get("parent") is not None else ""),
            json.dumps(item.get("pricing") or {}, sort_keys=True, default=str),
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def set_guid_on_flat_prestations(prestations: list[dict] | None) -> None:
    """
    Préprocessing hors LLM : attribue à chaque élément un guid déterministe (id, label, parent, pricing).
    À appeler après réception de chaque chunk pour permettre une fusion sûre.
    Modifie la liste en place.
    """
    if not prestations:
        return
    for it in prestations:
        if isinstance(it, dict):
            it["guid"] = _guid_for_flat_item(it)


def bpu_flat_to_tree(flat_list: list[dict] | None) -> list[dict] | None:
    """
    Reconstruit l'arborescence récursive des prestations BPU à partir de la liste plate.
    Profondeur variable : la hiérarchie parent/enfant de la liste plate est respectée (autant de niveaux que nécessaire).
    Déterministe : ordre des enfants = ordre d'apparition dans la liste plate (depth-first).

    - Élément avec pricing=null → nœud section { "code": ... | null, "intitule": "code - libellé", "content": [ ... ] } (content récursif).
    - Élément avec pricing non null → ligne feuille { "code": ... | null, "titre": "code - libellé", "prix_ht": ..., ... }.
    code : id du nœud s'il provient du document (ex. "UO 2.1.1", "LOT 1"), null pour id synthétique (ex. avec '_').
    titre / intitule : texte tel qu'il figure dans le document (label), sans préfixe ni reformulation. Si label vide, fallback sur l'id.
    """
    if not flat_list:
        return None

    # S'assurer que chaque élément a un guid
    items = []
    for it in flat_list:
        it = dict(it)
        if not it.get("guid"):
            it["guid"] = _guid_for_flat_item(it)
        items.append(it)

    # Index par id pour retrouver les parents
    by_id = {it["id"]: it for it in items}
    # Enfants par parent_id, dans l'ordre de la liste plate
    children_by_parent = {}
    for it in items:
        pid = it.get("parent") if it.get("parent") else None
        children_by_parent.setdefault(pid, []).append(it)

    def _id_as_code(id_val: str | None) -> str | None:
        """Retourne l'id comme code document (ex. UO 2.1.1, LOT 1, I.1, M1, M2b). Sinon null (id synthétique ou composite sans préfixe-code)."""
        if not id_val or not isinstance(id_val, str):
            return None
        s = id_val.strip()
        if not s:
            return None
        # Id avec underscore = synthétique (ex. maintenance_parc_materiel, periode_1)
        if "_" in s:
            return None
        # Id composite type "CODE-Suffix" (ex. M1-Fleury-Mérogis, M2b-Val-d'Oise) : extraire le préfixe court comme code
        if "-" in s:
            segments = s.split("-")
            first = segments[0].strip()
            rest_has_long_or_lowercase = any(
                len(seg.strip()) > 10 or any(c.isalpha() and c.islower() for c in (seg or ""))
                for seg in segments[1:]
            )
            # Si le reste ressemble à un suffixe (lieu, nom), et le premier segment est un court code (M1, M2b, etc.)
            if rest_has_long_or_lowercase and first and len(first) <= 8 and all(
                c.isalnum() or c in ". " for c in first
            ):
                return first
            # Sinon même règle qu'avant : tout le reste sans long/lowercase → id entier est code (ex. Phasage-1)
            for seg in segments[1:]:
                seg = (seg or "").strip()
                if len(seg) > 10:
                    return None
                if seg and any(c.isalpha() and c.islower() for c in seg):
                    return None
        return s

    def to_node(flat_item: dict):
        code_raw = (flat_item.get("id") or "").strip()
        label = (flat_item.get("label") or "").strip()
        # Code : celui extrait par le LLM (champ code) si présent, sinon déduit de l'id
        code_from_prompt = flat_item.get("code")
        if code_from_prompt is not None and isinstance(code_from_prompt, str):
            code_from_prompt = code_from_prompt.strip()
        code_out = code_from_prompt if (code_from_prompt) else None
        # Titre et intitule = texte du document uniquement (label), sans préfixe ni reformulation
        if not label:
            if not code_out:
                code_out = code_raw or None
            merged = code_raw  # fallback quand le document n'a pas de libellé
        else:
            if not code_out:
                code_out = _id_as_code(flat_item.get("id"))
            merged = label  # strictement ce qui est écrit dans le document
        if flat_item.get("pricing") is not None and flat_item.get("pricing") != {}:
            # Ligne feuille : titre = libellé tel qu'il figure dans le document
            titre = merged
            p = flat_item["pricing"] or {}
            return {
                "code": code_out,
                "titre": titre,
                "prix_ht": p.get("prix_ht"),
                "prix_ttc": p.get("prix_ttc"),
                "taux_tva": p.get("taux_tva"),
                "quantite": p.get("quantite"),
                "unité": p.get("unite"),
            }
        # Section : code et libellé fusionnés dans intitule
        kid_list = children_by_parent.get(flat_item["id"], [])
        return {
            "code": code_out,
            "intitule": merged,
            "content": [to_node(child) for child in kid_list],
        }

    roots = children_by_parent.get(None, [])
    return [to_node(r) for r in roots]


def post_processing_bpu_flat(data: dict) -> dict:
    """
    Post-traitement BPU : complète les guid manquants (hash déterministe).
    Sortie : prestations_flat (liste plate du LLM, sans guid) et prestations (arborescence récursive).
    """
    if not data:
        return data
    prestations_flat = data.get("prestations")
    if prestations_flat is None:
        return data
    if not isinstance(prestations_flat, list):
        return data

    # Guid toujours calculé côté code (hors LLM) pour fusion chunks sûre
    set_guid_on_flat_prestations(prestations_flat)

    # Arbre récursif → clé principale "prestations"
    data["prestations"] = bpu_flat_to_tree(prestations_flat)

    # Liste plate → "prestations_flat" ; retirer les guid de la sortie
    for it in prestations_flat:
        if isinstance(it, dict) and "guid" in it:
            del it["guid"]
    data["prestations_flat"] = prestations_flat
    return data


BPU_ATTRIBUTES = {
    "objet": {
        "consigne": """OBJET
   Définition : Objet du marché décrit dans le BPU (Bordereau de Prix Unitaire).
   RÈGLE OBLIGATOIRE : renvoyer l'objet BPU COMPLET tel qu'il figure dans le document — ne pas raccourcir, ne pas résumer (ex. "Accompagnement des communes pour des projets d'aménagement et de développement durables" et non "Accompagnement des communes").
   Indices :
   - Chercher après les mentions "BPU", "Bordereau de Prix Unitaire", "Numéro de BPU".
   - Ne rien renvoyer si aucun objet BPU trouvé
        Format : 
        - En bon Français
        - Attention, ne pas inclure le type de document dans l'objet BPU : "Devis pour ..." enlever "Devis pour" / "Avenant pour ..." enlever "Avenant pour" / "Marché pour ..." enlever "Marché pour".
        - Ne pas renvoyer une des prestations du BPU dans l'objet.
        - Si l'objet BPU est incompréhensible, proposer un objet BPU simple qui reflète le contenu du document.
""",
        "search": "",
        "output_field": "objet",
    },
    "prestations": {
        "consigne": """PRESTATIONS (liste plate, hiérarchie parent/enfant à profondeur variable)
   Modèle : chaque élément = un nœud de l'arbre avec id, parent, label, code, pricing. La structure du document (titres, tableaux, sous-sections) peut avoir autant de niveaux que nécessaire ; respecter exactement cette arborescence.

   - id : identifiant unique dans toute la liste, obligatoire pour que parent puisse référencer. Doit provenir du document : numéro ou code s'il existe (ex. "I.1", "1", "Phasage-1"), ou début du libellé / intitulé tel qu'il figure (ex. "Forfait pour la période du 27/08/18", "Prestation de maintenance du parc matériel..."). Ne pas inventer de mots ou libellés absents du document (ex. interdire "maintenance_parc_materiel", "periode_1" si "maintenance" et "periode" n'apparaissent pas dans le texte). Si le même libellé apparaît à plusieurs endroits, utiliser des id distincts en préfixant par le parent (ex. "Fleury-Prestation 1").
   - parent : id du nœud parent immédiat. null pour les racines (éléments sans parent dans le document, ex. titres de section de plus haut niveau). Tout élément non racine a exactement un parent dont l'id figure dans la liste.
   - label : libellé EXACT tel qu'il est écrit dans le document — ne pas reformuler, ne pas paraphraser, ne pas abréger ni utiliser de diminutifs. Copier les titres et intitulés mot pour mot. Pas de résumé ni troncature. Inclure tous les éléments de la prestation (titre de section, intitulé de prestation, désignation de ligne avec montant) tels qu'ils apparaissent. Ne pas y inclure l'unité ni le type de prix : ceux-ci vont dans pricing.unite.
   - code : référence ou code de la ligne tel qu'il figure dans le document (ex. "M1", "M2b", "UO 2.1.1", "LOT 1", "I.1"). Recopier le code exact tel qu'écrit. null si le document ne contient pas de code ou référence pour cette ligne.
   - pricing : null pour tout nœud qui a des enfants. Pour les lignes feuille : { prix_ht, prix_ttc, taux_tva, quantite, unite }. Valeurs absentes = null ; 0 seulement si le document indique 0.
   - pricing.unite : provient UNIQUEMENT d'une colonne dédiée du document (ex. "Unité", "Durée", "Type de prix"). Souvent une durée (jour, mois, an, heure) ou un type de prix (unitaire, forfaitaire). Ne pas interpréter ni extraire l'unité depuis le libellé / intitulé de la prestation. S'il n'existe pas de colonne dédiée, mettre null.

   Règles :
   - Conserver TOUS les niveaux présents dans le document : titres ## ou équivalent (niveau 1), sous-titres ou colonnes "Prestation" (niveau 2), lignes de mission (niveau 3), etc. Si un titre regroupe des tableaux, ce titre est une racine (parent null) et les éléments du tableau ont ce titre en parent.
   - Titres et intitulés : recopier le texte du document à l'identique. Aucune reformulation, paraphrase ou abréviation.
   - ORDRE : depth-first (parent avant ses enfants, frères dans l'ordre du document) pour permettre la reconstitution de l'arbre.
   - Ne pas inclure les lignes d'en-tête de tableau ni les lignes de total.
   - Ne rien renvoyer (liste vide ou null) si aucune prestation trouvée.
   Format : liste de json, chaque élément : { "id": "...", "parent": "..." | null, "label": "...", "code": "..." | null, "pricing": { ... } | null } (sans guid).
""",
        "search": "",
        "output_field": "prestations",
        "schema": {
            "type": ["array", "null"],
            "items": {"$ref": "#/$defs/prestationFlatItem"},
            "$defs": {
                "prestationFlatItem": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "parent": {"type": ["string", "null"]},
                        "label": {"type": "string"},
                        "code": {"type": ["string", "null"]},
                        "pricing": {
                            "type": ["object", "null"],
                            "properties": {
                                "prix_ht": {"type": ["number", "null"]},
                                "prix_ttc": {"type": ["number", "null"]},
                                "taux_tva": {"type": ["number", "null"]},
                                "quantite": {"type": ["number", "null"]},
                                "unite": {"type": ["string", "null"]},
                            },
                            "required": ["prix_ht", "prix_ttc", "taux_tva", "quantite", "unite"],
                        },
                    },
                    "required": ["id", "parent", "label", "pricing"],
                },
            },
        },
    },
}
