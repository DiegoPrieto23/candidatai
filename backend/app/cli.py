"""CLI `jh`: capa fina sobre `app.services`."""

import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn

import typer
import yaml

from app.agent_interface.cli import dump_json, register_tools
from app.agent_interface.errors import ErrorDetail, ToolError
from app.agent_interface.runner import to_tool_error
from app.core import migrations
from app.core.config import REPO_ROOT, get_settings
from app.core.db import session_scope
from app.services import profile
from app.services.doctor import CheckStatus, run_doctor

app = typer.Typer(help="Job Hunter: gestión local de la búsqueda de empleo.", no_args_is_help=True)
db_app = typer.Typer(help="Base de datos.", no_args_is_help=True)
events_app = typer.Typer(help="Eventos de las ofertas.", no_args_is_help=True)
jobs_app = typer.Typer(help="Ofertas: alta, consulta y extracción.", no_args_is_help=True)
agents_app = typer.Typer(help="Configuración de los agentes de IA.", no_args_is_help=True)
profile_app = typer.Typer(help="Perfil del candidato.", no_args_is_help=True)
app.add_typer(db_app, name="db")
app.add_typer(events_app, name="events")
app.add_typer(jobs_app, name="jobs")
app.add_typer(agents_app, name="agents")
app.add_typer(profile_app, name="profile")

JSON_OPTION = typer.Option(False, "--json", help="Salida en JSON.")
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_agents.py"

_MARKS = {
    CheckStatus.OK: ("OK", typer.colors.GREEN),
    CheckStatus.WARN: ("AVISO", typer.colors.YELLOW),
    CheckStatus.ERROR: ("ERROR", typer.colors.RED),
}


@app.callback()
def main() -> None:
    """Job Hunter: gestión local de la búsqueda de empleo."""
    # En Windows, si la salida va a una tubería (un agente leyendo `--json`), Python usa la
    # codificación ANSI del sistema. Forzamos UTF-8 para que tildes y eñes lleguen intactas.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")


@app.command()
def doctor(
    as_json: bool = typer.Option(False, "--json", help="Salida en JSON."),
) -> None:
    """Comprueba que el entorno local está listo."""
    report = run_doctor(get_settings())
    if as_json:
        payload = {"ok": report.ok, "checks": [c.model_dump(mode="json") for c in report.checks]}
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        typer.echo("Job Hunter · diagnóstico del entorno\n")
        width = max(len(c.name) for c in report.checks)
        for check in report.checks:
            label, color = _MARKS[check.status]
            mark = typer.style(f"[{label:^5}]", fg=color, bold=True)
            typer.echo(f"{mark} {check.name:<{width}}  {check.detail}")
        summary = "Todo listo." if report.ok else "Hay errores que corregir."
        typer.echo(f"\n{summary}")
    if not report.ok:
        raise typer.Exit(code=1)


@db_app.command("upgrade")
def db_upgrade(as_json: bool = JSON_OPTION) -> None:
    """Aplica las migraciones pendientes (crea la BD si no existe)."""
    before = migrations.current_revision()
    migrations.upgrade()
    after = migrations.current_revision()
    if as_json:
        typer.echo(dump_json({"ok": True, "from": before, "to": after}))
    elif before == after:
        typer.echo(f"La base de datos ya estaba al día (versión {after}).")
    else:
        typer.echo(f"Base de datos actualizada: {before or 'vacía'} -> {after}.")


# --- Salida legible (sin `--json`) de los comandos del registro ---------------------------------


def _render_status(report: Any) -> None:
    width = max(len(stage) for stage in report.by_stage)
    for stage, count in report.by_stage.items():
        typer.echo(f"{stage:<{width}}  {count:>4}")
    typer.echo(f"{'total':<{width}}  {report.total:>4}")
    if report.pending_tasks:
        typer.echo(f"\nTareas pendientes del worker: {report.pending_tasks}")


