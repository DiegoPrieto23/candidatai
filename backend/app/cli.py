"""CLI `jh`: capa fina sobre `app.services`."""

import io
import json
import logging
import subprocess
import sys
from logging.handlers import RotatingFileHandler
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
match_app = typer.Typer(help="Encaje de las ofertas con el perfil.", no_args_is_help=True)
eval_app = typer.Typer(help="Evaluación de la calidad del matching.", no_args_is_help=True)
cv_app = typer.Typer(help="CVs a medida: contenido, renders y verificación.", no_args_is_help=True)
templates_app = typer.Typer(help="Plantillas de CV.", no_args_is_help=True)
sources_app = typer.Typer(
    help="Fuentes de ofertas: empresas objetivo (ATS), portales con API y plataformas para la "
    "búsqueda con navegador.",
    no_args_is_help=True,
)
calendar_app = typer.Typer(help="Calendario .ics de los procesos.", no_args_is_help=True)
capture_app = typer.Typer(
    help="Botón «Enviar a Job Hunter» (extensión del navegador).", no_args_is_help=True
)
alerts_app = typer.Typer(
    help="Alertas de empleo por correo y ofertas resumen (pending_detail).", no_args_is_help=True
)
app.add_typer(db_app, name="db")
app.add_typer(events_app, name="events")
app.add_typer(jobs_app, name="jobs")
app.add_typer(agents_app, name="agents")
app.add_typer(profile_app, name="profile")
app.add_typer(match_app, name="match")
app.add_typer(eval_app, name="eval")
app.add_typer(cv_app, name="cv")
app.add_typer(templates_app, name="templates")
app.add_typer(sources_app, name="sources")
app.add_typer(alerts_app, name="alerts")
app.add_typer(capture_app, name="capture")
app.add_typer(calendar_app, name="calendar")

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


@app.command()
def serve(
    port: int = typer.Option(8000, help="Puerto (siempre en 127.0.0.1)."),
    reload: bool = typer.Option(False, "--reload", help="Recarga al cambiar el código."),
) -> None:
    """Levanta la API para la UI en http://127.0.0.1:<puerto>."""
    import uvicorn

    from app.api.main import HOST

    migrations.ensure_current()  # mejor fallar aquí que en cada petición
    uvicorn.run("app.api.main:app", host=HOST, port=port, reload=reload)


OPENAPI_OUT_OPTION = typer.Option(None, "--out", help="Fichero de salida. Por defecto, stdout.")


@app.command()
def openapi(out: Path | None = OPENAPI_OUT_OPTION) -> None:
    """Esquema OpenAPI de la API (lo usa `pnpm gen:api` en el frontend)."""
    from app.api.main import create_app, openapi_json

    text = openapi_json(create_app())
    if out is None:
        typer.echo(text, nl=False)
    else:
        out.write_text(text, encoding="utf-8", newline="\n")


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
        score = f"{job.score:>3}" if job.score is not None else "  -"
        line = f"{job.id:>5}  {job.stage or '-':<18} {score}  {job.title} · {job.company}"
        typer.echo(f"{line}{dup}{marks}")


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


def _render_match(view: Any) -> None:
    mark = " (por debajo del umbral)" if view.below_threshold else ""
    typer.echo(f"Oferta {view.job_id} · score {view.score}/100{mark}")
    if view.hard_filters.passed:
        typer.echo("Filtros duros: pasa.")
    else:
        typer.secho("Filtros duros: no pasa.", fg="yellow")
        for failure in view.hard_filters.failures:
            typer.echo(f"  - {failure.reason}")
    typer.echo("")
    for comp in view.breakdown.components:
        value = "-" if comp.value is None else f"{comp.value:.2f}"
        weight = f"{comp.effective_weight:.2f}"
        typer.echo(f"{comp.name:<24} {value:>5}  x {weight}  = {comp.points:5.1f}")
    breakdown = view.breakdown
    for label, cov in (
        ("Obligatorias", breakdown.must_have),
        ("Deseables", breakdown.nice_to_have),
    ):
        covered = ", ".join(f"{c.skill} ({c.level})" for c in cov.covered) or "-"
        typer.echo(f"\n{label}: cubiertas {covered}")
        typer.echo(f"{' ' * len(label)}  ausentes {', '.join(cov.missing) or '-'}")
    for note in breakdown.notes:
        typer.secho(f"\nNota: {note}", fg="yellow")
    if view.assessment:
        stale = " (de un cálculo anterior)" if view.assessment_stale else ""
        typer.echo(f"\nValoración del agente{stale}: {view.assessment.verdict}")
        typer.echo(view.assessment.rationale)


def _render_saved_assessment(result: Any) -> None:
    typer.echo(f"Valoración guardada para la oferta {result.job_id} (match {result.match_id}).")


