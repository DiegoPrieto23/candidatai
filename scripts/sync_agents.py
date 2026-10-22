# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Genera la configuración nativa de cada agente a partir de .agents/.

Uso (desde la raíz del repo):
    uv run scripts/sync_agents.py            # escribe los ficheros generados
    uv run scripts/sync_agents.py --check    # no escribe; sale con 1 si algo no está al día

Fuente única: .agents/manifest.yaml, .agents/skills/*/SKILL.md y .agents/roles/*.md.
Salidas: .claude/skills, .claude/agents, .mcp.json, .codex/config.toml, .codex/agents,
opencode.json, .opencode/agents, .qwen/settings.json, .qwen/skills, .qwen/agents y
.agents/mcp_config.json. Los JSON no admiten comentarios: van sin el marcador `GENERADO`.
Se copian ficheros (no enlaces simbólicos) para que funcione en Windows sin permisos especiales.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / ".agents"
MARKER = "GENERADO por scripts/sync_agents.py"


@dataclass
class Doc:
    meta: dict
    body: str
    source: Path


def read_doc(path: Path) -> Doc:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise SystemExit(f"{path}: falta el frontmatter YAML al principio")
    _, fm, body = text.split("---\n", 2)
    meta = yaml.safe_load(fm) or {}
    for key in ("name", "description"):
        if not meta.get(key):
            raise SystemExit(f"{path}: falta '{key}' en el frontmatter")
    return Doc(meta=meta, body=body.lstrip("\n"), source=path)


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def dump_frontmatter(meta: dict) -> str:
    return yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=1000).strip()


def md_with_marker(meta: dict, body: str, source: Path) -> str:
    note = f"<!-- {MARKER} desde {rel(source)}. No editar a mano: edita la fuente y regenera. -->"
    return f"---\n{dump_frontmatter(meta)}\n---\n\n{note}\n\n{body.rstrip()}\n"


def map_tools(logical: list[str], mapping: dict, where: str = "") -> list[str]:
    """Herramientas lógicas (`mcp:<tool>`, `read`, `web`…) → nombres nativos del agente."""
    native: list[str] = []
    for tool in logical:
        if tool.startswith("mcp:"):
            native.append(mapping["mcp_prefix"] + tool[4:])
        elif tool in mapping and tool != "mcp_prefix":
            native.extend(mapping[tool])
        else:
            place = f"{where}: " if where else ""
            raise SystemExit(
                f"{place}herramienta lógica desconocida {tool!r}: añádela a `tools` del agente en "
                ".agents/manifest.yaml o quítala del rol"
            )
    return native


def tier_model(cfg: dict, role: Doc) -> str | None:
    return (cfg.get("models") or {}).get(role.meta.get("tier", ""))


def copy_skills(skills: list[Doc], base_dir: Path, extras_for=None) -> dict[Path, str]:
    """Copia de `.agents/skills` (con sus ficheros extra) para un agente que no la lee directamente.
    `extras_for(nombre)` añade campos de frontmatter propios de ese agente."""
    out: dict[Path, str] = {}
    for skill in skills:
        meta = {"name": skill.meta["name"], "description": skill.meta["description"]}
        if extras_for is not None:
            meta.update(extras_for(skill.meta["name"]))
        base = base_dir / skill.source.parent.name
        out[base / "SKILL.md"] = md_with_marker(meta, skill.body, skill.source)
        for extra_file in sorted(skill.source.parent.rglob("*")):
            if extra_file.is_file() and extra_file.name != "SKILL.md":
                target = base / extra_file.relative_to(skill.source.parent)
                out[target] = extra_file.read_text(encoding="utf-8")
    return out


def dump_json(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def toml_str(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def toml_multiline(value: str) -> str:
    if "'''" not in value:
        return "'''\n" + value.rstrip() + "\n'''"
    escaped = value.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return '"""\n' + escaped.rstrip() + '\n"""'


# ---------------------------------------------------------------- emisores


def emit_claude(
    cfg: dict, skills: list[Doc], roles: list[Doc], mcp: dict, policy: dict
) -> dict[Path, str]:
    tools = cfg["tools"]
    extras_by_skill = cfg.get("skill_extras", {})

    def extras_for(name: str) -> dict:
        extras = dict(extras_by_skill.get(name, {}))
        if "allowed-tools" in extras:
            where = f"claude, skill {name}"
            extras["allowed-tools"] = " ".join(map_tools(extras["allowed-tools"], tools, where))
        return extras

    out = copy_skills(skills, ROOT / cfg["skills_dir"], extras_for)
    for role in roles:
        where = f"claude, rol {role.meta['name']}"
        meta = {
            "name": role.meta["name"],
            "description": role.meta["description"],
            "tools": ", ".join(map_tools(role.meta.get("tools", []), tools, where)),
        }
        model = tier_model(cfg, role)
        if model:
            meta["model"] = model
        path = ROOT / cfg["agents_dir"] / f"{role.meta['name']}.md"
        out[path] = md_with_marker(meta, role.body, role.source)
    server = {"command": mcp["command"], "args": mcp["args"], "env": mcp.get("env") or {}}
    out[ROOT / cfg["mcp_file"]] = dump_json({"mcpServers": {mcp["name"]: server}})
    check_claude_settings(cfg, policy)
    return out


CLAUDE_SETTINGS = ROOT / ".claude" / "settings.json"


def check_claude_settings(cfg: dict, policy: dict, path: Path | None = None) -> None:
    """`.claude/settings.json` se mantiene a mano (AGENTS.md), pero sus permisos de la app deben
    decir lo mismo que `policy` del manifiesto, que es lo que reciben los demás agentes."""
    path = path or CLAUDE_SETTINGS
    prefix = cfg["tools"]["mcp_prefix"]
    permissions = json.loads(path.read_text(encoding="utf-8")).get("permissions", {})
    allowed = {rule for rule in permissions.get("allow", []) if rule.startswith(prefix)}
    expected = set(map_tools(policy.get("auto_allow", []), cfg["tools"], "policy.auto_allow"))
    denied = set(permissions.get("deny", []))
    wanted_deny = {f"Read(./{p})" for p in policy.get("deny_read", [])}
    wanted_deny |= {f"Edit(./{p})" for p in policy.get("deny_edit", [])}
    problems = [f"falta en allow: {t}" for t in sorted(expected - allowed)]
    problems += [
        f"sobra en allow (no está en policy.auto_allow): {t}" for t in sorted(allowed - expected)
    ]
    problems += [f"falta en deny: {t}" for t in sorted(wanted_deny - denied)]
    if problems:
        raise SystemExit(
            f"{rel(path)} no dice lo mismo que `policy` de .agents/manifest.yaml:\n  - "
            + "\n  - ".join(problems)
        )


def emit_codex(
    cfg: dict, skills: list[Doc], roles: list[Doc], mcp: dict, policy: dict
) -> dict[Path, str]:
    out: dict[Path, str] = {}
    header = f"# {MARKER} desde .agents/. No editar a mano: edita la fuente y regenera.\n"
    lines = [header, f"[mcp_servers.{mcp['name']}]"]
    lines.append(f"command = {toml_str(mcp['command'])}")
    lines.append("args = [" + ", ".join(toml_str(a) for a in mcp["args"]) + "]")
    if mcp.get("pass_env"):  # Codex solo pasa al servidor una lista blanca del entorno
        lines.append("env_vars = [" + ", ".join(toml_str(v) for v in mcp["pass_env"]) + "]")
    if mcp.get("env"):
        lines.append(f"\n[mcp_servers.{mcp['name']}.env]")
        lines += [f"{k} = {toml_str(str(v))}" for k, v in mcp["env"].items()]
    # Sesión principal: las de `auto_allow` sin preguntar; el resto, con la aprobación de Codex.
    for tool in policy.get("auto_allow", []):
        if tool.startswith("mcp:"):
            lines.append(f"\n[mcp_servers.{mcp['name']}.tools.{tool[4:]}]")
            lines.append('approval_mode = "approve"')
    out[ROOT / cfg["config_file"]] = "\n".join(lines) + "\n"
    for role in roles:
        body = [header.replace(".agents/", rel(role.source))]
        body.append(f"name = {toml_str(role.meta['name'])}")
        body.append(f"description = {toml_str(role.meta['description'])}")
        model = tier_model(cfg, role)
        if model:
            body.append(f"model = {toml_str(model)}")
        if role.meta.get("sandbox"):
            body.append(f"sandbox_mode = {toml_str(role.meta['sandbox'])}")
        body.append(f"developer_instructions = {toml_multiline(role.body)}")
        out[ROOT / cfg["agents_dir"] / f"{role.meta['name']}.toml"] = "\n".join(body) + "\n"
    return out


def opencode_rules(native: list[str]) -> dict:
    """Nombres nativos de OpenCode → reglas de `permission` que los permiten. `bash:<patrón>`
    permite solo esa orden (p. ej. `bash:git diff *`)."""
    rules: dict = {}
    for name in native:
        tool, _, pattern = name.partition(":")
        if pattern:
            rules.setdefault(tool, {"*": "deny"})[pattern] = "allow"
        else:
            rules[tool] = "allow"
    return rules


def opencode_paths(patterns: list[str]) -> dict:
    """`{"*": "allow"}` y encima, denegadas, las rutas de `policy` (gana la última que encaja)."""
    return {"*": "allow", **{pattern: "deny" for pattern in patterns}}


def emit_opencode(
    cfg: dict, skills: list[Doc], roles: list[Doc], mcp: dict, policy: dict
) -> dict[Path, str]:
    """OpenCode lee AGENTS.md y .agents/skills de serie: aquí van el servidor MCP, los permisos de
    la sesión principal y un subagente por rol con solo sus herramientas (`permission`, que en la
    1.1.1 sustituyó a `tools`)."""
    out: dict[Path, str] = {}
    tools = cfg["tools"]
    prefix = tools["mcp_prefix"]
    # Sesión principal: toda herramienta de la app pide permiso salvo las de `auto_allow`.
    permission: dict = {f"{prefix}*": "ask"}
    for name in map_tools(policy.get("auto_allow", []), tools, "opencode, policy.auto_allow"):
        permission[name] = "allow"
    permission["read"] = opencode_paths(policy.get("deny_read", []))
    permission["edit"] = opencode_paths(policy.get("deny_edit", []))
    server: dict = {"type": "local", "command": [mcp["command"], *mcp["args"]], "enabled": True}
    if mcp.get("env"):
        server["environment"] = mcp["env"]
    config = {
        "$schema": "https://opencode.ai/config.json",
        "mcp": {mcp["name"]: server},
        "permission": permission,
    }
    out[ROOT / cfg["config_file"]] = dump_json(config)
    for role in roles:
        where = f"opencode, rol {role.meta['name']}"
        # Todo denegado y encima solo lo del rol: ni terminal, ni edición, ni web, ni otros
        # subagentes (`task`) ni skills, salvo lo que el rol declare.
        rules = {"*": "deny", **opencode_rules(map_tools(role.meta.get("tools", []), tools, where))}
        if rules.get("read") == "allow":
            rules["read"] = opencode_paths(policy.get("deny_read", []))
        meta = {"description": role.meta["description"], "mode": "subagent"}
        model = tier_model(cfg, role)
        if model:
            meta["model"] = model
        meta["permission"] = rules
        path = ROOT / cfg["agents_dir"] / f"{role.meta['name']}.md"
        out[path] = md_with_marker(meta, role.body, role.source)
    return out


QWEN_SETTINGS_VERSION = 4


def emit_qwen(
    cfg: dict, skills: list[Doc], roles: list[Doc], mcp: dict, policy: dict
) -> dict[Path, str]:
    """Qwen Code: `.qwen/settings.json` (MCP, AGENTS.md como contexto y permisos), una copia de los
    skills (solo lee `.qwen/skills`) y un subagente por rol, cuya lista `tools` es exclusiva."""
    tools = cfg["tools"]
    server: dict = {"command": mcp["command"], "args": mcp["args"]}
    if mcp.get("env"):
        server["env"] = mcp["env"]
    deny = [f"Read(./{p})" for p in policy.get("deny_read", [])]
    deny += [f"Edit(./{p})" for p in policy.get("deny_edit", [])]
    settings = {
        "context": {"fileName": "AGENTS.md"},
        "mcpServers": {mcp["name"]: server},
        "permissions": {
            "allow": map_tools(policy.get("auto_allow", []), tools, "qwen, policy.auto_allow"),
            "deny": deny,
        },
        # Versión del formato: sin ella, Qwen Code 0.25 migra el fichero al abrirlo y lo reescribe.
        "$version": QWEN_SETTINGS_VERSION,
    }
    out = {ROOT / cfg["config_file"]: dump_json(settings)}
    out.update(copy_skills(skills, ROOT / cfg["skills_dir"]))
    for role in roles:
        where = f"qwen, rol {role.meta['name']}"
        meta = {
            "name": role.meta["name"],
            "description": role.meta["description"],
            "tools": map_tools(role.meta.get("tools", []), tools, where),
        }
        model = tier_model(cfg, role)
        if model:
            meta["model"] = model
        path = ROOT / cfg["agents_dir"] / f"{role.meta['name']}.md"
        out[path] = md_with_marker(meta, role.body, role.source)
    return out


def emit_antigravity(
    cfg: dict, skills: list[Doc], roles: list[Doc], mcp: dict, policy: dict
) -> dict[Path, str]:
    """Antigravity lee AGENTS.md y .agents/skills de serie: solo hace falta el MCP del espacio de
    trabajo. Sin subagentes generados (nivel C): ver docs/AGENTS_COMPAT.md."""
    server: dict = {"command": mcp["command"], "args": mcp["args"]}
    if mcp.get("env"):
        server["env"] = mcp["env"]
    return {ROOT / cfg["mcp_file"]: dump_json({"mcpServers": {mcp["name"]: server}})}


EMITTERS = {
    "claude": emit_claude,
    "codex": emit_codex,
    "opencode": emit_opencode,
    "qwen": emit_qwen,
    "antigravity": emit_antigravity,
}


# ---------------------------------------------------------------- principal


def build() -> tuple[dict[Path, str], list[Path]]:
    manifest = yaml.safe_load((AGENTS / "manifest.yaml").read_text(encoding="utf-8"))
    skills = [read_doc(p) for p in sorted((AGENTS / "skills").glob("*/SKILL.md"))]
    roles = [read_doc(p) for p in sorted((AGENTS / "roles").glob("*.md")) if p.name != "README.md"]
    for skill in skills:
        if skill.meta["name"] != skill.source.parent.name:
            raise SystemExit(
                f"{rel(skill.source)}: 'name' debe coincidir con el nombre de la carpeta"
            )
    expected: dict[Path, str] = {}
    managed_dirs: list[Path] = []
    for target, cfg in manifest["targets"].items():
        # Lo mínimo que necesita este script. El backend valida el resto (agent_registry.py, y un
        # test carga el manifiesto real), así la CI detecta un manifiesto inválido.
        if not isinstance(cfg, dict):
            raise SystemExit(f"manifest.yaml, agente '{target}': no es un mapa")
        if cfg.get("config") not in ("generated", "none"):
            raise SystemExit(
                f"manifest.yaml, agente '{target}': 'config' debe ser generated o none"
            )
        if not cfg.get("enabled"):
            continue
        if cfg["config"] != "generated":
            raise SystemExit(
                f"manifest.yaml, agente '{target}': 'enabled: true' necesita 'config: generated'"
            )
        if target not in EMITTERS:
            raise SystemExit(f"No hay emisor para el agente '{target}' en scripts/sync_agents.py")
        policy = manifest.get("policy") or {}
        expected.update(EMITTERS[target](cfg, skills, roles, manifest["mcp_server"], policy))
        for key in ("skills_dir", "agents_dir"):
            if cfg.get(key):
                managed_dirs.append(ROOT / cfg[key])
    return expected, managed_dirs


