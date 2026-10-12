"""Fase 21, criterio de aceptación: ninguna herramienta MCP devuelve `private` ni los importes
privados de `received_offers` (POLICIES §4).

Recorre todos los casos de la paridad. Tras sembrar cada uno, añade un mínimo centinela en
`private` del perfil y una oferta recibida con importes centinela marcados como privados en la
oferta 1, llama a la herramienta por MCP y busca los centinelas en la respuesta (también en los
errores).
"""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy import select

from app.core.db import get_engine, session_scope
from app.models import Job, ProfileVersion, ReceivedOffer
from app.services import profile
from app.services.documents import pdf
from tests.agent_support import mcp_call
from tests.cv_support import fake_converter
from tests.test_parity import CASES, FIXTURES, URL, Case, _fresh_db

FLOOR = 876_543
BASE = 987_654
VARIABLE = 123_457
SENTINELS = (str(FLOOR), str(BASE), str(VARIABLE), "salary_floor_eur", "sentinela-privada")


def _seed_private() -> None:
    """Mínimo en `private` (nueva versión del perfil) e importes privados en la oferta 1."""
    with session_scope() as session:
        latest = session.scalars(select(ProfileVersion).order_by(ProfileVersion.id.desc())).first()
        data: dict[str, Any] = (
            dict(latest.data)
            if latest
            else profile.load_from_yaml(profile.EXAMPLE_PATH).model_dump(mode="json")
        )
        data["private"] = {"salary_floor_eur": FLOOR, "nota": "sentinela-privada"}
        session.add(ProfileVersion(data=data, content_hash="privacidad"))
        if session.get(Job, 1) is not None:
            row = session.scalars(select(ReceivedOffer).where(ReceivedOffer.job_id == 1)).first()
            if row is None:
                row = ReceivedOffer(job_id=1)
                session.add(row)
            row.base_salary, row.variable, row.amounts_private = BASE, VARIABLE, True


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


@respx.mock
@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_no_tool_leaks_private_data(
    case: Case, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pdf, "get_converter", lambda: fake_converter())
    html = (FIXTURES / "hidden_ai.html").read_text(encoding="utf-8")
    respx.get(URL).mock(return_value=httpx.Response(200, text=html))
    _fresh_db(tmp_path, monkeypatch, "privacidad")
    if case.seed:
        case.seed()
    _seed_private()

    _error, out = mcp_call(case.tool, case.mcp_args)
    get_engine.cache_clear()

    text = json.dumps(out, ensure_ascii=False, default=str)
    assert not [s for s in SENTINELS if s in text]
    assert "private" not in _keys(out)
