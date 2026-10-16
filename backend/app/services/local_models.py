"""Diagnóstico de los modelos locales (fase 24.6, ADR-037): si Ollama responde en este equipo, qué
modelos tiene y con qué contexto los serviría.

La app no hace inferencia (regla dura 1, ADR-001): de Ollama solo se leen **metadatos**, con
`GET /api/version`, `GET /api/tags` y `POST /api/show`. Cualquier otra ruta (`/api/generate`,
`/api/chat`, `/v1/*`…) se rechaza antes de salir (`ALLOWED`, también en un `event_hook` del
cliente), y un test lo comprueba. Solo se consulta una dirección de este equipo (`CAI_OLLAMA_URL`).

Lo que se avisa:
- contexto por debajo de `MIN_CONTEXT`: con los 4 096 que pone Ollama por defecto (menos de 24 GB
  de memoria de vídeo), los agentes no caben y fallan sin un error claro;
- un modelo pequeño (`SMALL_PARAMS_B` o menos) elegido para redactar (`WRITING_ACTIONS`): suelen
  fallar con esquemas estrictos.

El contexto que usará cada modelo: `num_ctx` de su Modelfile, si lo tiene; si no,
`OLLAMA_CONTEXT_LENGTH` del entorno (la variable que lee Ollama); si no, el valor por defecto.
Ninguno de los tres endpoints da el del servidor, así que la variable se lee de este proceso: si la
pusiste después de arrancar la app, reiníciala.
"""

import os
import re
from collections.abc import Iterable, Sequence
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel

from app.core.config import get_settings
from app.services import agent_registry

ALLOWED: frozenset[tuple[str, str]] = frozenset(
    {("GET", "/api/version"), ("GET", "/api/tags"), ("POST", "/api/show")}
)
LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})
TIMEOUT = httpx.Timeout(3.0, connect=1.0)
MIN_CONTEXT = 32_768
DEFAULT_CONTEXT = 4_096  # el de Ollama con menos de 24 GB de memoria de vídeo
SMALL_PARAMS_B = 9.0  # los «8B» (p. ej. 8,2B) cuentan como pequeños
MAX_MODELS = 30  # `/api/show` de cada uno: con más, solo los primeros
WRITING_ACTIONS: tuple[str, ...] = ("generate-cv", "generate-cover-letter")
CONTEXT_ENV = "OLLAMA_CONTEXT_LENGTH"

ContextSource = Literal["model", "env", "default"]
WarningCode = Literal["context_low", "small_model", "no_models", "model_missing"]
_PARAMS_RE = re.compile(r"^\s*([\d.]+)\s*([KMBT])\s*$", re.I)
_SCALE = {"K": 1e-6, "M": 1e-3, "B": 1.0, "T": 1e3}


class LocalModelError(Exception):
    pass


class LocalModel(BaseModel):
    name: str
    family: str | None = None
    parameter_size: str | None = None  # como lo da Ollama, p. ej. «20.9B»
    params_b: float | None = None  # miles de millones de parámetros
    quantization: str | None = None
    size_gb: float | None = None
    max_context: int | None = None  # el que admite el modelo
    context: int  # el que usará
    context_source: ContextSource
    tools: bool | None = None  # `None`: Ollama no lo dice
    small: bool = False


class LocalWarning(BaseModel):
    code: WarningCode
    text: str
    model: str | None = None
    action: str | None = None


class LocalModelsStatus(BaseModel):
    provider: Literal["ollama"] = "ollama"
    url: str
    running: bool
    version: str | None = None
    error: str | None = None
    env_context: int | None = None  # `OLLAMA_CONTEXT_LENGTH`, si está puesta
    default_context: int = DEFAULT_CONTEXT
    min_context: int = MIN_CONTEXT
    models: list[LocalModel] = []
    warnings: list[LocalWarning] = []


# --- Cliente con lista blanca --------------------------------------------------------------


def _check_request(request: httpx.Request) -> None:
    if (request.method, request.url.path) not in ALLOWED:
        raise LocalModelError(
            f"Ruta de Ollama no permitida: {request.method} {request.url.path}. La app solo lee "
            "metadatos (ADR-001)."
        )
    if request.url.host not in LOOPBACK:
        raise LocalModelError("Ollama solo se consulta en este equipo.")


