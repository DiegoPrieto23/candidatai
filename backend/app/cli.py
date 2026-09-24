"""CLI `jh`: capa fina sobre `app.services`."""

import io
import json
import subprocess
import sys
from typing import Any

import typer

from app.agent_interface.cli import dump_json, register_tools
from app.core import migrations
from app.core.config import REPO_ROOT, get_settings
from app.services.doctor import CheckStatus, run_doctor

app = typer.Typer(help="Job Hunter: gestión local de la búsqueda de empleo.", no_args_is_help=True)
db_app = typer.Typer(help="Base de datos.", no_args_is_help=True)
events_app = typer.Typer(help="Eventos de las ofertas.", no_args_is_help=True)
jobs_app = typer.Typer(help="Ofertas: alta, consulta y extracción.", no_args_is_help=True)
agents_app = typer.Typer(help="Configuración de los agentes de IA.", no_args_is_help=True)
app.add_typer(db_app, name="db")
app.add_typer(events_app, name="events")
app.add_typer(jobs_app, name="jobs")
app.add_typer(agents_app, name="agents")

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


register_tools(
    app,
    {"jobs": jobs_app, "events": events_app},
    {
        "get_status": _render_status,
        "add_job_from_url": _render_added,
        "add_job_from_text": _render_added,
        "list_jobs": _render_jobs,
        "get_job": _render_job,
        "save_extraction": _render_saved_extraction,
        "add_event": _render_event,
        "get_timeline": _render_timeline,
    },
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
