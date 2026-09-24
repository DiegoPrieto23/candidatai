"""CLI `jh`: capa fina sobre `app.services`."""

import io
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

import typer
from pydantic import BaseModel

from app.core import migrations
from app.core.config import get_settings
from app.core.db import session_scope
from app.services.doctor import CheckStatus, run_doctor
from app.services.events import JobNotFoundError, get_timeline
from app.services.ingest import IngestError, add_from_text, add_from_url
from app.services.jobs import DEFAULT_LIMIT, InvalidQueryError, list_jobs
from app.services.status import get_status

app = typer.Typer(help="Job Hunter: gestión local de la búsqueda de empleo.", no_args_is_help=True)
db_app = typer.Typer(help="Base de datos.", no_args_is_help=True)
events_app = typer.Typer(help="Eventos de las ofertas.", no_args_is_help=True)
jobs_app = typer.Typer(help="Ofertas: alta y listado.", no_args_is_help=True)
app.add_typer(db_app, name="db")
app.add_typer(events_app, name="events")
app.add_typer(jobs_app, name="jobs")

JSON_OPTION = typer.Option(False, "--json", help="Salida en JSON.")
TEXT_FILE_OPTION = typer.Option(
    ..., "--file", help="Fichero de texto con la oferta (UTF-8, con o sin BOM)."
)

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
    except (
        migrations.DatabaseNotReadyError,
        JobNotFoundError,
        IngestError,
        InvalidQueryError,
    ) as exc:
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


def _report_added(result: Any, as_json: bool) -> None:
    if as_json:
        _emit_json(result)
        return
    if not result.created:
        typer.echo(f"La oferta ya existía: {result.job_id}. No se ha cambiado nada.")
        return
    typer.echo(f"Oferta {result.job_id} dada de alta.")
    if result.duplicate_of is not None:
        typer.echo(f"Parece un duplicado de la oferta {result.duplicate_of}: queda cerrada.")
    if result.risk_flags:
        flags = ", ".join(result.risk_flags)
        typer.secho(f"Aviso: posible contenido dirigido a una IA ({flags}).", fg="yellow")


@jobs_app.command("add-url")
def jobs_add_url(url: str, as_json: bool = JSON_OPTION) -> None:
    """Descarga una oferta desde su URL y la da de alta (LinkedIn: usa `add-text`)."""

    def _add() -> Any:
        with session_scope() as session:
            return add_from_url(session, url)

    _report_added(_run(_add, as_json), as_json)


@jobs_app.command("add-text")
def jobs_add_text(
    title: str = typer.Option(..., "--title", help="Título de la oferta, tal cual."),
    company: str = typer.Option(..., "--company", help="Empresa que contrata."),
    file: Path = TEXT_FILE_OPTION,
    url: str | None = typer.Option(None, "--url", help="URL de la oferta, si la tiene."),
    location: str | None = typer.Option(None, "--location", help="Ubicación, tal cual."),
    as_json: bool = JSON_OPTION,
) -> None:
    """Da de alta una oferta a partir de su texto copiado en un fichero."""
    try:
        # `utf-8-sig`: el Bloc de notas y PowerShell pueden guardar con BOM.
        text = file.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        _fail(f"No se pudo leer {file}: {exc}", as_json)

    def _add() -> Any:
        with session_scope() as session:
            return add_from_text(session, title, company, text, url=url, location=location)

    _report_added(_run(_add, as_json), as_json)


@jobs_app.command("list")
def jobs_list(
    stage: str | None = typer.Option(None, "--stage", help="Filtra por etapa."),
    limit: int = typer.Option(DEFAULT_LIMIT, "--limit", help="Máximo de ofertas."),
    as_json: bool = JSON_OPTION,
) -> None:
    """Ofertas más recientes primero (sin el texto de la oferta)."""

    def _load() -> Any:
        with session_scope() as session:
            return list_jobs(session, stage=stage, limit=limit)

    jobs = _run(_load, as_json)
    if as_json:
        _emit_json({"jobs": [job.model_dump(mode="json") for job in jobs]})
        return
    if not jobs:
        typer.echo("No hay ofertas.")
        return
    for job in jobs:
        marks = " [!]" if job.risk_flags else ""
        dup = f" (duplicado de {job.duplicate_of})" if job.duplicate_of else ""
        typer.echo(f"{job.id:>5}  {job.stage or '-':<18} {job.title} · {job.company}{dup}{marks}")