def base_url() -> str:
    url = get_settings().ollama_url.rstrip("/")
    parts = urlsplit(url)
    if parts.scheme != "http" or parts.hostname not in LOOPBACK:
        raise LocalModelError(
            f"CAI_OLLAMA_URL tiene que ser una dirección de este equipo (http://127.0.0.1:…), no "
            f"«{url[:60]}»."
        )
    return url


def _client(url: str) -> httpx.Client:
    return httpx.Client(
        base_url=url,
        timeout=TIMEOUT,
        follow_redirects=False,
        trust_env=False,  # sin proxies del entorno: es una dirección local
        event_hooks={"request": [_check_request]},
    )


def _call(client: httpx.Client, method: str, path: str, body: Any = None) -> Any:
    if (method, path) not in ALLOWED:  # antes de construir la petición
        raise LocalModelError(f"Ruta de Ollama no permitida: {method} {path}.")
    response = client.request(method, path, json=body)
    response.raise_for_status()
    return response.json()


# --- Lectura -------------------------------------------------------------------------------


def params_billions(text: str | None) -> float | None:
    """«20.9B» → 20.9; «350M» → 0.35; lo que no se entiende → `None`."""
    match = _PARAMS_RE.match(text or "")
    if not match:
        return None
    return float(match.group(1)) * _SCALE[match.group(2).upper()]


def _num_ctx(parameters: str | None) -> int | None:
    for line in (parameters or "").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == "num_ctx" and parts[1].isdigit():
            return int(parts[1])
    return None


def _max_context(model_info: dict[str, Any] | None) -> int | None:
    for key, value in (model_info or {}).items():
        if key.endswith(".context_length") and isinstance(value, int):
            return value
    return None


def _short(value: Any) -> str | None:
    return str(value)[:40] if value else None


def env_context() -> int | None:
    raw = os.environ.get(CONTEXT_ENV, "").strip()
    return int(raw) if raw.isdigit() and int(raw) > 0 else None


def _model(entry: dict[str, Any], show: dict[str, Any] | None, env_ctx: int | None) -> LocalModel:
    details = {**(entry.get("details") or {}), **((show or {}).get("details") or {})}
    size = entry.get("size")
    params = params_billions(details.get("parameter_size"))
    num_ctx = _num_ctx((show or {}).get("parameters"))
    source: ContextSource
    if num_ctx:
        context, source = num_ctx, "model"
    elif env_ctx:
        context, source = env_ctx, "env"
    else:
        context, source = DEFAULT_CONTEXT, "default"
    max_ctx = _max_context((show or {}).get("model_info"))
    capabilities = (show or {}).get("capabilities")
    return LocalModel(
        name=str(entry.get("name") or entry.get("model") or "?")[:100],
        family=_short(details.get("family")),
        parameter_size=_short(details.get("parameter_size")),
        params_b=params,
        quantization=_short(details.get("quantization_level")),
        size_gb=round(size / 1e9, 1) if isinstance(size, int) else None,
        max_context=max_ctx,
        context=min(context, max_ctx) if max_ctx else context,
        context_source=source,
        tools=("tools" in capabilities) if isinstance(capabilities, list) else None,
        small=params is not None and params <= SMALL_PARAMS_B,
    )


def _short_names(name: str) -> set[str]:
    """Las formas en que se puede nombrar un modelo de Ollama: con o sin `:latest`."""
    return {name, name.removesuffix(":latest")} if name.endswith(":latest") else {name}


def model_names(agent: str | None, model: str | None, preset: str | None) -> list[str]:
    """Los nombres de modelo que lleva una elección: el modelo (también sin `proveedor/`) o lo que
    va detrás de `-m`/`--model` en el preset del agente."""
    names: list[str] = []
    if model:
        names.append(model)
        if "/" in model:
            names.append(model.split("/", 1)[1])
    if preset and agent:
        spec = agent_registry.get(agent)
        args = spec.models.presets.get(preset, []) if spec else []
        for flag, value in zip(args, args[1:], strict=False):
            if flag in ("-m", "--model"):
                names.append(value)
    return names


