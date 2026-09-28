# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Genera la configuración nativa de cada agente a partir de .agents/.

Uso (desde la raíz del repo):
    uv run scripts/sync_agents.py            # escribe los ficheros generados
    uv run scripts/sync_agents.py --check    # no escribe; sale con 1 si algo no está al día

Fuente única: .agents/manifest.yaml, .agents/skills/*/SKILL.md y .agents/roles/*.md.
Salidas: .claude/skills, .claude/agents, .mcp.json, .codex/config.toml, .codex/agents.
Se copian ficheros (no enlaces simbólicos) para que funcione en Windows sin permisos especiales.
"""

from __future__ import annotations

import argparse
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
    return path.relative_to(ROOT).as_posix()


def dump_frontmatter(meta: dict) -> str:
    return yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=1000).strip()


def md_with_marker(meta: dict, body: str, source: Path) -> str:
    note = f"<!-- {MARKER} desde {rel(source)}. No editar a mano: edita la fuente y regenera. -->"
    return f"---\n{dump_frontmatter(meta)}\n---\n\n{note}\n\n{body.rstrip()}\n"


def map_tools(logical: list[str], mapping: dict) -> list[str]:
    native: list[str] = []
    for tool in logical:
        if tool.startswith("mcp:"):
            native.append(mapping["mcp_prefix"] + tool[4:])
        elif tool in mapping:
            native.extend(mapping[tool])
        else:
            raise SystemExit(f"Herramienta lógica desconocida: {tool!r} (añádela al manifiesto)")
    return native


def toml_str(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def toml_multiline(value: str) -> str:
    if "'''" not in value:
        return "'''\n" + value.rstrip() + "\n'''"
    escaped = value.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return '"""\n' + escaped.rstrip() + '\n"""'


# ---------------------------------------------------------------- emisores


def emit_claude(cfg: dict, skills: list[Doc], roles: list[Doc], mcp: dict) -> dict[Path, str]:
    out: dict[Path, str] = {}
    tools = cfg["tools"]
    extras_by_skill = cfg.get("skill_extras", {})
    for skill in skills:
        meta = {"name": skill.meta["name"], "description": skill.meta["description"]}
        extras = dict(extras_by_skill.get(skill.meta["name"], {}))
        if "allowed-tools" in extras:
            extras["allowed-tools"] = " ".join(map_tools(extras["allowed-tools"], tools))
        meta.update(extras)
        base = ROOT / cfg["skills_dir"] / skill.source.parent.name
        out[base / "SKILL.md"] = md_with_marker(meta, skill.body, skill.source)
        for extra_file in sorted(skill.source.parent.rglob("*")):
            if extra_file.is_file() and extra_file.name != "SKILL.md":
                target = base / extra_file.relative_to(skill.source.parent)
                out[target] = extra_file.read_text(encoding="utf-8")
    for role in roles:
        meta = {
            "name": role.meta["name"],
            "description": role.meta["description"],
            "tools": ", ".join(map_tools(role.meta.get("tools", []), tools)),
        }
        model = cfg["models"].get(role.meta.get("tier", ""))
        if model:
            meta["model"] = model
        path = ROOT / cfg["agents_dir"] / f"{role.meta['name']}.md"
        out[path] = md_with_marker(meta, role.body, role.source)
    server = {"command": mcp["command"], "args": mcp["args"], "env": mcp.get("env") or {}}
    out[ROOT / cfg["mcp_file"]] = (
        json.dumps({"mcpServers": {mcp["name"]: server}}, indent=2, ensure_ascii=False) + "\n"
    )
    return out


def emit_codex(cfg: dict, skills: list[Doc], roles: list[Doc], mcp: dict) -> dict[Path, str]:
    out: dict[Path, str] = {}
    header = f"# {MARKER} desde .agents/. No editar a mano: edita la fuente y regenera.\n"
    lines = [header, f"[mcp_servers.{mcp['name']}]"]
    lines.append(f"command = {toml_str(mcp['command'])}")
    lines.append("args = [" + ", ".join(toml_str(a) for a in mcp["args"]) + "]")
    if mcp.get("env"):
        lines.append(f"\n[mcp_servers.{mcp['name']}.env]")
        lines += [f"{k} = {toml_str(str(v))}" for k, v in mcp["env"].items()]
    out[ROOT / cfg["config_file"]] = "\n".join(lines) + "\n"
    for role in roles:
        body = [header.replace(".agents/", rel(role.source))]
        body.append(f"name = {toml_str(role.meta['name'])}")
        body.append(f"description = {toml_str(role.meta['description'])}")
        model = cfg["models"].get(role.meta.get("tier", ""))
        if model:
            body.append(f"model = {toml_str(model)}")
        if role.meta.get("sandbox"):
            body.append(f"sandbox_mode = {toml_str(role.meta['sandbox'])}")
        body.append(f"developer_instructions = {toml_multiline(role.body)}")
        out[ROOT / cfg["agents_dir"] / f"{role.meta['name']}.toml"] = "\n".join(body) + "\n"
    return out


EMITTERS = {"claude": emit_claude, "codex": emit_codex}


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
        if not cfg.get("enabled"):
            continue
        if target not in EMITTERS:
            raise SystemExit(f"No hay emisor para el agente '{target}' en scripts/sync_agents.py")
        expected.update(EMITTERS[target](cfg, skills, roles, manifest["mcp_server"]))
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
    print(f"Listo: {len(changed)} escritos, {len(stale)} borrados, {len(expected)} en total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
