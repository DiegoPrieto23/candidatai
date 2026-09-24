"""Comandos `jh` derivados del registro de herramientas (paridad con la MCP por construcción).

Cada comando recoge sus argumentos como texto, lee `--file` si lo hay y llama a `runner.call_tool`
con el mismo diccionario que enviaría un cliente MCP. Con `--json` imprime exactamente el mismo JSON
que la herramienta MCP (o el mismo error) y la llamada queda en `mcp_calls` con canal `cli`.
"""

import inspect
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

import typer
from pydantic import BaseModel

from app.agent_interface.errors import ToolError
from app.agent_interface.registry import CallContext, ToolSpec
from app.agent_interface.runner import call_tool
from app.agent_interface.tools import TOOLS
from app.core.config import REPO_ROOT, get_settings


def dump_json(payload: BaseModel | dict[str, Any]) -> str:
    """JSON compacto, igual en los dos canales."""
    data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _fail(error: ToolError, as_json: bool) -> NoReturn:
    if as_json:
        typer.echo(dump_json(error.payload()))
    else:
        typer.secho(f"Error: {error.info.message}", fg=typer.colors.RED, err=True)
        for detail in error.info.details:
            received = f" (recibido: {detail.received!r})" if detail.received is not None else ""
            typer.secho(f"  - {detail.field}: {detail.reason}{received}", err=True)
    raise typer.Exit(code=1)


def resolve_input_file(path: Path) -> Path:
    """Ruta absoluta de `--file`, que debe estar dentro de `data/tmp/`.

    Una ruta relativa vale desde el directorio actual o desde la raíz del repo: con
    `uv run --directory backend jh …` (lo que usan los agentes) el proceso corre en `backend/`,
    pero la ruta se escribe pensando en la raíz (`data/tmp/oferta.txt`).
    """
    tmp_dir = get_settings().tmp_dir.resolve()
    candidates = [path] if path.is_absolute() else [Path.cwd() / path, REPO_ROOT / path]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_relative_to(tmp_dir):
            return resolved
    raise ToolError(
        "invalid_file",
        f"`--file` debe estar dentro de {tmp_dir} (se borra tras procesarse bien).",
    )


def read_input_file(resolved: Path, file_format: str) -> Any:
    """Lee una entrada larga ya resuelta en `data/tmp/`: texto (UTF-8, con o sin BOM) o JSON."""
    try:
        # `utf-8-sig`: el Bloc de notas y PowerShell pueden guardar con BOM.
        text = resolved.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise ToolError("invalid_file", f"No se pudo leer {resolved}: {exc}") from exc
    if file_format == "text":
        return text
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ToolError(
            "invalid_file",
            f"{resolved} no es JSON válido (línea {exc.lineno}, columna {exc.colno}): {exc.msg}.",
        ) from exc


def _option_name(spec: ToolSpec, field: str) -> str:
    return spec.cli.option_names.get(field, "--" + field.replace("_", "-"))


def _parameters(spec: ToolSpec) -> list[inspect.Parameter]:
    """Parámetros Typer: todos opcionales y de tipo texto, para que valide el `input_model`."""
    fields = spec.input_model.model_fields
    kind = inspect.Parameter.KEYWORD_ONLY
    params: list[inspect.Parameter] = []
    for name in spec.cli.arguments:
        help_text = fields[name].description or name
        params.append(
            inspect.Parameter(
                name, kind, default=typer.Argument(None, help=help_text), annotation=str | None
            )
        )
    for name, info in fields.items():
        if name in spec.cli.arguments or name == spec.cli.file_field:
            continue
        option = typer.Option(None, _option_name(spec, name), help=info.description)
        params.append(inspect.Parameter(name, kind, default=option, annotation=str | None))
    if spec.cli.file_field:
        what = "texto de la oferta" if spec.cli.file_format == "text" else "JSON"
        option = typer.Option(None, "--file", help=f"Fichero con el {what}, dentro de data/tmp/.")
        params.append(inspect.Parameter("file", kind, default=option, annotation=Path | None))
    params.append(
        inspect.Parameter(
            "as_json",
            kind,
            default=typer.Option(False, "--json", help="Salida en JSON (la de la MCP)."),
            annotation=bool,
        )
    )
    return params


def make_command(spec: ToolSpec, render: Callable[[Any], None] | None) -> Callable[..., None]:
    def command(**kwargs: Any) -> None:
        as_json: bool = kwargs.pop("as_json")
        file: Path | None = kwargs.pop("file", None)
        raw_args = {name: value for name, value in kwargs.items() if value is not None}
        try:
            if spec.cli.file_field and file is not None:
                file = resolve_input_file(file)
                raw_args[spec.cli.file_field] = read_input_file(file, spec.cli.file_format)
            settings = get_settings()
            ctx = CallContext(channel="cli", client_name=settings.client_name, audit=as_json)
            result = call_tool(spec, raw_args, ctx)
        except ToolError as error:
            _fail(error, as_json)
        if file is not None:
            file.unlink(missing_ok=True)
        if as_json:
            typer.echo(dump_json(result))
        elif render is not None:
            render(result)
        else:
            typer.echo(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))

    command.__signature__ = inspect.Signature(_parameters(spec))  # type: ignore[attr-defined]
    command.__name__ = spec.cli.path[-1].replace("-", "_")
    command.__doc__ = spec.description
    return command


def register_tools(
    root: typer.Typer,
    groups: dict[str, typer.Typer],
    renderers: dict[str, Callable[[Any], None]],
) -> None:
    """Añade a `jh` un comando por herramienta del registro."""
    for spec in TOOLS:
        *group_path, name = spec.cli.path
        target = groups[group_path[0]] if group_path else root
        target.command(name, help=spec.description)(make_command(spec, renderers.get(spec.name)))
