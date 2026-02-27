"""
Analyse le contexte fourni en utilisant l'api et les modèles d'IA. Prend en entrée un contexte (plus ou moins long)
Contexte = parfois tout le texte extrait, parfois seulement une liste de chunks concaténés.

Pour les BPU (bordereaux de prix unitaires), extraction en plusieurs appels (chunking) pour éviter
timeout et dépassement de la longueur de sortie : premier chunk → objet + prestations, chunks suivants → prestations uniquement, puis fusion.
"""

import logging
import re
import time

import pandas as pd

from ..llm.client import LLMClient
from .attributes.bpu import set_guid_on_flat_prestations
from .attributes_query import ATTRIBUTES, select_attr
from .post_processing_llm import clean_llm_response

logger = logging.getLogger("docia." + __name__)

# Types de document BPU pour lesquels on utilise le chunking (extraction prestations par morceaux)
BPU_DOC_TYPES = ("bordereau_prix", "decomposition_prix", "detail_quantitatif_estimatif")

# Limites tokens BPU (entrée + sortie) pour rester sous le timeout
BPU_MAX_INPUT_TOKENS = 10_000
BPU_MAX_OUTPUT_TOKENS = 16_000  # marge pour éviter troncature JSON (Unterminated string, ex. line 1399)
# Estimation conservatrice : ~3 caractères par token (français)
BPU_CHARS_PER_TOKEN_ESTIMATE = 3

# Chunking BPU : taille max par chunk (caractères) et recouvrement pour ne pas couper une ligne au milieu.
# Chunks plus petits = moins de prestations par réponse = JSON complet sous la limite de sortie.
BPU_CHUNK_MAX_CHARS = 10_000  # ~3.3k tokens entrée ; limite la sortie pour rester sous BPU_MAX_OUTPUT_TOKENS
BPU_CHUNK_OVERLAP_CHARS = 800


def _chunk_text_by_pages(text: str) -> list[str] | None:
    """
    Découpe le texte en chunks par page lorsque des marqueurs [[PAGE i / total]] / [[FIN PAGE ...]] sont présents.
    Retourne None si aucun marqueur trouvé (le caller fera un découpage par taille).
    """
    pattern = re.compile(r"\[\[PAGE\s+(\d+)\s*/\s*\d+\]\]", re.IGNORECASE)
    fin_pattern = re.compile(r"\[\[FIN\s+PAGE\s+\d+\s*/\s*\d+\]\]", re.IGNORECASE)
    if not pattern.search(text) and not fin_pattern.search(text):
        return None
    # Découper en gardant les blocs entre [[PAGE ...]] et [[FIN PAGE ...]] (ou début/fin de texte)
    parts = re.split(r"(\[\[(?:FIN\s+)?PAGE\s+\d+\s*/\s*\d+\]\])", text, flags=re.IGNORECASE)
    chunks = []
    current = []
    for i, part in enumerate(parts):
        current.append(part)
        if re.match(r"\[\[FIN\s+PAGE", part, re.IGNORECASE):
            chunk = "".join(current).strip()
            if chunk:
                chunks.append(chunk)
            current = []
    if current:
        chunk = "".join(current).strip()
        if chunk:
            chunks.append(chunk)
    return chunks if chunks else None


def chunk_text_for_bpu(text: str) -> list[str]:
    """
    Découpe le texte en chunks pour l'extraction BPU : d'abord par page ([[PAGE]]/[[FIN PAGE]])
    si présent, sinon par taille (BPU_CHUNK_MAX_CHARS) avec recouvrement (BPU_CHUNK_OVERLAP_CHARS).
    Retourne au moins un élément (texte entier si court).
    """
    text = text.strip()
    if not text:
        return []

    page_chunks = _chunk_text_by_pages(text)
    if page_chunks is not None:
        # Fusionner les pages trop petites pour limiter le nombre d'appels, tout en restant sous la limite
        merged = []
        acc = ""
        for c in page_chunks:
            if not acc:
                acc = c
            elif len(acc) + len(c) <= BPU_CHUNK_MAX_CHARS:
                acc = acc + "\n\n" + c
            else:
                merged.append(acc)
                acc = c
        if acc:
            merged.append(acc)
        return merged if merged else [text]

    if len(text) <= BPU_CHUNK_MAX_CHARS:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + BPU_CHUNK_MAX_CHARS
        if end < len(text):
            # Chercher un bon point de coupure (fin de ligne) dans la zone de recouvrement
            overlap_start = end - BPU_CHUNK_OVERLAP_CHARS
            search_zone = text[overlap_start:end]
            last_newline = search_zone.rfind("\n")
            if last_newline >= 0:
                end = overlap_start + last_newline + 1
            # sinon on coupe à end
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end
    return chunks if chunks else [text]


