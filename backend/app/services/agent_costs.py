"""Coste de las ejecuciones en segundo plano (fase 25.4): por acción, agente y modelo, por oferta
y en el embudo. Solo lo que dice cada agente (`agent_usage`): nada se estima ni se pasa a euros.

- **Por ventana** (7 y 30 días): las ejecuciones terminadas en ella, con totales y medias. Las
  que no traen uso (un agente que no lo da) cuentan en `runs` pero no en las medias.
- **Por oferta**: una ejecución con `job_id` (generar el CV) es entera de su oferta. Una de lote
  (procesar ofertas, evaluar encaje) se reparte a partes iguales entre las ofertas en que escribió:
  las llamadas de escritura de su acción en `mcp_calls` entre su inicio y su fin. Si a la vez haces
  lo mismo en una terminal, o lo hace otro agente, esas ofertas también cuentan (deuda
  conocida): `mcp_calls.client_name` es el nombre que da el cliente MCP, no el agente.
- Las ejecuciones en terminal no tienen uso: el agente no lo devuelve a la app.
"""

from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, load_only

from app.models import AgentRun, Job, McpCall
from app.models.base import utcnow
from app.services import agent_launch
from app.services.agent_actions import ACTIONS
from app.services.agent_runs import FINISHED
from app.services.agent_usage import USAGE_KEYS, normalize_usage
from app.services.events import JobNotFoundError
from app.services.instruction_size import measure

WINDOWS = (7, 30)
NO_MODEL = "default"  # sin modelo elegido: el del agente


class CostTotals(BaseModel):
    runs: int = 0
    with_usage: int = 0  # las que trajeron algún dato de uso
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    turns: int = 0
    duration_ms: int = 0
    cost_usd: float | None = None  # `None` si ninguna lo dio
    avg_tokens: float | None = None  # entrada + salida, por ejecución con uso
    avg_duration_ms: float | None = None
    avg_cost_usd: float | None = None  # por ejecución que dio coste


class CostGroup(CostTotals):
    key: str  # la acción, el agente o «agente/modelo»
    label: str
    instruction_tokens: int | None = None  # solo por acción: lo que pesa su skill (fase 24.2)


class CostWindow(BaseModel):
    days: int
    since: datetime
    total: CostTotals
    by_action: list[CostGroup]
    by_agent: list[CostGroup]
    by_model: list[CostGroup]


class AgentCosts(BaseModel):
    windows: list[CostWindow]  # 7 y 30 días
    terminal_note: str  # que las de terminal no cuentan


class _Acc:
    """Suma de uso, con cuántas ejecuciones dieron cada cosa (para las medias)."""

    def __init__(self) -> None:
        self.runs = 0
        self.with_usage = 0
        self.sums: dict[str, float] = defaultdict(float)
        self.cost_runs = 0
        self.duration_runs = 0

    def add(self, usage: dict[str, int | float] | dict[str, float]) -> None:
        self.runs += 1
        if not usage:
            return
        self.with_usage += 1
        for key in USAGE_KEYS:
            if key in usage:
                self.sums[key] += usage[key]
        self.cost_runs += "cost_usd" in usage
        self.duration_runs += "duration_ms" in usage

    def totals(self) -> CostTotals:
        s = self.sums
        tokens = s["input_tokens"] + s["output_tokens"]
        return CostTotals(
            runs=self.runs,
            with_usage=self.with_usage,
            input_tokens=round(s["input_tokens"]),
            output_tokens=round(s["output_tokens"]),
            cached_tokens=round(s["cached_tokens"]),
            turns=round(s["turns"]),
            duration_ms=round(s["duration_ms"]),
            cost_usd=round(s["cost_usd"], 6) if self.cost_runs else None,
            avg_tokens=round(tokens / self.with_usage, 1) if self.with_usage and tokens else None,
            avg_duration_ms=(
                round(s["duration_ms"] / self.duration_runs) if self.duration_runs else None
            ),
            avg_cost_usd=round(s["cost_usd"] / self.cost_runs, 6) if self.cost_runs else None,
        )


