"""Esquemas publicados de lo que rellena el agente (fase 24.2): `cai schema` y `get_schema`.

Sin MCP, el esquema de cada entrada no llega con la herramienta: el agente lo pide aquí en vez de
buscarlo en `docs/AGENT_INTERFACE.md`. El esquema publicado es **exactamente lo que va en
`--file`**: el modelo del campo (`file_field`) o un objeto con las claves de `file_keys`. Por MCP
es lo mismo que el campo correspondiente de la herramienta.

Cada esquema tiene un ejemplo mínimo válido en `demo/schemas/<nombre>.json`, con los ids del
perfil de la demo (sin datos personales). Un test comprueba que toda herramienta con `--file`
JSON tiene esquema y que cada ejemplo valida.
"""

import json
from dataclasses import dataclass
from functools import cache
from typing import Any

from pydantic import BaseModel, ConfigDict, create_model

from app.agent_interface.errors import model_at
from app.agent_interface.registry import ToolSpec
from app.core.config import REPO_ROOT

EXAMPLES_DIR = REPO_ROOT / "demo" / "schemas"


@dataclass(frozen=True)
class SchemaEntry:
    name: str
    tool: str
    description: str


# Herramienta → nombre corto del esquema de su `--file`. El orden es el del flujo.
CATALOG: tuple[SchemaEntry, ...] = (
    SchemaEntry("extraction", "save_extraction", "Datos estructurados de una oferta"),
    SchemaEntry("fit-assessment", "save_fit_assessment", "Valoración explicada del encaje"),
    SchemaEntry("cv-content", "save_cv_content", "Contenido del CV y opciones de render"),
    SchemaEntry("cv-render-options", "render_cv", "Opciones para volver a renderizar un CV"),
    SchemaEntry("cv-verification", "save_cv_verification", "Resultado del rol verifier (CV)"),
    SchemaEntry("application-answers", "save_application_answers", "Respuestas de screening"),
    SchemaEntry("cover-letter-brief", "save_cover_letter_brief", "Indicaciones para la carta"),
    SchemaEntry("cover-letter", "save_cover_letter", "Carta de presentación y opciones"),
    SchemaEntry(
        "cover-letter-render-options", "render_cover_letter", "Opciones para renderizar la carta"
    ),
    SchemaEntry(
        "cover-letter-verification",
        "save_cover_letter_verification",
        "Resultado del rol verifier (carta)",
    ),
    SchemaEntry("reply-proposal", "save_reply_proposal", "Clasificación de un correo"),
    SchemaEntry("message-draft", "save_message_draft", "Borrador de mensaje o correo"),
    SchemaEntry("company-research", "save_company_research", "Dosier de la empresa"),
    SchemaEntry("interview-plan", "save_interview_plan", "Plan de preparación de entrevista"),
    SchemaEntry("interview-notes", "save_interview_notes", "Notas del repaso de una entrevista"),
    SchemaEntry("source", "save_source", "Plataforma de búsqueda con el navegador"),
    SchemaEntry("source-run", "record_source_run", "Resultado de un recorrido por una plataforma"),
)
BY_NAME = {entry.name: entry for entry in CATALOG}
BY_TOOL = {entry.tool: entry for entry in CATALOG}


def has_json_file(spec: ToolSpec) -> bool:
    """La herramienta recibe por `--file` una entrada estructurada (y necesita esquema)."""
    return bool(spec.cli.file_keys) or (
        spec.cli.file_field is not None and spec.cli.file_format == "json"
    )


def schema_for_tool(tool: str) -> str | None:
    entry = BY_TOOL.get(tool)
    return entry.name if entry else None


def _spec(entry: SchemaEntry) -> ToolSpec:
    from app.agent_interface.tools import TOOLS_BY_NAME  # `tools` importa este módulo

    return TOOLS_BY_NAME[entry.tool]


@cache
def file_model(name: str) -> type[BaseModel]:
    """El modelo que valida el `--file` del esquema `name`."""
    entry = BY_NAME[name]
    spec = _spec(entry)
    fields = spec.input_model.model_fields
    if spec.cli.file_keys:
        return create_model(  # type: ignore[call-overload,no-any-return]
            f"{spec.input_model.__name__}File",
            __config__=ConfigDict(extra="forbid"),
            __doc__=f"Lo que va en `--file` de `{spec.name}`.",
            **{key: (fields[key].annotation, fields[key]) for key in spec.cli.file_keys},
        )
    assert spec.cli.file_field is not None
    model = model_at(spec.input_model, (spec.cli.file_field,))
    if model is None:
        raise RuntimeError(f"{spec.name}: `{spec.cli.file_field}` no es un modelo")
    return model


def json_schema(name: str) -> dict[str, Any]:
    return file_model(name).model_json_schema()


def example(name: str) -> Any:
    """El ejemplo mínimo de `demo/schemas/`, ya validado por los tests."""
    path = EXAMPLES_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def file_note(name: str) -> str:
    """Cómo se envía por CLI: qué va en `--file` y con qué comando."""
    spec = _spec(BY_NAME[name])
    command = "cai " + " ".join(spec.cli.path)
    if spec.cli.file_keys:
        what = "un objeto JSON con " + ", ".join(f"`{k}`" for k in spec.cli.file_keys)
    else:
        what = f"el objeto `{spec.cli.file_field}` tal cual (sin envolverlo)"
    return (
        f"`{command} … --file data/tmp/<fichero>.json --json`: el fichero lleva {what}. Por MCP, "
        f"lo mismo en el campo de la herramienta `{spec.name}`."
    )
