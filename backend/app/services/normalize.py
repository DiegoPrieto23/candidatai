"""Normalización de empresa, título y ubicación, y huella de una oferta (ver `DATA_MODEL.md`).

Todo es determinista y sin red: la misma oferta publicada con variaciones de formato («ACME,
S.A.» / «Acme S.L.», «(m/f/d)», «– Remote»…) debe dar la misma huella.
"""

import hashlib
import re
import unicodedata
from functools import lru_cache
from typing import Any

# Formas jurídicas, ya sin puntos y en minúsculas. Solo se quitan al final del nombre.
LEGAL_FORMS = frozenset(
    {
        "sl", "slu", "sll", "sa", "sau", "sc", "scoop", "scp", "cb", "sal",
        "gmbh", "ag", "kg", "ug", "se",
        "inc", "incorporated", "llc", "llp", "lp", "ltd", "limited", "plc",
        "corp", "corporation", "co", "company",
        "bv", "nv", "sarl", "sas", "srl", "spa", "oy", "ab", "as", "aps",
    }
)  # fmt: skip

_WORK_MODES = r"remote|remoto|en remoto|teletrabajo|hybrid|h[ií]brido|on-?site|presencial"
_SENIORITY = r"senior|junior|mid|mid-level|mid-senior|semi-?senior|ssr|sr\.?|jr\.?|trainee"
_GENDER = r"[a-z](?:\s*[/|]\s*[a-z]){1,3}|all genders|any gender|todos los g[eé]neros"

# Etiquetas genéricas entre paréntesis o corchetes: género, seniority o modalidad.
_GENERIC_TAG = re.compile(
    rf"[\(\[]\s*(?:{_GENDER}|{_SENIORITY}|(?:100\s*%\s*)?(?:{_WORK_MODES}))\s*[\)\]]",
    re.IGNORECASE,
)
# Sufijo de modalidad tras un separador: «Data Engineer – Remote», «… | Híbrido».
_WORK_MODE_SUFFIX = re.compile(
    rf"\s*[-–—|,:]\s*(?:100\s*%\s*)?(?:{_WORK_MODES})\s*$",
    re.IGNORECASE,
)
_ABBREVIATIONS = [
    (re.compile(r"\bsr\b\.?", re.IGNORECASE), "senior"),
    (re.compile(r"\bjr\b\.?", re.IGNORECASE), "junior"),
]
_SEGMENT_SEPARATOR = re.compile(r"[()\[\]]|\s[-–—|/]\s|\|")
_REMOTE_WORDS = re.compile(r"\b(?:remoto|en remoto|teletrabajo|remote)\b")


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _clean(value: str, keep: str = "") -> str:
    """Minúsculas, sin tildes, sin emojis ni signos (salvo `keep`) y con espacios simples."""
    value = _strip_accents(unicodedata.normalize("NFKC", value)).lower()
    value = "".join(ch if ch.isalnum() or ch in keep else " " for ch in value)
    return " ".join(value.split())


def fold(value: str, keep: str = "") -> str:
    """Forma comparable de un texto: minúsculas, sin tildes ni signos (salvo `keep`)."""
    return _clean(value, keep)


def normalize_company(name: str) -> str:
    """«ACME, S.A.» y «Acme S.L.» -> «acme»."""
    # Quitar los puntos antes de separar para que «S.L.U.» sea un solo token («slu»).
    tokens = _clean(name.replace(".", "")).split()
    while len(tokens) > 1 and tokens[-1] in LEGAL_FORMS:
        tokens.pop()
    return " ".join(tokens)


def normalize_title(title: str) -> str:
    """«Sr. Data Engineer – Remote» -> «senior data engineer»; «(m/f/d)» desaparece."""
    value = unicodedata.normalize("NFKC", title)
    value = _GENERIC_TAG.sub(" ", value)
    value = _WORK_MODE_SUFFIX.sub("", value.strip())
    for pattern, replacement in _ABBREVIATIONS:
        value = pattern.sub(replacement, value)
    # `+` y `#` distinguen tecnologías (C++, C#).
    return _clean(value, keep="+#")