# Solo lo que hace falta para sumar: nada de `progress`, `prompt`, `result` ni `command`.
_COST_COLUMNS = (
    AgentRun.id,
    AgentRun.action,
    AgentRun.job_id,
    AgentRun.agent,
    AgentRun.model,
    AgentRun.preset,
    AgentRun.status,
    AgentRun.usage,
    AgentRun.started_at,
    AgentRun.finished_at,
)


def _finished(session: Session, since: datetime | None = None) -> list[AgentRun]:
    query = (
        select(AgentRun)
        .options(load_only(*_COST_COLUMNS))
        .where(AgentRun.status.in_(FINISHED))
        .order_by(AgentRun.id)
    )
    if since is not None:
        query = query.where(AgentRun.finished_at >= since)
    return list(session.scalars(query))


def _model_key(row: AgentRun) -> tuple[str, str]:
    model = agent_launch.model_label(row.model, row.preset)
    key = f"{row.agent}/{model or NO_MODEL}"
    return key, f"{row.agent} · {model}" if model else f"{row.agent} · por defecto"


def _groups(
    rows: Iterable[AgentRun],
    key_of: Callable[[AgentRun], tuple[str, str]],
    sizes: dict[str, int] | None = None,
) -> list[CostGroup]:
    accs: dict[str, _Acc] = defaultdict(_Acc)
    labels: dict[str, str] = {}
    for row in rows:
        key, label = key_of(row)
        accs[key].add(normalize_usage(row.usage))
        labels[key] = label
    out = [
        CostGroup(
            key=key,
            label=labels[key],
            instruction_tokens=(sizes or {}).get(key),
            **acc.totals().model_dump(),
        )
        for key, acc in accs.items()
    ]
    return sorted(out, key=lambda g: (-g.runs, g.key))


def _skill_tokens() -> dict[str, int]:
    """Tokens de las instrucciones del skill de cada acción (`instruction_size`)."""
    sizes = {i.name: i.tokens for i in measure().items if i.kind == "skill"}
    out: dict[str, int] = {}
    for action, spec in ACTIONS.items():
        skill = spec.skill or action
        if skill in sizes:
            out[action] = sizes[skill]
    return out


def window(session: Session, days: int, now: datetime | None = None) -> CostWindow:
    since = (now or utcnow()) - timedelta(days=days)
    rows = _finished(session, since)
    total = _Acc()
    for row in rows:
        total.add(normalize_usage(row.usage))
    labels = {action: spec.label for action, spec in ACTIONS.items()}
    return CostWindow(
        days=days,
        since=since,
        total=total.totals(),
        by_action=_groups(
            rows, lambda r: (r.action, labels.get(r.action, r.action)), _skill_tokens()
        ),
        by_agent=_groups(rows, lambda r: (r.agent, r.agent)),
        by_model=_groups(rows, _model_key),
    )


def get_costs(session: Session, now: datetime | None = None) -> AgentCosts:
    return AgentCosts(
        windows=[window(session, days, now) for days in WINDOWS],
        terminal_note="Solo las ejecuciones en segundo plano: en una terminal el agente no "
        "devuelve su uso a la app.",
    )


# --- Por oferta ----------------------------------------------------------------------------------


def _write_tools(action: str) -> list[str]:
    spec = ACTIONS.get(action)  # type: ignore[call-overload]
    return [tool for tool in (spec.background if spec else ()) if tool.startswith("save_")]


def jobs_of_run(session: Session, row: AgentRun) -> list[int]:
    """Las ofertas de una ejecución: la suya, o en las de lote, en las que escribió."""
    if row.job_id is not None:
        return [row.job_id]
    tools = _write_tools(row.action)
    if not tools or row.started_at is None or row.finished_at is None:
        return []
    ids = session.scalars(
        select(McpCall.job_id)
        .where(
            McpCall.tool.in_(tools),
            McpCall.ok.is_(True),
            McpCall.job_id.is_not(None),
            McpCall.called_at >= row.started_at,
            McpCall.called_at <= row.finished_at,
        )
        .distinct()
    )
    return sorted(i for i in ids if i is not None)


