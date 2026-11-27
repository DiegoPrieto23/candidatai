"""El texto de `docs/POLICIES.md` por secciones, para el agente (`get_policies`).

Los roles que redactan y verifican (`writer`, `verifier`) necesitan las políticas. Pedírselas a la
app, en vez de leer el fichero, deja ejecutarlos sin lectura de ficheros: así caben en el techo de
los agentes que no saben limitar la lectura a `docs/` (Codex, OpenCode). Solo lectura y sin datos
personales: es un documento del repositorio.
"""

import re
from functools import cache
from pathlib import Path

from pydantic import BaseModel

from app.core.config import REPO_ROOT

POLICIES_FILE = REPO_ROOT / "docs" / "POLICIES.md"
SOURCE = "docs/POLICIES.md"
_HEADING = re.compile(r"^## (\d+)\. (.+?)\s*$")


class PolicySection(BaseModel):
    number: int
    title: str
    text: str  # la sección entera en Markdown, con su título y sus apartados


class PoliciesView(BaseModel):
    source: str
    sections: list[PolicySection]


class UnknownSectionError(LookupError):
    pass


@cache
def _sections(path: Path) -> tuple[PolicySection, ...]:
    found: list[PolicySection] = []
    current: tuple[int, str] | None = None
    lines: list[str] = []

    def close() -> None:
        if current is not None:
            found.append(
                PolicySection(number=current[0], title=current[1], text="\n".join(lines).strip())
            )

    for line in path.read_text(encoding="utf-8").splitlines():
        if match := _HEADING.match(line):
            close()
            current = (int(match.group(1)), match.group(2))
            lines = [line]
        elif current is not None:
            lines.append(line)
    close()
    return tuple(found)


def read(sections: list[int] | None = None, path: Path = POLICIES_FILE) -> PoliciesView:
    """Las secciones pedidas, en su orden del documento (sin pedir ninguna, todas).
    `UnknownSectionError` si alguna no existe."""
    every = _sections(path)
    if not sections:
        return PoliciesView(source=SOURCE, sections=list(every))
    numbers = {section.number for section in every}
    if missing := sorted(set(sections) - numbers):
        listed = ", ".join(str(n) for n in sorted(numbers))
        raise UnknownSectionError(
            f"No existe la sección {', '.join(map(str, missing))} de las políticas (hay: {listed})."
        )
    return PoliciesView(source=SOURCE, sections=[s for s in every if s.number in set(sections)])
