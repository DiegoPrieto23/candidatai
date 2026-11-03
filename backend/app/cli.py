"""CLI `cai`: capa fina sobre `app.services`.

Este módulo es solo la raíz, y no carga la app: `cai --help`, el supervisor de `cai start` y la API
(`cai serve`) no pagan por importar los demás comandos (SQLAlchemy, httpx, python-docx…, unos 2 s
y más de 100 MB). Los demás viven en `app.cli_commands`, que se carga al pedir uno. Para listarlos
en la ayuda sin cargarlos, `COMMANDS` guarda el nombre y la primera línea de ayuda de cada uno (un
test comprueba que coincide con los de verdad).
"""

import inspect
import io
import sys
from functools import cache
from typing import Any

import click
import typer
from typer.core import TyperGroup

# Los comandos de `app.cli_commands` que se ven en `cai --help`, con el primer párrafo de su ayuda.
COMMANDS: dict[str, str] = {
    "doctor": "Comprueba que el entorno local está listo.",
    "openapi": "Esquema OpenAPI de la API (lo usa `pnpm gen:api` en el frontend).",
    "worker": (
        "Ejecuta las tareas en segundo plano (scores, recálculos) y la ingesta diaria de las "
        "fuentes a la hora de `connectors.daily_at`. Ctrl+C para parar."
    ),
    "status": "Recuento de ofertas por etapa y tareas pendientes del worker.",
    "schema": (
        "JSON Schema de lo que rellenas para una herramienta de escritura (extracción, "
        "valoración, CV, carta, respuestas…), cómo se envía y, con `example`, un ejemplo mínimo "
        "válido. Sin `name`, el catálogo. Úsalo antes de escribir el JSON."
    ),
    "followups": (
        "Candidaturas enviadas (etapa `applied`) sin respuesta desde hace N días o más, contando "
        "desde el envío o el último `followup_sent`, la que más espera primero, sin las que ya "
        "tienen 2 seguimientos ni las que tienen un correo de la empresa por revisar (ya "
        "contestó: mira `list_replies`); y `thanks_due`: entrevistas hechas en los últimos días "
        "sin agradecimiento. Con los nombres de los contactos y el borrador vigente."
    ),
    "upcoming": (
        "Entrevistas, pruebas y plazos (de los procesos y de las ofertas sin enviar) desde hoy "
        "hasta dentro de `days` días, por fecha. Horas en UTC: muéstralas en Europe/Madrid."
    ),
    "db": "Base de datos.",
    "events": "Eventos de las ofertas.",
    "jobs": "Ofertas: alta, consulta y extracción.",
    "agents": "Configuración de los agentes de IA.",
    "profile": "Perfil del candidato.",
    "match": "Encaje de las ofertas con el perfil.",
    "eval": "Evaluación de la calidad del matching.",
    "cv": "CVs a medida: contenido, renders y verificación.",
    "templates": "Plantillas de CV.",
    "sources": (
        "Fuentes de ofertas: empresas objetivo (ATS), portales con API y plataformas para la "
        "búsqueda con navegador."
    ),
    "alerts": "Alertas de empleo por correo y ofertas resumen (pending_detail).",
    "mail-sources": (
        "Buzones de las alertas por correo (fase 27.4). Se añaden y cambian en la UI, en Alertas "
        "por correo."
    ),
    "capture": "Botón «Enviar a CandidatAI» (extensión del navegador).",
    "calendar": "Calendario .ics de los procesos.",
    "stats": "Analítica de la búsqueda.",
    "applications": "Paquete de candidatura.",
    "letter": "Cartas de presentación.",
    "context": "Contexto del candidato (data/contexto/) y carpetas de documentos.",
    "prompts": "Avisos al usuario (captcha, login…) mientras el agente busca ofertas.",
    "skills": "Huecos de skills: lo que piden las ofertas y tu perfil no cubre.",
    "replies": "Respuestas de las empresas por correo: ingesta y propuestas del agente.",
    "drafts": "Borradores de seguimiento y agradecimiento (la app no envía nada).",
    "interviews": "Entrevistas: plan de preparación y repaso posterior en el hito.",
    "contacts": "Tu red de LinkedIn (Connections.csv) y los contactos de cada proceso.",
    "companies": "Dosier de cada empresa (skill research-company).",
    "received-offers": (
        "La oferta que te ha hecho la empresa (lo que ve el agente; los datos, en la ficha)."
    ),
    "requests": "Cola de encargos: lo que dejaste en la UI para tu agente (fase 19).",
    "demo": "Modo demo: una búsqueda ficticia para probar la app.",
}


@cache
def _commands() -> click.Group:
    from app.cli_commands import app as commands_app

    return typer.main.get_group(commands_app)


def first_paragraph(text: str | None) -> str:
    return " ".join(inspect.cleandoc(text or "").split("\n\n")[0].split())


class LazyGroup(TyperGroup):
    """Raíz de `cai`: sus comandos propios y, al pedir otro, los de `app.cli_commands`."""

    _listing = False

    def list_commands(self, ctx: click.Context) -> list[str]:
        return [*super().list_commands(ctx), *COMMANDS]

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        own = super().get_command(ctx, cmd_name)
        if own is not None:
            return own
        if self._listing and cmd_name in COMMANDS:
            return click.Command(cmd_name, help=COMMANDS[cmd_name])
        return _commands().get_command(ctx, cmd_name)

    def format_help(self, ctx: click.Context, formatter: Any) -> None:
        # Para la lista de la ayuda basta con el nombre y la línea de `COMMANDS`.
        self._listing = True
        try:
            super().format_help(ctx, formatter)
        finally:
            self._listing = False


app = typer.Typer(
    cls=LazyGroup,
    help="CandidatAI: gestión local de la búsqueda de empleo.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """CandidatAI: gestión local de la búsqueda de empleo."""
    # En Windows, si la salida va a una tubería (un agente leyendo `--json`), Python usa la
    # codificación ANSI del sistema. Forzamos UTF-8 para que tildes y eñes lleguen intactas.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")


@app.command()
def serve(
    port: int = typer.Option(8000, help="Puerto (siempre en 127.0.0.1)."),
    reload: bool = typer.Option(False, "--reload", help="Recarga al cambiar el código."),
    migrate: bool = typer.Option(
        False, "--migrate", hidden=True, help="Aplica las migraciones pendientes (`cai start`)."
    ),
) -> None:
    """Levanta la API para la UI en http://127.0.0.1:<puerto>."""
    import uvicorn

    from app.core import migrations
    from app.core.config import get_settings
    from app.services import container

    if migrate:
        migrations.upgrade()  # `cai start` no migra: lo hace aquí, que ya carga SQLAlchemy
    else:
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
    """Arranca CandidatAI entera (la API con la UI, y el worker) y abre el navegador.

    Ctrl+C para cerrarla."""
    from app.core.config import get_settings
    from app.services import launcher

    try:
        launcher.start(get_settings(), port, dev=dev, open_browser=not no_browser, say=typer.echo)
    except launcher.LaunchError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    except KeyboardInterrupt:
        typer.echo("Cancelado.")


@app.command()
def paths(as_json: bool = typer.Option(False, "--json", help="Salida en JSON.")) -> None:
    """Carpetas de la app: la de datos en uso y la de la app instalada en este sistema.

    La de la app instalada es la que fija el instalador en CAI_DATA_DIR. No crea ninguna."""
    from app.agent_interface.output import dump_json
    from app.core.config import REPO_ROOT, Settings, install_dir, installed_data_dir

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
