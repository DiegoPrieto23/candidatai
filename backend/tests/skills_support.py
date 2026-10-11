"""Perfil de `demo/`, ofertas con skills a medida y una copia de `config/skill_aliases.yaml` para
los tests de la fase 14 (nunca tocan el fichero del repo)."""

import shutil
from pathlib import Path
from typing import Any

import pytest

from app.core import policies
from app.core.config import REPO_ROOT
from app.core.db import session_scope
from app.schemas.llm_io import JobExtraction
from app.services import extractions, ingest, profile
from tests.matching_support import demo_extraction_data

ORIGINAL_ALIASES = REPO_ROOT / "config" / "skill_aliases.yaml"


def use_aliases_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "skill_aliases.yaml"
    shutil.copyfile(ORIGINAL_ALIASES, path)
    monkeypatch.setattr(policies, "SKILL_ALIASES_PATH", path)
    return path


def import_demo_profile() -> None:
    with session_scope() as session:
        profile.import_profile(session, profile.EXAMPLE_PATH)


def add_job(must: list[str], nice: list[str] | None = None, title: str = "Data Engineer") -> int:
    """Oferta con extracción (la de demo, con estas skills); queda en `pending_triage`."""
    data: dict[str, Any] = demo_extraction_data("01-data-engineer")
    data.update(must_have_skills=must, nice_to_have_skills=nice or [])
    with session_scope() as session:
        job_id = ingest.add_from_text(
            session, title, f"Empresa {title} {must}", "Texto de la oferta. " * 20
        ).job_id
        extractions.save_extraction(session, job_id, JobExtraction.model_validate(data))
    return job_id