def _render_profile(result: Any) -> None:
    typer.echo(f"# Perfil, versión {result.profile_version_id} (sin email, teléfono ni privados)")
    typer.echo(yaml.safe_dump(result.profile, allow_unicode=True, sort_keys=False, width=100))


def _render_templates(result: Any) -> None:
    for t in result.templates:
        tags = ["ATS" if t.ats_friendly else "no ATS", "foto" if t.photo_supported else "sin foto"]
        if t.accent_colors:
            tags.append("color")
        origin = "integrada" if t.origin == "builtin" else "tuya"
        typer.echo(f"{t.id:<20} {t.name} ({t.engine}, {origin}; {', '.join(tags)})")
    for bad in result.invalid:
        typer.secho(f"{bad.id:<20} NO VÁLIDA: {bad.reason}", fg="yellow")
    typer.echo(f"Por defecto, si ninguna regla elige otra: {result.fallback_template}")


def _render_cv_render(render: Any) -> None:
    pages = f"{render.pages}/{render.max_pages} pág."
    mark = " · seleccionado para enviar" if render.selected else ""
    typer.echo(f"Render {render.render_id} con «{render.template_id}» · {pages}{mark}")
    typer.echo(f"  PDF:  data/{render.pdf_path}")
    if render.docx_path:
        typer.echo(f"  DOCX: data/{render.docx_path}")
    cov = render.keyword_coverage
    typer.echo(
        f"  Keywords: {', '.join(cov.present) or '-'}; ausentes: {', '.join(cov.missing) or '-'}"
    )
    for warning in render.warnings:
        typer.secho(f"  Aviso {warning.code}: {warning.message}", fg="yellow")


def _render_cv_saved(result: Any) -> None:
    typer.echo(f"CV {result.document_id} guardado para la oferta {result.job_id}.")
    _render_cv_render(result.render)


def _render_cv_view(view: Any) -> None:
    content = view.content
    typer.echo(f"CV {view.document_id} de la oferta {view.job_id} ({content.language})")
    typer.echo(f"{content.subtitle}\n\n{content.summary}")
    for exp in content.experience:
        typer.echo(f"\n[{exp.experience_id}]")
        for bullet in exp.bullets:
            typer.echo(f"  - {bullet.text}  ({', '.join(bullet.evidence)})")
    if view.verification is None:
        typer.echo("\nSin verificar.")
    else:
        verdict = "PASA" if view.verification.passed else "NO PASA"
        typer.echo(f"\nVerificación: {verdict} ({len(view.verification.issues)} problemas)")
    for render in view.renders:
        _render_cv_render(render)


def _render_cv_verification(result: Any) -> None:
    verdict = "verificado" if result.passed else "rechazado"
    typer.echo(f"CV {result.document_id} {verdict}. Etapa de la oferta: {result.stage}.")
    if result.note:
        typer.secho(result.note, fg="yellow")


@match_app.command("rescore")
def match_rescore(as_json: bool = JSON_OPTION) -> None:
    """Recalcula ahora los matches desfasados de las ofertas abiertas (p. ej. tras instalar el
    extra `matching` o editar `config/policies.yaml`) y cierra las que no pasan los filtros."""
    from app.services.matching import service as matching

    try:
        with session_scope() as session:
            result = matching.rescore_open_jobs(session)
    except profile.ProfileNotFoundError as exc:
        _profile_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json(result.model_dump(mode="json")))
        return
    typer.echo(f"Ofertas abiertas revisadas: {result.scored}.")
    if result.closed:
        closed = ", ".join(str(job_id) for job_id in result.closed)
        typer.echo(f"Cerradas por no pasar los filtros duros: {closed}.")


# --- Evaluación del matching ------------------------------------------------------------------


def _metric(value: float | None) -> str:
    return "  —  " if value is None else f"{value:5.2f}"


EVAL_PROFILE_OPTION = typer.Option(
    None, "--profile", help="Perfil para los casos de data/evals/. Por defecto, data/profile.yaml."
)


