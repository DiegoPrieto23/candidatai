"""Cuánto cuesta leer las instrucciones (fase 24.2): tokens estimados de `AGENTS.md` y de cada
skill y rol de `.agents/`, para `cai agents doctor --tokens`.

Aproximación de 4 caracteres por token, sin dependencias: basta para comparar y para ver qué
skill pesa demasiado para un modelo pequeño. career-ops midió unos 26 000 tokens de
instrucciones por evaluación.
"""

import math
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.core.config import REPO_ROOT

CHARS_PER_TOKEN = 4
SKILL_LIMIT = 6000  # tokens: por encima, deuda en dev/ROADMAP.md

Kind = Literal["instructions", "skill", "role"]


class InstructionSize(BaseModel):
    kind: Kind
    name: str
    path: str  # relativa a la raíz del repo
    chars: int
    tokens: int
    over_limit: bool  # solo los skills: más de `SKILL_LIMIT`


class InstructionSizes(BaseModel):
    items: list[InstructionSize]
    limit: int = SKILL_LIMIT

    def total(self, *names: str) -> int:
        return sum(i.tokens for i in self.items if i.name in names)


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def _size(kind: Kind, name: str, files: list[Path], root: Path) -> InstructionSize:
    text = "".join(f.read_text(encoding="utf-8") for f in files)
    chars, tokens = len(text), estimate_tokens(text)
    return InstructionSize(
        kind=kind,
        name=name,
        path=files[0].relative_to(root).as_posix(),
        chars=chars,
        tokens=tokens,
        over_limit=kind == "skill" and tokens > SKILL_LIMIT,
    )


def measure(root: Path = REPO_ROOT) -> InstructionSizes:
    """`AGENTS.md`, cada skill (su `SKILL.md` y los ficheros que trae al lado) y cada rol."""
    agents = root / ".agents"
    items = [_size("instructions", "AGENTS.md", [root / "AGENTS.md"], root)]
    for skill_md in sorted((agents / "skills").glob("*/SKILL.md")):
        extra = sorted(f for f in skill_md.parent.rglob("*") if f.is_file() and f != skill_md)
        items.append(_size("skill", skill_md.parent.name, [skill_md, *extra], root))
    for role in sorted((agents / "roles").glob("*.md")):
        if role.name != "README.md":
            items.append(_size("role", role.stem, [role], root))
    return InstructionSizes(items=items)
