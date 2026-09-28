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
match_app = typer.Typer(help="Encaje de las ofertas con el perfil.", no_args_is_help=True)
eval_app = typer.Typer(help="Evaluación de la calidad del matching.", no_args_is_help=True)
cv_app = typer.Typer(help="CVs a medida: contenido, renders y verificación.", no_args_is_help=True)
templates_app = typer.Typer(help="Plantillas de CV.", no_args_is_help=True)
app.add_typer(db_app, name="db")
app.add_typer(events_app, name="events")
app.add_typer(jobs_app, name="jobs")
app.add_typer(agents_app, name="agents")
app.add_typer(profile_app, name="profile")
app.add_typer(match_app, name="match")
app.add_typer(eval_app, name="eval")
app.add_typer(cv_app, name="cv")
app.add_typer(templates_app, name="templates")

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


register_tools(
    app,
    {
        "jobs": jobs_app,
        "events": events_app,
        "profile": profile_app,
        "match": match_app,
        "cv": cv_app,
        "templates": templates_app,
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
    },
)


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


def _render_worker_run(run: Any) -> None:
    for outcome in run.outcomes:
        if outcome.ok:
            detail = json.dumps(outcome.result, ensure_ascii=False) if outcome.result else ""
            typer.echo(f"[ok]    tarea {outcome.task_id} {outcome.kind} {detail}")
        else:
            failed = f"[error] tarea {outcome.task_id} {outcome.kind}: {outcome.error}"
            typer.secho(failed, fg="red")


@app.command()
def worker(
    once: bool = typer.Option(False, "--once", help="Vacía la cola y termina."),
    interval: float = typer.Option(5.0, help="Segundos entre pasadas (sin --once)."),
    as_json: bool = JSON_OPTION,
) -> None:
    """Ejecuta las tareas en segundo plano (scores, recálculos). Ctrl+C para parar."""
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
    typer.echo(f"Worker en marcha (cada {interval:g} s). Ctrl+C para parar.")
    try:
        worker_service.run_forever(interval, _render_worker_run)
    except KeyboardInterrupt:
        typer.echo("Worker parado.")


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