@eval_app.command("matching")
def eval_matching(
    profile_path: Path | None = EVAL_PROFILE_OPTION,
    no_seed: bool = typer.Option(False, "--no-seed", help="Sin los casos de evals/matching/."),
    no_embeddings: bool = typer.Option(
        False, "--no-embeddings", help="Sin similitud semántica aunque esté instalada."
    ),
    as_json: bool = JSON_OPTION,
) -> None:
    """Precision, recall y F1 del matching con el umbral actual y por umbral; guarda el informe."""
    from app.services.matching import evaluation

    try:
        report = evaluation.run(
            include_seed=not no_seed,
            profile_path=_profile_path(profile_path) if profile_path else None,
            use_embeddings=not no_embeddings,
        )
    except (evaluation.EvalFileError, profile.ProfileValidationError) as exc:
        _profile_fail(exc, as_json)
    json_path, md_path = evaluation.save_report(report, get_settings().evals_dir / "reports")
    if as_json:
        paths = [str(json_path), str(md_path)]
        typer.echo(dump_json({**report.model_dump(mode="json"), "report_paths": paths}))
        return
    m = report.metrics
    model = report.embeddings_model or "sin embeddings"
    typer.echo(f"Matching · {len(report.cases)} casos · umbral {report.threshold} · {model}")
    typer.echo(
        f"Precision {_metric(m.precision)}   Recall {_metric(m.recall)}   F1 {_metric(m.f1)}"
        f"   (VP {m.tp}, FP {m.fp}, FN {m.fn}, VN {m.tn})"
    )
    typer.echo("\nUmbral  Precision  Recall     F1")
    for point in report.curve:
        pm = point.metrics
        mark = "  <- actual" if point.threshold == report.threshold else ""
        typer.echo(
            f"{point.threshold:>6}  {_metric(pm.precision):>9}  {_metric(pm.recall):>6}  "
            f"{_metric(pm.f1):>5}{mark}"
        )
    wrong = [c for c in report.cases if c.label != c.predicted]
    if wrong:
        typer.echo("\nErrores con el umbral actual:")
        for case in wrong:
            why = "; ".join(case.failures) if case.failures else f"score {case.score}"
            typer.echo(f"  {case.id}: etiqueta {case.label}, predice {case.predicted} ({why})")
    for note in report.notes:
        typer.secho(f"\nNota: {note}", fg="yellow")
    typer.echo(f"\nInforme: {md_path}")


# --- Worker: tareas en segundo plano -------------------------------------------------------------


def _outcome_line(outcome: Any) -> str:
    from app.services import worker as worker_service

    mark = "[ok]   " if outcome.ok else "[error]"
    if outcome.kind == "run_source" or outcome.ok:
        return f"{mark} tarea {outcome.task_id} {outcome.kind}: {worker_service.describe(outcome)}"
    return f"{mark} tarea {outcome.task_id} {outcome.kind}: {outcome.error}"


def _render_worker_run(run: Any) -> None:
    for outcome in run.outcomes:
        typer.secho(_outcome_line(outcome), fg=None if outcome.ok else "red")


def _worker_logger() -> logging.Logger:
    """Log legible en consola y en `data/logs/worker.log` (rotado, 1 MB x 3)."""
    logger = logging.getLogger("jobhunter.worker")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
    logger.addHandler(console)
    logs_dir = get_settings().logs_dir
    logs_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        logs_dir / "worker.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(file_handler)
    # APScheduler anuncia cada ejecución en INFO: solo interesan sus avisos.
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    return logger


@app.command()
def worker(
    once: bool = typer.Option(False, "--once", help="Vacía la cola y termina."),
    interval: float = typer.Option(5.0, help="Segundos entre pasadas por la cola (sin --once)."),
    as_json: bool = JSON_OPTION,
) -> None:
    """Ejecuta las tareas en segundo plano (scores, recálculos) y la ingesta diaria de las fuentes
    a la hora de `connectors.daily_at`. Ctrl+C para parar."""
    from app.services import worker as worker_service

    try:
        migrations.ensure_current()
    except migrations.DatabaseNotReadyError as exc:
        _profile_fail(exc, as_json)
    if once:
        run = worker_service.run_pending()
        if as_json:
            typer.echo(dump_json(run))
        elif run.outcomes:
            _render_worker_run(run)
        else:
            typer.echo("No hay tareas pendientes.")
        if run.failed:
            raise typer.Exit(code=1)
        return
    log = _worker_logger()

    def on_run(run: Any) -> None:
        for outcome in run.outcomes:
            (log.info if outcome.ok else log.warning)(_outcome_line(outcome))

    log.info(f"Worker en marcha (cola cada {interval:g} s). Ctrl+C para parar.")
    try:
        worker_service.run_scheduler(interval, on_run, log.info)
    except (KeyboardInterrupt, SystemExit):
        log.info("Worker parado.")
    finally:
        for handler in list(log.handlers):  # en Windows, un fichero abierto no se puede borrar
            log.removeHandler(handler)
            handler.close()


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


# --- Plantillas: importar un CV de Word (solo CLI; las usa el skill importar-plantilla-cv) -----


def _templates_fail(exc: Exception, as_json: bool) -> NoReturn:
    from app.services.documents.templates import TemplateInvalidError

    if isinstance(exc, TemplateInvalidError):  # aquí es lo que se está validando: con detalle
        details = [ErrorDetail(field=i.field, received=None, reason=i.reason) for i in exc.issues]
        error = ToolError("validation_error", str(exc), details)
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


