"""Coste por acción, agente, modelo y oferta (fase 25.4, `services/agent_costs.py`), con ejecuciones
falsas que traen uso, y uso normalizado (`agent_usage`)."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.models import AgentRun, Job, McpCall
from app.models.base import utcnow
from app.services import agent_costs, analytics, events
from app.services.agent_usage import normalize_usage
from app.services.events import JobNotFoundError

NOW = utcnow()


def _run(
    session: Session,
    action: str,
    agent: str = "claude",
    *,
    usage: dict[str, Any] | None = None,
    job_id: int | None = None,
    model: str | None = None,
    days_ago: float = 1,
    minutes: float = 5,
    status: str = "done",
) -> AgentRun:
    finished = NOW - timedelta(days=days_ago)
    row = AgentRun(
        action=action,
        job_id=job_id,
        agent=agent,
        model=model,
        status=status,
        prompt="Usa el skill…",
        command=["x"],
        unset_env=[],
        output_format="claude-stream-json",
        progress=[],
        questions=[],
        usage=usage,
        started_at=finished - timedelta(minutes=minutes),
        finished_at=finished,
    )
    session.add(row)
    session.flush()
    return row


def _write(session: Session, tool: str, job_id: int, run: AgentRun, ok: bool = True) -> None:
    assert run.started_at is not None
    session.add(
        McpCall(
            channel="mcp",
            client_name="claude-code",
            tool=tool,
            job_id=job_id,
            ok=ok,
            called_at=run.started_at + timedelta(minutes=1),
        )
    )
    session.flush()


def test_normalize_usage_translates_old_keys_and_drops_the_rest() -> None:
    old = {"num_turns": 4, "total_cost_usd": 0.5, "cache_read_tokens": 10, "denied_tools": ["x"]}
    assert normalize_usage(old) == {"turns": 4, "cost_usd": 0.5, "cached_tokens": 10}
    assert normalize_usage({"turns": True, "input_tokens": 3}) == {"input_tokens": 3}
    assert normalize_usage(None) == {}


def test_window_sums_by_action_agent_and_model(session: Session) -> None:
    u = {"input_tokens": 1000, "output_tokens": 200, "turns": 4, "duration_ms": 60_000}
    _run(session, "process-jobs", usage={**u, "cost_usd": 0.10})
    _run(session, "process-jobs", usage={**u, "cost_usd": 0.30}, model="sonnet")
    _run(session, "assess-fit", "opencode", usage={"input_tokens": 500, "output_tokens": 100})
    _run(session, "assess-fit", "opencode", usage=None)  # sin uso: cuenta, sin medias
    _run(session, "process-jobs", usage=u, days_ago=20)  # solo en la ventana de 30 días
    _run(session, "process-jobs", usage=u, status="running", days_ago=0)  # sin terminar

    week, month = agent_costs.get_costs(session, NOW).windows
    assert (week.days, month.days) == (7, 30)
    assert week.total.runs == 4 and week.total.with_usage == 3
    assert week.total.input_tokens == 2500 and week.total.output_tokens == 500
    assert week.total.cost_usd == pytest.approx(0.4)
    assert month.total.runs == 5

    actions = {g.key: g for g in week.by_action}
    process = actions["process-jobs"]
    assert process.runs == 2 and process.cost_usd == pytest.approx(0.4)
    assert process.avg_cost_usd == pytest.approx(0.2) and process.avg_tokens == 1200
    assert process.avg_duration_ms == 60_000
    assert process.instruction_tokens and process.instruction_tokens > 0  # lo que pesa su skill
    assess = actions["assess-fit"]
    assert assess.runs == 2 and assess.with_usage == 1
    assert assess.cost_usd is None and assess.avg_tokens == 600  # OpenCode sin coste: no se estima

    assert {g.key: g.runs for g in week.by_agent} == {"claude": 2, "opencode": 2}
    models = {g.key: g.runs for g in week.by_model}
    assert models == {"claude/default": 1, "claude/sonnet": 1, "opencode/default": 2}


@pytest.fixture
def two_jobs(session: Session, make_job: Callable[..., Job]) -> tuple[Job, Job]:
    jobs = make_job(), make_job()
    for job in jobs:
        events.record(session, job.id, "found", "system")
    return jobs


def test_batch_runs_are_shared_among_the_jobs_they_wrote(
    session: Session, two_jobs: tuple[Job, Job]
) -> None:
    a, b = two_jobs
    batch = _run(session, "process-jobs", usage={"input_tokens": 1000, "cost_usd": 0.2})
    _write(session, "save_extraction", a.id, batch)
    _write(session, "save_extraction", b.id, batch)
    _write(session, "get_job", b.id, batch)  # leer no cuenta
    _write(session, "save_extraction", a.id, batch, ok=False)  # repetida y fallida: no suma
    cv = _run(session, "generate-cv", job_id=a.id, usage={"input_tokens": 300, "cost_usd": 0.1})
    other = _run(session, "assess-fit", usage={"input_tokens": 50})
    _write(session, "save_extraction", b.id, other)  # escritura de otra acción: no cuenta

    assert agent_costs.jobs_of_run(session, batch) == [a.id, b.id]
    assert agent_costs.jobs_of_run(session, cv) == [a.id]
    assert agent_costs.jobs_of_run(session, other) == []

    cost_a = agent_costs.job_cost(session, a.id)
    assert [(r.action, r.share, r.shared_with) for r in cost_a.runs] == [
        ("process-jobs", 0.5, 2),
        ("generate-cv", 1.0, 1),
    ]
    assert cost_a.total.input_tokens == 800  # 500 del lote + 300 del CV
    assert cost_a.total.cost_usd == pytest.approx(0.2)
    assert agent_costs.job_cost(session, b.id).total.input_tokens == 500
    with pytest.raises(JobNotFoundError):
        agent_costs.job_cost(session, 999)


def test_funnel_cost_per_application_and_interview(
    session: Session, two_jobs: tuple[Job, Job]
) -> None:
    a, b = two_jobs
    for kind in ("extracted", "approved", "applied_manually", "interview_scheduled"):
        actor = "agent" if kind == "extracted" else "user"
        events.record(session, a.id, kind, actor)
    _run(session, "generate-cv", job_id=a.id, usage={"input_tokens": 900, "output_tokens": 100})
    _run(session, "generate-cv", job_id=b.id, usage={"output_tokens": 1000, "cost_usd": 0.5})
    stats = analytics.get_funnel_stats(session)
    cost = stats.agent_cost
    assert (cost.runs, cost.tokens, cost.applied, cost.interview) == (2, 2000, 1, 1)
    assert cost.cost_usd == pytest.approx(0.5)
    assert cost.tokens_per_applied == 2000 and cost.cost_per_applied_usd == pytest.approx(0.5)
    assert cost.tokens_per_interview == 2000
    assert sum(s.tokens for s in stats.by_source) == 2000
