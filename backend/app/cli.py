"""CLI `cai`: capa fina sobre `app.services`."""

import io
import json
import logging
import shlex
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
from app.core.config import REPO_ROOT, data_root, get_settings
from app.core.db import session_scope
from app.services import profile
from app.services.doctor import CheckStatus, run_doctor

app = typer.Typer(help="CandidatAI: gestión local de la búsqueda de empleo.", no_args_is_help=True)
db_app = typer.Typer(help="Base de datos.", no_args_is_help=True)
events_app = typer.Typer(help="Eventos de las ofertas.", no_args_is_help=True)
jobs_app = typer.Typer(help="Ofertas: alta, consulta y extracción.", no_args_is_help=True)
agents_app = typer.Typer(help="Configuración de los agentes de IA.", no_args_is_help=True)
requests_app = typer.Typer(
    help="Cola de encargos: lo que dejaste en la UI para tu agente (fase 19).",
    no_args_is_help=True,
)
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
mail_sources_app = typer.Typer(
    help="Buzones de las alertas por correo (fase 27.4). Se añaden y cambian en la UI, en Alertas.",
    no_args_is_help=True,
)
calendar_app = typer.Typer(help="Calendario .ics de los procesos.", no_args_is_help=True)
stats_app = typer.Typer(help="Analítica de la búsqueda.", no_args_is_help=True)
applications_app = typer.Typer(help="Paquete de candidatura.", no_args_is_help=True)
letter_app = typer.Typer(help="Cartas de presentación.", no_args_is_help=True)
context_app = typer.Typer(
    help="Contexto del candidato (data/contexto/) y carpetas de documentos.", no_args_is_help=True
)
skills_app = typer.Typer(
    help="Huecos de skills: lo que piden las ofertas y tu perfil no cubre.", no_args_is_help=True
)
drafts_app = typer.Typer(
    help="Borradores de seguimiento y agradecimiento (la app no envía nada).",
    no_args_is_help=True,
)
companies_app = typer.Typer(
    help="Dosier de cada empresa (skill research-company).", no_args_is_help=True
)
contacts_app = typer.Typer(
    help="Tu red de LinkedIn (Connections.csv) y los contactos de cada proceso.",
    no_args_is_help=True,
)
interviews_app = typer.Typer(
    help="Entrevistas: plan de preparación y repaso posterior en el hito.", no_args_is_help=True
)
received_offers_app = typer.Typer(
    help="La oferta que te ha hecho la empresa (lo que ve el agente; los datos, en la ficha).",
    no_args_is_help=True,
)
replies_app = typer.Typer(
    help="Respuestas de las empresas por correo: ingesta y propuestas del agente.",
    no_args_is_help=True,
)
prompts_app = typer.Typer(
    help="Avisos al usuario (captcha, login…) mientras el agente busca ofertas.",
    no_args_is_help=True,
)
capture_app = typer.Typer(
    help="Botón «Enviar a CandidatAI» (extensión del navegador).", no_args_is_help=True
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
app.add_typer(mail_sources_app, name="mail-sources")
app.add_typer(capture_app, name="capture")
app.add_typer(calendar_app, name="calendar")
app.add_typer(stats_app, name="stats")
app.add_typer(applications_app, name="applications")
app.add_typer(letter_app, name="letter")
app.add_typer(context_app, name="context")
app.add_typer(prompts_app, name="prompts")
app.add_typer(skills_app, name="skills")
app.add_typer(replies_app, name="replies")
app.add_typer(drafts_app, name="drafts")
app.add_typer(interviews_app, name="interviews")
app.add_typer(contacts_app, name="contacts")
app.add_typer(companies_app, name="companies")
app.add_typer(received_offers_app, name="received-offers")
app.add_typer(requests_app, name="requests")
demo_app = typer.Typer(
    help="Modo demo: una búsqueda ficticia para probar la app.", no_args_is_help=True
)
app.add_typer(demo_app, name="demo")

JSON_OPTION = typer.Option(False, "--json", help="Salida en JSON.")
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_agents.py"

_MARKS = {
    CheckStatus.OK: ("OK", typer.colors.GREEN),
    CheckStatus.WARN: ("AVISO", typer.colors.YELLOW),
    CheckStatus.ERROR: ("ERROR", typer.colors.RED),
}


@app.callback()
def main() -> None:
    """CandidatAI: gestión local de la búsqueda de empleo."""
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
        typer.echo("CandidatAI · diagnóstico del entorno\n")
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

    from app.services import container

    migrations.ensure_current()  # mejor fallar aquí que en cada petición
    # En Docker, en todas las interfaces del contenedor: el compose la publica solo en 127.0.0.1.
    host = container.listen_host(get_settings())
    uvicorn.run("app.api.main:app", host=host, port=port, reload=reload)


@app.command()
def start(
    port: int = typer.Option(8000, help="Puerto de la app (siempre en 127.0.0.1)."),
    dev: bool = typer.Option(
        False, "--dev", help="Arranca también Vite (pnpm dev) para desarrollar."
    ),
    no_browser: bool = typer.Option(False, "--no-browser", help="No abre el navegador."),
) -> None:
    """Arranca CandidatAI entera (la API con la UI, y el worker) y abre el navegador. Ctrl+C para
    cerrarla."""
    from app.services import launcher

    try:
        launcher.start(get_settings(), port, dev=dev, open_browser=not no_browser, say=typer.echo)
    except launcher.LaunchError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    except KeyboardInterrupt:
        typer.echo("Cancelado.")


OPENAPI_OUT_OPTION = typer.Option(None, "--out", help="Fichero de salida. Por defecto, stdout.")


@app.command()
def paths(as_json: bool = JSON_OPTION) -> None:
    """Carpetas de la app: la de datos en uso y la que usa la app instalada en este sistema (la
    que fija el instalador en CAI_DATA_DIR). No crea ninguna."""
    from app.core.config import Settings, install_dir, installed_data_dir

    settings = Settings()  # sin `get_settings`: esa crea la carpeta de datos
    found = {
        "data_dir": str(settings.data_dir),
        "install_dir": str(install_dir()),
        "installed_data_dir": str(installed_data_dir()),
        "repo_root": str(REPO_ROOT),
    }
    if as_json:
        typer.echo(dump_json(found))
        return
    typer.echo(f"Datos en uso: {found['data_dir']}")
    typer.echo(f"App instalada en: {found['install_dir']}")
    typer.echo(f"Datos de la app instalada: {found['installed_data_dir']}")
    typer.echo(f"Código: {found['repo_root']}")


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
    if report.agent_requests:
        typer.echo(f"Encargos para tu agente: {report.agent_requests} (`cai requests list`)")


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
    if view.signals:
        typer.echo("\nSeñales de oferta dudosa (no cuentan en el score):")
        for signal in view.signals:
            typer.echo(f"  - {signal.code}: {signal.text}")
    if view.assessment:
        stale = " (de un cálculo anterior)" if view.assessment_stale else ""
        typer.echo(f"\nValoración del agente{stale}: {view.assessment.verdict}")
        typer.echo(view.assessment.rationale)


def _render_saved_assessment(result: Any) -> None:
    typer.echo(f"Valoración guardada para la oferta {result.job_id} (match {result.match_id}).")


def _render_saved_answers(result: Any) -> None:
    typer.echo(
        f"Respuestas guardadas para la oferta {result.job_id} (documento {result.document_id})."
    )
    if result.needs_user_input:
        typer.echo(f"{result.needs_user_input} esperan un dato tuyo: complétalas en la ficha.")


def _render_letter_brief(result: Any) -> None:
    typer.echo(
        f"Indicaciones de la carta guardadas para la oferta {result.job_id} "
        f"(máximo {result.max_words} palabras)."
    )


def _letter_render_line(render: Any) -> str:
    warnings = ", ".join(w.code for w in render.warnings) or "sin avisos"
    mark = " · para enviar" if render.selected else ""
    return (
        f"render {render.render_id}: {render.template_id}, {render.pages} pág., {warnings}{mark}"
        f"\n  {render.pdf_path}"
    )


def _render_letter(result: Any) -> None:
    typer.echo(f"Oferta {result.job_id} ({result.stage}) · límite {result.max_words} palabras")
    if result.brief and result.brief.instructions:
        typer.echo(f"Indicaciones de la oferta: {result.brief.instructions}")
    letter = result.letter
    if letter is None:
        typer.echo("Aún no hay carta.")
        return
    state = "sin verificar"
    if letter.verification is not None:
        state = "verificada" if letter.verification.passed else "no pasa la verificación"
    if letter.edited_by_user:
        state = "editada por ti"
    typer.echo(f"Carta {letter.document_id} · {letter.word_count} palabras · {state}\n")
    content = letter.content
    for block in (content.greeting, *(p.text for p in content.paragraphs), content.sign_off):
        typer.echo(block + "\n")
    for render in letter.renders:
        typer.echo(_letter_render_line(render))


def _render_letter_saved(result: Any) -> None:
    typer.echo(
        f"Carta {result.document_id} guardada para la oferta {result.job_id} "
        f"({result.word_count} palabras)."
    )
    typer.echo(_letter_render_line(result.render))


def _render_letter_render(result: Any) -> None:
    typer.echo(_letter_render_line(result))


def _render_letter_verification(result: Any) -> None:
    verdict = "pasa" if result.passed else "NO pasa"
    typer.echo(f"Verificación de la carta {result.document_id} guardada: {verdict}.")


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


DEMO_DIR_OPTION = typer.Option(
    None,
    "--dir",
    help="Carpeta de la demo (relativa a la raíz del repo o, instalada, a la carpeta de "
    "instalación). Por defecto, data-demo; en Docker, /data-demo (su volumen).",
)


@demo_app.command("seed")
def demo_seed(
    target: Path | None = DEMO_DIR_OPTION,
    force: bool = typer.Option(False, "--force", help="Recrea una demo que ya existe."),
    eval_cv: bool = typer.Option(
        False,
        "--eval-cv",
        help="Añade los 10 casos del eval de CV, aprobados y sin CV (en una demo existente, "
        "solo los que falten).",
    ),
    compat: bool = typer.Option(
        False,
        "--compat",
        help="Añade las 5 ofertas de la matriz de compatibilidad (evals/compat/), solo con su "
        "texto: por extraer.",
    ),
    lang: str = typer.Option(
        "es",
        "--lang",
        help="Idioma de la demo: es (candidata en Galicia) o en (candidata en Dublín, en inglés).",
    ),
    as_json: bool = JSON_OPTION,
) -> None:
    """Crea una carpeta de datos con 65 ofertas ficticias, 8 semanas de historial y 2 CVs."""
    from app.services import container, demo
    from app.services.evals.cv import CvEvalFileError

    docker = container.in_docker()
    if target is None:
        target = container.DEMO_MOUNT if docker else Path("data-demo")
    try:
        summary = demo.seed(target, force=force, eval_cv=eval_cv, compat=compat, lang=lang)
    except (demo.DemoSeedError, CvEvalFileError) as exc:
        if as_json:
            typer.echo(dump_json(ToolError("validation_error", str(exc)).payload()))
        else:
            typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None
    if as_json:
        typer.echo(dump_json(summary.model_dump(mode="json")))
        return
    typer.echo(f"Demo creada en {summary.data_dir}")
    typer.echo(f"  {summary.jobs} ofertas y {summary.events} eventos.")
    stages = ", ".join(f"{stage} {count}" for stage, count in summary.by_stage.items())
    typer.echo(f"  Por etapa: {stages}.")
    engine = f" (PDF con {summary.pdf_engine})" if summary.cvs else ""
    typer.echo(f"  CVs verificados: {summary.cvs}{engine}.")
    for warning in summary.warnings:
        typer.secho(f"Aviso: {warning}", fg=typer.colors.YELLOW, err=True)
    folder = target.as_posix()
    if docker:  # fase 26.3: se abre desde tu equipo, cambiando la carpeta del contenedor
        typer.echo("\nPara abrirla, desde la carpeta del repositorio en tu equipo:")
        typer.echo(f"  {container.DEMO_COMPOSE}")
        typer.echo("Para volver a tus datos: docker compose up -d")
        typer.echo("Tu agente, por MCP contra el contenedor, ve la carpeta que esté abierta.")
    elif data_root() != REPO_ROOT:  # fase 28.1: app instalada, con la UI ya compilada
        typer.echo("\nPara abrirla, cierra CandidatAI y, desde app/backend/:")
        if sys.platform == "win32":
            typer.echo(f'  $env:CAI_DATA_DIR = "{folder}"; uv run cai start')
        else:
            typer.echo(f"  CAI_DATA_DIR={shlex.quote(folder)} uv run cai start")
        typer.echo("Para volver a tus datos, ciérrala y abre CandidatAI como siempre.")
    elif sys.platform == "win32":
        typer.echo("\nPara abrirla (PowerShell, desde backend/):")
        typer.echo(f'  $env:CAI_DATA_DIR = "{folder}"; uv run cai serve')
        typer.echo("  y en otra terminal: cd frontend; pnpm dev")
    else:  # fase 26.1: bash o zsh
        typer.echo("\nPara abrirla (desde backend/):")
        typer.echo(f"  CAI_DATA_DIR={shlex.quote(folder)} uv run cai serve")
        typer.echo("  y en otra terminal: cd frontend && pnpm dev")
    if not docker:
        typer.echo(
            f"Con un agente, arráncalo con CAI_DATA_DIR={folder} para que el MCP use la demo."
        )
    if compat:
        typer.echo(
            "Matriz de compatibilidad: con tu agente, process-jobs, assess-fit, aprueba "
            "las de empleo.example.com/eval-cv/ y generate-cv; después `cai eval cv --agent …`."
        )
    if eval_cv:
        typer.echo(
            "Eval de CV: lanza `generate-cv` sobre las ofertas de empleo.example.com/eval-cv/ "
            "(«CV listo» pendiente) y después `cai eval cv`."
        )


@eval_app.command("cv")
def eval_cv_command(
    agent: str | None = typer.Option(
        None, "--agent", help="Solo los CVs que guardó este agente (`claude-code`, `codex`…)."
    ),
    min_coverage: float = typer.Option(
        0.8, "--min-coverage", min=0.0, max=1.0, help="Cobertura mínima de keywords (0-1)."
    ),
    as_json: bool = JSON_OPTION,
) -> None:
    """Comprueba los CVs que dejó `generate-cv` sobre los casos de evals/cv/ (en la demo)."""
    from app.services.evals import cv as cv_eval

    try:
        with session_scope() as session:
            report = cv_eval.evaluate(session, agent=agent, min_coverage=min_coverage)
    except (cv_eval.CvEvalFileError, cv_eval.CvEvalNotDemoError) as exc:
        if as_json:
            typer.echo(dump_json(ToolError("validation_error", str(exc)).payload()))
        else:
            typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None
    json_path, md_path = cv_eval.save_report(report, get_settings().evals_dir / "reports")
    if as_json:
        paths = [str(json_path), str(md_path)]
        typer.echo(dump_json({**report.model_dump(mode="json"), "report_paths": paths}))
        return
    who = report.agent or "todos los agentes"
    typer.echo(
        f"CV · {len(report.cases)} casos · {who} · evaluados {report.evaluated}, "
        f"pasan {report.passed}, pendientes {report.pending}"
    )
    for case in report.cases:
        failed = [c for c in case.checks if c.passed is False]
        line = f"  {case.id}: {cv_eval.STATUS_LABELS[case.status]}"
        if case.agent_name:
            line += f" ({case.agent_name})"
        typer.echo(line)
        for check in failed:
            typer.echo(f"    - {cv_eval.CHECKS[check.name]}: {check.detail}")
    typer.echo(f"\nInforme: {md_path}")


@eval_app.command("compat")
def eval_compat_command(
    agent: str = typer.Option(
        ..., "--agent", help="El agente del manifiesto (`claude`, `opencode`…)."
    ),
    model: str | None = typer.Option(None, "--model", help="El modelo, como lo escribe el agente."),
    preset: str | None = typer.Option(
        None, "--preset", help="Un preset del agente (p. ej. `local`)."
    ),
    import_: bool = typer.Option(
        False, "--import", help="No lanza nada: mide la demo en la que trabajaste a mano."
    ),
    approve_only: bool = typer.Option(
        False, "--approve", help="Solo aprueba en la demo las ofertas de la matriz (paso manual)."
    ),
    cases: int | None = typer.Option(
        None,
        "--cases",
        min=1,
        help="Solo las N primeras ofertas (p. ej. 1): pasada corta, con su demo y su resultado.",
    ),
    timeout: int | None = typer.Option(
        None, "--timeout", min=1, help="Minutos máximos por ejecución (por defecto, la política)."
    ),
    as_json: bool = JSON_OPTION,
) -> None:
    """Matriz de compatibilidad (fase 24.6): process-jobs, assess-fit y generate-cv con ese agente y
    modelo sobre una demo propia (`data-demo-compat-<agente>-<modelo>/`), medidos y guardados en
    evals/compat/. Lanza tu agente: usa tu suscripción o tu modelo, como los botones."""
    from app.services.evals import compat
    from app.services.evals import cv as cv_eval

    def say(message: str) -> None:
        if not as_json:
            typer.echo(message)

    try:
        if approve_only:
            target = compat.data_dir(agent, model, preset, cases)
            notes = compat.approve(target)
            if as_json:
                typer.echo(dump_json({"ok": True, "data_dir": target.name, "notes": notes}))
            say("Aprobadas en la demo." + (f" Ojo: {'; '.join(notes)}" if notes else ""))
            return
        if import_:
            result = compat.import_results(agent, model, preset, cases=cases)
        else:
            result = compat.run(
                agent,
                model,
                preset,
                timeout=timeout * 60 if timeout else None,
                progress=say,
                cases=cases,
            )
    except (compat.CompatError, cv_eval.CvEvalFileError, cv_eval.CvEvalNotDemoError) as exc:
        if as_json:
            typer.echo(dump_json(ToolError("validation_error", str(exc)).payload()))
        else:
            typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None
    path = compat.save(result)
    if as_json:
        typer.echo(dump_json({**result.model_dump(mode="json"), "result_path": str(path)}))
        return
    typer.echo(
        f"\n{result.display_name} · {result.model or result.preset or 'modelo por defecto'}: "
        f"extracción {result.fields_equal}/{result.fields_total} campos, "
        f"{result.assessed}/{len(result.extraction)} valoraciones, "
        f"CVs {result.cv.passed}/{result.cv.evaluated} pasan."
    )
    if result.manual_steps:
        typer.secho("\nFalta hacerlo a mano (este agente no puede en segundo plano):", bold=True)
        for number, line in enumerate(result.manual_steps, 1):
            typer.echo(f"  {number}. {line}")
    typer.echo(f"\nResultado: {path}\nInforme: {compat.REPORT_PATH}")


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
    logger = logging.getLogger("candidatai.worker")
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
        from app.services import agent_runner

        run = worker_service.run_pending()
        run.agent_runs = agent_runner.run_pending()  # las de «En segundo plano» (fase 19)
        if as_json:
            typer.echo(dump_json(run))
        elif run.outcomes or run.agent_runs:
            _render_worker_run(run)
            for agent_run in run.agent_runs:
                typer.echo(agent_runner.describe(agent_run))
        else:
            typer.echo("No hay tareas pendientes.")
        if run.failed or any(r.status in ("failed", "timeout") for r in run.agent_runs):
            raise typer.Exit(code=1)
        return
    log = _worker_logger()

    def on_run(run: Any) -> None:
        for outcome in run.outcomes:
            (log.info if outcome.ok else log.warning)(_outcome_line(outcome))

    from app.services.launcher import stop_on_signals

    log.info(f"Worker en marcha (cola cada {interval:g} s). Ctrl+C para parar.")
    # Fase 26.1: en macOS y Linux, `cai start` lo para con SIGTERM. Con el manejador puesto
    # también durante la limpieza, una segunda señal no la corta y no quedan huérfanos.
    with stop_on_signals():
        try:
            worker_service.run_scheduler(interval, on_run, log.info)
        except (KeyboardInterrupt, SystemExit):
            log.info("Worker parado.")
        finally:
            from app.services import agent_runner
            from app.services.applier.browser import shutdown_host

            if stopped := agent_runner.stop_active():  # segundo plano (fase 19): sin huérfanos
                log.info(f"Parada la ejecución en segundo plano en curso ({stopped}).")
            shutdown_host()  # el navegador de las candidaturas (fase 11), si se abrió
            for handler in list(log.handlers):  # en Windows, un fichero abierto no se puede borrar
                log.removeHandler(handler)
                handler.close()


# --- Perfil: validar, importar, comparar e iniciar ----------------------------------------------

PROFILE_PATH_ARG = typer.Argument(None, help="Ruta del perfil. Por defecto, data/profile.yaml.")


def _profile_path(path: Path | None) -> Path:
    """Ruta del perfil: relativa al directorio actual o, si ahí no existe, a la raíz del repo.

    Con `uv run --directory backend cai …` el proceso corre en `backend/`, pero la ruta se escribe
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
            "(skill `update-profile`) y luego ejecuta `cai profile validate` e `import`."
        )


# --- Contexto del candidato (fase 13) ---------------------------------------------------------


@context_app.command("init")
def context_init(as_json: bool = JSON_OPTION) -> None:
    """Crea los ficheros de contexto que falten (vacíos) y las carpetas de data/documentos/."""
    from app.services import context

    result = context.init()
    if as_json:
        typer.echo(dump_json(result))
        return
    for path in result.created:
        typer.echo(f"Creado data/{path}")
    for path in result.existing:
        typer.echo(f"Ya existía data/{path} (no se toca)")
    typer.echo(
        "Rellénalos con tu editor (o con el skill `update-profile`). Orientan a los skills, "
        "pero nunca respaldan un hecho: eso va en data/profile.yaml."
    )


def _render_context(view: Any) -> None:
    for item in view.files:
        if not item.exists:
            typer.echo(f"## {item.section}: no existe (crea los ficheros con `cai context init`)")
            continue
        state = "vacío" if item.empty else f"{item.size_bytes} bytes"
        typer.echo(f"## {item.section} ({state})")
        for warning in item.warnings:
            typer.secho(f"Aviso: {warning}", fg=typer.colors.YELLOW)
        if not item.empty:
            typer.echo(item.text)
        typer.echo("")


@jobs_app.command("signals")
def jobs_signals(
    recompute: bool = typer.Option(
        False, "--recompute", help="Recalcula las señales de oferta dudosa de todas las ofertas."
    ),
    as_json: bool = JSON_OPTION,
) -> None:
    """Señales de oferta dudosa (rango salarial amplio, empresa oculta, temporal, publicada hace
    meses, cribado con IA). Se calculan solas al extraer; esto las recalcula todas, p. ej. tras
    editar config/doubtful_patterns.yaml. No cambian el score."""
    from app.services import doubtful

    if not recompute:
        _fail_plain("Indica `--recompute`.", as_json)
    try:
        migrations.ensure_current()
        with session_scope() as session:
            result = doubtful.recompute_all(session)
    except Exception as exc:
        error = to_tool_error(exc)
        if as_json:
            typer.echo(dump_json(error.payload()))
        else:
            typer.secho(f"Error: {error.info.message}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if as_json:
        typer.echo(dump_json(result.model_dump()))
        return
    typer.echo(f"{result.jobs} ofertas revisadas; {result.with_signals} con alguna señal.")
    for code, count in result.counts.items():
        typer.echo(f"  {code}: {count}")


@applications_app.command("archive")
def applications_archive(
    job_id: int | None = typer.Argument(None, help="Id de la oferta enviada."),
    all_jobs: bool = typer.Option(False, "--all", help="Todas las enviadas sin carpeta aún."),
    as_json: bool = JSON_OPTION,
) -> None:
    """Archiva en data/documentos/candidaturas/ lo enviado (CV, carta y respuestas).

    Las candidaturas nuevas se archivan solas al marcarlas como enviadas; esto es para las de antes.
    Las que ya tienen carpeta no se tocan.
    """
    from app.services import application_archive

    if (job_id is None) == (not all_jobs):
        _fail_plain("Indica el id de una oferta o `--all`, uno de los dos.", as_json)
    try:
        migrations.ensure_current()
        with session_scope() as session:
            results = application_archive.archive_existing(session, job_id)
    except Exception as exc:
        error = to_tool_error(exc)
        if as_json:
            typer.echo(dump_json(error.payload()))
        else:
            typer.secho(f"Error: {error.info.message}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if as_json:
        typer.echo(json.dumps([r.model_dump() for r in results], ensure_ascii=False))
        return
    if not results:
        typer.echo("No hay candidaturas enviadas.")
    for result in results:
        state = "archivada en" if result.created else "ya estaba en"
        typer.echo(f"Oferta {result.job_id}: {state} data/{result.folder}")


def _fail_plain(message: str, as_json: bool) -> NoReturn:
    error = ToolError("invalid_request", message)
    if as_json:
        typer.echo(dump_json(error.payload()))
    else:
        typer.secho(f"Error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


# --- Plantillas: importar un CV de Word (solo CLI; las usa el skill import-cv-template) -----


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
    typer.echo("Completa template.yaml y ejecuta `cai templates validate` y `preview`.")


@templates_app.command("build-letter")
def templates_build_letter(
    template_id: str = TEMPLATE_ID_ARG,
    force: bool = FORCE_OPTION,
    as_json: bool = JSON_OPTION,
) -> None:
    """Crea letter.docx (carta a juego) de una plantilla docx tuya, desde su cabecera."""
    from app.services.documents import authoring

    try:
        result = authoring.build_letter(template_id, force=force)
    except Exception as exc:
        _templates_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json(result))
        return
    typer.echo(f"Carta creada: data/{result.path} ({result.header_blocks} bloques de cabecera).")
    for warning in result.warnings:
        typer.secho(f"  Aviso: {warning}", fg=typer.colors.YELLOW)
    typer.echo(f"Mírala con `cai templates preview {result.template_id} --letter`.")


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
    letter: bool = typer.Option(
        False, "--letter", help="Su diseño de carta de presentación, con una carta de muestra."
    ),
    as_json: bool = JSON_OPTION,
) -> None:
    """PDF y PNG de la plantilla (o de su carta) con el perfil demo o con el tuyo."""
    from app.services.documents import authoring

    try:
        if which not in ("demo", "real"):
            raise ValueError("`--profile` debe ser demo o real.")
        if which == "real":
            migrations.ensure_current()
            with session_scope() as session:
                result = authoring.preview_template(session, template_id, "real", letter)
        else:
            result = authoring.preview_template(None, template_id, "demo", letter)
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

KIND_OPTION = typer.Option(
    ...,
    "--kind",
    help=(
        "ATS: greenhouse, lever, ashby, personio, teamtailor, workable, smartrecruiters o "
        "recruitee. Portales: infojobs, adzuna, manfred o freehire."
    ),
)
NAME_OPTION = typer.Option(..., "--name", help="Empresa (en un ATS) o etiqueta de la búsqueda.")
SLUG_OPTION = typer.Option(None, "--slug", help="Slug del tablero del ATS (p. ej. `acme`).")
REGION_OPTION = typer.Option("global", "--region", help="Lever: `global` o `eu`.")
QUERY_OPTION = typer.Option(None, "--query", help="Portales: palabras de búsqueda.")
WHERE_OPTION = typer.Option(None, "--where", help="Adzuna: ubicación.")
PROVINCE_OPTION = typer.Option(None, "--province", help="InfoJobs: provincia (p. ej. `a-coruna`).")
COUNTRY_OPTION = typer.Option(
    "es", "--country", help="Adzuna y freehire: país (código de 2 letras)."
)
LANGUAGE_OPTION = typer.Option(
    None, "--language", help="Personio: idioma de la descripción (`es`, `en`…)."
)
LANG_OPTION = typer.Option("ES", "--lang", help="Manfred: idioma de las ofertas (`ES` o `EN`).")
REMOTE_ONLY_OPTION = typer.Option(False, "--remote-only", help="freehire: solo ofertas remotas.")
WEBSITE_OPTION = typer.Option(
    None, "--website", help="ATS: web de la empresa (p. ej. `acme.com`), para su logo en la UI."
)
KEYWORDS_OPTION = typer.Option(
    None, "--keywords", help="Palabras extra que dejan pasar un título, separadas por comas."
)
SOURCE_ID_ARG = typer.Argument(..., help="Id de la fuente (ver `cai sources list`).")


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
    language: str | None = None,
    lang: str = "ES",
    remote_only: bool = False,
    website: str | None = None,
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
            "language": language,
            "lang": lang,
            "remote_only": remote_only,
            "title_keywords": _csv(keywords) or [],
            "website": website,
        }
    )


def _render_source(source: Any) -> None:
    state = "activa" if source.active else "pausada"
    target = source.config.get("slug") or source.config.get("query") or ""
    if source.browse:
        browse = source.browse
        state = "navegación " + ("activada" if browse.allow_agent_browsing else "desactivada")
        target = f"{browse.platform}, prioridad {browse.priority}, acceso {browse.access}"
    typer.echo(f"{source.id:>4}  {source.kind_label:<15} {source.name} [{target}] ({state})")
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
            "Ejecuta `process-jobs` en tu agente para extraerlas."
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
    language: str | None = LANGUAGE_OPTION,
    lang: str = LANG_OPTION,
    remote_only: bool = REMOTE_ONLY_OPTION,
    website: str | None = WEBSITE_OPTION,
    as_json: bool = JSON_OPTION,
) -> None:
    """Añade una empresa objetivo (ATS + slug) o una búsqueda en un portal con API."""
    from app.services.ingestion import service as sources

    try:
        migrations.ensure_current()
        data = _source_input(
            kind,
            name,
            slug,
            region,
            query,
            where,
            province,
            country,
            keywords,
            language,
            lang,
            remote_only,
            website,
        )
        with session_scope() as session:
            view = sources.add_source(session, data)
    except Exception as exc:
        _profile_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json(view))
        return
    typer.echo(f"Fuente añadida. Pruébala con `cai sources test {view.id}`.")
    _render_source(view)


def _render_source_list(result: Any) -> None:
    if not result.sources:
        typer.echo("No hay fuentes. Añade una con `cai sources add`.")
    for source in result.sources:
        _render_source(source)


def _render_mail_sources(result: Any) -> None:
    if result.demo:
        typer.echo("Demo: no se lee ningún buzón IMAP.")
    if not result.sources:
        typer.echo("No hay buzones. Añade uno en la UI: Alertas → Añadir buzón.")
    for box in result.sources:
        state = "activo" if box.enabled else "desactivado"
        if box.kind == "folder":
            where = box.path
        else:
            where = f"{box.user} en {box.host}:{box.port}, carpeta «{box.folder}»"
            if not box.has_password:
                where += f" (falta la contraseña: {box.secret_ref})"
        origin = " (de .env)" if box.from_env else ""
        typer.echo(f"[{box.id}] {box.label}{origin}: {where}; {state}")
        if box.last_error:
            typer.secho(f"      Último error: {box.last_error.message}", fg="yellow")


@mail_sources_app.command("test")
def mail_sources_test(
    source_id: int = typer.Argument(..., help="Id del buzón (ver `cai mail-sources list`)."),
    as_json: bool = JSON_OPTION,
) -> None:
    """Prueba un buzón: login y apertura de su carpeta en solo lectura, sin leer correos."""
    from app.core.db import session_scope
    from app.services import mail_sources

    try:
        with session_scope() as session:
            result = mail_sources.probe_mail_source(session, source_id)
    except mail_sources.MailSourceNotFoundError as exc:
        error = ToolError("not_found", str(exc))
        if as_json:
            typer.echo(dump_json(error.payload()))
        else:
            typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None
    if as_json:
        typer.echo(dump_json(result))
    else:
        typer.secho(result.message, fg="green" if result.ok else "red")
    if not result.ok:
        raise typer.Exit(1)


def _render_message(result: Any) -> None:
    typer.echo(result.message)


def _render_agent_requests(result: Any) -> None:
    if not result.requests:
        typer.echo("No hay encargos.")
        return
    for request in result.requests:
        when = request.created_at.strftime("%Y-%m-%d %H:%M")
        typer.echo(f"#{request.id}  {when}  [{request.status}]  {request.label}")
        typer.echo(f"    {request.prompt}")
        if request.summary:
            typer.echo(f"    Hecho: {request.summary}")


def _render_search_titles(result: Any) -> None:
    roles = ", ".join(result.roles) or "ninguno (sin perfil)"
    typer.echo(f"Puestos buscados: {roles}")
    sections = (("Aprobadas o enviadas", result.positive), ("Descartadas", result.negative))
    for label, groups in sections:
        typer.echo("")
        typer.echo(f"{label} (últimos {result.days} días):")
        if not groups:
            typer.echo("  (ninguna)")
        for group in groups:
            extra = ""
            if group.matches_roles is False:
                extra = "  [no pasa el filtro previo]"
            if group.reasons:
                extra += "  " + ", ".join(f"{k} ×{v}" for k, v in group.reasons.items())
            typer.echo(f"  {group.count:>3}  {group.title}{extra}")


def _render_prompt(result: Any) -> None:
    left = f", quedan {result.seconds_left} s" if result.status == "pending" else ""
    typer.echo(f"Aviso {result.id} ({result.kind}): {result.status}{left}.")


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
    language: str | None = LANGUAGE_OPTION,
    lang: str = LANG_OPTION,
    remote_only: bool = REMOTE_ONLY_OPTION,
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
                kind,
                name,
                slug,
                region,
                query,
                where,
                province,
                country,
                keywords,
                language,
                lang,
                remote_only,
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
        typer.echo("No hay fuentes activas. Añade una con `cai sources add`.")
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


DISCOVER_FILE_OPTION = typer.Option(
    ..., "--file", help="Texto con una empresa por línea (`Nombre | slug` fuerza un slug)."
)
DISCOVER_ADD_OPTION = typer.Option(
    False, "--add", help="Da de alta las encontradas fiables (confirmadas o probables)."
)

_CONFIDENCE_LABEL = {
    "confirmed": "confirmada",
    "probable": "probable",
    "doubtful": "dudosa: compruébala antes",
}


def _render_discover(result: Any, add: bool) -> None:
    from app.schemas.sources import KIND_LABELS

    for item in result.companies:
        if not item.hits:
            tried = ", ".join(item.tried) or "ningún slug válido"
            typer.echo(f"- {item.company}: sin tablero (probado: {tried})")
        for hit in item.hits:
            label = KIND_LABELS.get(hit.kind, hit.kind)
            region = " (UE)" if hit.region == "eu" else ""
            name = f" «{hit.board_name}»" if hit.board_name else ""
            typer.echo(
                f"+ {item.company}: {label}{region} `{hit.slug}`{name}, {hit.jobs_count} ofertas, "
                f"{_CONFIDENCE_LABEL[hit.confidence]}"
            )
            if hit.sample_titles:
                typer.echo(f"    p. ej.: {'; '.join(hit.sample_titles)}")
            if hit.existing_source_id is not None:
                state = "añadida" if hit.existing_source_id in item.added_source_ids else "ya es"
                typer.echo(f"    {state} fuente {hit.existing_source_id}")
            elif not add or hit.confidence == "doubtful":
                typer.echo(f"    {hit.add_command}")
        for error in item.errors:
            typer.secho(f"    ! {error}", fg="yellow")
    typer.echo(result.message)
    if not add and any(h.existing_source_id is None for c in result.companies for h in c.hits):
        typer.echo("Para darlas de alta, ejecuta los comandos de arriba o repite con --add.")


@sources_app.command("discover")
def sources_discover(
    file: Path = DISCOVER_FILE_OPTION,
    add: bool = DISCOVER_ADD_OPTION,
    as_json: bool = JSON_OPTION,
) -> None:
    """Busca el tablero de Greenhouse, Lever o Ashby de cada empresa del fichero y lo propone
    como fuente (con --add, lo da de alta). Solo APIs públicas: sin agente ni tokens."""
    from app.services.ingestion import discover

    # Con `uv run --directory backend` el proceso corre en `backend/`: una ruta relativa vale
    # también desde la raíz del repo (`data/empresas.txt`).
    if not file.is_absolute() and not file.exists() and (REPO_ROOT / file).exists():
        file = REPO_ROOT / file
    try:
        companies = discover.read_companies(file)
        migrations.ensure_current()
        with session_scope() as session:
            result = discover.discover(session, companies, add=add)
    except Exception as exc:
        _profile_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json(result))
    else:
        _render_discover(result, add)


@sources_app.command("enable")
def sources_enable(source_id: int = SOURCE_ID_ARG, as_json: bool = JSON_OPTION) -> None:
    """Reactiva una fuente: vuelve a entrar en la ingesta diaria."""
    _set_active(source_id, True, as_json)


@sources_app.command("disable")
def sources_disable(source_id: int = SOURCE_ID_ARG, as_json: bool = JSON_OPTION) -> None:
    """Pausa una fuente: deja de entrar en la ingesta diaria (sus ofertas se conservan)."""
    _set_active(source_id, False, as_json)


# --- Búsqueda pública de LinkedIn (fase 22, ADR-033) -----------------------------------------

linkedin_public_app = typer.Typer(
    help="Búsqueda pública de LinkedIn sin sesión. Se activa solo en la UI (Plataformas).",
    no_args_is_help=True,
)
sources_app.add_typer(linkedin_public_app, name="linkedin-public")


def _render_linkedin_public(view: Any) -> None:
    state = "activada" if view.enabled else "desactivada (se activa en la UI, en Plataformas)"
    typer.echo(f"Búsqueda pública de LinkedIn: {state}")
    if view.enabled:
        detail = "sí" if view.fetch_detail else "no (entran como resumen)"
        typer.echo(f"  Descarga la descripción: {detail}")
    for search in view.searches:
        what = " · ".join(v for v in (search.keywords, search.location) if v)
        typer.echo(f"  - {what or search.url}")
    for issue in view.ignored:
        typer.secho(f"  ! {issue.item}: {issue.message}", fg="yellow")
    if view.blocked_at:
        typer.secho(f"  Último bloqueo de LinkedIn: {view.blocked_at:%d/%m %H:%M} UTC", fg="yellow")
    if view.next_run_at:
        typer.echo(f"  Próxima ejecución posible: {view.next_run_at:%d/%m %H:%M} UTC")


@linkedin_public_app.command("status")
def linkedin_public_status(as_json: bool = JSON_OPTION) -> None:
    """Estado, búsquedas que lanzará y límites."""
    from app.services.ingestion import linkedin_public

    try:
        migrations.ensure_current()
        with session_scope() as session:
            view = linkedin_public.get_view(session)
    except Exception as exc:
        _profile_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json(view))
    else:
        _render_linkedin_public(view)


@linkedin_public_app.command("run")
def linkedin_public_run(as_json: bool = JSON_OPTION) -> None:
    """Ejecuta ahora la búsqueda, si está activada y le toca (una vez al día). Tarda: hay una
    pausa de al menos 10 s entre peticiones."""
    from app.services.ingestion import linkedin_public

    try:
        migrations.ensure_current()
        with session_scope() as session:
            result = linkedin_public.run(session, actor="user")
    except Exception as exc:
        _profile_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json(result))
    else:
        typer.echo(result.message)
        for issue in result.errors:
            typer.secho(f"  ! {issue.message}", fg="yellow")
    if result.blocked:
        raise typer.Exit(code=1)


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


# --- Botón «Enviar a CandidatAI» ---------------------------------------------------------------


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
        "Pégalo en las opciones de la extensión «Enviar a CandidatAI» "
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
    else:
        typer.echo(f"Sin respuesta desde hace {result.days_without_reply} días o más:")
    for item in result.followups:
        sent = f"  ({item.followups_sent}/{result.max_followups} enviados)"
        draft = "  [borrador]" if item.draft_id else ""
        typer.echo(
            f"{item.job_id:>5}  {item.days_waiting:>3} días  {item.title} · {item.company}"
            f"{sent if item.followups_sent else ''}{draft}"
        )
    if result.thanks_due:
        typer.echo("Entrevistas por agradecer:")
    for thanks in result.thanks_due:
        when = _local(thanks.interview_at, False)
        draft = "  [borrador]" if thanks.draft_id else ""
        typer.echo(f"{thanks.job_id:>5}  {when}  {thanks.title} · {thanks.company}{draft}")


def _render_upcoming(result: Any) -> None:
    if not result.items:
        typer.echo(f"Nada en los próximos {result.days} días.")
        return
    for item in result.items:
        when = _local(item.starts_at, item.all_day)
        typer.echo(f"{when:<16}  {item.title} · {item.job_title} ({item.company}) [{item.job_id}]")


def _render_interviews(view: Any) -> None:
    offer = " · oferta recibida" if view.offer_received else ""
    typer.echo(f"{view.job_title} ({view.company}) [{view.job_id}] · {view.stage or '—'}{offer}")
    if not view.interviews:
        typer.echo("Sin entrevistas anotadas.")
    for item in view.interviews:
        when = _local(item.starts_at, item.all_day)
        extras = []
        if item.prep_plan:
            extras.append(f"plan de {len(item.prep_plan.blocks)} bloques")
        if item.debrief_notes:
            extras.append("con repaso")
        extra = f"  ({', '.join(extras)})" if extras else ""
        typer.echo(f"  [{item.id}] {when:<16}  {item.title} · {item.status}{extra}")


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.0%}"


def _render_skill_gaps(view: Any) -> None:
    marks = {"gap": "no la tengo", "have": "la tengo"}
    typer.echo(
        f"{len(view.gaps)} skills ausentes en {view.jobs_considered} ofertas "
        f"(abiertas y aprobadas o enviadas en {view.days} días):"
    )
    for gap in view.gaps:
        mark = f"  [{marks[gap.mark]}]" if gap.mark else ""
        jobs = "oferta " if gap.jobs_count == 1 else "ofertas"
        typer.echo(
            f"  {gap.skill:<32} {gap.jobs_count:>3} {jobs} ({gap.must_have_count} oblig., "
            f"{gap.nice_to_have_count} des.)  peso {gap.weight}{mark}"
        )


def _render_funnel(result: Any) -> None:
    since = f" desde el {result.since:%d/%m/%Y}" if result.since else ""
    typer.echo(f"Embudo{since} ({result.duplicates_excluded} duplicadas fuera):")
    for step in result.steps:
        rate = "" if step.rate_from_previous is None else f"  {_pct(step.rate_from_previous)}"
        typer.echo(f"  {step.label:<14} {step.count:>5}{rate}")
    rt = result.response_time
    if rt.median_days is not None:
        typer.echo(
            f"Primera respuesta: mediana {rt.median_days} días, media {rt.mean_days} días "
            f"({rt.replied} de {rt.applied} enviadas)."
        )
    typer.echo(f"Sin respuesta: {rt.awaiting_reply} esperando, {rt.closed_without_reply} cerradas.")
    for source in result.by_source:
        typer.echo(
            f"  {source.name} ({source.kind}): {source.found} encontradas, "
            f"{source.applied} enviadas, respuesta {_pct(source.reply_rate)}"
        )
    labels = {"given": "Con referencia", "requested": "Referencia pedida", "none": "Sin referencia"}
    for group in result.by_referral:
        if group.applied:
            typer.echo(
                f"  {labels[group.group]}: {group.applied} enviadas, "
                f"respuesta {_pct(group.reply_rate)}"
            )
    if result.discard_reasons:
        reasons = ", ".join(f"{r.reason} ({r.count})" for r in result.discard_reasons)
        typer.echo(f"Descartes: {reasons}")
    if result.hard_filter_failures:
        filters = ", ".join(f"{f.filter} ({f.count})" for f in result.hard_filter_failures)
        typer.echo(f"Filtros duros: {filters}")


def _render_calibration(result: Any) -> None:
    since = f" desde el {result.since:%d/%m/%Y}" if result.since else ""
    typer.echo(
        f"¿Acierta el score? Candidaturas enviadas{since}: {result.total.applied}. Orientativo: "
        f"intervalo al {result.confidence:.0%}; «pocos datos» con menos de {result.min_cases}."
    )
    sections = (
        ("Score al enviar", result.by_score),
        ("Veredicto del agente", result.by_verdict),
        ("Fuente", result.by_source),
        ("Portal", result.by_platform),
        ("Plantilla del CV", result.by_template),
        ("Carta", result.by_cover_letter),
        ("Referencia", result.by_referral),
        ("Días hasta el envío", result.by_days_to_apply),
        (
            "Señal de oferta dudosa (las de ahora; una oferta puede estar en varias)",
            result.by_signal,
        ),
    )
    for title, groups in sections:
        typer.echo(f"{title}:")
        for g in groups:
            if not g.applied:
                continue
            reply, interview = g.reply_rate, g.interview_rate
            low = "  (pocos datos)" if g.low_data else ""
            sent = "enviada " if g.applied == 1 else "enviadas"
            typer.echo(
                f"  {g.label:<22} {g.applied:>4} {sent} · respuesta {_pct(reply.rate)} "
                f"[{_pct(reply.low)}-{_pct(reply.high)}] · entrevista {_pct(interview.rate)}"
                f"{low}"
            )


@stats_app.command("story")
def stats_story(as_json: bool = JSON_OPTION) -> None:
    """Tu búsqueda entera en números agregados (ofertas evaluadas, candidaturas, respuestas,
    entrevistas y ofertas, con fechas) y una línea para pegar en un README. Sin empresas ni datos
    personales; publicarlo o no lo decides tú."""
    from app.services import analytics

    with session_scope() as session:
        story = analytics.get_search_story(session)
    if as_json:
        typer.echo(dump_json(story.model_dump(mode="json")))
        return
    if not story.found:
        typer.echo("Aún no hay ofertas: no hay historia que contar.")
        return
    period = (
        f"Del {story.started_on:%d/%m/%Y} al {story.last_activity_on:%d/%m/%Y} "
        f"({story.weeks} semanas)."
    )
    typer.echo(period)
    rows = (
        ("Ofertas vistas", story.found),
        ("Evaluadas", story.evaluated),
        ("Aprobadas", story.approved),
        ("Candidaturas", story.applied),
        ("Con respuesta", story.replied),
        ("Entrevistas", story.interviews),
        ("Ofertas recibidas", story.offers),
        ("Aceptadas", story.accepted),
    )
    for label, value in rows:
        typer.echo(f"  {label:<18} {value:>6}")
    if story.applied:
        typer.echo(
            f"Respuesta {_pct(story.reply_rate)}, entrevista {_pct(story.interview_rate)} "
            "de las enviadas."
        )
    typer.echo("\nPara el README (español):")
    typer.echo(story.markdown["es"])
    typer.echo("\nFor the README (English):")
    typer.echo(story.markdown["en"])


CALENDAR_OUT_OPTION = typer.Option(
    None, "--out", help="Fichero de salida. Por defecto, data/calendar/candidatai.ics."
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
    # Mismo intérprete que `cai` (el venv del backend ya trae pyyaml, la única dependencia).
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


def _yes_no(value: bool | None) -> str:
    return "sin comprobar" if value is None else ("sí" if value else "no")


@agents_app.command("list")
def agents_list(
    as_json: bool = JSON_OPTION,
    refresh: bool = typer.Option(False, "--refresh", help="Vuelve a detectar sin usar la caché."),
) -> None:
    """Los agentes del manifiesto: qué son, qué saben hacer y si los tienes instalados."""
    from app.services import agent_launch, agent_registry

    try:
        if as_json:  # lo mismo que `GET /agent/agents`, con tus preferencias (fase 24.4)
            with session_scope() as session:
                typer.echo(dump_json(agent_launch.overview(session, refresh=refresh)))
            return
        listed = agent_registry.list_agents(refresh=refresh)
    except agent_registry.ManifestError as exc:
        _fail_plain(str(exc), as_json)
    for entry in listed.agents:
        state = "habilitado" if entry.enabled else "solo compatible vía AGENTS.md"
        if not entry.enabled and entry.info.note:
            state = "deshabilitado"
        found = entry.version or entry.detect_error or "instalado"
        installed = found if entry.installed else "no instalado"
        license_ = f"{entry.info.license}{', open-source' if entry.info.open_source else ''}"
        caps = entry.capabilities
        typer.secho(f"{entry.info.display_name} ({entry.name})", bold=True)
        typer.echo(f"  {state} · {installed} · {entry.info.vendor}, {license_}")
        typer.echo(
            f"  MCP {_yes_no(caps.mcp)} · subagentes {caps.subagents} · nivel "
            f"{caps.isolation_level} · segundo plano {_yes_no(caps.headless)} · modelos locales "
            f"{_yes_no(caps.local_models)}"
        )
        if entry.info.note:
            typer.secho(f"  {entry.info.note}", fg="yellow")


def _instruction_tokens() -> None:
    from app.services import instruction_size

    sizes = instruction_size.measure()
    per = instruction_size.CHARS_PER_TOKEN
    typer.echo(f"CandidatAI · tokens de las instrucciones (aprox., {per} caracteres por token)\n")
    labels = {"instructions": "Instrucciones", "skill": "Skills", "role": "Roles"}
    for kind, label in labels.items():
        rows = sorted(
            (i for i in sizes.items if i.kind == kind), key=lambda i: i.tokens, reverse=True
        )
        typer.secho(label, bold=True)
        for item in rows:
            mark = typer.style("  > límite", fg="yellow") if item.over_limit else ""
            typer.echo(f"  {item.tokens:>6}  {item.name}{mark}")
    base = sizes.total("AGENTS.md")
    typer.echo(
        f"\nUna valoración (AGENTS.md + assess-fit): ~{base + sizes.total('assess-fit')} tokens; "
        f"un CV (AGENTS.md + generate-cv + writer + verifier): "
        f"~{base + sizes.total('generate-cv', 'writer', 'verifier')} tokens."
    )
    over = [i.name for i in sizes.items if i.over_limit]
    if over:
        typer.secho(f"Skills por encima de {sizes.limit} tokens: {', '.join(over)}.", fg="yellow")


@agents_app.command("doctor")
def agents_doctor(
    refresh: bool = typer.Option(False, "--refresh", help="Vuelve a detectar sin usar la caché."),
    tokens: bool = typer.Option(
        False, "--tokens", help="Tokens estimados de AGENTS.md y de cada skill y rol."
    ),
) -> None:
    """Qué agentes tienes, cuál se usaría hoy y por qué, y qué falta para los demás."""
    from app.services.doctor import agents_overview

    if tokens:
        _instruction_tokens()
        return
    overview = agents_overview(get_settings(), refresh=refresh)
    typer.echo("CandidatAI · agentes de IA\n")
    if overview.error:
        typer.secho(overview.error, fg="red", err=True)
        raise typer.Exit(code=1)
    if overview.selected:
        typer.secho(f"Se usaría: {overview.selected} ({overview.selected_reason}).", bold=True)
    else:
        typer.secho(f"No se usaría ninguno: {overview.selected_reason}", fg="yellow", bold=True)
    if overview.background:
        typer.echo(f"En segundo plano: {overview.background}.")
    else:
        typer.echo(f"En segundo plano: no disponible ({overview.background_reason})")
    if sys.platform != "win32":  # fase 26.1: qué terminal abrirían los botones
        from app.services import terminals

        found = terminals.find()
        if isinstance(found, str):
            typer.secho(f"Terminal para los botones: ninguna. {found}", fg="yellow")
        else:
            typer.echo(f"Terminal para los botones: {found.name} ({found.exe}).")
    for line in overview.agents:
        mark, color = ("OK", typer.colors.GREEN) if line.installed else ("--", None)
        found = (line.version or "instalado") if line.installed else "no instalado"
        typer.echo("")
        typer.secho(f"[{mark:^4}] ", fg=color, bold=True, nl=False)
        open_source = ", open-source" if line.open_source else ""
        typer.echo(f"{line.display_name} ({line.name}): {found}{open_source}")
        for item in line.missing:
            typer.echo(f"       - {item}")
        if not line.missing:
            typer.echo("       listo")
    _local_models_section()


def _local_models_section() -> None:
    """Fase 24.6: el Ollama de este equipo, solo con sus metadatos."""
    from sqlalchemy.exc import SQLAlchemyError

    from app.services import local_models

    try:
        with session_scope() as session:
            status = local_models.diagnose_for(session)
    except SQLAlchemyError:  # sin base de datos todavía: sin el aviso del modelo para redactar
        status = local_models.diagnose()
    typer.echo("")
    typer.secho("Modelos locales (Ollama)", bold=True)
    if not status.running:
        typer.echo(f"  {status.error or 'Ollama no responde.'} Ver docs/MODELOS_GRATIS.md.")
        return
    env = f"{status.env_context}" if status.env_context else "sin poner"
    typer.echo(f"  {status.url} · versión {status.version} · OLLAMA_CONTEXT_LENGTH {env}")
    for item in status.models:
        size = f"{item.parameter_size or '?'}"
        tools = {True: "herramientas sí", False: "herramientas no", None: "herramientas ?"}
        typer.echo(
            f"  - {item.name}: {size}, contexto {item.context} ({item.context_source}), "
            f"{tools[item.tools]}"
        )
    for warning in status.warnings:
        typer.secho(f"  ! {warning.text}", fg="yellow")


# --- Respuestas de las empresas (fase 15) ---------------------------------------------------


@replies_app.command("poll")
def replies_poll(as_json: bool = JSON_OPTION) -> None:
    """Lee ahora los correos de las empresas de tus procesos (IMAP en solo lectura y
    `data/inbox/respuestas/`). Solo guarda los que casan con una candidatura enviada."""
    from app.services.replies import poll_replies

    try:
        migrations.ensure_current()
        with session_scope() as session:
            result = poll_replies(session)
    except Exception as exc:
        _profile_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json(result))
    else:
        typer.secho(result.message, fg="yellow" if result.errors else None)
        for issue in result.errors:
            where = f" ({issue.item})" if issue.item else ""
            typer.secho(f"  ! {issue.message}{where}", fg="yellow")
        if result.created:
            typer.echo("  Clasifícalos con review-replies y revísalos en «Respuestas».")
    if result.errors and not result.created:
        raise typer.Exit(code=1)


def _render_replies(result: Any) -> None:
    from app.services.process import local_zone

    if not result.replies:
        typer.echo("No hay respuestas.")
        return
    for item in result.replies:
        when = (
            item.received_at.astimezone(local_zone()).strftime("%d/%m/%Y %H:%M")
            if item.received_at
            else "?"
        )
        jobs = ", ".join(str(j) for j in item.candidate_job_ids)
        proposal = f" → {item.proposal_event} ({item.confidence})" if item.proposal_event else ""
        flags = " [riesgo]" if item.risk_flags else ""
        typer.echo(
            f"  {item.reply_id:>5}  {item.status:<9} {when}  {item.sender}  ofertas {jobs}"
            f"{proposal}{flags}"
        )


# --- Red de LinkedIn (fase 18) --------------------------------------------------------------

CONNECTIONS_ARG = typer.Argument(
    None,
    help="El Connections.csv de la exportación de LinkedIn. Por defecto, "
    "data/documentos/linkedin/Connections.csv.",
)


@contacts_app.command("import-linkedin")
def contacts_import_linkedin(
    path: Path | None = CONNECTIONS_ARG, as_json: bool = JSON_OPTION
) -> None:
    """Importa tus contactos de LinkedIn (la exportación oficial) y los cruza con tus ofertas.

    Sincroniza: añade los nuevos, actualiza los cambiados y quita los que ya no están. No guarda
    emails ni navega LinkedIn."""
    from app.services import network

    # Con `uv run --directory backend` el proceso corre en `backend/`: una ruta relativa vale
    # también desde la raíz del repo.
    relative = path is not None and not path.is_absolute() and not path.exists()
    if relative and path is not None and (REPO_ROOT / path).exists():
        path = REPO_ROOT / path
    try:
        migrations.ensure_current()
        with session_scope() as session:
            result = network.import_connections(session, path)
    except Exception as exc:
        _profile_fail(exc, as_json)
    if as_json:
        typer.echo(dump_json(result))
        return
    typer.echo(result.message)
    if result.skipped:
        typer.echo(f"  {result.skipped} filas saltadas (sin nombre o repetidas).")
    if result.without_company:
        typer.echo(f"  {result.without_company} personas sin empresa: no se cruzan con ofertas.")


_RELATION_LABEL = {
    "referral": "referencia",
    "recruiter": "recruiter",
    "hiring_manager": "responsable",
}
_REFERRAL_LABEL = {"requested": "referencia pedida", "given": "referencia dada"}


def _render_job_contacts(view: Any) -> None:
    typer.echo(f"Oferta {view.job_id} · {view.company}")
    typer.echo("Contactos del proceso:" if view.contacts else "Sin contactos en el proceso.")
    for c in view.contacts:
        extra = [
            x
            for x in (_RELATION_LABEL.get(c.relation or ""), _REFERRAL_LABEL.get(c.referral or ""))
            if x
        ]
        role = f" · {c.role}" if c.role else ""
        tags = f"  [{', '.join(extra)}]" if extra else ""
        typer.echo(f"  #{c.id} {c.name}{role}{tags}")
    if not view.network_imported:
        typer.echo("Red de LinkedIn sin importar: cai contacts import-linkedin")
        return
    typer.echo(
        f"Conoces a {len(view.network)} en {view.company}:"
        if view.network
        else "Nadie de tu red trabaja ahí."
    )
    for person in view.network:
        position = f" · {person.position}" if person.position else ""
        probable = " (empresa probable)" if person.match == "probable" else ""
        added = "  [en el proceso]" if person.in_process else ""
        typer.echo(f"  {person.name}{position}{probable}{added}")


def _render_company_research(view: Any) -> None:
    research = view.research
    if research is None:
        typer.echo(f"{view.company}: sin dosier. Usa el skill research-company.")
        return
    content = research.content
    typer.echo(f"{view.company} · dosier de hace {research.age_days} días ({research.file})")
    if research.risk_flags:
        typer.secho("  Ojo: contiene frases dirigidas a una IA.", fg="yellow")
    typer.echo(content.summary)
    if content.stack:
        typer.echo(f"Stack: {', '.join(content.stack)}")
    for n, source in enumerate(content.sources, start=1):
        typer.echo(f"  [{n}] {source.title} · {source.url}")


_WORK_MODE_LABEL = {"remote": "remoto", "hybrid": "híbrido", "onsite": "presencial"}


def _render_received_offer(view: Any) -> None:
    typer.echo(f"Oferta recibida · oferta {view.job_id}")
    if view.amounts_private:
        typer.echo("  Importes: privados")
    else:
        period = "año" if view.period == "year" else "mes"
        has_base = view.base_salary is not None
        fixed = f"{view.base_salary} {view.currency}/{period}" if has_base else "—"
        variable = f" + variable {view.variable}/año" if view.variable is not None else ""
        typer.echo(f"  Fijo: {fixed}{variable}")
    for label, value in (
        ("Modalidad", _WORK_MODE_LABEL.get(view.work_mode or "")),
        ("Ubicación", view.location),
        ("Incorporación", view.start_date),
        ("Responder antes de", view.respond_by),
        ("Beneficios", view.benefits),
        ("Notas", view.notes),
    ):
        if value:
            typer.echo(f"  {label}: {value}")


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
        "mail-sources": mail_sources_app,
        "stats": stats_app,
        "applications": applications_app,
        "letter": letter_app,
        "prompts": prompts_app,
        "context": context_app,
        "skills": skills_app,
        "replies": replies_app,
        "drafts": drafts_app,
        "interviews": interviews_app,
        "contacts": contacts_app,
        "companies": companies_app,
        "received-offers": received_offers_app,
        "requests": requests_app,
    },
    {
        "list_agent_requests": _render_agent_requests,
        "complete_agent_request": _render_message,
        "get_status": _render_status,
        "get_job_contacts": _render_job_contacts,
        "get_company_research": _render_company_research,
        "get_received_offer": _render_received_offer,
        "save_company_research": _render_message,
        "add_job_from_url": _render_added,
        "add_job_from_text": _render_added,
        "list_jobs": _render_jobs,
        "get_job": _render_job,
        "check_job_open": _render_message,
        "get_search_titles": _render_search_titles,
        "save_extraction": _render_saved_extraction,
        "add_event": _render_event,
        "get_timeline": _render_timeline,
        "get_profile": _render_profile,
        "get_context": _render_context,
        "get_match": _render_match,
        "save_fit_assessment": _render_saved_assessment,
        "list_cv_templates": _render_templates,
        "save_cv_content": _render_cv_saved,
        "render_cv": _render_cv_render,
        "get_cv_content": _render_cv_view,
        "save_cv_verification": _render_cv_verification,
        "list_sources": _render_source_list,
        "list_mail_sources": _render_mail_sources,
        "save_source": _render_message,
        "record_source_run": _render_recorded_run,
        "request_user_action": _render_prompt,
        "wait_user_action": _render_prompt,
        "list_followups_due": _render_followups,
        "list_replies": _render_replies,
        "save_reply_proposal": _render_message,
        "save_message_draft": _render_message,
        "get_interviews": _render_interviews,
        "save_interview_plan": _render_message,
        "save_interview_notes": _render_message,
        "list_upcoming": _render_upcoming,
        "get_funnel_stats": _render_funnel,
        "get_calibration": _render_calibration,
        "get_skill_gaps": _render_skill_gaps,
        "save_application_answers": _render_saved_answers,
        "save_cover_letter_brief": _render_letter_brief,
        "get_cover_letter": _render_letter,
        "save_cover_letter": _render_letter_saved,
        "render_cover_letter": _render_letter_render,
        "save_cover_letter_verification": _render_letter_verification,
    },
)
