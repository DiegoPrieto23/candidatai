import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app import cli
from app.core.config import get_settings
from app.services import doctor
from app.services.doctor import CheckStatus, run_doctor
from app.services.documents import pdf
from tests.cv_support import fake_converter, requires_chromium, write_template

runner = CliRunner()


@pytest.fixture
def no_system_soffice(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Simula una máquina sin LibreOffice ni Word, independientemente de la real."""
    monkeypatch.setattr(pdf, "word_converter", lambda: None)
    monkeypatch.setattr(pdf.shutil, "which", lambda _name: None)
    monkeypatch.setattr(pdf, "WINDOWS_SOFFICE_PATHS", (tmp_path / "missing.exe",))


def test_check_python() -> None:
    assert doctor.check_python((3, 12, 4)).status == CheckStatus.OK
    assert doctor.check_python((3, 11, 9)).status == CheckStatus.ERROR
    assert doctor.check_python().status == CheckStatus.OK


def test_check_data_dir(tmp_path: Path) -> None:
    assert doctor.check_data_dir(tmp_path).status == CheckStatus.OK
    assert doctor.check_data_dir(tmp_path / "nope").status == CheckStatus.ERROR


def test_check_data_dir_not_writable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def deny(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("acceso denegado")

    monkeypatch.setattr(doctor.tempfile, "TemporaryFile", deny)
    result = doctor.check_data_dir(tmp_path)
    assert result.status == CheckStatus.ERROR
    assert "no es escribible" in result.detail


@pytest.mark.usefixtures("no_system_soffice")
def test_soffice_missing_is_a_warning() -> None:
    assert doctor.check_soffice(None).status == CheckStatus.WARN


def test_soffice_from_env(tmp_path: Path) -> None:
    exe = tmp_path / "soffice.exe"
    assert doctor.check_soffice(exe).status == CheckStatus.WARN
    exe.touch()
    assert doctor.check_soffice(exe) == doctor.CheckResult(
        name="LibreOffice", status=CheckStatus.OK, detail=str(exe)
    )


def test_cv_templates(tmp_path: Path) -> None:
    builtin, own = tmp_path / "templates", tmp_path / "data" / "templates"
    check = doctor.check_cv_templates(builtin, own)
    assert check.status == CheckStatus.WARN
    assert "falta «ats-simple»" in check.detail
    write_template(builtin, "ats-simple", origin="builtin")
    (builtin / "sin-yaml").mkdir()  # una carpeta sin template.yaml no cuenta
    check = doctor.check_cv_templates(builtin, own)
    assert (check.status, check.detail) == (CheckStatus.OK, "integradas: ats-simple")
    write_template(own, "mi-cv")
    assert doctor.check_cv_templates(builtin, own).detail == "integradas: ats-simple; tuyas: mi-cv"
    (own / "rota").mkdir()
    (own / "rota" / "template.yaml").write_text("id: rota\n", encoding="utf-8")
    check = doctor.check_cv_templates(builtin, own)
    assert check.status == CheckStatus.WARN
    assert check.detail.endswith("no válidas: rota (jh templates list)")


def test_pdf_conversion_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf, "converter_name", lambda: "Falso")
    monkeypatch.setattr(pdf, "get_converter", lambda: fake_converter())
    check = doctor.check_pdf_conversion()
    assert check.status == CheckStatus.OK
    assert check.detail.startswith("Falso: «ats-simple» → PDF de 1 pág.")


def test_pdf_conversion_font_substituted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf, "converter_name", lambda: "Falso")
    monkeypatch.setattr(pdf, "get_converter", lambda: fake_converter(font="Carlito"))
    check = doctor.check_pdf_conversion()
    assert check.status == CheckStatus.WARN and "Calibri" in check.detail


def test_pdf_conversion_without_converter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf, "converter_name", lambda: None)
    assert doctor.check_pdf_conversion().status == CheckStatus.WARN


def test_pdf_conversion_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(_docx: Path, _pdf: Path, _timeout: int) -> None:
        raise pdf.PdfConversionError("LibreOffice no terminó la conversión en 60 s.")

    monkeypatch.setattr(pdf, "converter_name", lambda: "Falso")
    monkeypatch.setattr(pdf, "get_converter", lambda: broken)
    check = doctor.check_pdf_conversion()
    assert (check.status, check.detail) == (
        CheckStatus.ERROR,
        "Falso: LibreOffice no terminó la conversión en 60 s.",
    )


def demo_profile_file(tmp_path: Path, **cv: object) -> Path:
    import yaml

    from app.services.profile import EXAMPLE_PATH

    data = yaml.safe_load(EXAMPLE_PATH.read_text(encoding="utf-8"))
    data["preferences"]["cv"].update(cv)
    path = tmp_path / "profile.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def test_photo_check(tmp_path: Path) -> None:
    from app.core.config import REPO_ROOT

    data = tmp_path / "data"
    data.mkdir()
    assert doctor.check_photo(data / "profile.yaml", data).detail == "sin perfil: no se comprueba"

    # El perfil demo usa `clasica-foto` y la política permite foto en España: falta la foto.
    check = doctor.check_photo(demo_profile_file(data), data)
    assert check.status == CheckStatus.WARN and "clasica-foto" in check.detail

    (data / "photo.png").write_bytes((REPO_ROOT / "demo" / "photo.png").read_bytes())
    check = doctor.check_photo(demo_profile_file(data), data)
    assert (check.status, check.detail) == (CheckStatus.OK, str(data / "photo.png"))
    (data / "photo.png").unlink()

    # Sin plantillas con foto, o con una política que nunca la permite, no hace falta.
    no_photo_templates = demo_profile_file(data, default_template="ats-simple")
    assert doctor.check_photo(no_photo_templates, data).status == CheckStatus.OK
    never = demo_profile_file(data, photo_policy={"default": False, "by_country": {}})
    assert doctor.check_photo(never, data).status == CheckStatus.OK

    (data / "profile.yaml").write_text("preferences: [", encoding="utf-8")
    assert doctor.check_photo(data / "profile.yaml", data).status == CheckStatus.WARN


@pytest.mark.usefixtures("no_system_soffice")
def test_run_doctor_only_warns_on_fresh_setup() -> None:
    report = run_doctor(get_settings())
    statuses = {c.name: c.status for c in report.checks}
    assert report.ok
    assert statuses["Directorio de datos"] == CheckStatus.OK
    assert statuses["LibreOffice"] == CheckStatus.WARN
    assert statuses["Plantillas de CV"] == CheckStatus.OK
    assert statuses["Conversión a PDF"] == CheckStatus.WARN


@pytest.mark.usefixtures("no_system_soffice")
def test_cli_doctor_text() -> None:
    result = runner.invoke(cli.app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "Job Hunter" in result.output
    assert "AVISO" in result.output
    assert "Todo listo." in result.output


@pytest.mark.usefixtures("no_system_soffice")
def test_cli_doctor_json() -> None:
    result = runner.invoke(cli.app, ["doctor", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert [c["name"] for c in payload["checks"]] == [
        "Python",
        "Directorio de datos",
        "LibreOffice",
        "Plantillas de CV",
        "Conversión a PDF",
        "Motor html (Chromium)",
        "Foto del CV",
        "Embeddings",
        "Conectores de ofertas",
    ]


def test_cli_doctor_fails_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # Se parchea `cli.run_doctor` (no `doctor.run_doctor`) porque cli.py importa el nombre.
    monkeypatch.setattr(
        cli,
        "run_doctor",
        lambda _s: doctor.DoctorReport(
            checks=[doctor.CheckResult(name="X", status=CheckStatus.ERROR, detail="mal")]
        ),
    )
    result = runner.invoke(cli.app, ["doctor"])
    assert result.exit_code == 1
    assert "ERROR" in result.output


@requires_chromium
def test_check_html_engine_renders_without_network() -> None:
    result = doctor.check_html_engine()
    assert result.status == CheckStatus.OK, result.detail
    assert "moderna-2col" in result.detail and "sin red" in result.detail


def test_check_html_engine_without_chromium(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.documents.engines import html as html_engine

    def missing(*_args: object, **_kwargs: object) -> None:
        raise html_engine.ChromiumUnavailableError("no hay Chromium")

    monkeypatch.setattr(html_engine, "_print", missing)
    result = doctor.check_html_engine()
    assert result.status == CheckStatus.WARN
    assert "playwright install chromium" in result.detail


def test_check_connectors(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    result = doctor.check_connectors(get_settings())
    assert result.status == doctor.CheckStatus.OK
    assert "ninguno (opcionales)" in result.detail and "07:30" in result.detail

    monkeypatch.setenv("JH_ADZUNA_APP_ID", "id-secreto-1")
    monkeypatch.setenv("JH_ADZUNA_APP_KEY", "clave-secreta-2")
    monkeypatch.setenv("JH_INFOJOBS_CLIENT_ID", "id-secreto-3")
    get_settings.cache_clear()
    result = doctor.check_connectors(get_settings())
    assert result.status == doctor.CheckStatus.WARN
    assert "portales con claves: Adzuna" in result.detail
    assert "Falta una de las dos claves de InfoJobs" in result.detail
    assert "secret" not in result.detail  # nunca muestra las claves
