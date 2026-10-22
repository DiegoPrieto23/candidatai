"""DOCX → PDF y lectura del PDF (páginas, texto y fuentes).

Conversión con LibreOffice headless (`SOFFICE_PATH`, `soffice` o `libreoffice` en el `PATH`, o las
rutas típicas de Windows, macOS y Linux, fase 26.1) y,
si no está, con Microsoft Word a través de `docx2pdf` (extra opcional `word`). Cada conversión de
LibreOffice usa un perfil temporal propio, para no chocar con un LibreOffice abierto ni dejar
restos, y tiene un tiempo máximo: si se agota, se mata el proceso y todos sus hijos.
"""

import contextlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from app.core.config import get_settings
from app.core.policies import get_policies
from app.services.normalize import fold

WINDOWS_SOFFICE_PATHS = (
    Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
    Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
)
MACOS_SOFFICE_PATHS = (
    Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
    Path.home() / "Applications" / "LibreOffice.app" / "Contents" / "MacOS" / "soffice",
)
# Sin Flatpak ni Snap: su sandbox no ve el /tmp del sistema, donde se hace la conversión (y Snap
# tampoco las carpetas ocultas de tu home, como la de datos). El PDF lo hace Chromium si no hay
# otro LibreOffice.
LINUX_SOFFICE_PATHS = (
    Path("/usr/lib/libreoffice/program/soffice"),
    Path("/opt/libreoffice/program/soffice"),
)
SOFFICE_NAMES = ("soffice", "libreoffice")
SANDBOXED = ("/snap/", "/var/lib/flatpak/")  # en el `PATH`, pero no servirían (ver arriba)

Converter = Callable[[Path, Path, int], None]  # (docx, pdf, timeout_s)


class PdfConversionError(RuntimeError):
    pass


class PdfConverterUnavailableError(PdfConversionError):
    pass


def find_soffice(configured: Path | None) -> Path | None:
    if configured is not None:
        return configured if configured.is_file() else None
    for name in SOFFICE_NAMES:
        found = shutil.which(name)
        if found and not found.startswith(SANDBOXED):
            return Path(found)
    return next((p for p in _typical_paths() if p.is_file()), None)


def _typical_paths() -> tuple[Path, ...]:
    if sys.platform == "win32":
        return WINDOWS_SOFFICE_PATHS
    if sys.platform == "darwin":
        return MACOS_SOFFICE_PATHS
    # El paquete oficial de LibreOffice se instala en /opt/libreoffice<versión>.
    return (*LINUX_SOFFICE_PATHS, *sorted(Path("/opt").glob("libreoffice*/program/soffice")))


def _kill_tree(process: subprocess.Popen[bytes]) -> None:
    # En Windows, soffice.exe lanza soffice.bin: matar solo al padre dejaría el hijo vivo.
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            capture_output=True,
            check=False,
        )
    else:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, 9)
    with contextlib.suppress(Exception):
        process.wait(timeout=10)


def libreoffice_converter(soffice: Path) -> Converter:
    def convert(docx: Path, pdf: Path, timeout: int) -> None:
        workdir = Path(tempfile.mkdtemp(prefix="cai-soffice-"))
        try:
            profile = (workdir / "profile").resolve().as_uri()
            outdir = workdir / "out"
            outdir.mkdir()
            args = [
                str(soffice),
                f"-env:UserInstallation={profile}",
                "--headless",
                "--invisible",
                "--nologo",
                "--norestore",
                "--nolockcheck",
                "--convert-to",
                "pdf",
                "--outdir",
                str(outdir),
                str(docx),
            ]
            kwargs: dict[str, object] = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            else:
                kwargs["start_new_session"] = True
            process = subprocess.Popen(  # noqa: S603 - ruta del ejecutable configurada por el usuario
                args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs
            )
            try:
                _out, err = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                _kill_tree(process)
                raise PdfConversionError(
                    f"LibreOffice no terminó la conversión en {timeout} s."
                ) from exc
            produced = outdir / f"{docx.stem}.pdf"
            if process.returncode != 0 or not produced.is_file():
                detail = err.decode(errors="replace").strip()[:300]
                raise PdfConversionError(
                    f"LibreOffice no generó el PDF (código {process.returncode}). {detail}".strip()
                )
            pdf.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(produced), pdf)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    return convert


def word_converter() -> Converter | None:
    if sys.platform != "win32":
        return None
    try:
        from docx2pdf import convert as docx2pdf_convert  # type: ignore[import-not-found]
    except ImportError:
        return None

    def convert(docx: Path, pdf: Path, _timeout: int) -> None:
        pdf.parent.mkdir(parents=True, exist_ok=True)
        try:
            docx2pdf_convert(str(docx), str(pdf))
        except Exception as exc:  # COM de Word: cualquier fallo se explica igual
            raise PdfConversionError(f"Word no pudo convertir el documento: {exc}") from exc
        if not pdf.is_file():
            raise PdfConversionError("Word no generó el PDF.")

    return convert


def converter_name() -> str | None:
    """Qué se usará para convertir: `LibreOffice (<ruta>)`, `Microsoft Word` o `None`."""
    soffice = find_soffice(get_settings().soffice_path)
    if soffice is not None:
        return f"LibreOffice ({soffice})"
    return "Microsoft Word" if word_converter() is not None else None


def get_converter() -> Converter:
    soffice = find_soffice(get_settings().soffice_path)
    if soffice is not None:
        return libreoffice_converter(soffice)
    word = word_converter()
    if word is not None:
        return word
    raise PdfConverterUnavailableError(
        "No hay con qué convertir a PDF: instala LibreOffice (o define SOFFICE_PATH) o, en "
        "Windows con Word, `uv sync --extra word`. Comprueba con `cai doctor`."
    )


def convert(docx: Path, pdf: Path) -> Path:
    """Convierte `docx` en `pdf` con el conversor disponible."""
    get_converter()(docx, pdf, get_policies().cv.pdf_timeout_seconds)
    return pdf


# --- Lectura del PDF ------------------------------------------------------------------------

_SUBSET_PREFIX = re.compile(r"^[A-Z]{6}\+")


class PdfInfo:
    def __init__(self, pages: int, text: str, fonts: list[str]) -> None:
        self.pages = pages
        self.text = text
        self.fonts = fonts


def read_pdf(path: Path) -> PdfInfo:
    from pypdf import PdfReader  # solo al leer un PDF, no al arrancar

    reader = PdfReader(path)
    fonts: set[str] = set()
    texts = []
    for page in reader.pages:
        texts.append(page.extract_text() or "")
        resources = page.get("/Resources")
        font_dict = resources.get_object().get("/Font") if resources else None
        if not font_dict:
            continue
        for ref in font_dict.get_object().values():
            base = ref.get_object().get("/BaseFont")
            if base:
                fonts.add(_SUBSET_PREFIX.sub("", str(base).lstrip("/")))
    return PdfInfo(pages=len(reader.pages), text="\n".join(texts), fonts=sorted(fonts))


def _font_key(name: str) -> str:
    return fold(name).replace(" ", "")


def missing_fonts(expected: list[str], pdf_fonts: list[str]) -> list[str]:
    """Fuentes de la plantilla que no aparecen en el PDF (el conversor usó otra en su lugar).

    En el PDF las fuentes llevan el estilo pegado (`Calibri-Bold`, `SourceSans3-Regular`): basta
    con que alguna empiece por el nombre de la fuente sin espacios.
    """
    available = [_font_key(f) for f in pdf_fonts]
    return [f for f in expected if not any(a.startswith(_font_key(f)) for a in available)]
