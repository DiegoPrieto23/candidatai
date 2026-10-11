"""Huecos de skills (fase 14): qué piden las ofertas que el perfil no cubre, y con qué frecuencia.

Se miran las ofertas abiertas con extracción y las aprobadas o enviadas en los últimos `days`
días (aunque ya estén cerradas). La cobertura se recalcula aquí con el perfil y los alias de ahora
(`matching.skills`, sin embeddings ni escrituras): un alias añadido desde la UI quita el hueco al
momento, sin esperar a que el worker recalcule los matches.

Muchas ausencias son vocabulario («data warehousing», «cloud») y no huecos: la página «Skills»
deja decir «es lo mismo que…» (alias, `services.skill_aliases`), «la tengo» o «no la tengo»
(`skill_gap_marks`). Ver `docs/POLICIES.md` §2.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Company, Event, Job, SkillGapMark
from app.models.base import utcnow
from app.schemas.llm_io import JobExtraction
from app.services import extractions
from app.services import profile as profiles
from app.services.matching import skills
from app.services.matching.service import latest_scores
from app.services.pipeline import WORKING_STAGES, EventType

DEFAULT_DAYS = 60
MAX_EXAMPLES = 3
KIND_WEIGHT = {"must_have": 1.0, "nice_to_have": 0.5}  # obligatoria > deseable
UNSCORED = 50  # score supuesto de una oferta sin match todavía
MAX_SKILL_CHARS = 80  # un nombre más largo no es una skill: texto raro de la oferta, se ignora
RECENT_EVENTS = (EventType.APPROVED, EventType.APPLIED, EventType.APPLIED_MANUALLY)

SkillKind = Literal["must_have", "nice_to_have"]
MarkStatus = Literal["gap", "have"]
StatusFilter = Literal["gap", "have", "unmarked"]


class GapExample(BaseModel):
    job_id: int
    title: str
    company: str
    score: int | None
    kind: SkillKind


class SkillGap(BaseModel):
    skill: str  # la forma más frecuente en las ofertas
    key: str  # forma canónica plegada: identifica el hueco y su marca
    must_have_count: int  # ofertas que la piden como obligatoria
    nice_to_have_count: int  # … como deseable (sin contar las que ya la piden obligatoria)
    jobs_count: int
    weight: float  # suma por oferta: 1,0 obligatoria / 0,5 deseable × score / 100
    mark: MarkStatus | None
    examples: list[GapExample]  # las de más score primero


class ProfileSkillOption(BaseModel):
    name: str
    level: skills.CoveredLevel


class SkillGapsView(BaseModel):
    days: int
    jobs_considered: int
    gaps: list[SkillGap]
    profile_skills: list[ProfileSkillOption]  # para «Es lo mismo que…»


class MarkResult(BaseModel):
    ok: bool = True
    key: str
    skill: str
    mark: MarkStatus | None


@dataclass
class _Acc:
    names: Counter[str] = field(default_factory=Counter)
    kinds: dict[int, SkillKind] = field(default_factory=dict)  # job_id -> tipo


def _job_ids(session: Session, days: int) -> list[int]:
    open_ids = session.scalars(
        select(Application.job_id).where(Application.stage.in_([s.value for s in WORKING_STAGES]))
    ).all()
    since = utcnow() - timedelta(days=days)
    recent_ids = session.scalars(
        select(Event.job_id).where(
            Event.type.in_([e.value for e in RECENT_EVENTS]), Event.occurred_at >= since
        )
    ).all()
    return sorted({*open_ids, *recent_ids})


def _marks(session: Session) -> dict[str, SkillGapMark]:
    return {m.skill_key: m for m in session.scalars(select(SkillGapMark))}


def _accumulate(
    session: Session, job_ids: Sequence[int], index: dict[str, str], covered: set[str]
) -> tuple[dict[str, _Acc], int]:
    acc: dict[str, _Acc] = {}
    considered = 0
    for job_id, row in extractions.latest_rows(session, list(job_ids)).items():
        considered += 1
        ext = JobExtraction.model_validate(row.data)
        kinds: list[tuple[SkillKind, list[str]]] = [
            ("must_have", ext.must_have_skills),
            ("nice_to_have", ext.nice_to_have_skills),
        ]
        for kind, names in kinds:
            for name in names:
                key = skills.canonical(name, index)
                if not key or key in covered or len(name.strip()) > MAX_SKILL_CHARS:
                    continue
                entry = acc.setdefault(key, _Acc())
                entry.names[name.strip()] += 1
                entry.kinds.setdefault(job_id, kind)  # obligatoria gana si sale en las dos
    return acc, considered


def _job_labels(session: Session, job_ids: Sequence[int]) -> dict[int, tuple[str, str]]:
    if not job_ids:
        return {}
    rows = session.execute(
        select(Job.id, Job.title, Company.name)
        .join(Company, Company.id == Job.company_id)
        .where(Job.id.in_(job_ids))
    )
    return {job_id: (title, company) for job_id, title, company in rows}


def get_skill_gaps(
    session: Session, days: int = DEFAULT_DAYS, status: StatusFilter | None = None
) -> SkillGapsView:
    """Skills ausentes agregadas, de más a menos ofertas. Las marcadas salen aunque ya no las pida
    ninguna oferta del periodo (`jobs_count: 0`), mientras el perfil no las cubra. `skill` es la
    forma que más se repite en las extracciones (cuenta apariciones, no ofertas).

    Los nombres de skill y los títulos de los ejemplos salen de ofertas: son datos no confiables.

    Sin perfil importado lanza `ProfileNotFoundError`: no hay con qué comparar."""
    profile = profiles.current(session).profile
    index = skills.alias_index()
    levels = skills.profile_levels(profile, index)
    job_ids = _job_ids(session, days)
    acc, considered = _accumulate(session, job_ids, index, set(levels))
    involved = sorted({job_id for entry in acc.values() for job_id in entry.kinds})
    scores = latest_scores(session, involved)
    labels = _job_labels(session, involved)
    marks = _marks(session)

    gaps: list[SkillGap] = []
    for key, entry in acc.items():
        mark = marks.get(key)
        ordered = sorted(entry.kinds.items(), key=lambda kv: (-scores.get(kv[0], UNSCORED), kv[0]))
        weight = sum(
            KIND_WEIGHT[kind] * scores.get(job_id, UNSCORED) / 100 for job_id, kind in ordered
        )
        must = sum(1 for kind in entry.kinds.values() if kind == "must_have")
        gaps.append(
            SkillGap(
                skill=entry.names.most_common(1)[0][0],
                key=key,
                must_have_count=must,
                nice_to_have_count=len(entry.kinds) - must,
                jobs_count=len(entry.kinds),
                weight=round(weight, 2),
                mark=_status(mark),
                examples=[
                    GapExample(
                        job_id=job_id,
                        title=labels[job_id][0],
                        company=labels[job_id][1],
                        score=scores.get(job_id),
                        kind=kind,
                    )
                    for job_id, kind in ordered[:MAX_EXAMPLES]
                ],
            )
        )
    # Una marca no se pierde porque sus ofertas salgan del periodo: «no la tengo» sigue siendo un
    # hueco y «la tengo» sigue pendiente de añadir al perfil (el botón del agente la busca).
    for key, mark in marks.items():
        if key not in acc and key not in levels:
            gaps.append(
                SkillGap(
                    skill=mark.skill_name,
                    key=key,
                    must_have_count=0,
                    nice_to_have_count=0,
                    jobs_count=0,
                    weight=0.0,
                    mark=_status(mark),
                    examples=[],
                )
            )
    if status == "unmarked":
        gaps = [g for g in gaps if g.mark is None]
    elif status is not None:
        gaps = [g for g in gaps if g.mark == status]
    gaps.sort(key=lambda g: (-g.jobs_count, -g.weight, g.key))
    options = [ProfileSkillOption(name=s.name, level=s.level) for s in profile.skills]
    options += [ProfileSkillOption(name=name, level="basic") for name in profile.basic_skills]
    return SkillGapsView(days=days, jobs_considered=considered, gaps=gaps, profile_skills=options)


def _status(mark: SkillGapMark | None) -> MarkStatus | None:
    if mark is None:
        return None
    return "gap" if mark.status == "gap" else "have"


def set_mark(session: Session, skill: str, status: MarkStatus | None) -> MarkResult:
    """«No la tengo» (`gap`), «La tengo» (`have`) o quitar la marca (`None`). Se guarda por la
    forma canónica, así que vale cualquier forma de escribir la skill."""
    key = skills.canonical(skill, skills.alias_index())
    if not key:
        raise ValueError("La skill no puede quedar vacía.")
    name = skill.strip()
    mark = session.scalar(select(SkillGapMark).where(SkillGapMark.skill_key == key))
    if status is None:
        if mark is not None:
            session.delete(mark)
    elif mark is None:
        session.add(SkillGapMark(skill_key=key, skill_name=name, status=status))
    else:
        mark.status = status
        mark.skill_name = name
    session.flush()
    return MarkResult(key=key, skill=name, mark=status)
