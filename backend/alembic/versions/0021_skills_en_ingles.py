"""skills y roles en inglés

Fase 23.2: los nombres de skill guardados en `agent_runs` y `agent_requests` (la acción, la orden y
el comando) pasan de español a inglés (`procesar-ofertas` → `process-jobs`…), para que un encargo
pendiente o una ejecución en cola sigan funcionando con los skills renombrados. Se puede deshacer.

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-12 21:30:00

"""

import json
import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | Sequence[str] | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Copia fija (no se importa de la app): una migración no debe cambiar si cambia el código.
SKILLS = {
    "actualizar-perfil": "update-profile",
    "ampliar-busqueda": "broaden-search",
    "atender-encargos": "handle-requests",
    "buscar-ofertas": "search-jobs",
    "evaluar-encaje": "assess-fit",
    "generar-carta": "generate-cover-letter",
    "generar-cv": "generate-cv",
    "implementar-fase": "implement-phase",
    "importar-plantilla-cv": "import-cv-template",
    "investigar-empresa": "research-company",
    "plan-formacion": "training-plan",
    "preparar-candidatura": "prepare-application",
    "preparar-entrevista": "prepare-interview",
    "preparar-negociacion": "prepare-negotiation",
    "procesar-ofertas": "process-jobs",
    "redactar-mensaje": "draft-message",
    "redactar-seguimiento": "draft-follow-up",
    "repasar-entrevista": "debrief-interview",
    "resumen-diario": "daily-summary",
    "revisar-busqueda": "review-search",
    "revisar-linkedin": "review-linkedin",
    "revisar-respuestas": "review-replies",
    "simular-entrevista": "mock-interview",
}
# Acciones de la UI que no son un skill (`agent_launch.ActionId`): solo en la columna `action`.
ACTIONS = {
    "anadir-skills": "add-skills",
    "redactar-seguimientos": "draft-follow-ups",
    "dudas-oferta": "offer-questions",
}
ROLES = {
    "redactor": "writer",
    "verificador": "verifier",
    "clasificador": "classifier",
    "revisor": "reviewer",
}


def _translator(mapping: dict[str, str]):  # type: ignore[no-untyped-def]
    names = sorted(mapping, key=len, reverse=True)
    # Ni dentro de otra palabra ni como nombre de fichero (`plan-formacion-2026.md`, `/x.json`).
    pattern = re.compile(r"(?<![\w./-])(" + "|".join(map(re.escape, names)) + r")(?![\w-]|\.\w)")
    return lambda text: pattern.sub(lambda m: mapping[m.group(1)], text)


def _migrate(skills: dict[str, str], roles: dict[str, str], actions: dict[str, str]) -> None:
    skill = _translator(skills)
    # Los roles solo como identificadores: entre comillas invertidas o como subagente.
    role_names = "|".join(map(re.escape, roles))
    role = re.compile(rf"(`|Agent\(|subagent_type[\"']?\s*[:=]\s*[\"']?)({role_names})(?![\w-])")

    def text(value: str) -> str:
        return role.sub(lambda m: m.group(1) + roles[m.group(2)], skill(value))

    bind = op.get_bind()
    for table in ("agent_runs", "agent_requests"):
        columns = ["id", "action", "prompt"] + (["command"] if table == "agent_runs" else [])
        rows = bind.execute(sa.text(f"SELECT {', '.join(columns)} FROM {table}")).mappings().all()
        for row in rows:
            values = {
                "id": row["id"],
                "action": skills.get(row["action"], actions.get(row["action"], row["action"])),
                "prompt": text(row["prompt"]) if row["prompt"] else row["prompt"],
            }
            sets = "action = :action, prompt = :prompt"
            if table == "agent_runs":
                command = row["command"]
                parsed = json.loads(command) if isinstance(command, str) else command
                values["command"] = json.dumps([text(str(part)) for part in parsed or []])
                sets += ", command = :command"
            bind.execute(sa.text(f"UPDATE {table} SET {sets} WHERE id = :id"), values)


def upgrade() -> None:
    _migrate(SKILLS, ROLES, ACTIONS)


def downgrade() -> None:
    _migrate(
        {v: k for k, v in SKILLS.items()},
        {v: k for k, v in ROLES.items()},
        {v: k for k, v in ACTIONS.items()},
    )