# Fonction pour générer le prompt à partir des attributs à chercher
def get_prompt_from_attributes(df_attributes: pd.DataFrame):
    question = """Extrait les informations clés et renvoie-les uniquement au format 
        JSON spécifié, sans texte supplémentaire.

        Format de réponse (commence par "{" et termine par "}") :
        {
    """
    for idx, row in df_attributes.iterrows():
        attr = row["attribut"]
        if idx != df_attributes.index[-1]:
            question += f"""  "{attr}": "", \n"""
        else:
            question += f"""  "{attr}": "" \n"""
    question += """}

  Instructions d'extraction :\n\n"""
    for idx, row in df_attributes.iterrows():
        consigne = row["consigne"]
        if idx != df_attributes.index[-1]:
            question += f"""{consigne}\n"""
        else:
            question += f"""{consigne}"""
    return question


def create_response_format(df_attributes, classification):
    df_filtered = select_attr(df_attributes, classification)

    # Schéma par défaut : type string
    default_schema = {"type": ["string", "null"]}

    # Construire le dictionnaire des propriétés avec les schémas appropriés
    properties = {}
    l_output_field = []

    root_defs = {}

    for idx, row in df_filtered.iterrows():
        output_field = row["output_field"]
        l_output_field.append(output_field)

        # Par défaut, utiliser le schéma string
        schema_to_use = default_schema

        # Si la colonne 'schema' existe et contient une valeur valide
        if "schema" in df_filtered.columns:
            schema_value = row.get("schema")

            if schema_value:
                if not isinstance(schema_value, dict):
                    raise ValueError(f"Schema must be a dict (field={output_field})")
                schema_to_use = schema_value.copy()

        # Remonter les $defs à la racine pour que les $ref (ex. #/$defs/prestationItem) soient résolus
        if isinstance(schema_to_use, dict) and "$defs" in schema_to_use:
            nested_defs = schema_to_use.pop("$defs")
            for def_name, def_schema in nested_defs.items():
                if def_name in root_defs and root_defs[def_name] != def_schema:
                    raise ValueError(f"Schema $defs name clash: '{def_name}' (field={output_field})")
                root_defs[def_name] = def_schema

        properties[output_field] = schema_to_use

    schema = {"type": "object", "properties": properties, "required": l_output_field}
    if root_defs:
        schema["$defs"] = root_defs

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": f"{classification}",
            "schema": schema,
            "strict": True,
        },
    }
    return response_format


def _get_prestations_only_response_format(document_type: str):
    """Construit le response_format pour une extraction prestations seule (chunks 2..N BPU)."""
    df = select_attr(ATTRIBUTES, document_type)
    row = df[df["output_field"] == "prestations"].iloc[0]
    schema_to_use = (row.get("schema") or {}).copy()
    root_defs = {}
    if isinstance(schema_to_use, dict) and "$defs" in schema_to_use:
        root_defs = schema_to_use.pop("$defs", {})
    schema = {
        "type": "object",
        "properties": {"prestations": schema_to_use},
        "required": ["prestations"],
    }
    if root_defs:
        schema["$defs"] = root_defs
    return {
        "type": "json_schema",
        "json_schema": {
            "name": f"{document_type}_prestations",
            "schema": schema,
            "strict": True,
        },
    }


def _get_prestations_only_prompt(document_type: str) -> str:
    """Prompt pour extraire uniquement la liste plate des prestations (fragment de BPU)."""
    df = select_attr(ATTRIBUTES, document_type)
    row = df[df["output_field"] == "prestations"].iloc[0]
    consigne = row["consigne"]
    return (
        "Extrait les informations clés et renvoie-les uniquement au format JSON spécifié, sans texte supplémentaire.\n\n"
        "Tu dois renvoyer UNIQUEMENT le champ « prestations » : liste plate des prestations/sections visibles dans ce fragment.\n"
        "Format : { \"prestations\": [ ... ] }\n\n"
        "Instructions d'extraction pour les prestations :\n\n"
        f"{consigne}"
    )


