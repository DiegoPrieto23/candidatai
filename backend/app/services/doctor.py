"""Comprobaciones del entorno local para `jh doctor`."""

import shutil
import sys
import tempfile
import time
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

from app.core.config import REPO_ROOT, Settings
from app.services.documents import pdf

MIN_PYTHON = (3, 12)
BUILTIN_TEMPLATES_DIR = REPO_ROOT / "templates"


class CheckStatus(StrEnum):
    OK = "ok"
    WARN = "warn"
    ERROR = "error"


class CheckResult(BaseModel):
    name: str
    status: CheckStatus
    detail: str


class DoctorReport(BaseModel):
    checks: list[CheckResult]

    @property
    def ok(self) -> bool:
        return all(c.status != CheckStatus.ERROR for c in self.checks)


def check_python(version: tuple[int, ...] | None = None) -> CheckResult:
    if version is None:
        version = tuple(sys.version_info[:3])
    shown = ".".join(str(n) for n in version)
    if version[:2] >= MIN_PYTHON:
        return CheckResult(name="Python", status=CheckStatus.OK, detail=shown)
    wanted = ".".join(str(n) for n in MIN_PYTHON)
    return CheckResult(
        name="Python", status=CheckStatus.ERROR, detail=f"{shown}; se necesita {wanted} o superior"
    )


def check_data_dir(data_dir: Path) -> CheckResult:
    name = "Directorio de datos"
    if not data_dir.is_dir():
        return CheckResult(name=name, status=CheckStatus.ERROR, detail=f"{data_dir} no existe")
    try:
        with tempfile.TemporaryFile(dir=data_dir):
            pass
    except OSError as exc:
        return CheckResult(
            name=name, status=CheckStatus.ERROR, detail=f"{data_dir} no es escribible: {exc}"
        )
    return CheckResult(name=name, status=CheckStatus.OK, detail=f"{data_dir} (escribible)")


def check_soffice(configured: Path | None) -> CheckResult:
    name = "LibreOffice"
    path = pdf.find_soffice(configured)
    if path is not None:
        return CheckResult(name=name, status=CheckStatus.OK, detail=str(path))
    if configured is not None:
        detail = f"SOFFICE_PATH apunta a {configured}, que no existe"
    else:
        detail = "no encontrado; instálalo o define SOFFICE_PATH (necesario para los PDF)"
    return CheckResult(name=name, status=CheckStatus.WARN, detail=detail)


def check_cv_templates(builtin_dir: Path, user_dir: Path) -> CheckResult:
    """Plantillas de CV integradas (`templates/`) y del usuario (`data/templates/`). ADR-014."""
    from app.core.policies import get_policies
    from app.services.documents import templates

    name = "Plantillas de CV"
    found, invalid = templates.list_templates(builtin_dir, user_dir)
    builtin = [t.id for t in found if t.path.parent == builtin_dir]
    own = [t.id for t in found if t.path.parent != builtin_dir]
    fallback = get_policies().cv.fallback_template
    parts = [f"integradas: {', '.join(builtin) or 'ninguna'}"]
    if own:
        parts.append(f"tuyas: {', '.join(own)}")
    problems = []
    if invalid:
        problems.append(f"no válidas: {', '.join(i.id for i in invalid)} (jh templates list)")
    if fallback not in [t.id for t in found]:
        problems.append(
            f"falta «{fallback}», la de reserva: regenérala con scripts/build_builtin_templates.py"
        )
    status = CheckStatus.WARN if problems else CheckStatus.OK
    return CheckResult(name=name, status=status, detail="; ".join(parts + problems))