Choice = tuple[str, str | None, str | None, str | None]  # acción, agente, modelo, preset


def _warnings(
    models: Sequence[LocalModel], choices: Iterable[Choice], running: bool
) -> list[LocalWarning]:
    found: list[LocalWarning] = []
    if running and not models:
        found.append(
            LocalWarning(
                code="no_models",
                text="Ollama responde, pero no tiene ningún modelo: descarga uno con "
                "`ollama pull` (ver docs/MODELOS_GRATIS.md).",
            )
        )
    for item in models:
        if item.context < MIN_CONTEXT:
            how = {
                "model": "su Modelfile (num_ctx)",
                "env": CONTEXT_ENV,
                "default": "el valor por defecto de Ollama",
            }[item.context_source]
            found.append(
                LocalWarning(
                    code="context_low",
                    model=item.name,
                    text=f"{item.name}: contexto de {item.context} tokens (por {how}). Los agentes "
                    f"necesitan al menos {MIN_CONTEXT}: pon {CONTEXT_ENV}={MIN_CONTEXT} y reinicia "
                    "Ollama.",
                )
            )
    by_name = {short: m for m in models for short in _short_names(m.name)}
    for action, agent, model, preset in choices:
        if action not in WRITING_ACTIONS:
            continue
        for name in model_names(agent, model, preset):
            local = by_name.get(name)
            if local is not None and local.small:
                found.append(
                    LocalWarning(
                        code="small_model",
                        model=local.name,
                        action=action,
                        text=f"{local.name} ({local.parameter_size}) está elegido para «{action}»: "
                        f"los modelos de unos 8B o menos suelen fallar con los "
                        "esquemas del CV. Usa uno más grande o tu suscripción para redactar.",
                    )
                )
                break
    return found


def diagnose(
    choices: Iterable[Choice] = (), *, client: httpx.Client | None = None
) -> LocalModelsStatus:
    """Lo que hay en el Ollama de este equipo. `choices`: el agente y modelo de cada acción, para
    avisar de un modelo pequeño elegido para redactar. Nunca lanza por un Ollama caído."""
    env_ctx = env_context()
    try:
        url = base_url()
    except LocalModelError as exc:
        return LocalModelsStatus(url="", running=False, error=str(exc), env_context=env_ctx)
    status = LocalModelsStatus(url=url, running=False, env_context=env_ctx)
    owned = client is None
    client = client or _client(url)
    try:
        version = _call(client, "GET", "/api/version")
        status.running = True
        status.version = str(version.get("version"))[:40] if isinstance(version, dict) else None
        tags = _call(client, "GET", "/api/tags")
        entries = tags.get("models") if isinstance(tags, dict) else None
        models: list[LocalModel] = []
        for entry in (entries or [])[:MAX_MODELS]:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name") or entry.get("model")
            try:
                show = _call(client, "POST", "/api/show", {"model": name}) if name else None
            except (httpx.HTTPError, ValueError):
                show = None
            models.append(_model(entry, show if isinstance(show, dict) else None, env_ctx))
        status.models = models
    except (httpx.ConnectError, httpx.TimeoutException):
        status.error = f"Ollama no responde en {url}."
    except (httpx.HTTPError, ValueError) as exc:
        status.error = f"Ollama respondió algo inesperado ({type(exc).__name__})."
    finally:
        if owned:
            client.close()
    status.warnings = _warnings(status.models, choices, status.running)
    return status


def choices_from(session: Any) -> list[Choice]:
    """El agente y modelo efectivos de cada acción que redacta, según tus preferencias (24.4)."""
    from app.services import agent_launch  # import tardío: agent_launch no depende de este módulo

    ctx = agent_launch.Context(session)
    found: list[Choice] = []
    for action in WRITING_ACTIONS:
        if action not in agent_launch.ACTIONS:
            continue  # la carta aún no tiene botón
        res = agent_launch.choose(session, action, ctx=ctx)[1]
        found.append((action, res.agent, res.model, res.preset))
    return found


def diagnose_for(session: Any) -> LocalModelsStatus:
    return diagnose(choices_from(session))
