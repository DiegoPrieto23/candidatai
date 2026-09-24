"""Comprobaciones del entorno local para `jh doctor`."""

import shutil
import sys
import tempfile
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

from app.core.config import Settings

MIN_PYTHON = (3, 12)

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


def check_cv_template(template: Path) -> CheckResult:
    name = "Plantilla de CV"
    if template.is_file():
        return CheckResult(name=name, status=CheckStatus.OK, detail=str(template))
    return CheckResult(
        name=name,
        status=CheckStatus.WARN,
        detail=f"no hay {template.name} en {template.parent} (necesaria para generar CVs)",
    )


def run_doctor(settings: Settings) -> DoctorReport:
    return DoctorReport(
        checks=[
            check_python(),
            check_data_dir(settings.data_dir),
            check_soffice(settings.soffice_path),
            check_cv_template(settings.cv_template_path),
        ]
    )