SOURCE_FILE_ARG = typer.Argument(..., help="CV original, dentro de data/uploads/ o data/tmp/.")
SOURCE_OPTION = typer.Option(..., "--source", help="CV de Word, en data/uploads/ o data/tmp/.")
VISUAL_SOURCE_OPTION = typer.Option(
    ..., "--source", help="CV en PDF, imagen o HTML, en data/uploads/ o data/tmp/."
)
SECTIONS_OPTION = typer.Option(
    None,
    "--sections",
    help="Secciones en su orden, separadas por comas (si inspect no las leyó: imágenes).",
)
SIDE_OPTION = typer.Option(
    None, "--side", help="Secciones de la columna lateral, separadas por comas."
)
MAPPING_OPTION = typer.Option(..., "--mapping", help="Mapeo JSON, en data/tmp/.")
TEMPLATE_ID_OPTION = typer.Option(..., "--id", help="Id de la plantilla (minúsculas y guiones).")
TEMPLATE_NAME_OPTION = typer.Option(None, "--name", help="Nombre visible de la plantilla.")
FORCE_OPTION = typer.Option(False, "--force", help="Sustituye una plantilla con el mismo id.")
TEMPLATE_ID_ARG = typer.Argument(..., help="Id de la plantilla.")
PREVIEW_PROFILE_OPTION = typer.Option("demo", "--profile", help="demo (ficticio) o real (el tuyo).")


def _echo_visual_inspection(report: Any) -> None:
    lay = report.layout
    typer.echo(
        f"{report.file} ({report.format}): {report.pages} página(s), {report.page.size} "
        f"({report.page.width_mm}×{report.page.height_mm} mm)."
    )
    typer.echo("Páginas en PNG: " + ", ".join(f"data/{p}" for p in report.page_images))
    side = f", barra lateral {lay.sidebar} ({lay.sidebar_color})" if lay.sidebar else ""
    band = f", banda de cabecera {lay.header_band_color}" if lay.header_band_color else ""
    typer.echo(f"Columnas: {lay.columns}{side}{band} · márgenes (mm): {lay.margins_mm}")
    typer.echo(
        "Colores: "
        + ", ".join(f"{c.color} ({c.share:.0%})" for c in report.colors)
        + f" · fuentes: {', '.join(report.fonts) or '-'}"
    )
    photos = [i for i in report.images if i.photo_candidate]
    typer.echo(f"Imágenes: {len(report.images)} ({len(photos)} con pinta de foto)")
    typer.echo(
        "Secciones: "
        + (" · ".join(f"{s.title} ({s.section}, col. {s.column})" for s in report.sections) or "-")
    )
    cap = report.capacity
    if report.capacity_note:
        typer.echo("Capacidad: sin texto que medir (léela en la imagen)")
    else:
        typer.echo(
            f"Capacidad: perfil {cap.summary_chars or '?'} caracteres, logros "
            f"{cap.bullets_per_experience}, {cap.skill_groups or '?'} grupos de habilidades"
        )
    typer.echo(f"Apto para ATS: no ({' '.join(report.ats.reasons)})")
    for note in report.notes:
        typer.secho(f"  Nota: {note}", fg=typer.colors.YELLOW)
    if report.text_blocks:
        typer.echo("Bloques de texto (x, y en mm · tamaño en pt):")
        for b in report.text_blocks:
            style = ("N" if b.bold else "") + ("C" if b.italic else "")
            typer.echo(
                f"  {b.index:>3} p{b.page} {b.x_mm:>6.1f},{b.y_mm:>6.1f} {b.size_pt:>4.1f} "
                f"{style:<2} {b.text[:70]!r}"
            )


@templates_app.command("inspect")
def templates_inspect(file: Path = SOURCE_FILE_ARG, as_json: bool = JSON_OPTION) -> None:
    """Analiza un CV: diseño, secciones, capacidad y ATS (Word, PDF, imagen o HTML)."""
    from app.services.documents import authoring
    from app.services.documents.importer.visual import VisualInspection

    try:
        report = authoring.inspect_file(file)
    except Exception as exc:
        _templates_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json(report))
        return
    if isinstance(report, VisualInspection):
        _echo_visual_inspection(report)
        return
    page = report.page[0] if report.page else None
    typer.echo(f"{report.file}: {report.pages or '?'} página(s), {page.size if page else '?'}.")
    if report.pages_note:
        typer.echo(f"  {report.pages_note}")
    fonts, colors = ", ".join(report.fonts) or "-", ", ".join(report.colors) or "-"
    typer.echo(f"Fuentes: {fonts} · colores: {colors}")
    typer.echo(
        f"Tablas: {len(report.tables)} · cuadros de texto: {len(report.text_boxes)} · "
        f"imágenes: {len(report.images)}"
    )
    typer.echo("Secciones: " + " · ".join(f"{s.title} ({s.section})" for s in report.sections))
    ats = "sí" if report.ats.ats_friendly else "no (" + " ".join(report.ats.reasons) + ")"
    typer.echo(f"Apto para ATS: {ats}")
    typer.echo("Párrafos:")
    for p in report.paragraphs:
        where = p.location + (f" t{p.table}f{p.row}c{p.cell}" if p.table is not None else "")
        image = " [imagen]" if p.images else ""
        typer.echo(f"  {p.index:>3} {where:<14} {p.text[:70]!r}{image}")


