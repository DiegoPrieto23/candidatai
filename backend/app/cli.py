"""CLI `jh`: capa fina sobre `app.services`."""

import io
import json
import sys
from collections.abc import Callable
from typing import Any, NoReturn

import typer
from pydantic import BaseModel

from app.core import migrations
from app.core.config import get_settings
from app.core.db import session_scope
from app.services.doctor import CheckStatus, run_doctor
from app.services.events import JobNotFoundError, get_timeline
from app.services.status import get_status

app = typer.Typer(help="Job Hunter: gestión local de la búsqueda de empleo.", no_args_is_help=True)
db_app = typer.Typer(help="Base de datos.", no_args_is_help=True)
events_app = typer.Typer(help="Eventos de las ofertas.", no_args_is_help=True)
app.add_typer(db_app, name="db")
app.add_typer(events_app, name="events")

JSON_OPTION = typer.Option(False, "--json", help="Salida en JSON.")

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


def _emit_json(data: BaseModel | dict[str, Any]) -> None:
    payload = data.model_dump(mode="json") if isinstance(data, BaseModel) else data
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def _fail(message: str, as_json: bool) -> NoReturn:
    if as_json:
        _emit_json({"ok": False, "error": message})
    else:
        typer.secho(f"Error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


def _run[T](func: Callable[[], T], as_json: bool) -> T:
    """Ejecuta un servicio sobre la BD y traduce los errores esperables a un mensaje claro."""
    try:
        migrations.ensure_current()
        return func()
    except (migrations.DatabaseNotReadyError, JobNotFoundError) as exc:
        _fail(str(exc), as_json)


@db_app.command("upgrade")
def db_upgrade(as_json: bool = JSON_OPTION) -> None:
    """Aplica las migraciones pendientes (crea la BD si no existe)."""
    before = migrations.current_revision()
    migrations.upgrade()
    after = migrations.current_revision()
    if as_json:
        _emit_json({"ok": True, "from": before, "to": after})
    elif before == after:
        typer.echo(f"La base de datos ya estaba al día (versión {after}).")
    else:
        typer.echo(f"Base de datos actualizada: {before or 'vacía'} -> {after}.")


@app.command()
def status(as_json: bool = JSON_OPTION) -> None:
    """Recuento de ofertas por etapa."""

    def _load() -> Any:
        with session_scope() as session:
            return get_status(session)

    report = _run(_load, as_json)
    if as_json:
        _emit_json(report)
        return
    width = max(len(stage) for stage in report.by_stage)
    for stage, count in report.by_stage.items():
        typer.echo(f"{stage:<{width}}  {count:>4}")
    typer.echo(f"{'total':<{width}}  {report.total:>4}")


@events_app.command("list")
def events_list(job_id: int, as_json: bool = JSON_OPTION) -> None:
    """Etapa actual y eventos de una oferta, en orden cronológico."""

    def _load() -> Any:
        with session_scope() as session:
            return get_timeline(session, job_id)

    timeline = _run(_load, as_json)
    if as_json:
        _emit_json(timeline)
        return
    typer.echo(f"Oferta {timeline.job_id} · etapa: {timeline.stage or 'sin eventos'}\n")
    for event in timeline.events:
        who = f"{event.actor}/{event.agent_name}" if event.agent_name else event.actor
        when = event.occurred_at.strftime("%Y-%m-%d %H:%M")
        extra = f"  {json.dumps(event.payload, ensure_ascii=False)}" if event.payload else ""
        typer.echo(f"{event.id:>5}  {when} UTC  {event.type:<22} {who}{extra}")
