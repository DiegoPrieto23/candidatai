"""Diagnóstico de los modelos locales (fase 24.6): solo metadatos de Ollama, nunca inferencia
(regla dura 1), avisos de contexto bajo y de modelo pequeño para redactar. Sin red: `respx`."""

import ast
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import cli
from app.api.main import create_app
from app.core import migrations
from app.core.config import REPO_ROOT, get_settings
from app.services import local_models
from app.services.local_models import ALLOWED, LocalModelError
from tests.agent_support import runner

URL = "http://127.0.0.1:11434"
TAGS = {
    "models": [
        {
            "name": "gpt-oss:20b",
            "model": "gpt-oss:20b",
            "size": 13_780_000_000,
            "details": {
                "family": "gptoss",
                "parameter_size": "20.9B",
                "quantization_level": "MXFP4",
            },
        },
        {
            "name": "qwen3:8b",
            "model": "qwen3:8b",
            "size": 5_200_000_000,
            "details": {
                "family": "qwen3",
                "parameter_size": "8.2B",
                "quantization_level": "Q4_K_M",
            },
        },
        {
            "name": "mi-modelo:latest",
            "model": "mi-modelo:latest",
            "size": 2_000_000_000,
            "details": {"family": "llama", "parameter_size": "3.2B"},
        },
    ]
}
SHOW: dict[str, dict[str, Any]] = {
    "gpt-oss:20b": {
        "parameters": "temperature 1",
        "model_info": {"general.architecture": "gptoss", "gptoss.context_length": 131072},
        "capabilities": ["completion", "tools", "thinking"],
    },
    "qwen3:8b": {
        "parameters": "",
        "model_info": {"qwen3.context_length": 40960},
        "capabilities": ["completion", "tools"],
    },
    "mi-modelo:latest": {
        "parameters": "num_ctx 65536\nstop <|eot|>",
        "model_info": {"llama.context_length": 131072},
        "capabilities": ["completion"],
    },
}


@pytest.fixture
def ollama(monkeypatch: pytest.MonkeyPatch) -> Iterator[respx.MockRouter]:
    """Un Ollama falso con tres modelos. Cualquier ruta que no sea de metadatos hace fallar el
    test: `respx` responde 599 y queda en `forbidden`."""
    monkeypatch.setenv("CAI_OLLAMA_URL", URL)
    get_settings.cache_clear()

    def show(request: httpx.Request) -> httpx.Response:
        name = json.loads(request.content)["model"]
        return httpx.Response(200, json=SHOW[name])

    with respx.mock(base_url=URL, assert_all_called=False) as router:
        router.get("/api/version").respond(json={"version": "0.12.6"})
        router.get("/api/tags").respond(json=TAGS)
        router.post("/api/show").mock(side_effect=show)
        router.route(name="forbidden").respond(599)
        yield router
    get_settings.cache_clear()


def _paths(router: respx.MockRouter) -> set[tuple[str, str]]:
    return {(call.request.method, call.request.url.path) for call in router.calls}


def test_reads_models_and_context(ollama: respx.MockRouter) -> None:
    status = local_models.diagnose()
    assert status.running and status.version == "0.12.6" and status.error is None
    by_name = {m.name: m for m in status.models}
    gpt = by_name["gpt-oss:20b"]
    assert gpt.params_b == pytest.approx(20.9) and not gpt.small and gpt.tools is True
    assert gpt.max_context == 131072
    assert (gpt.context, gpt.context_source) == (4096, "default")
    assert by_name["qwen3:8b"].small
    custom = by_name["mi-modelo:latest"]
    assert (custom.context, custom.context_source, custom.tools) == (65536, "model", False)
    low = [w.model for w in status.warnings if w.code == "context_low"]
    assert low == ["gpt-oss:20b", "qwen3:8b"]
    assert "OLLAMA_CONTEXT_LENGTH=32768" in status.warnings[0].text


def test_only_metadata_endpoints(ollama: respx.MockRouter) -> None:
    local_models.diagnose([("generate-cv", "opencode", "ollama/qwen3:8b", None)])
    assert ollama.calls, "no consultó Ollama"
    assert _paths(ollama) <= ALLOWED
    assert not ollama.routes["forbidden"].called


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/generate"),
        ("POST", "/api/chat"),
        ("POST", "/api/embed"),
        ("POST", "/v1/chat/completions"),
        ("GET", "/v1/models"),
        ("POST", "/api/pull"),
        ("GET", "/api/ps"),
    ],
)
def test_any_other_route_is_refused(ollama: respx.MockRouter, method: str, path: str) -> None:
    with local_models._client(URL) as client, pytest.raises(LocalModelError):
        local_models._call(client, method, path, {})
    # También el `event_hook`, por si alguien construye la petición a mano.
    with local_models._client(URL) as client, pytest.raises(LocalModelError):
        client.request(method, path)
    assert not ollama.calls