@templates_app.command("build-docx")
def templates_build_docx(
    source: Path = SOURCE_OPTION,
    mapping: Path = MAPPING_OPTION,
    template_id: str = TEMPLATE_ID_OPTION,
    name: str | None = TEMPLATE_NAME_OPTION,
    force: bool = FORCE_OPTION,
    as_json: bool = JSON_OPTION,
) -> None:
    """Crea data/templates/<id>/ a partir del Word y del mapeo."""
    from app.services.documents import authoring

    try:
        result = authoring.build_docx(source, mapping, template_id, name=name, force=force)
    except Exception as exc:
        _templates_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json(result))
        return
    typer.echo(f"Plantilla creada: data/{result.path}")
    typer.echo(f"Secciones: {', '.join(result.sections)} · máximo {result.max_pages} página(s).")
    for warning in result.warnings:
        typer.secho(f"  Aviso: {warning}", fg=typer.colors.YELLOW)
    typer.echo("Completa template.yaml y ejecuta `jh templates validate` y `preview`.")


def _csv(value: str | None) -> list[str] | None:
    if value is None:
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


@templates_app.command("scaffold-html")
def templates_scaffold_html(
    source: Path = VISUAL_SOURCE_OPTION,
    template_id: str = TEMPLATE_ID_OPTION,
    name: str | None = TEMPLATE_NAME_OPTION,
    sections: str | None = SECTIONS_OPTION,
    side: str | None = SIDE_OPTION,
    force: bool = FORCE_OPTION,
    as_json: bool = JSON_OPTION,
) -> None:
    """Crea data/templates/<id>/ (motor html) con un HTML y un CSS base según el original."""
    from app.services.documents import authoring

    try:
        result = authoring.scaffold_html(
            source,
            template_id,
            name=name,
            sections=_csv(sections),
            side=_csv(side),
            force=force,
        )
    except Exception as exc:
        _templates_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json(result))
        return
    typer.echo(f"Plantilla html creada: data/{result.path} ({', '.join(result.files)})")
    typer.echo(
        f"Secciones: {', '.join(result.sections)}"
        + (f" · lateral: {', '.join(result.side_sections)}" if result.side_sections else "")
    )
    typer.echo(f"Acento {result.accent_color} · fuentes: {', '.join(result.fonts) or '-'}")
    for warning in result.warnings:
        typer.secho(f"  Aviso: {warning}", fg=typer.colors.YELLOW)
    typer.echo("Siguientes pasos:")
    for step in result.next_steps:
        typer.echo(f"  - {step}")


@templates_app.command("compare")
def templates_compare(
    template_id: str = TEMPLATE_ID_ARG,
    source: Path = VISUAL_SOURCE_OPTION,
    as_json: bool = JSON_OPTION,
) -> None:
    """Original y recreación (perfil demo) lado a lado en un PNG, con su SSIM orientativa."""
    from app.services.documents import authoring

    try:
        result = authoring.compare_template(template_id, source)
    except Exception as exc:
        _templates_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json(result))
        return
    typer.echo(f"Comparación: data/{result.image_path}")
    typer.echo(f"SSIM: {result.ssim:.3f} (0-1). {result.note}")


@templates_app.command("validate")
def templates_validate(
    template_id: str = TEMPLATE_ID_ARG,
    as_json: bool = JSON_OPTION,
) -> None:
    """Comprueba template.yaml, las variables del contrato y que renderiza con el perfil demo."""
    from app.services.documents import authoring

    try:
        result = authoring.validate(template_id)
    except Exception as exc:
        _templates_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json(result))
    else:
        typer.echo(f"Plantilla válida: {result.template_id} ({result.engine}).")


@templates_app.command("preview")
def templates_preview(
    template_id: str = TEMPLATE_ID_ARG,
    which: str = PREVIEW_PROFILE_OPTION,
    as_json: bool = JSON_OPTION,
) -> None:
    """PDF y PNG de la plantilla con el perfil demo o con el tuyo."""
    from app.services.documents import authoring

    try:
        if which not in ("demo", "real"):
            raise ValueError("`--profile` debe ser demo o real.")
        if which == "real":
            migrations.ensure_current()
            with session_scope() as session:
                result = authoring.preview_template(session, template_id, "real")
        else:
            result = authoring.preview_template(None, template_id, "demo")
    except Exception as exc:
        _templates_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json(result))
        return
    typer.echo(f"Preview: {result.pdf_path} · {result.png_path}")
    typer.echo(f"{result.pages} de {result.max_pages} página(s) como máximo.")
    for warning in result.warnings:
        typer.secho(f"  Aviso: {warning}", fg=typer.colors.YELLOW)


# --- Fuentes: empresas objetivo y portales -----------------------------------------------------

