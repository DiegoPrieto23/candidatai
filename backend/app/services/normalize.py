"""Normalización de empresa, título y ubicación, y huella de una oferta (ver `DATA_MODEL.md`).

Todo es determinista y sin red: la misma oferta publicada con variaciones de formato («ACME,
S.A.» / «Acme S.L.», «(m/f/d)», «– Remote»…) debe dar la misma huella.
"""

import hashlib
import re
import unicodedata

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
_REMOTE_WORDS = re.compile(r"\b(?:remoto|en remoto|teletrabajo|remote)\b")


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _clean(value: str, keep: str = "") -> str:
    """Minúsculas, sin tildes, sin emojis ni signos (salvo `keep`) y con espacios simples."""
    value = _strip_accents(unicodedata.normalize("NFKC", value)).lower()
    value = "".join(ch if ch.isalnum() or ch in keep else " " for ch in value)
    return " ".join(value.split())


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