def _strings(source: str) -> list[str]:
    """Los textos del código, sin docstrings (que explican qué rutas no se usan) ni comentarios."""
    tree = ast.parse(source)
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def test_source_never_names_inference_routes() -> None:
    """Ningún módulo de la app que hable con Ollama nombra una ruta de inferencia."""
    forbidden = ("/api/generate", "/api/chat", "/api/embed", "/v1/", "/api/pull")
    offenders = []
    for path in (REPO_ROOT / "backend" / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "ollama" not in text.lower() and "11434" not in text:
            continue
        offenders += [
            f"{path.name}: {route}"
            for value in _strings(text)
            for route in forbidden
            if route in value
        ]
    assert offenders == []


def test_env_context(ollama: respx.MockRouter, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_CONTEXT_LENGTH", "32768")
    status = local_models.diagnose()
    assert status.env_context == 32768
    by_name = {m.name: m for m in status.models}
    assert (by_name["gpt-oss:20b"].context, by_name["gpt-oss:20b"].context_source) == (
        32768,
        "env",
    )
    assert by_name["mi-modelo:latest"].context_source == "model"  # num_ctx manda
    assert not [w for w in status.warnings if w.code == "context_low"]


def test_context_capped_by_model(ollama: respx.MockRouter, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_CONTEXT_LENGTH", "262144")
    by_name = {m.name: m for m in local_models.diagnose().models}
    assert by_name["qwen3:8b"].context == 40960


def test_small_model_for_writing(ollama: respx.MockRouter) -> None:
    status = local_models.diagnose(
        [
            ("generate-cv", "opencode", "ollama/qwen3:8b", None),
            ("process-jobs", "opencode", "ollama/qwen3:8b", None),  # cerrada: sin aviso
        ]
    )
    small = [w for w in status.warnings if w.code == "small_model"]
    assert [(w.model, w.action) for w in small] == [("qwen3:8b", "generate-cv")]


def test_small_model_by_preset_and_latest(ollama: respx.MockRouter) -> None:
    # El preset `local` de Codex lleva `-m gpt-oss:20b`: grande, sin aviso.
    status = local_models.diagnose([("generate-cv", "codex", None, "local")])
    assert not [w for w in status.warnings if w.code == "small_model"]
    status = local_models.diagnose([("generate-cv", "opencode", "ollama/mi-modelo", None)])
    assert [w.model for w in status.warnings if w.code == "small_model"] == ["mi-modelo:latest"]


def test_ollama_down_does_not_raise() -> None:
    status = local_models.diagnose()  # conftest: un puerto donde no escucha nada
    assert not status.running and status.models == [] and status.warnings == []
    assert status.error and "no responde" in status.error


def test_only_this_machine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAI_OLLAMA_URL", "http://ollama.example.com:11434")
    get_settings.cache_clear()
    status = local_models.diagnose()
    assert not status.running and status.error and "este equipo" in status.error


def test_no_models_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAI_OLLAMA_URL", URL)
    get_settings.cache_clear()
    with respx.mock(base_url=URL) as router:
        router.get("/api/version").respond(json={"version": "0.12.6"})
        router.get("/api/tags").respond(json={"models": []})
        status = local_models.diagnose()
    assert [w.code for w in status.warnings] == ["no_models"]


def test_params_billions() -> None:
    assert local_models.params_billions("20.9B") == pytest.approx(20.9)
    assert local_models.params_billions("350M") == pytest.approx(0.35)
    assert local_models.params_billions("") is None
    assert local_models.params_billions("muchos") is None


def test_api_and_doctor(ollama: respx.MockRouter, tmp_path: Path) -> None:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        body = client.get("/agent/local-models").json()
    assert body["running"] and len(body["models"]) == 3
    result = runner.invoke(cli.app, ["agents", "doctor"])
    assert result.exit_code == 0, result.output
    assert "Modelos locales (Ollama)" in result.output
    assert "gpt-oss:20b" in result.output and "OLLAMA_CONTEXT_LENGTH" in result.output
    assert _paths(ollama) <= ALLOWED
