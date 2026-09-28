"""Comprobaciones del entorno local para `jh doctor`."""

import shutil
import sys
import tempfile
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

from app.core.config import REPO_ROOT, Settings

MIN_PYTHON = (3, 12)
BUILTIN_TEMPLATES_DIR = REPO_ROOT / "templates"

WINDOWS_SOFFICE_PATHS = (
    Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
    Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
)


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


def find_soffice(configured: Path | None) -> Path | None:
    if configured is not None:
        return configured if configured.is_file() else None
    found = shutil.which("soffice")
    if found:
        return Path(found)
    return next((p for p in WINDOWS_SOFFICE_PATHS if p.is_file()), None)


def check_soffice(configured: Path | None) -> CheckResult:
    name = "LibreOffice"
    path = find_soffice(configured)
    if path is not None:
        return CheckResult(name=name, status=CheckStatus.OK, detail=str(path))
    if configured is not None:
        detail = f"SOFFICE_PATH apunta a {configured}, que no existe"
    else:
        detail = "no encontrado; instálalo o define SOFFICE_PATH (necesario para los PDF)"
    return CheckResult(name=name, status=CheckStatus.WARN, detail=detail)


def _template_ids(root: Path) -> list[str]:
    """Carpetas de `root` con un `template.yaml` (una plantilla cada una)."""
    if not root.is_dir():
        return []
    return sorted(d.name for d in root.iterdir() if (d / "template.yaml").is_file())


def check_cv_templates(builtin_dir: Path, user_dir: Path) -> CheckResult:
    """Plantillas de CV integradas (`templates/`) y del usuario (`data/templates/`). ADR-014."""
    name = "Plantillas de CV"
    builtin, own = _template_ids(builtin_dir), _template_ids(user_dir)
    if not builtin and not own:
        detail = (
            "aún no hay ninguna (las integradas llegan con la fase 08; necesarias para los CVs)"
        )
        return CheckResult(name=name, status=CheckStatus.WARN, detail=detail)
    parts = [f"integradas: {', '.join(builtin) or 'ninguna'}"]
    if own:
        parts.append(f"tuyas: {', '.join(own)}")
    return CheckResult(name=name, status=CheckStatus.OK, detail="; ".join(parts))


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
            check_embeddings(settings),
        ]
    )
