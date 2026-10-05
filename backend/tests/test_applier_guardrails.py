"""Candidatura asistida (fase 11): ninguna ruta pulsa el envío sin la confirmación de la UI.

Comprobaciones estáticas sobre el código de la app (complementan los tests con navegador, donde
el servidor local cuenta 0 envíos al rellenar y exactamente 1 con el token):
- solo `applier/submit.py` pulsa el botón de envío (`click_submit`, `data-jh-submit`);
- `click_submit` solo lo llama `service.run_submit`, después de `tokens.consume`;
- el bloqueo del envío solo lo retiran `submit.py` y «Lo termino yo» (`run_focus`);
- los clics de los rellenadores solo pasan por `safe_click` y `check_box`, que rechazan los
  controles de envío, y nada pulsa teclas (un Enter podría enviar el formulario);
- la confirmación se emite solo en `confirm_submission`, que no está en la interfaz para agentes.
"""

import ast
from pathlib import Path

from app.agent_interface import tools

APP = Path(__file__).resolve().parents[1] / "app"
APPLIER = APP / "services" / "applier"


def sources(root: Path = APP) -> dict[str, str]:
    return {
        path.relative_to(APP).as_posix(): path.read_text(encoding="utf-8")
        for path in root.rglob("*.py")
    }


def calls_in(source: str, names: set[str]) -> list[tuple[str, str]]:
    """(función que la contiene, método llamado) de cada llamada `x.<name>(...)`."""
    found: list[tuple[str, str]] = []

    def visit(node: ast.AST, owner: str) -> None:
        for child in ast.iter_child_nodes(node):
            name = owner
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = child.name
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr in names
            ):
                found.append((owner, child.func.attr))
            visit(child, name)

    visit(ast.parse(source), "<module>")
    return found


def test_only_submit_module_presses_the_submit_button() -> None:
    for path, source in sources().items():
        if path == "services/applier/submit.py":
            continue
        assert "data-jh-submit" not in source, path
        for owner, _ in calls_in(source, {"click_submit"}):
            assert (path, owner) == ("services/applier/service.py", "_submit_in_browser"), path


def test_submit_block_is_released_only_by_submit_and_focus() -> None:
    allowed = {
        ("services/applier/submit.py", "click_submit"),
        ("services/applier/service.py", "_focus"),
    }
    for path, source in sources().items():
        for owner, _ in calls_in(source, {"release_submit_block"}):
            assert (path, owner) in allowed, (path, owner)


def test_fillers_only_click_through_the_safe_helpers() -> None:
    risky = {"click", "dblclick", "tap", "dispatch_event", "press", "press_sequentially", "type"}
    for path, source in sources(APPLIER).items():
        if path.endswith("submit.py"):
            continue
        for owner, method in calls_in(source, risky):
            assert method == "click" and owner in ("safe_click", "check_box"), (path, owner)
        assert "keyboard" not in source, path
        assert "get_by_role" not in source, path
    # Nada fuera del paquete del navegador maneja páginas con clics.
    for path, source in sources().items():
        if path.startswith("services/applier/"):
            continue
        assert not calls_in(source, {"click", "tap", "press", "set_input_files"}), path


def test_page_scripts_never_submit_forms() -> None:
    for path, source in sources(APPLIER).items():
        if path.endswith(("submit.py", "guard.py")):
            continue  # guard.py redefine `submit()`/`requestSubmit()` para bloquearlos
        assert "requestSubmit" not in source, path
        assert ".submit()" not in source, path


def test_confirmation_is_only_issued_from_the_service() -> None:
    for path, source in sources().items():
        if path in ("services/applier/tokens.py", "services/applier/service.py"):
            continue
        assert "tokens.issue(" not in source and "_ISSUER" not in source, path
        assert "confirm_submission" not in source or path.startswith("api/"), path
        assert "SubmitConfirmation(" not in source, path


def test_no_agent_tool_or_cli_command_applies() -> None:
    """La interfaz para agentes (MCP y CLI) no prepara ni envía candidaturas: la CLI solo cierra
    el navegador al parar el worker."""
    names = {tool.name for tool in tools.TOOLS}
    assert not {n for n in names if "apply" in n or "submit" in n or "applier" in n}
    forbidden = ("applier.service", "applier import service", "applier.tokens", "applier.submit",
                 "applier import submit", "applier import tokens")  # fmt: skip
    for path, source in sources().items():
        if path == "cli.py" or path.startswith(("mcp/", "agent_interface/")):
            assert not any(f in source for f in forbidden), path
