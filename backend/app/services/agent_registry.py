"""Registro de agentes (fase 24.1, ADR-037): el único lector de `.agents/manifest.yaml` en el
backend. Lo usan los botones «en tu agente» (`agent_launch`), el segundo plano (`agent_runner`),
`cai agents` y el doctor.

- Valida cada clave con Pydantic: una clave mal escrita falla con un mensaje que nombra el agente
  y la clave (`ManifestError`).
- Caché que se invalida si cambia la fecha de modificación del fichero.
- Detección (`detect`): si el programa de `info.detect` está en el `PATH` y qué versión dice, con
  un tiempo máximo, sin las variables de `launch.unset_env` (las claves de API) y en caché unos
  minutos para no lanzar procesos en cada petición.

Lo específico de cada agente está en el manifiesto, nunca aquí (regla dura 2).
"""

import contextlib
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.core.config import REPO_ROOT

MANIFEST = REPO_ROOT / ".agents" / "manifest.yaml"

PROMPT_PLACEHOLDER = "{prompt}"
TOOLS_PLACEHOLDER = "{allowed_tools}"
DENIED_PLACEHOLDER = "{denied_tools}"
SKILL_PLACEHOLDER = "{skill}"
SESSION_PLACEHOLDER = "{session_id}"
MODEL_PLACEHOLDER = "{model}"
# Formatos de salida en segundo plano que sabe leer `agent_output.py`.
HEADLESS_OUTPUTS = frozenset({"claude-stream-json", "opencode-json"})
# Configuraciones de una ejecución que sabe escribir `agent_run_config.py` (fase 24.5).
RUN_CONFIG_FORMATS = frozenset({"opencode"})
# Banderas de los agentes que aprueban solas lo que pida permiso o quitan el sandbox: una orden en
# segundo plano que lleve alguna no tiene techo (fase 24.5).
APPROVE_ALL_FLAGS = frozenset(
    {
        "--auto",
        "--yolo",
        "--dangerously-skip-permissions",
        "--dangerously-bypass-approvals-and-sandbox",
        "--allow-dangerously-skip-permissions",
    }
)

DETECT_TIMEOUT = 5.0  # segundos para `info.detect`
DETECT_TTL = 300.0  # segundos que vale una detección con versión
DETECT_TTL_MISS = 30.0  # sin instalar o con error: lo bastante corto para ver lo recién instalado
VERSION_MAX = 120  # caracteres de la versión que se guardan

Platform = Literal["windows", "macos", "linux"]