KIND_OPTION = typer.Option(..., "--kind", help="greenhouse, lever, ashby, infojobs o adzuna.")
NAME_OPTION = typer.Option(..., "--name", help="Empresa (en un ATS) o etiqueta de la búsqueda.")
SLUG_OPTION = typer.Option(None, "--slug", help="Slug del tablero del ATS (p. ej. `acme`).")
REGION_OPTION = typer.Option("global", "--region", help="Lever: `global` o `eu`.")
QUERY_OPTION = typer.Option(None, "--query", help="Portales: palabras de búsqueda.")
WHERE_OPTION = typer.Option(None, "--where", help="Adzuna: ubicación.")
PROVINCE_OPTION = typer.Option(None, "--province", help="InfoJobs: provincia (p. ej. `a-coruna`).")
COUNTRY_OPTION = typer.Option("es", "--country", help="Adzuna: país (código de 2 letras).")
KEYWORDS_OPTION = typer.Option(
    None, "--keywords", help="Palabras extra que dejan pasar un título, separadas por comas."
)
SOURCE_ID_ARG = typer.Argument(..., help="Id de la fuente (ver `jh sources list`).")


def _source_input(
    kind: str,
    name: str,
    slug: str | None,
    region: str,
    query: str | None,
    where: str | None,
    province: str | None,
    country: str,
    keywords: str | None,
) -> Any:
    from app.schemas.sources import SourceInput

    return SourceInput.model_validate(
        {
            "kind": kind,
            "name": name,
            "slug": slug,
            "region": region,
            "query": query,
            "where": where,
            "province": province,
            "country": country,
            "title_keywords": _csv(keywords) or [],
        }
    )


def _render_source(source: Any) -> None:
    state = "activa" if source.active else "pausada"
    target = source.config.get("slug") or source.config.get("query") or ""
    if source.browse:
        browse = source.browse
        state = "navegación " + ("activada" if browse.allow_agent_browsing else "desactivada")
        target = f"{browse.platform}, prioridad {browse.priority}, acceso {browse.access}"
    typer.echo(f"{source.id:>4}  {source.kind_label:<11} {source.name} [{target}] ({state})")
    if source.keys_missing:
        typer.secho("      Sin claves en .env: se omite al ejecutar.", fg="yellow")
    if source.last_run:
        run = source.last_run
        when = run.started_at.astimezone().strftime("%d/%m %H:%M")
        line = f"      Última: {when}, {run.found} encontradas, {run.after_filters} tras filtros, "
        line += f"{run.created} nuevas"
        if run.errors:
            line += f", {len(run.errors)} avisos: {run.errors[0].message}"
        typer.echo(line)


def _render_preview(result: Any) -> None:
    typer.echo(f"{result.name}: {result.message.rstrip('.')}.")
    if result.found == 0 and result.errors:
        return  # el mensaje ya es el error de la fuente
    for job in result.jobs:
        mark = "+" if job.passed else "-"
        where = f" · {job.location}" if job.location else ""
        reason = f"  ({job.reason})" if job.reason else ""
        typer.echo(f"  {mark} {job.title}{where}{reason}")
    for issue in result.errors:
        typer.secho(f"  ! {issue.message}", fg="yellow")


def _render_source_run(result: Any) -> None:
    color = "yellow" if result.skipped or result.errors else None
    typer.secho(result.message, fg=color)
    for issue in result.errors:
        typer.secho(f"  ! {issue.message}", fg="yellow")
    if result.job_ids:
        ids = ", ".join(map(str, result.job_ids[:10]))
        if len(result.job_ids) > 10:
            ids += f" y {len(result.job_ids) - 10} más"
        typer.echo(
            f"  Nuevas en pending_extraction: {ids}. "
            "Ejecuta `procesar-ofertas` en tu agente para extraerlas."
        )


@sources_app.command("add")
def sources_add(
    kind: str = KIND_OPTION,
    name: str = NAME_OPTION,
    slug: str | None = SLUG_OPTION,
    region: str = REGION_OPTION,
    query: str | None = QUERY_OPTION,
    where: str | None = WHERE_OPTION,
    province: str | None = PROVINCE_OPTION,
    country: str = COUNTRY_OPTION,
    keywords: str | None = KEYWORDS_OPTION,
    as_json: bool = JSON_OPTION,
) -> None:
    """Añade una empresa objetivo (ATS + slug) o una búsqueda en un portal con API."""
    from app.services.ingestion import service as sources

    try:
        migrations.ensure_current()
        data = _source_input(kind, name, slug, region, query, where, province, country, keywords)
        with session_scope() as session:
            view = sources.add_source(session, data)
    except Exception as exc:
        _profile_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json(view))
        return
    typer.echo(f"Fuente añadida. Pruébala con `jh sources test {view.id}`.")
    _render_source(view)


