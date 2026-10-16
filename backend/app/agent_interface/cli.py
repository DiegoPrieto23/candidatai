"""Comandos `cai` derivados del registro de herramientas (paridad con la MCP por construcción).

Cada comando recoge sus argumentos como texto, lee `--file` si lo hay y llama a `runner.call_tool`
con el mismo diccionario que enviaría un cliente MCP. Con `--json` imprime exactamente el mismo JSON
que la herramienta MCP (o el mismo error) y la llamada queda en `mcp_calls` con canal `cli`.
"""

import inspect
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

import typer

from app.agent_interface.errors import ToolError
from app.agent_interface.output import dump_json
from app.agent_interface.registry import CallContext, ToolSpec
from app.agent_interface.runner import call_tool
from app.agent_interface.tools import TOOLS
from app.core.config import REPO_ROOT, get_settings
from app.core.validation import short


def _fail(error: ToolError, as_json: bool) -> NoReturn:
    if as_json:
        typer.echo(dump_json(error.payload()))
    else:
        typer.secho(f"Error: {error.info.message}", fg=typer.colors.RED, err=True)
        for detail in error.info.details:
            received = f" (recibido: {detail.received!r})" if detail.received is not None else ""
            typer.secho(f"  - {detail.field}: {detail.reason}{received}", err=True)
            if detail.expected:
                typer.secho(f"    esperado: {detail.expected}", err=True)
            if detail.hint:
                typer.secho(f"    pista: {detail.hint}", err=True)
    raise typer.Exit(code=1)


def resolve_input_file(path: Path) -> Path:
    """Ruta absoluta de `--file`, que debe estar dentro de `data/tmp/`.

    Una ruta relativa vale desde el directorio actual o desde la raíz del repo: con
    `uv run --directory backend cai …` (lo que usan los agentes) el proceso corre en `backend/`,
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
        found = lenient_json(text)
        if found is not None:
            return found
        raise ToolError(
            "invalid_file",
            f"{resolved} no es JSON válido (línea {exc.lineno}, columna {exc.colno}): {exc.msg}.",
        ) from exc


_FENCE = re.compile(r"```[a-zA-Z]*[ \t]*\r?\n(.*?)```", re.DOTALL)


def lenient_json(text: str) -> Any | None:
    """Fase 24.2: los modelos pequeños envuelven a menudo el JSON en un bloque de código Markdown
    o le ponen texto antes o después. Se acepta el primer bloque de código que sea JSON o, si no,
    un objeto o lista que empiece en el primer `{` o `[` del texto y tras el que no haya otro (así
    un JSON truncado no se convierte en uno de sus fragmentos). Si no, None, y vale el error
    original con su línea y columna. Nada más: el esquema sigue siendo estricto."""
    for block in _FENCE.findall(text):
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            continue
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if not starts:
        return None
    try:
        value, end = json.JSONDecoder().raw_decode(text, min(starts))
    except json.JSONDecodeError:
        return None
    rest = text[end:]
    return None if "{" in rest or "[" in rest else value


def read_json_fields(resolved: Path, keys: tuple[str, ...]) -> dict[str, Any]:
    """Lee un `--file` que es un objeto JSON con algunos campos de la entrada (`file_keys`)."""
    data = read_input_file(resolved, "json")
    if not isinstance(data, dict):
        raise ToolError(
            "invalid_file", f"{resolved} debe ser un objeto JSON con: {', '.join(keys)}."
        )
    unknown = sorted(set(data) - set(keys))
    if unknown:
        raise ToolError(
            "invalid_file",
            f"{resolved} tiene claves que no se esperan ({', '.join(short(k) for k in unknown)}); "
            f"solo: {', '.join(keys)}.",
        )
    return data


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
        if name in spec.cli.arguments or name == spec.cli.file_field or name in spec.cli.file_keys:
            continue
        option = typer.Option(None, _option_name(spec, name), help=info.description)
        params.append(inspect.Parameter(name, kind, default=option, annotation=str | None))
    if spec.cli.file_field or spec.cli.file_keys:
        if spec.cli.file_keys:
            what = "JSON con " + ", ".join(f"`{k}`" for k in spec.cli.file_keys)
        else:
            what = "texto de la oferta" if spec.cli.file_format == "text" else "JSON"
        where = "tmp/ de la carpeta de datos (data/tmp/, o la de CAI_DATA_DIR)"
        option = typer.Option(None, "--file", help=f"Fichero con el {what}, dentro de {where}.")
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
            elif spec.cli.file_keys and file is not None:
                file = resolve_input_file(file)
                raw_args.update(read_json_fields(file, spec.cli.file_keys))
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
    """Añade a `cai` un comando por herramienta del registro."""
    for spec in TOOLS:
        *group_path, name = spec.cli.path
        target = groups[group_path[0]] if group_path else root
        target.command(name, help=spec.description)(make_command(spec, renderers.get(spec.name)))