class ManifestError(Exception):
    """El manifiesto no se puede leer o tiene una clave mal escrita o con un valor inválido."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InstallSpec(_Strict):
    """Cómo se instala, por sistema (solo texto para enseñar)."""

    windows: str | None = None
    macos: str | None = None
    linux: str | None = None


class AgentInfo(_Strict):
    display_name: str
    vendor: str
    open_source: bool
    license: str
    homepage: str
    install: InstallSpec = InstallSpec()
    detect: list[str] = Field(min_length=1)  # p. ej. `[claude, --version]`
    invoke: str  # `"/{skill} {args}"`, `"${skill} {args}"` o `natural`
    instructions: str  # qué fichero de instrucciones lee (`AGENTS.md`, `CLAUDE.md`…)
    note: str | None = None  # por qué no se recomienda (p. ej. Gemini CLI); el doctor lo avisa


class AgentCapabilities(_Strict):
    """Qué sabe hacer el agente. `None`: sin comprobar."""

    mcp: bool
    subagents: Literal["isolated", "inherited", "none"]
    isolation_level: Literal["A", "B", "C"]  # tabla de garantías de docs/AGENTS_COMPAT.md
    vision: bool | None = None
    web: bool | None = None
    browser: bool | None = None
    local_models: bool | None = None  # modelos locales o endpoints compatibles con OpenAI
    headless: bool = False  # se deriva de `launch.headless`; no se escribe en el manifiesto

    @model_validator(mode="before")
    @classmethod
    def _headless_is_derived(cls, data: Any) -> Any:
        if isinstance(data, dict) and "headless" in data:
            raise ValueError(
                "«headless» no se escribe: se deriva de que haya un `launch.headless` válido"
            )
        return data


class ModelsSpec(_Strict):
    """`models` (fase 24.3): el modelo de cada `tier` de los roles y cómo se elige uno al lanzar."""

    fast: str | None = None  # `None`: el subagente hereda el modelo de la sesión
    capable: str | None = None
    flag: list[str] = []  # argumentos con `{model}`, p. ej. `["--model", "{model}"]`
    presets: dict[str, list[str]] = {}  # configuraciones con nombre, p. ej. `local` en Codex
    # Fase 24.4: expresión regular que valida el nombre de un modelo (p. ej. `proveedor/modelo` en
    # OpenCode) y su ejemplo para la UI. Sin ella, cualquier nombre con caracteres seguros.
    pattern: str | None = None
    example: str | None = None

    @model_validator(mode="after")
    def _flag_has_model(self) -> "ModelsSpec":
        if self.flag and MODEL_PLACEHOLDER not in self.flag:
            raise ValueError(f"`flag` necesita un argumento «{MODEL_PLACEHOLDER}»")
        if self.pattern is not None:
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(f"`pattern` no es una expresión regular válida: {exc}") from exc
        for name, args in self.presets.items():
            if not args:
                raise ValueError(f"el preset «{name}» está vacío")
        return self

    def tier(self, tier: str) -> str | None:
        return {"fast": self.fast, "capable": self.capable}.get(tier)


class RunConfigSpec(_Strict):
    """`launch.headless.config` (fase 24.5): la configuración propia de cada ejecución, para los
    agentes que limitan las herramientas por configuración y no por argumentos."""

    format: str  # quién la escribe en `agent_run_config.py` (`opencode`)
    env: str  # la variable de entorno con que se le pasa al agente
    value: Literal["content", "path"] = "content"  # el contenido del fichero o su ruta
    agent: str  # el agente que define la configuración; la orden lo nombra
    # Variables que se quitan del entorno solo en segundo plano: las que podrían cargar otra
    # configuración o cambiar permisos por debajo de la de la ejecución.
    clear_env: list[str] = []


class HeadlessSpec(_Strict):
    """`launch.headless`: cómo se lanza sin ventana (fase 19, ADR-032).

    `ceiling` (fase 24.5) es cómo se pone el techo de herramientas: `args`, en la orden
    (`{allowed_tools}` y `{denied_tools}`); `config`, en una configuración propia de la ejecución
    (`config`) que solo enciende las herramientas MCP de la acción."""

    ceiling: Literal["args", "config"] = "args"
    command: list[str] = []
    allow: list[str] = []
    skill_rule: str = ""
    output: str = ""
    config: RunConfigSpec | None = None

    @property
    def complete(self) -> bool:
        """Lleva la orden, un formato de salida conocido y una forma de denegar el resto: la lista
        de denegadas (`args`) o una configuración que se sabe escribir (`config`). Sin eso no hay
        garantía, y entonces no hay segundo plano."""
        if PROMPT_PLACEHOLDER not in self.command or self.output not in HEADLESS_OUTPUTS:
            return False
        if APPROVE_ALL_FLAGS & set(self.command):
            return False
        if self.ceiling == "args":
            return (
                TOOLS_PLACEHOLDER in self.command
                and DENIED_PLACEHOLDER in self.command
                and SKILL_PLACEHOLDER in self.skill_rule
                and self.config is None
            )
        config = self.config
        return (
            config is not None
            and config.format in RUN_CONFIG_FORMATS
            and config.agent in self.command
            and not self.allow  # lo que se permite lo decide la configuración, no el manifiesto
            and TOOLS_PLACEHOLDER not in self.command
            and DENIED_PLACEHOLDER not in self.command
        )


class LaunchSpec(_Strict):
    """`launch`: los botones «en tu agente» de la UI (ADR-024)."""

    command: list[str] = []  # con `{prompt}`
    unset_env: list[str] = []
    resume: list[str] = []  # con `{session_id}`
    headless: HeadlessSpec | None = None


class AgentSpec(_Strict):
    """Un agente de `targets` del manifiesto."""

    name: str = ""  # la clave en `targets`; la pone el registro
    enabled: bool = False
    config: Literal["generated", "none"]
    info: AgentInfo
    capabilities: AgentCapabilities
    # Lo que usa `scripts/sync_agents.py` para generar la configuración.
    skills_dir: str | None = None
    agents_dir: str | None = None
    mcp_file: str | None = None
    config_file: str | None = None
    models: ModelsSpec = ModelsSpec()
    tools: dict[str, str | list[str]] = {}  # herramientas lógicas → nativas, y `mcp_prefix`
    skill_extras: dict[str, dict[str, Any]] = {}
    launch: LaunchSpec | None = None

    @model_validator(mode="after")
    def _enabled_needs_config(self) -> "AgentSpec":
        if self.enabled and self.config != "generated":
            raise ValueError("un agente con `enabled: true` necesita `config: generated`")
        return self

    @property
    def mcp_prefix(self) -> str | None:
        prefix = self.tools.get("mcp_prefix")
        return prefix if isinstance(prefix, str) and prefix else None

    @property
    def launchable(self) -> bool:
        """Los botones de la UI lo pueden abrir: está habilitado y su `launch` lleva `{prompt}`."""
        return bool(self.enabled and self.launch and PROMPT_PLACEHOLDER in self.launch.command)

    @property
    def headless(self) -> HeadlessSpec | None:
        """`launch.headless`, si se puede usar: completo y con `tools.mcp_prefix`."""
        if self.launch is None or self.launch.headless is None or self.mcp_prefix is None:
            return None
        return self.launch.headless if self.launch.headless.complete else None

    @property
    def unset_env(self) -> list[str]:
        return list(self.launch.unset_env) if self.launch else []

    def model_args(self, model: str | None = None, preset: str | None = None) -> list[str]:
        """Los argumentos que eligen un modelo al lanzar el agente: un `preset` de `models.presets`
        o un `model` con `models.flag`. Nada si no se pide ninguno (el modelo por defecto)."""
        if model and preset:
            raise ValueError("elige un modelo o un preset, no los dos")
        if preset:
            if preset not in self.models.presets:
                raise ValueError(f"{self.info.display_name} no tiene el preset «{preset}»")
            return list(self.models.presets[preset])
        if model:
            if not self.models.flag:
                raise ValueError(f"{self.info.display_name} no sabe elegir el modelo al lanzarlo")
            return [part.replace(MODEL_PLACEHOLDER, model) for part in self.models.flag]
        return []


class _Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mcp_server: dict[str, Any]
    policy: dict[str, Any] = {}  # permisos neutrales; los traduce `scripts/sync_agents.py`
    targets: dict[str, Any]


def _describe(agent: str, exc: ValidationError) -> str:
    problems = []
    for error in exc.errors(include_url=False):
        key = ".".join(str(part) for part in error["loc"])
        where = f"targets.{agent}" + (f".{key}" if key else "")
        if error["type"] == "extra_forbidden":
            problems.append(f"{where}: clave desconocida «{error['loc'][-1]}»")
        elif error["type"] == "missing":
            problems.append(f"{where}: falta la clave")
        else:
            message = str(error["msg"]).removeprefix("Value error, ")
            problems.append(f"{where}: {message}")
    return f"{MANIFEST.name}, agente «{agent}»: " + "; ".join(problems)


def parse(data: Any) -> dict[str, AgentSpec]:
    """Valida el contenido del manifiesto ya leído y devuelve sus agentes, en su orden."""
    if not isinstance(data, dict):
        raise ManifestError(f"{MANIFEST.name}: no es un mapa YAML")
    try:
        manifest = _Manifest.model_validate(data)
    except ValidationError as exc:
        keys = ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors())
        raise ManifestError(f"{MANIFEST.name}: claves de primer nivel inválidas ({keys})") from exc
    agents: dict[str, AgentSpec] = {}
    for name, raw in manifest.targets.items():
        if not isinstance(raw, dict):
            raise ManifestError(f"{MANIFEST.name}, agente «{name}»: no es un mapa")
        try:
            spec = AgentSpec.model_validate({**raw, "name": str(name)})
        except ValidationError as exc:
            raise ManifestError(_describe(str(name), exc)) from exc
        capabilities = spec.capabilities.model_copy(update={"headless": spec.headless is not None})
        agents[str(name)] = spec.model_copy(update={"capabilities": capabilities})
    return agents


_lock = threading.Lock()
_cache: tuple[Path, int, Mapping[str, AgentSpec]] | None = None


def load(path: Path | None = None) -> Mapping[str, AgentSpec]:
    """Los agentes del manifiesto. Se vuelve a leer solo si cambia su fecha de modificación."""
    global _cache
    path = path or MANIFEST
    try:
        mtime = path.stat().st_mtime_ns
    except OSError as exc:
        raise ManifestError(f"No se puede leer {path.name}: {exc.strerror}") from exc
    with _lock:
        if _cache is not None and _cache[0] == path and _cache[1] == mtime:
            return _cache[2]
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ManifestError(f"No se puede leer {path.name}: {exc}") from exc
    agents = MappingProxyType(parse(data))  # solo lectura: la comparten todas las llamadas
    with _lock:
        _cache = (path, mtime, agents)
    return agents


def get(name: str) -> AgentSpec | None:
    return load().get(name)


# --- Detección ---------------------------------------------------------------------------------


class Detection(BaseModel):
    installed: bool  # el programa de `info.detect` está en el `PATH`
    version: str | None = None  # primera línea de su salida
    error: str | None = None  # por qué no hay versión, si está instalado


_detected: dict[tuple[str, ...], tuple[float, Detection]] = {}
_detecting: dict[tuple[str, ...], threading.Lock] = {}  # una detección a la vez por agente


def clean_env(unset_env: list[str]) -> dict[str, str]:
    """El entorno actual sin las variables de `launch.unset_env` (sin distinguir mayúsculas)."""
    unset = {name.upper() for name in unset_env}
    return {k: v for k, v in os.environ.items() if k.upper() not in unset}


def current_platform() -> Platform:
    if sys.platform == "win32":
        return "windows"
    return "macos" if sys.platform == "darwin" else "linux"


def _run_detect(command: list[str], unset_env: list[str], timeout: float) -> Detection:
    exe = shutil.which(command[0])
    if exe is None:
        return Detection(installed=False)
    kwargs: dict[str, Any] = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(  # noqa: S603 - comando del manifiesto, sin shell
            [exe, *command[1:]],
            cwd=REPO_ROOT,
            env=clean_env(unset_env),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            **kwargs,
        )
    except OSError as exc:
        return Detection(installed=True, error=f"no se pudo ejecutar: {exc.strerror or exc}")
    try:
        output, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        # Se importa aquí: `agent_runner` importa `agent_launch`, que importa este módulo.
        from app.services.agent_runner import _kill_tree

        _kill_tree(proc)
        with contextlib.suppress(Exception):
            proc.communicate(timeout=5)
        return Detection(installed=True, error=f"no respondió en {timeout:g} s")
    line = next((ln.strip() for ln in (output or "").splitlines() if ln.strip()), "")
    if proc.returncode != 0:
        return Detection(installed=True, error=f"salió con el código {proc.returncode}")
    return Detection(installed=True, version=line[:VERSION_MAX] or None)


def detect(spec: AgentSpec, *, timeout: float = DETECT_TIMEOUT, refresh: bool = False) -> Detection:
    """Si el agente está instalado y su versión. En caché `DETECT_TTL` segundos (`DETECT_TTL_MISS`
    si no está o falló). Dos peticiones a la vez esperan a la misma detección, no lanzan dos."""
    key = (*spec.info.detect, "|", *spec.unset_env)
    with _lock:
        flight = _detecting.setdefault(key, threading.Lock())
    with flight:
        with _lock:
            cached = _detected.get(key)
        if cached and not refresh:
            at, found = cached
            ttl = DETECT_TTL if found.version else DETECT_TTL_MISS
            if time.monotonic() - at < ttl:
                return found
        found = _run_detect(spec.info.detect, spec.unset_env, timeout)
        with _lock:
            _detected[key] = (time.monotonic(), found)
        return found


def clear_detection_cache() -> None:
    with _lock:
        _detected.clear()


class ModelChoice(BaseModel):
    """Cómo se puede elegir el modelo de un agente (la elección se guarda con `agent_prefs`)."""

    by_name: bool  # admite un modelo por su nombre (`models.flag`)
    presets: list[str]  # nombres de `models.presets`
    example: str | None = None  # cómo se escribe un nombre de modelo (`models.example`)
    # El modelo de los subagentes (roles), de la configuración generada; `None`: el de la sesión.
    fast: str | None = None
    capable: str | None = None


class AgentEntry(BaseModel):
    """Un agente para `cai agents list --json` y `GET /agent/agents`."""

    name: str
    enabled: bool  # con configuración generada y botones de la UI
    config: Literal["generated", "none"]
    info: AgentInfo
    capabilities: AgentCapabilities
    models: ModelChoice
    installed: bool
    version: str | None = None
    detect_error: str | None = None


class AgentList(BaseModel):
    agents: list[AgentEntry]


def list_agents(refresh: bool = False) -> AgentList:
    """Todos los agentes del manifiesto con su detección (en paralelo: cada una tarda)."""
    specs = list(load().values())
    with ThreadPoolExecutor(max_workers=max(1, len(specs))) as pool:
        found = list(pool.map(lambda s: detect(s, refresh=refresh), specs))
    return AgentList(
        agents=[
            AgentEntry(
                name=spec.name,
                enabled=spec.enabled,
                config=spec.config,
                info=spec.info,
                capabilities=spec.capabilities,
                models=ModelChoice(
                    by_name=bool(spec.models.flag),
                    presets=list(spec.models.presets),
                    example=spec.models.example,
                    fast=spec.models.fast,
                    capable=spec.models.capable,
                ),
                installed=detection.installed,
                version=detection.version,
                detect_error=detection.error,
            )
            for spec, detection in zip(specs, found, strict=True)
        ]
    )