def title_segments(title: str) -> list[str]:
    """Partes normalizadas de un título: lo de fuera y lo de dentro de cada paréntesis, y lo que
    separan « - », « | » o « / ».

    «Sales Engineer (Data Platform)» -> «sales engineer» y «data platform»;
    «Ingeniero/a de datos (Data Engineer)» -> «ingeniero a de datos» y «data engineer».
    """
    value = _GENERIC_TAG.sub(" ", unicodedata.normalize("NFKC", title))
    value = _WORK_MODE_SUFFIX.sub("", value.strip())
    parts = _SEGMENT_SEPARATOR.split(value)
    return [seg for part in parts if (seg := normalize_title(part))]


def _title_aliases() -> tuple[re.Pattern[str] | None, dict[str, str]]:
    from app.core.policies import get_title_aliases  # config/: solo al usarse

    # `get_title_aliases` devuelve el mismo diccionario mientras no se edite el fichero: se compila
    # una vez por versión, sin reconstruir la clave en cada título (el filtro previo pasa miles).
    aliases = get_title_aliases()
    if _COMPILED[0] is not aliases:
        frozen = tuple((k, tuple(v)) for k, v in aliases.items())
        _COMPILED[:] = [aliases, _compile_title_aliases(frozen)]
    return _COMPILED[1]


# El último diccionario leído y su compilación.
_COMPILED: list[Any] = [None, (None, {})]


@lru_cache(maxsize=4)
def _compile_title_aliases(
    frozen: tuple[tuple[str, tuple[str, ...]], ...],
) -> tuple[re.Pattern[str] | None, dict[str, str]]:
    """Una sola expresión con todas las formas (se buscan en una pasada: el filtro previo pasa
    miles de títulos) y la forma -> su puesto en inglés."""
    names: dict[str, str] = {}
    for name, aliases in frozen:
        for alias in aliases:
            if (key := fold(alias)) and fold(name):
                names.setdefault(key, fold(name))
    if not names:
        return None, names
    # Las variantes largas primero: «ingeniero de big data» antes que «ingeniero de datos».
    ordered = sorted(names, key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(map(re.escape, ordered)) + r")\b"), names


def translate_title(segment: str) -> str:
    """Un segmento normalizado con los puestos de `config/title_aliases.yaml` en inglés:
    «ingeniero de datos snowflake» -> «data engineer snowflake». Sin cambios si no hay ninguno."""
    pattern, names = _title_aliases()
    if pattern is None:
        return segment
    return pattern.sub(lambda m: names[m.group(0)], segment)


def role_forms(text: str) -> tuple[str, ...]:
    """Un puesto o una frase de título normalizados y, si cambia, también en inglés: así da igual
    en qué idioma lo escriba el usuario y en cuál la oferta («ingeniero de datos» y «data
    engineer» se comparan como «data engineer»)."""
    base = normalize_title(text)
    translated = " ".join(translate_title(base).split())
    return (base,) if translated == base else (base, translated)


def phrase_in_title(phrase: str, title: str) -> bool:
    """`phrase` como palabras completas dentro de `title`, sin importar tildes, mayúsculas ni el
    idioma de los puestos de `config/title_aliases.yaml`: «analista de datos» está en «Senior
    Data Analyst» y «data engineer» en «Ingeniera de datos»."""
    folded = fold(phrase)
    if not folded:
        return False
    if f" {folded} " in f" {fold(title)} ":
        return True
    translated = " ".join(translate_title(normalize_title(phrase)).split())
    if not translated:
        return False
    return f" {translated} " in f" {' '.join(translate_title(normalize_title(title)).split())} "


def normalize_location(location: str | None) -> str:
    """Minúsculas, sin tildes ni signos; las variantes de «remoto» pasan a «remote»."""
    if not location:
        return ""
    return _REMOTE_WORDS.sub("remote", _clean(location))


def fingerprint(company: str, title: str, location: str | None) -> str:
    """`sha256(normalized_company | normalized_title | normalized_location)` en hexadecimal."""
    key = "|".join(
        (normalize_company(company), normalize_title(title), normalize_location(location))
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