def _render_added(result: Any) -> None:
    if not result.created:
        typer.echo(f"La oferta ya existía: {result.job_id}. No se ha cambiado nada.")
        return
    typer.echo(f"Oferta {result.job_id} dada de alta.")
    if result.duplicate_of is not None:
        typer.echo(f"Parece un duplicado de la oferta {result.duplicate_of}: queda cerrada.")
    if result.risk_flags:
        flags = ", ".join(result.risk_flags)
        typer.secho(f"Aviso: posible contenido dirigido a una IA ({flags}).", fg="yellow")


def _render_jobs(result: Any) -> None:
    if not result.jobs:
        typer.echo("No hay ofertas.")
        return
    for job in result.jobs:
        marks = " [!]" if job.risk_flags else ""
        dup = f" (duplicado de {job.duplicate_of})" if job.duplicate_of else ""
        typer.echo(f"{job.id:>5}  {job.stage or '-':<18} {job.title} · {job.company}{dup}{marks}")


def _render_job(job: Any) -> None:
    typer.echo(f"Oferta {job.id} · {job.title} · {job.company}")
    typer.echo(f"Etapa: {job.stage or '-'} · Ubicación: {job.location or '-'}")
    typer.echo(f"URL: {job.url or '-'}")
    if job.risk_flags:
        flags = ", ".join(job.risk_flags)
        typer.secho(f"Aviso: posible contenido dirigido a una IA ({flags}).", fg="yellow")
    typer.echo(f"\n{job.text}")


def _render_timeline(timeline: Any) -> None:
    typer.echo(f"Oferta {timeline.job_id} · etapa: {timeline.stage or 'sin eventos'}\n")
    for event in timeline.events:
        who = f"{event.actor}/{event.agent_name}" if event.agent_name else event.actor
        when = event.occurred_at.strftime("%Y-%m-%d %H:%M")
        extra = f"  {json.dumps(event.payload, ensure_ascii=False)}" if event.payload else ""
        typer.echo(f"{event.id:>5}  {when} UTC  {event.type:<22} {who}{extra}")


def _render_saved_extraction(result: Any) -> None:
    typer.echo(f"Extracción guardada para la oferta {result.job_id}. Etapa: {result.stage}.")
    if result.injection_suspected:
        typer.secho("Registrado también `injection_suspected`.", fg="yellow")


def _render_event(result: Any) -> None:
    typer.echo(f"Evento {result.event_id} registrado. Etapa: {result.stage}.")


def _render_profile(result: Any) -> None:
    typer.echo(f"# Perfil, versión {result.profile_version_id} (sin email, teléfono ni privados)")
    typer.echo(yaml.safe_dump(result.profile, allow_unicode=True, sort_keys=False, width=100))


register_tools(
    app,
    {"jobs": jobs_app, "events": events_app, "profile": profile_app},
    {
        "get_status": _render_status,
        "add_job_from_url": _render_added,
        "add_job_from_text": _render_added,
        "list_jobs": _render_jobs,
        "get_job": _render_job,
        "save_extraction": _render_saved_extraction,
        "add_event": _render_event,
        "get_timeline": _render_timeline,
        "get_profile": _render_profile,
    },
)


# --- Perfil: validar, importar, comparar e iniciar ----------------------------------------------

PROFILE_PATH_ARG = typer.Argument(None, help="Ruta del perfil. Por defecto, data/profile.yaml.")


def _profile_path(path: Path | None) -> Path:
    """Ruta del perfil: relativa al directorio actual o, si ahí no existe, a la raíz del repo.

    Con `uv run --directory backend jh …` el proceso corre en `backend/`, pero la ruta se escribe
    pensando en la raíz (`demo/profile.example.yaml`).
    """
    if path is None:
        return profile.default_path()
    if path.is_absolute() or path.exists():
        return path.resolve()
    return (REPO_ROOT / path).resolve()