def stale_files(expected: dict[Path, str], managed_dirs: list[Path]) -> list[Path]:
    stale = []
    for directory in managed_dirs:
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and path not in expected:
                try:
                    if MARKER in path.read_text(encoding="utf-8"):
                        stale.append(path)
                except UnicodeDecodeError:
                    pass
    return stale


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="no escribe; falla si hay diferencias")
    args = parser.parse_args()

    expected, managed_dirs = build()
    changed = [
        p for p, c in expected.items() if not p.exists() or p.read_text(encoding="utf-8") != c
    ]
    stale = stale_files(expected, managed_dirs)

    if args.check:
        for p in changed:
            print(f"desactualizado: {rel(p)}")
        for p in stale:
            print(f"sobrante:       {rel(p)}")
        if changed or stale:
            print("Ejecuta: uv run scripts/sync_agents.py")
            return 1
        print(f"OK: {len(expected)} ficheros generados al día")
        return 0

    for p in changed:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(expected[p], encoding="utf-8", newline="\n")
        print(f"escrito:  {rel(p)}")
    for p in stale:
        p.unlink()
        print(f"borrado:  {rel(p)}")
        # Un skill renombrado deja su carpeta vacía (`.claude/skills/<viejo>/`): se quita también.
        with contextlib.suppress(OSError):
            p.parent.rmdir()
    print(f"Listo: {len(changed)} escritos, {len(stale)} borrados, {len(expected)} en total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
