# /// script
# requires-python = ">=3.11"
# ///
"""Saca de CHANGELOG.md las notas de una versión, para la release de GitHub (fase 25.6).

Uso (desde la raíz del repo):
    python scripts/release_notes.py v0.2.0     # escribe en la salida la sección [0.2.0]
    python scripts/release_notes.py --check    # comprueba la estructura del CHANGELOG

Sale con 1, con el motivo en la salida de errores, si la etiqueta no es una versión semántica, si
el CHANGELOG no tiene su sección o la tiene vacía, o si su estructura no es la esperada.
Solo usa la biblioteca estándar: el workflow de release lo ejecuta sin instalar nada.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"

UNRELEASED = "Sin publicar"
# Los grupos de Keep a Changelog 1.1.0, en español y en su orden.
GROUPS = ("Añadido", "Cambiado", "Obsoleto", "Eliminado", "Corregido", "Seguridad")

SEMVER = r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
TAG_RE = re.compile(rf"^v?({SEMVER})$")
VERSION_RE = re.compile(rf"^## \[({SEMVER})\] - (\d{{4}}-\d{{2}}-\d{{2}})$")
UNRELEASED_RE = re.compile(rf"^## \[{UNRELEASED}\]$")
LINK_RE = re.compile(r"^\[([^\]]+)\]: (https://\S+)$")


@dataclass
class Section:
    name: str  # «Sin publicar» o la versión, sin la «v»
    date: str | None
    line: int
    body: list[str] = field(default_factory=list)

    def text(self) -> str:
        return "\n".join(self.body).strip()


class ChangelogError(Exception):
    pass


def parse(text: str) -> tuple[list[Section], dict[str, str]]:
    """Las secciones `## [...]`, en orden, y los enlaces `[nombre]: url` del final."""
    sections: list[Section] = []
    links: dict[str, str] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        version, unreleased = VERSION_RE.match(line), UNRELEASED_RE.match(line)
        link = LINK_RE.match(line)
        if version:
            sections.append(Section(version.group(1), version.group(2), number))
        elif unreleased:
            sections.append(Section(UNRELEASED, None, number))
        elif line.startswith("## "):
            raise ChangelogError(
                f"Línea {number}: «{line}» no es «## [{UNRELEASED}]» ni «## [X.Y.Z] - AAAA-MM-DD»."
            )
        elif link:
            links[link.group(1)] = link.group(2)
        elif sections:
            sections[-1].body.append(line)
    return sections, links


def _semver(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def check(text: str) -> list[str]:
    """Lo que no cumple la estructura esperada (vacío si está bien)."""
    try:
        sections, links = parse(text)
    except ChangelogError as exc:
        return [str(exc)]
    errors: list[str] = []
    if not text.startswith("# Changelog\n"):
        errors.append("Tiene que empezar por «# Changelog».")
    if not sections or sections[0].name != UNRELEASED:
        errors.append(f"La primera sección tiene que ser «## [{UNRELEASED}]».")
    if [s.name for s in sections].count(UNRELEASED) > 1:
        errors.append(f"Hay más de una sección «{UNRELEASED}».")
    released = [s for s in sections if s.name != UNRELEASED]
    if not released:
        errors.append("No hay ninguna versión publicada.")
    for newer, older in zip(released, released[1:], strict=False):
        if _semver(newer.name) <= _semver(older.name):
            errors.append(
                f"Las versiones van de la más nueva a la más vieja: {newer.name}, {older.name}."
            )
        if newer.date and older.date and newer.date < older.date:
            errors.append(f"La fecha de {newer.name} es anterior a la de {older.name}.")
    for section in sections:
        groups = [line[4:] for line in section.body if line.startswith("### ")]
        unknown = [g for g in groups if g not in GROUPS]
        if unknown:
            errors.append(
                f"[{section.name}]: grupos desconocidos {unknown}; valen {', '.join(GROUPS)}."
            )
        known = [g for g in groups if g in GROUPS]
        if known != sorted(known, key=GROUPS.index) or len(set(known)) != len(known):
            errors.append(
                f"[{section.name}]: los grupos van una vez y en el orden {', '.join(GROUPS)}."
            )
        if section.name != UNRELEASED and not any(x.startswith("- ") for x in section.body):
            errors.append(f"[{section.name}] no tiene ninguna entrada.")
        if section.name not in links:
            errors.append(f"Falta el enlace «[{section.name}]: https://…» al final.")
    return errors


def notes_for(tag: str, text: str) -> str:
    """El cuerpo de la sección de `tag` (`v0.2.0` o `0.2.0`), sin su título."""
    match = TAG_RE.match(tag)
    if not match:
        raise ChangelogError(f"«{tag}» no es una versión semántica (vX.Y.Z).")
    version = match.group(1)
    sections, _ = parse(text)
    for section in sections:
        if section.name == version:
            body = section.text()
            if not body:
                raise ChangelogError(f"la sección [{version}] está vacía.")
            return body + "\n"
    raise ChangelogError(
        f"no hay sección «## [{version}] - AAAA-MM-DD». Pasa lo de "
        f"«{UNRELEASED}» a esa versión antes de poner la etiqueta."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tag", nargs="?", help="Etiqueta de la release, p. ej. v0.2.0.")
    parser.add_argument("--check", action="store_true", help="Solo comprueba la estructura.")
    parser.add_argument("--changelog", type=Path, default=CHANGELOG)
    args = parser.parse_args(argv)
    # En Windows la consola no es UTF-8: tildes, «» y → saldrían rotas.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if not args.check and not args.tag:
        parser.error("Indica una etiqueta (p. ej. v0.2.0) o --check.")
    text = args.changelog.read_text(encoding="utf-8")
    errors = check(text)
    if errors:
        for error in errors:
            print(f"CHANGELOG.md: {error}", file=sys.stderr)
        return 1
    if args.check:
        print("CHANGELOG.md: estructura correcta.")
        return 0
    try:
        notes = notes_for(args.tag, text)
    except ChangelogError as exc:
        print(f"CHANGELOG.md: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