def _render_source_list(result: Any) -> None:
    if not result.sources:
        typer.echo("No hay fuentes. Añade una con `jh sources add`.")
    for source in result.sources:
        _render_source(source)


def _render_message(result: Any) -> None:
    typer.echo(result.message)


def _render_recorded_run(result: Any) -> None:
    typer.echo(f"Recorrido anotado (ejecución {result.run_id}).")


@sources_app.command("test")
def sources_test(
    source_id: int | None = typer.Argument(None, help="Id de una fuente guardada."),
    kind: str | None = typer.Option(None, "--kind", help="Para probar sin guardar: el tipo."),
    name: str | None = typer.Option(None, "--name", help="Para probar sin guardar: el nombre."),
    slug: str | None = SLUG_OPTION,
    region: str = REGION_OPTION,
    query: str | None = QUERY_OPTION,
    where: str | None = WHERE_OPTION,
    province: str | None = PROVINCE_OPTION,
    country: str = COUNTRY_OPTION,
    keywords: str | None = KEYWORDS_OPTION,
    as_json: bool = JSON_OPTION,
) -> None:
    """Descarga y filtra una fuente sin guardar nada: «12 ofertas encontradas, 3 tras filtros»."""
    from app.services.ingestion import service as sources

    try:
        migrations.ensure_current()
        if source_id is not None:
            target: Any = source_id
        elif kind and name:
            target = _source_input(
                kind, name, slug, region, query, where, province, country, keywords
            )
        else:
            raise ValueError(
                "Indica el id de una fuente o, para probar sin guardar, --kind y --name."
            )
        with session_scope() as session:
            result = sources.preview_source(session, target)
    except Exception as exc:
        _profile_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json(result))
    else:
        _render_preview(result)
    if result.found == 0 and result.errors:
        raise typer.Exit(code=1)


@sources_app.command("run")
def sources_run(
    source_id: int | None = typer.Argument(None, help="Id de la fuente. Sin id, las activas."),
    as_json: bool = JSON_OPTION,
) -> None:
    """Ejecuta ahora una fuente (o todas las activas) y guarda las ofertas nuevas."""
    from app.schemas.sources import SourceRunBatch
    from app.services.ingestion import service as sources

    try:
        migrations.ensure_current()
        with session_scope() as session:
            ids = (
                [source_id]
                if source_id is not None
                else [s.id for s in sources.connector_sources(session)]
            )
        runs = []
        for current in ids:  # una transacción por fuente: un fallo no deshace las demás
            with session_scope() as session:
                runs.append(sources.run_source(session, current, actor="user"))
    except Exception as exc:
        _profile_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json(SourceRunBatch(runs=runs)))
    elif not runs:
        typer.echo("No hay fuentes activas. Añade una con `jh sources add`.")
    else:
        for run in runs:
            _render_source_run(run)
    if any(run.errors and not run.found for run in runs):
        raise typer.Exit(code=1)


def _set_active(source_id: int, active: bool, as_json: bool) -> None:
    from app.services.ingestion import service as sources

    try:
        migrations.ensure_current()
        with session_scope() as session:
            view = sources.set_active(session, source_id, active)
    except Exception as exc:
        _profile_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json(view))
    else:
        _render_source(view)


@sources_app.command("enable")
def sources_enable(source_id: int = SOURCE_ID_ARG, as_json: bool = JSON_OPTION) -> None:
    """Reactiva una fuente: vuelve a entrar en la ingesta diaria."""
    _set_active(source_id, True, as_json)


@sources_app.command("disable")
def sources_disable(source_id: int = SOURCE_ID_ARG, as_json: bool = JSON_OPTION) -> None:
    """Pausa una fuente: deja de entrar en la ingesta diaria (sus ofertas se conservan)."""
    _set_active(source_id, False, as_json)


# --- Alertas por correo y ofertas resumen ---------------------------------------------------


@alerts_app.command("poll")
def alerts_poll(as_json: bool = JSON_OPTION) -> None:
    """Lee ahora las alertas nuevas (IMAP en solo lectura y `data/inbox/`) y da de alta sus
    ofertas."""
    from app.services.ingestion.email.service import poll_email

    try:
        migrations.ensure_current()
        with session_scope() as session:
            result = poll_email(session, actor="user")
    except Exception as exc:
        _profile_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json(result))
    else:
        typer.secho(result.message, fg="yellow" if result.errors else None)
        for issue in result.errors:
            where = f" ({issue.item})" if issue.item else ""
            typer.secho(f"  ! {issue.message}{where}", fg="yellow")
        if result.summaries:
            typer.echo("  Los resúmenes están en «Alertas»: complétalos o descártalos.")
    if result.errors and not result.messages:
        raise typer.Exit(code=1)