def analyze_file_text_llm_bpu_chunked(
    text: str, document_type: str, llm_model: str = "openweight-medium", temperature: float = 0.0
) -> dict:
    """
    Extraction BPU par chunking : plusieurs appels LLM (objet + premier chunk de prestations, puis prestations seules pour les chunks suivants), puis fusion des listes prestations.
    Réduit les timeouts et la longueur de sortie par appel.
    """
    chunks = chunk_text_for_bpu(text)
    if not chunks:
        raise ValueError("Le texte est vide après découpage.")

    n_chunks = len(chunks)
    logger.info(
        "BPU chunking: %s chunk(s), texte total ~%s car (est. ~%s tokens entrée)",
        n_chunks,
        len(text),
        len(text) // BPU_CHARS_PER_TOKEN_ESTIMATE,
    )

    llm_env = LLMClient()
    question_full = get_prompt_from_attributes(select_attr(ATTRIBUTES, document_type))
    response_format_full = create_response_format(ATTRIBUTES, document_type)

    # Premier chunk : objet + prestations
    system_prompt = "Vous êtes un assistant IA qui analyse des documents juridiques."
    user_prompt_0 = f"Analyse le contexte suivant et réponds à la question : {question_full}\n\nContexte : {chunks[0]}"
    messages_0 = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt_0}]
    chunk0_chars = len(user_prompt_0) + len(system_prompt)
    logger.info(
        "BPU chunk 1/%s (objet + prestations) - appel LLM, entrée ~%s car (~%s tokens)",
        n_chunks,
        chunk0_chars,
        chunk0_chars // BPU_CHARS_PER_TOKEN_ESTIMATE,
    )
    _t0 = time.perf_counter()
    response_0 = llm_env.ask_llm(
        messages_0,
        model=llm_model,
        response_format=response_format_full,
        temperature=temperature,
        max_tokens=BPU_MAX_OUTPUT_TOKENS,
    )
    _elapsed = time.perf_counter() - _t0
    all_prestations = list(response_0.get("prestations") or [])
    set_guid_on_flat_prestations(all_prestations)
    logger.info(
        "BPU chunk 1/%s terminé - %s prestations extraites (durée %.2fs)",
        n_chunks,
        len(all_prestations),
        _elapsed,
    )

    # Chunks suivants : prestations uniquement
    prestations_only_prompt = _get_prestations_only_prompt(document_type)
    prestations_only_format = _get_prestations_only_response_format(document_type)
    for i, chunk in enumerate(chunks[1:], start=2):
        user_prompt = (
            f"Ceci est un fragment (partie {i} sur {len(chunks)}) d'un bordereau de prix unitaires. "
            f"{prestations_only_prompt}\n\nContexte : {chunk}"
        )
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        chunk_chars = len(user_prompt) + len(system_prompt)
        logger.info(
            "BPU chunk %s/%s - appel LLM, entrée ~%s car (~%s tokens)",
            i,
            n_chunks,
            chunk_chars,
            chunk_chars // BPU_CHARS_PER_TOKEN_ESTIMATE,
        )
        _t0 = time.perf_counter()
        resp = llm_env.ask_llm(
            messages,
            model=llm_model,
            response_format=prestations_only_format,
            temperature=temperature,
            max_tokens=BPU_MAX_OUTPUT_TOKENS,
        )
        _elapsed = time.perf_counter() - _t0
        part = list(resp.get("prestations") or [])
        set_guid_on_flat_prestations(part)
        all_prestations.extend(part)
        logger.info(
            "BPU chunk %s/%s terminé - %s prestations (total %s) (durée %.2fs)",
            i,
            n_chunks,
            len(part),
            len(all_prestations),
            _elapsed,
        )

    logger.info("BPU fusion terminée - %s prestations au total", len(all_prestations))
    return {"objet": response_0.get("objet"), "prestations": all_prestations}


def analyze_file_text(text: str, document_type: str, llm_model: str = "openweight-medium", temperature: float = 0.0):
    """
    Analyse le texte pour extraire des informations.

    Pour les types BPU (bordereau_prix, decomposition_prix, detail_quantitatif_estimatif), utilise
    un extraction par chunking (plusieurs appels LLM puis fusion) pour éviter timeout et sortie trop longue.

    Args:
        text: Texte à analyser
        document_type: Type de document (détermine attributs et post-traitement)
        llm_model: Modèle LLM
        temperature: Température pour la génération (0.0 = déterministe)

    Returns:
        dict avec "llm_response" (réponse brute) et "structured_data" (après clean_llm_response)
    """
    text = text or ""
    if not text.strip():
        raise ValueError("Le texte est vide.")

    if document_type in BPU_DOC_TYPES:
        response = analyze_file_text_llm_bpu_chunked(text, document_type, llm_model, temperature)
    else:
        response = analyze_file_text_llm(text, document_type, llm_model, temperature)

    data = clean_llm_response(document_type, response)

    return {
        "llm_response": response,
        "structured_data": data,
    }


def analyze_file_text_llm(
    text: str, document_type: str, llm_model: str = "openweight-medium", temperature: float = 0.0
):
    llm_env = LLMClient()

    question = get_prompt_from_attributes(select_attr(ATTRIBUTES, document_type))
    response_format = create_response_format(ATTRIBUTES, document_type)

    if not text:
        raise ValueError("Le texte est vide.")

    system_prompt = "Vous êtes un assistant IA qui analyse des documents juridiques."
    user_prompt = f"Analyse le contexte suivant et réponds à la question : {question}\n\nContexte : {text}"

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

    response = llm_env.ask_llm(messages, model=llm_model, response_format=response_format, temperature=temperature)

    return response
