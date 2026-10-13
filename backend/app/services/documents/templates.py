"""Registro de plantillas de CV: integradas (`templates/`) y del usuario (`data/templates/`).

Cada plantilla es una carpeta con `template.yaml` (`TemplateMeta`) y los ficheros de su motor. Si
una del usuario tiene el mismo `id` que una integrada, gana la del usuario.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ValidationError

from app.core.config import REPO_ROOT, get_settings
from app.core.validation import describe_error
from app.schemas.cv import TemplateMeta

BUILTIN_TEMPLATES_DIR = REPO_ROOT / "templates"
META_FILE = "template.yaml"

# Ficheros obligatorios de cada motor; el primero es el que se renderiza.
ENGINE_FILES: dict[str, tuple[str, ...]] = {
    "docx": ("template.docx",),
    "html": ("template.html", "style.css"),
}

# Variables de primer nivel del contrato (docs/CV_TEMPLATES.md §Contrato de variables).
CONTRACT_VARIABLES = frozenset(
    {
        "name",
        "subtitle",
        "summary",
        "contact",
        "photo",
        "experience",
        "projects",
        "education",
        "certifications",
        "extra_sections",
        "skills",
        "languages",
        "labels",
        "accent_color",
        "show",
    }
)

Kind = Literal["cv", "letter"]
LETTER_CSS = "letter.css"  # motor html: estilos propios de la carta (no cuentan para el CV)

# Variables de la carta (fase 08c): la cabecera del CV y lo propio de la carta.
LETTER_CONTRACT_VARIABLES = frozenset(
    {
        "name",
        "subtitle",
        "contact",
        "photo",
        "accent_color",
        "labels",
        "date",
        "place",
        "recipient",
        "greeting",
        "paragraphs",
        "sign_off",
    }
)

# No cuentan para el hash: se generan a partir de la plantilla o son el original importado.
_NOT_HASHED_PREFIXES = ("preview.", "source.")


class TemplateNotFoundError(LookupError):
    pass


class TemplateIssue(BaseModel):
    field: str
    reason: str


class TemplateInvalidError(ValueError):
    def __init__(self, template_id: str, issues: list[TemplateIssue]) -> None:
        self.template_id = template_id
        self.issues = issues
        detail = "; ".join(f"{i.field}: {i.reason}" for i in issues)
        super().__init__(f"La plantilla «{template_id}» no es válida: {detail}")


def _filler(line: bytes) -> bool:
    """Línea vacía o comentario en la columna 0."""
    stripped = line.strip()
    return not stripped or (stripped.startswith(b"#") and line[:1] == b"#")


def _indented(line: bytes) -> bool:
    return line[:1] in (b" ", b"	")


def without_letter_block(meta_yaml: bytes) -> bytes:
    """`template.yaml` sin el bloque `letter:` de primer nivel: el CV no depende de él.

    El bloque es la línea `letter:` y las que siguen indentadas, también con líneas vacías o de
    comentario en medio si después sigue el bloque. Un flujo (`letter: {file: …}`) va en una línea.
    """
    lines = meta_yaml.splitlines(keepends=True)
    out: list[bytes] = []
    i = 0
    while i < len(lines):
        if not lines[i].startswith(b"letter:"):
            out.append(lines[i])
            i += 1
            continue
        i += 1
        while i < len(lines):
            if _indented(lines[i]):
                i += 1
                continue
            j = i
            while j < len(lines) and _filler(lines[j]):
                j += 1
            if j > i and j < len(lines) and _indented(lines[j]):
                i = j  # lo vacío de en medio es parte del bloque
                continue
            break
    return b"".join(out)


@dataclass(frozen=True)
class Template:
    meta: TemplateMeta
    path: Path

    @property
    def id(self) -> str:
        return self.meta.id

    @property
    def engine_file(self) -> Path:
        return self.path / ENGINE_FILES[self.meta.engine][0]

    @property
    def letter_file(self) -> Path | None:
        """El diseño de carta (fase 08c), si lo tiene."""
        return self.path / self.meta.letter.file if self.meta.letter else None

    def file_hash(self, kind: Kind = "cv") -> str:
        """sha256 de los ficheros (sin previews ni original): ¿cambió tras un render?

        El del CV no mira `letter.*` y el de la carta no mira `template.*`: añadir o retocar la
        carta no marca como cambiados los CVs ya renderizados, ni al revés.
        """
        other = ("letter.",) if kind == "cv" else ("template.docx", "template.html")
        skip = _NOT_HASHED_PREFIXES + other
        digest = hashlib.sha256()
        for file in sorted(p for p in self.path.rglob("*") if p.is_file()):
            relative = file.relative_to(self.path).as_posix()
            if relative.startswith(skip):
                continue
            data = file.read_bytes()
            if kind == "cv" and relative == META_FILE:
                data = without_letter_block(data)
            digest.update(relative.encode())
            digest.update(b"\0")
            digest.update(data)
            digest.update(b"\0")
        return digest.hexdigest()


class InvalidTemplate(BaseModel):
    """Una carpeta con `template.yaml` que no se puede usar, y por qué."""

    id: str
    path: str
    reason: str


def _roots(builtin_dir: Path | None, user_dir: Path | None) -> list[Path]:
    # En orden de prioridad creciente: la del usuario, al final, sustituye a la integrada.
    return [
        builtin_dir or BUILTIN_TEMPLATES_DIR,
        user_dir or get_settings().user_templates_dir,
    ]


def load_meta(folder: Path) -> TemplateMeta:
    try:
        with (folder / META_FILE).open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        issue = TemplateIssue(field=META_FILE, reason=f"YAML mal formado: {exc}")
        raise TemplateInvalidError(folder.name, [issue]) from exc
    try:
        meta = TemplateMeta.model_validate(data)
    except ValidationError as exc:
        issues = []
        for error in exc.errors(include_url=False):
            _received, reason = describe_error(error)
            loc = ".".join(str(p) for p in error["loc"]) or META_FILE
            issues.append(TemplateIssue(field=loc, reason=reason))
        raise TemplateInvalidError(folder.name, issues) from exc
    problems = []
    if meta.id != folder.name:
        problems.append(
            TemplateIssue(field="id", reason=f"Debe coincidir con la carpeta («{folder.name}»).")
        )
    required = list(ENGINE_FILES[meta.engine]) if meta.kind == "cv" else []
    if meta.letter:
        required.append(meta.letter.file)
        if meta.engine == "html":
            required.append("style.css")
    for name in dict.fromkeys(required):
        if not (folder / name).is_file():
            problems.append(
                TemplateIssue(field=name, reason=f"Falta el fichero del motor {meta.engine}.")
            )
    if problems:
        raise TemplateInvalidError(folder.name, problems)
    return meta


def _scan(
    builtin_dir: Path | None, user_dir: Path | None
) -> tuple[dict[str, Template], dict[str, InvalidTemplate]]:
    found: dict[str, Template] = {}
    invalid: dict[str, InvalidTemplate] = {}
    for root in _roots(builtin_dir, user_dir):
        if not root.is_dir():
            continue
        for folder in sorted(p for p in root.iterdir() if (p / META_FILE).is_file()):
            try:
                meta = load_meta(folder)
            except TemplateInvalidError as exc:
                invalid[folder.name] = InvalidTemplate(
                    id=folder.name, path=str(folder), reason=str(exc)
                )
                # Una del usuario rota no deja pasar en silencio la integrada del mismo id.
                found.pop(folder.name, None)
                continue
            invalid.pop(meta.id, None)
            found[meta.id] = Template(meta=meta, path=folder)
    return found, invalid


def _usable(template: Template, kind: Kind) -> bool:
    """De CV: las de `kind: cv`. De carta: las que tienen diseño de carta (`letter`)."""
    return template.meta.kind == "cv" if kind == "cv" else template.meta.letter is not None


def list_templates(
    builtin_dir: Path | None = None, user_dir: Path | None = None, kind: Kind = "cv"
) -> tuple[list[Template], list[InvalidTemplate]]:
    """Plantillas utilizables (ordenadas por `id`) y las que tienen algún problema."""
    found, invalid = _scan(builtin_dir, user_dir)
    usable = [found[k] for k in sorted(found) if _usable(found[k], kind)]
    return usable, [invalid[k] for k in sorted(invalid)]


def get(
    template_id: str,
    builtin_dir: Path | None = None,
    user_dir: Path | None = None,
    kind: Kind | None = "cv",
) -> Template:
    """Una plantilla de CV (`kind="cv"`), con diseño de carta (`"letter"`) o cualquiera (`None`)."""
    found, invalid = _scan(builtin_dir, user_dir)
    if template_id in found and (kind is None or _usable(found[template_id], kind)):
        return found[template_id]
    if template_id in found:
        what = "de CV" if kind == "cv" else "con diseño de carta"
        raise TemplateNotFoundError(f"«{template_id}» no es una plantilla {what}.")
    if template_id in invalid:
        raise TemplateNotFoundError(invalid[template_id].reason)
    available = ", ".join(sorted(found)) or "ninguna"
    raise TemplateNotFoundError(
        f"La plantilla «{template_id}» no existe. Disponibles: {available}."
    )


def undeclared_variables(template: Template, file: Path | None = None) -> set[str]:
    """Variables de primer nivel que usa la plantilla (o su `file`, p. ej. la carta)."""
    file = file or template.engine_file
    if template.meta.engine == "html":
        from jinja2 import Environment, meta

        source = file.read_text(encoding="utf-8")
        return set(meta.find_undeclared_variables(Environment().parse(source)))
    from docxtpl import DocxTemplate

    return set(DocxTemplate(file).get_undeclared_template_variables())


def unsafe_content(template: Template) -> list[TemplateIssue]:
    """Motor html: lo que el saneado no admite en `template.html` y `style.css`, con su línea."""
    if template.meta.engine != "html":
        return []
    from app.services.documents import sanitize

    issues = []
    names = list(ENGINE_FILES["html"]) if template.meta.kind == "cv" else ["style.css"]
    if template.meta.letter:
        names.append(template.meta.letter.file)
        if (template.path / LETTER_CSS).is_file():  # estilos propios de la carta, opcionales
            names.append(LETTER_CSS)
    for name in names:
        text = (template.path / name).read_text(encoding="utf-8")
        for finding in sanitize.scan(text, name):
            issues.append(
                TemplateIssue(
                    field=f"{finding.file}:{finding.line}",
                    reason=f"No se admite {finding.what} (solo recursos locales, sin scripts).",
                )
            )
    return issues


def validate(
    template_id: str,
    builtin_dir: Path | None = None,
    user_dir: Path | None = None,
    kind: Kind | None = "cv",
) -> Template:
    """Comprueba `template.yaml`, los ficheros del motor y que solo use variables del contrato
    (el de la carta en `letter.*`). `kind=None`: cualquier plantilla (`cai templates validate`)."""
    template = get(template_id, builtin_dir, user_dir, kind)
    try:
        unsafe = unsafe_content(template)
    except (OSError, UnicodeError) as exc:
        issue = TemplateIssue(field=template.engine_file.name, reason=f"No se puede leer: {exc}")
        raise TemplateInvalidError(template_id, [issue]) from exc
    if unsafe:
        raise TemplateInvalidError(template_id, unsafe)
    files: list[tuple[Path, frozenset[str]]] = []
    if template.meta.kind == "cv":
        files.append((template.engine_file, CONTRACT_VARIABLES))
    if template.letter_file is not None:
        files.append((template.letter_file, LETTER_CONTRACT_VARIABLES))
    for file, contract in files:
        try:
            unknown = sorted(undeclared_variables(template, file) - contract)
        except Exception as exc:  # docxtpl/jinja2: marcador mal formado o fichero ilegible
            issue = TemplateIssue(field=file.name, reason=f"No se puede leer: {exc}")
            raise TemplateInvalidError(template_id, [issue]) from exc
        if unknown:
            issue = TemplateIssue(
                field=file.name,
                reason=f"Usa variables fuera del contrato: {', '.join(unknown)}.",
            )
            raise TemplateInvalidError(template_id, [issue])
    return template