def _profile_fail(exc: Exception, as_json: bool) -> NoReturn:
    if isinstance(exc, profile.ProfileValidationError):
        details = [ErrorDetail(**issue.model_dump()) for issue in exc.issues]
        error = ToolError("validation_error", str(exc), details)
    elif isinstance(exc, profile.ProfileNotFoundError | FileExistsError):
        error = ToolError("not_found" if isinstance(exc, LookupError) else "exists", str(exc))
    else:
        error = to_tool_error(exc)
    if as_json:
        typer.echo(dump_json(error.payload()))
    else:
        typer.secho(f"Error: {error.info.message}", fg=typer.colors.RED, err=True)
        for detail in error.info.details:
            received = f" (recibido: {detail.received!r})" if detail.received is not None else ""
            typer.secho(f"  - {detail.field}: {detail.reason}{received}", err=True)
    raise typer.Exit(code=1)


@profile_app.command("validate")
def profile_validate(path: Path | None = PROFILE_PATH_ARG, as_json: bool = JSON_OPTION) -> None:
    """Valida un perfil sin importarlo."""
    resolved = _profile_path(path)
    try:
        loaded = profile.load_from_yaml(resolved)
    except (profile.ProfileValidationError, profile.ProfileNotFoundError) as exc:
        _profile_fail(exc, as_json)
    counts = {
        "experience": len(loaded.experience),
        "achievements": sum(len(e.achievements) for e in loaded.experience),
        "skills": len(loaded.skills),
        "stories": len(loaded.stories),
    }
    if as_json:
        typer.echo(dump_json({"ok": True, "path": str(resolved), "counts": counts}))
    else:
        typer.echo(
            f"Perfil válido: {resolved}\n{counts['experience']} experiencias, "
            f"{counts['achievements']} logros, {counts['skills']} skills, "
            f"{counts['stories']} historias."
        )


@profile_app.command("import")
def profile_import(path: Path | None = PROFILE_PATH_ARG, as_json: bool = JSON_OPTION) -> None:
    """Valida el perfil y crea una versión nueva si ha cambiado."""
    resolved = _profile_path(path)
    try:
        migrations.ensure_current()
        with session_scope() as session:
            result = profile.import_profile(session, resolved)
    except Exception as exc:
        _profile_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json({"ok": True, **result.model_dump(mode="json")}))
    elif result.created:
        typer.echo(f"Perfil importado: versión {result.profile_version_id}.")
    else:
        typer.echo(f"Sin cambios: sigue vigente la versión {result.profile_version_id}.")


@profile_app.command("diff")
def profile_diff(as_json: bool = JSON_OPTION) -> None:
    """Diferencias entre las dos últimas versiones importadas (`private` no se muestra)."""
    try:
        migrations.ensure_current()
        with session_scope() as session:
            result = profile.diff_last_two(session)
    except Exception as exc:
        _profile_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json(result))
    elif result.from_version is None:
        typer.echo(f"Solo hay una versión ({result.to_version}): nada con qué compararla.")
    elif not result.diff:
        versions = f"{result.from_version} y {result.to_version}"
        typer.echo(f"Sin diferencias entre las versiones {versions}.")
    else:
        typer.echo(result.diff, nl=False)


@profile_app.command("init")
def profile_init(as_json: bool = JSON_OPTION) -> None:
    """Copia el perfil de ejemplo a data/profile.yaml si aún no existe."""
    try:
        dest = profile.init_profile()
    except FileExistsError as exc:
        _profile_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json({"ok": True, "path": str(dest)}))
    else:
        typer.echo(
            f"Creado {dest} a partir del ejemplo (candidata ficticia). Rellénalo con tus datos "
            "(skill `actualizar-perfil`) y luego ejecuta `jh profile validate` e `import`."
        )


# --- Configuración de agentes: delega en scripts/sync_agents.py ---------------------------------


def _run_sync(*extra: str) -> None:
    # Mismo intérprete que `jh` (el venv del backend ya trae pyyaml, la única dependencia).
    completed = subprocess.run([sys.executable, str(SYNC_SCRIPT), *extra], cwd=REPO_ROOT)
    raise typer.Exit(code=completed.returncode)


@agents_app.command("sync")
def agents_sync() -> None:
    """Regenera .claude/, .codex/ y .mcp.json desde .agents/."""
    _run_sync()


@agents_app.command("check")
def agents_check() -> None:
    """Falla si la configuración generada de los agentes no está al día."""
    _run_sync("--check")