class JobRunCost(BaseModel):
    run_id: int
    action: str
    label: str
    agent: str
    model: str | None
    finished_at: datetime | None
    share: float  # la parte de la ejecución que es de esta oferta (1 = entera)
    shared_with: int  # cuántas ofertas se la reparten
    usage: dict[str, float]  # ya multiplicado por `share`


class JobCost(BaseModel):
    job_id: int
    runs: list[JobRunCost]
    total: CostTotals
    terminal_note: str


def _batch_jobs(session: Session, rows: list[AgentRun]) -> dict[int, list[int]]:
    """Las ofertas de las ejecuciones de lote, con una sola consulta a `mcp_calls` para todas."""
    batches = [
        r
        for r in rows
        if r.job_id is None and r.started_at and r.finished_at and _write_tools(r.action)
    ]
    if not batches:
        return {}
    tools = sorted({tool for r in batches for tool in _write_tools(r.action)})
    calls = session.execute(
        select(McpCall.tool, McpCall.job_id, McpCall.called_at).where(
            McpCall.tool.in_(tools),
            McpCall.ok.is_(True),
            McpCall.job_id.is_not(None),
            McpCall.called_at >= min(r.started_at for r in batches if r.started_at),
            McpCall.called_at <= max(r.finished_at for r in batches if r.finished_at),
        )
    ).all()
    out: dict[int, list[int]] = {}
    for r in batches:
        assert r.started_at is not None and r.finished_at is not None
        own = set(_write_tools(r.action))
        out[r.id] = sorted(
            {
                job_id
                for tool, job_id, at in calls
                if tool in own and job_id is not None and r.started_at <= at <= r.finished_at
            }
        )
    return out


def attributed(
    session: Session, since: datetime | None = None, for_job: int | None = None
) -> dict[int, list[JobRunCost]]:
    """Lo de cada oferta en las ejecuciones terminadas (desde `since`, todas si es `None`). Con
    `for_job`, solo las que pueden ser de esa oferta: las suyas y las de lote."""
    query = (
        select(AgentRun)
        .options(load_only(*_COST_COLUMNS))
        .where(AgentRun.status.in_(FINISHED))
        .order_by(AgentRun.id)
    )
    if since is not None:
        query = query.where(AgentRun.finished_at >= since)
    if for_job is not None:
        query = query.where(or_(AgentRun.job_id == for_job, AgentRun.job_id.is_(None)))
    rows = list(session.scalars(query))
    batch = _batch_jobs(session, rows)
    out: dict[int, list[JobRunCost]] = defaultdict(list)
    for row in rows:
        jobs = [row.job_id] if row.job_id is not None else batch.get(row.id, [])
        if not jobs:
            continue
        share = 1 / len(jobs)
        usage = {k: round(v * share, 6) for k, v in normalize_usage(row.usage).items()}
        spec = ACTIONS.get(row.action)  # type: ignore[call-overload]
        for job_id in jobs:
            out[job_id].append(
                JobRunCost(
                    run_id=row.id,
                    action=row.action,
                    label=spec.label if spec else row.action,
                    agent=row.agent,
                    model=agent_launch.model_label(row.model, row.preset),
                    finished_at=row.finished_at,
                    share=round(share, 4),
                    shared_with=len(jobs),
                    usage=usage,
                )
            )
    return out


def sum_runs(runs: Iterable[JobRunCost]) -> CostTotals:
    acc = _Acc()
    for run in runs:
        acc.add(run.usage)  # ya repartido
    return acc.totals()


def job_cost(session: Session, job_id: int) -> JobCost:
    if session.get(Job, job_id) is None:
        raise JobNotFoundError(f"No existe la oferta {job_id}.")
    runs = attributed(session, for_job=job_id).get(job_id, [])
    return JobCost(
        job_id=job_id,
        runs=runs,
        total=sum_runs(runs),
        terminal_note="No cuenta lo que hagas en una terminal: ahí el agente no devuelve su uso.",
    )