def check_pdf_conversion() -> CheckResult:
    """Renderiza `ats-simple` con el perfil demo y lo convierte a PDF de verdad (tarda unos s)."""
    from app.core.policies import get_policies
    from app.services.documents import templates
    from app.services.documents.preview import render_preview
    from app.services.profile import EXAMPLE_PATH, load_from_yaml

    name = "Conversión a PDF"
    converter = pdf.converter_name()
    if converter is None:
        return CheckResult(
            name=name,
            status=CheckStatus.WARN,
            detail="sin LibreOffice ni Word: no se pueden generar los PDF de los CVs",
        )
    fallback = get_policies().cv.fallback_template
    try:
        template = templates.get(fallback)
    except templates.TemplateNotFoundError as exc:
        return CheckResult(name=name, status=CheckStatus.WARN, detail=str(exc))
    workdir = Path(tempfile.mkdtemp(prefix="jh-doctor-"))
    start = time.monotonic()
    try:
        output = render_preview(template, load_from_yaml(EXAMPLE_PATH), workdir / "doctor.pdf")
        info = pdf.read_pdf(output)
    except Exception as exc:  # cualquier fallo del conversor se enseña tal cual
        return CheckResult(
            name=name, status=CheckStatus.ERROR, detail=f"{converter}: {exc}".strip()
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    seconds = time.monotonic() - start
    detail = f"{converter}: «{fallback}» → PDF de {info.pages} pág. en {seconds:.0f} s"
    missing = pdf.missing_fonts(template.meta.fonts, info.fonts)
    if missing:
        detail += f"; falta la fuente {', '.join(missing)} y el PDF usa otra"
        return CheckResult(name=name, status=CheckStatus.WARN, detail=detail)
    return CheckResult(name=name, status=CheckStatus.OK, detail=detail)


def check_photo(profile_path: Path, data_dir: Path) -> CheckResult:
    """Avisa si el perfil puede pedir foto (plantilla con foto y política que la deja) y no hay."""
    from app.services import profile as profile_service
    from app.services.documents import photo, templates

    name = "Foto del CV"
    if not profile_path.is_file():
        return CheckResult(name=name, status=CheckStatus.OK, detail="sin perfil: no se comprueba")
    try:
        profile = profile_service.load_from_yaml(profile_path)
    except Exception as exc:  # perfil a medio escribir: lo explica `jh profile validate`
        detail = f"no se puede leer el perfil ({type(exc).__name__}); usa jh profile validate"
        return CheckResult(name=name, status=CheckStatus.WARN, detail=detail)

    found = photo.find_photo(profile, data_dir)
    if found is not None:
        return CheckResult(name=name, status=CheckStatus.OK, detail=str(found))
    prefs = profile.preferences.cv
    policy = prefs.photo_policy
    wanted = [prefs.default_template] if prefs.default_template else []
    wanted += [rule.use for rule in prefs.template_rules]
    with_photo = []
    for template_id in dict.fromkeys(wanted):
        try:
            if templates.get(template_id).meta.photo.supported:
                with_photo.append(template_id)
        except templates.TemplateNotFoundError:
            continue
    if with_photo and (policy.default or any(policy.by_country.values())):
        detail = (
            f"tu perfil usa {', '.join(with_photo)}, con foto, pero no hay "
            f"data/{prefs.photo_file} ni data/photo.*: esos CVs saldrán sin foto"
        )
        return CheckResult(name=name, status=CheckStatus.WARN, detail=detail)
    return CheckResult(name=name, status=CheckStatus.OK, detail="tus plantillas no piden foto")


def check_embeddings(settings: Settings) -> CheckResult:
    from app.core.policies import get_policies
    from app.services.matching import embeddings

    name = "Embeddings"
    reason = embeddings.unavailable_reason()
    if reason is not None:
        detail = f"{reason} El score se calcula sin similitud semántica."
        return CheckResult(name=name, status=CheckStatus.WARN, detail=detail)
    model = get_policies().scoring.semantic.model
    return CheckResult(
        name=name, status=CheckStatus.OK, detail=f"{model} (caché en {settings.models_dir})"
    )


def run_doctor(settings: Settings) -> DoctorReport:
    return DoctorReport(
        checks=[
            check_python(),
            check_data_dir(settings.data_dir),
            check_soffice(settings.soffice_path),
            check_cv_templates(BUILTIN_TEMPLATES_DIR, settings.user_templates_dir),
            check_pdf_conversion(),
            check_photo(settings.data_dir / "profile.yaml", settings.data_dir),
            check_embeddings(settings),
        ]
    )
