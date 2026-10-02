"""Registro de plantillas de CV: integradas (`templates/`) y del usuario (`data/templates/`).

Cada plantilla es una carpeta con `template.yaml` (`TemplateMeta`) y los ficheros de su motor. Si
una del usuario tiene el mismo `id` que una integrada, gana la del usuario.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

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

    def file_hash(self) -> str:
        """sha256 de los ficheros (sin previews ni original): ¿cambió tras un render?"""
        digest = hashlib.sha256()
        for file in sorted(p for p in self.path.rglob("*") if p.is_file()):
            relative = file.relative_to(self.path).as_posix()
            if relative.startswith(_NOT_HASHED_PREFIXES):
                continue
            digest.update(relative.encode())
            digest.update(b"\0")
            digest.update(file.read_bytes())
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
    for name in ENGINE_FILES[meta.engine]:
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


def list_templates(
    builtin_dir: Path | None = None, user_dir: Path | None = None
) -> tuple[list[Template], list[InvalidTemplate]]:
    """Plantillas utilizables (ordenadas por `id`) y las que tienen algún problema."""
    found, invalid = _scan(builtin_dir, user_dir)
    return [found[k] for k in sorted(found)], [invalid[k] for k in sorted(invalid)]


def get(
    template_id: str, builtin_dir: Path | None = None, user_dir: Path | None = None
) -> Template:
    found, invalid = _scan(builtin_dir, user_dir)
    if template_id in found:
        return found[template_id]
    if template_id in invalid:
        raise TemplateNotFoundError(invalid[template_id].reason)
    available = ", ".join(sorted(found)) or "ninguna"
    raise TemplateNotFoundError(
        f"La plantilla «{template_id}» no existe. Disponibles: {available}."
    )


def undeclared_variables(template: Template) -> set[str]:
    """Variables de primer nivel que usa la plantilla (sin las que define ella misma)."""
    if template.meta.engine == "html":
        from jinja2 import Environment, meta

        source = template.engine_file.read_text(encoding="utf-8")
        return set(meta.find_undeclared_variables(Environment().parse(source)))
    from docxtpl import DocxTemplate

    return set(DocxTemplate(template.engine_file).get_undeclared_template_variables())


def unsafe_content(template: Template) -> list[TemplateIssue]:
    """Motor html: lo que el saneado no admite en `template.html` y `style.css`, con su línea."""
    if template.meta.engine != "html":
        return []
    from app.services.documents import sanitize

    issues = []
    for name in ENGINE_FILES["html"]:
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
    template_id: str, builtin_dir: Path | None = None, user_dir: Path | None = None
) -> Template:
    """Comprueba `template.yaml`, los ficheros del motor y que solo use variables del contrato."""
    template = get(template_id, builtin_dir, user_dir)
    try:
        unsafe = unsafe_content(template)
    except (OSError, UnicodeError) as exc:
        issue = TemplateIssue(field=template.engine_file.name, reason=f"No se puede leer: {exc}")
        raise TemplateInvalidError(template_id, [issue]) from exc
    if unsafe:
        raise TemplateInvalidError(template_id, unsafe)
    try:
        unknown = sorted(undeclared_variables(template) - CONTRACT_VARIABLES)
    except Exception as exc:  # docxtpl/jinja2: marcador mal formado o fichero ilegible
        issue = TemplateIssue(field=template.engine_file.name, reason=f"No se puede leer: {exc}")
        raise TemplateInvalidError(template_id, [issue]) from exc
    if unknown:
        issue = TemplateIssue(
            field=template.engine_file.name,
            reason=f"Usa variables fuera del contrato: {', '.join(unknown)}.",
        )
        raise TemplateInvalidError(template_id, [issue])
    return template