@alerts_app.command("list")
def alerts_list(as_json: bool = JSON_OPTION) -> None:
    """Ofertas resumen (pending_detail), primero las que pasan el prefiltro."""
    from app.services.summaries import list_alerts

    try:
        migrations.ensure_current()
        with session_scope() as session:
            result = list_alerts(session)
    except Exception as exc:
        _profile_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json(result))
        return
    if not result.jobs:
        typer.echo("No hay ofertas resumen pendientes.")
        return
    typer.echo(f"{result.total} ofertas resumen, {result.passed} pasan el prefiltro.")
    for job in result.jobs:
        mark = "+" if job.prefilter_passed else "-"
        where = f" · {job.location}" if job.location else ""
        reason = f"  ({job.prefilter_reason})" if job.prefilter_reason else ""
        typer.echo(f"  {mark} {job.job_id:>5}  {job.title} — {job.company}{where}{reason}")


@alerts_app.command("expire")
def alerts_expire(as_json: bool = JSON_OPTION) -> None:
    """Cierra con `expired` los resúmenes sin completar más antiguos que `summary_expire_days`."""
    from app.services.summaries import expire_summaries

    try:
        migrations.ensure_current()
        with session_scope() as session:
            result = expire_summaries(session)
    except Exception as exc:
        _profile_fail(exc, as_json)
    typer.echo(dump_json(result) if as_json else result.message)


# --- Botón «Enviar a Job Hunter» ---------------------------------------------------------------


@capture_app.command("token")
def capture_token(as_json: bool = JSON_OPTION) -> None:
    """Genera un token nuevo para la extensión (el anterior deja de valer) y lo muestra una vez."""
    from app.services.capture import rotate_token

    settings = get_settings()
    token = rotate_token(settings)
    if as_json:
        typer.echo(json.dumps({"token": token, "extension_id": settings.capture_extension_id}))
        return
    typer.echo("Token nuevo (solo se muestra ahora; el anterior ya no vale):")
    typer.echo()
    typer.secho(f"  {token}", bold=True)
    typer.echo()
    typer.echo(
        "Pégalo en las opciones de la extensión «Enviar a Job Hunter» "
        "(clic derecho en su icono → Opciones)."
    )
    typer.echo(f"Origen aceptado: {settings.capture_origin}")


# --- Seguimiento (fase 10) -------------------------------------------------------------------


def _local(value: Any, all_day: bool = False) -> str:
    from app.services.process import local_zone

    local = value.astimezone(local_zone())
    return local.strftime("%d/%m/%Y") if all_day else local.strftime("%d/%m/%Y %H:%M")


def _render_followups(result: Any) -> None:
    if not result.followups:
        days = result.days_without_reply
        typer.echo(f"Ningún seguimiento pendiente ({days} días sin respuesta).")
        return
    typer.echo(f"Sin respuesta desde hace {result.days_without_reply} días o más:")
    for item in result.followups:
        typer.echo(f"{item.job_id:>5}  {item.days_waiting:>3} días  {item.title} · {item.company}")


def _render_upcoming(result: Any) -> None:
    if not result.items:
        typer.echo(f"Nada en los próximos {result.days} días.")
        return
    for item in result.items:
        when = _local(item.starts_at, item.all_day)
        typer.echo(f"{when:<16}  {item.title} · {item.job_title} ({item.company}) [{item.job_id}]")


CALENDAR_OUT_OPTION = typer.Option(
    None, "--out", help="Fichero de salida. Por defecto, data/calendar/jobhunter.ics."
)


@calendar_app.command("export")
def calendar_export(out: Path | None = CALENDAR_OUT_OPTION, as_json: bool = JSON_OPTION) -> None:
    """Escribe el .ics con los hitos futuros y los plazos, para importarlo en tu calendario."""
    from app.services import calendar_ics

    try:
        migrations.ensure_current()
        with session_scope() as session:
            path = calendar_ics.export_feed(session, out.resolve() if out else None)
    except Exception as exc:
        _profile_fail(exc, as_json)
    if as_json:
        typer.echo(json.dumps({"path": str(path)}, ensure_ascii=False))
        return
    typer.echo(f"Calendario escrito en {path}.")
    typer.echo("Impórtalo en Google Calendar (Configuración → Importar) o en tu cliente de correo.")


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


# Al final: los renderizadores de arriba ya existen.
register_tools(
    app,
    {
        "jobs": jobs_app,
        "events": events_app,
        "profile": profile_app,
        "match": match_app,
        "cv": cv_app,
        "templates": templates_app,
        "sources": sources_app,
    },
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
        "get_match": _render_match,
        "save_fit_assessment": _render_saved_assessment,
        "list_cv_templates": _render_templates,
        "save_cv_content": _render_cv_saved,
        "render_cv": _render_cv_render,
        "get_cv_content": _render_cv_view,
        "save_cv_verification": _render_cv_verification,
        "list_sources": _render_source_list,
        "save_source": _render_message,
        "record_source_run": _render_recorded_run,
        "list_followups_due": _render_followups,
        "list_upcoming": _render_upcoming,
    },
)
