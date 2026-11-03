"""Fase 10.2: analítica del embudo con un histórico de eventos sintético construido a mano."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.models import Company, Job, JobExtraction, Source
from app.services import analytics, events


def _t(day: int, hour: float = 10, month: int = 9) -> datetime:
    return datetime(2026, month, day, tzinfo=UTC) + timedelta(hours=hour)


class History:
    """Ofertas ficticias con sus eventos, fechados a mano."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.count = 0
        self.ats = Source(kind="greenhouse", name="Greenhouse Acme")
        self.alerts = Source(kind="email_alerts", name="Alertas por correo")
        session.add_all([self.ats, self.alerts])
        session.flush()

    def job(
        self,
        source: Source,
        seen: datetime,
        title: str | None,
        *steps: tuple[str, datetime] | tuple[str, datetime, dict[str, Any]],
    ) -> Job:
        self.count += 1
        n = self.count
        company = Company(name=f"Empresa {n}", normalized_name=f"empresa {n}")
        self.session.add(company)
        self.session.flush()
        job = Job(
            source_id=source.id,
            company_id=company.id,
            url=f"https://example.com/{n}",
            title=title or "Oferta",
            raw_text="Texto.",
            fingerprint=f"fp-{n}",
            first_seen_at=seen,
        )
        self.session.add(job)
        self.session.flush()
        if title is not None:
            data = {"title_normalized": title}
            self.session.add(JobExtraction(job_id=job.id, schema_version=1, data=data))
        events.record(self.session, job.id, "found", "system", occurred_at=seen)
        for step in steps:
            kind, when, *rest = step
            payload = rest[0] if rest else {}
            actor = "system" if kind in ("hard_filter_failed", "duplicate_detected") else "user"
            events.record(self.session, job.id, kind, actor, payload=payload, occurred_at=when)
        self.session.flush()
        return job


@pytest.fixture
def history(session: Session) -> History:
    h = History(session)
    ats, alerts = h.ats, h.alerts
    triaged = (("extracted", _t(14, 11)), ("approved", _t(14, 12)))
    # 1 · Semana 38: llega hasta aceptada. Respuesta a los 2 días.
    h.job(
        ats,
        _t(14),
        "data engineer",
        *triaged,
        ("applied_manually", _t(15)),
        ("reply_received", _t(17)),
        ("interview_scheduled", _t(18)),
        ("offer_received", _t(20)),
        ("accepted", _t(22)),
    )
    # 2 · Semana 38: rechazada tras el envío (es respuesta): 4 días.
    h.job(
        ats,
        _t(14),
        "data engineer",
        *triaged,
        ("applied_manually", _t(15, 0)),
        ("rejected", _t(19, 0)),
    )
    # 3 · Domingo 22:30 UTC = lunes 00:30 en Madrid: semana 39. Sin respuesta, esperando.
    h.job(
        ats,
        _t(20, 22.5),
        "data analyst",
        ("extracted", _t(21, 1)),
        ("approved", _t(21, 2)),
        ("applied_manually", _t(21, 3)),
    )
    # 4 · Semana 39: enviada y retirada sin respuesta.
    h.job(
        alerts,
        _t(22),
        "data analyst",
        ("extracted", _t(22, 11)),
        ("approved", _t(22, 12)),
        ("applied_manually", _t(23)),
        ("withdrawn", _t(25)),
    )
    # 5 · Semana 39: descartada, reabierta y descartada otra vez (cuenta una vez).
    h.job(
        alerts,
        _t(22),
        "ml engineer",
        ("extracted", _t(22, 11)),
        ("discarded", _t(22, 12), {"reason": "skills"}),
        ("reopened", _t(22, 13)),
        ("discarded", _t(22, 14), {"reason": "skills"}),
    )
    # 6 · Semana 39: cerrada por los filtros duros: no llega a triaje.
    h.job(
        alerts,
        _t(23),
        "ml engineer",
        ("extracted", _t(23, 11)),
        (
            "hard_filter_failed",
            _t(23, 11.5),
            {
                "failures": [
                    {"filter": "location", "reason": "x"},
                    {"filter": "salary", "reason": "y"},
                ]
            },
        ),
    )
    # 7 · Semana 39: cerrada por filtros, reabierta por el usuario y aprobada.
    h.job(
        alerts,
        _t(24),
        "bi developer",
        ("extracted", _t(24, 11)),
        ("hard_filter_failed", _t(24, 11.5), {"failures": [{"filter": "location", "reason": "x"}]}),
        ("reopened", _t(24, 12)),
        ("approved", _t(24, 13)),
    )
    # 8 · Semana 40: sin extraer, descartada sin motivo.
    h.job(ats, _t(28), None, ("discarded", _t(28, 11)))
    # 9 · Semana 40: duplicada: fuera del embudo.
    h.job(ats, _t(28), "data engineer", ("duplicate_detected", _t(28, 11)))
    # 10 · Semana 36: enviada sin aprobar (desde `pending_extraction`); respuesta en 12 h.
    h.job(
        alerts, _t(1), "data engineer", ("applied_manually", _t(2)), ("reply_received", _t(2, 22))
    )
    # 11 · Semana 40: rechazo antes de enviar: no es respuesta.
    h.job(ats, _t(29), "data analyst", ("extracted", _t(29, 11)), ("rejected", _t(29, 12)))
    return h  # fmt: skip


def test_steps_are_cumulative_and_count_each_job_once(session: Session, history: History) -> None:
    stats = analytics.get_funnel_stats(session)
    assert stats.duplicates_excluded == 1
    assert [(s.step, s.count) for s in stats.steps] == [
        ("found", 10),
        ("triaged", 8),
        ("approved", 6),
        ("applied", 5),
        ("replied", 3),
        ("interview", 1),
        ("offer", 1),
        ("accepted", 1),
    ]
    assert [s.rate_from_previous for s in stats.steps] == [
        None, 0.8, 0.75, 0.8333, 0.6, 0.3333, 1.0, 1.0,
    ]  # fmt: skip
    assert [s.rate_from_start for s in stats.steps] == [
        1.0, 0.8, 0.6, 0.5, 0.3, 0.1, 0.1, 0.1,
    ]  # fmt: skip
    assert stats.steps[1].label == "Pasan filtros"


def test_by_source(session: Session, history: History) -> None:
    stats = analytics.get_funnel_stats(session)
    assert [s.model_dump() for s in stats.by_source] == [
        {"source_id": history.ats.id, "kind": "greenhouse", "name": "Greenhouse Acme",
         "found": 5, "approved": 3, "applied": 3, "replied": 2, "interview": 1,
         "reply_rate": 0.6667, "tokens": 0, "cost_usd": None},
        {"source_id": history.alerts.id, "kind": "email_alerts", "name": "Alertas por correo",
         "found": 5, "approved": 3, "applied": 2, "replied": 1, "interview": 0,
         "reply_rate": 0.5, "tokens": 0, "cost_usd": None},
    ]  # fmt: skip


def test_by_title_groups_the_rest_as_others(session: Session, history: History) -> None:
    stats = analytics.get_funnel_stats(session, top_titles=2)
    rows = [
        (t.title, t.group, t.found, t.approved, t.applied, t.replied, t.interview, t.reply_rate)
        for t in stats.by_title
    ]
    assert rows == [
        ("data analyst", "title", 3, 2, 2, 0, 0, 0.0),
        ("data engineer", "title", 3, 3, 3, 3, 1, 1.0),
        ("Otros", "others", 3, 1, 0, 0, 0, None),
        ("Sin extraer", "not_extracted", 1, 0, 0, 0, 0, None),
    ]
    default = analytics.get_funnel_stats(session)
    assert [t.title for t in default.by_title] == [
        "data analyst", "data engineer", "ml engineer", "bi developer", "Sin extraer",
    ]  # fmt: skip


def test_by_week_uses_madrid_iso_weeks_and_fills_gaps(session: Session, history: History) -> None:
    stats = analytics.get_funnel_stats(session)
    rows = [
        (w.week, w.week_start, w.found, w.approved, w.applied, w.replied, w.interview)
        for w in stats.by_week
    ]
    assert rows == [
        ("2026-W36", date(2026, 8, 31), 1, 1, 1, 1, 0),
        ("2026-W37", date(2026, 9, 7), 0, 0, 0, 0, 0),
        ("2026-W38", date(2026, 9, 14), 2, 2, 2, 2, 1),
        ("2026-W39", date(2026, 9, 21), 5, 3, 2, 0, 0),
        ("2026-W40", date(2026, 9, 28), 2, 0, 0, 0, 0),
    ]
    assert stats.by_week[1].reply_rate is None


def test_response_time(session: Session, history: History) -> None:
    response = analytics.get_funnel_stats(session).response_time
    assert response.model_dump() == {
        "applied": 5,
        "replied": 3,
        "median_days": 2.0,
        "mean_days": 2.2,  # (2 + 4 + 0,5) / 3
        "awaiting_reply": 1,
        "closed_without_reply": 1,
    }


def test_discard_reasons_and_hard_filters(session: Session, history: History) -> None:
    stats = analytics.get_funnel_stats(session)
    assert [(r.reason, r.count) for r in stats.discard_reasons] == [
        ("skills", 1),
        ("unspecified", 1),
    ]
    assert [(f.filter, f.count) for f in stats.hard_filter_failures] == [
        ("location", 2),
        ("salary", 1),
    ]


def test_since_filters_by_first_seen_from_local_midnight(
    session: Session, history: History
) -> None:
    # Desde el lunes 21 en Madrid: entra la oferta 3 (domingo 22:30 UTC).
    stats = analytics.get_funnel_stats(session, since=date(2026, 9, 21))
    assert stats.since == date(2026, 9, 21)
    assert stats.duplicates_excluded == 1
    assert [s.count for s in stats.steps] == [7, 5, 3, 2, 0, 0, 0, 0]
    assert [w.week for w in stats.by_week] == ["2026-W39", "2026-W40"]
    assert stats.response_time.applied == 2 and stats.response_time.median_days is None
    assert [(r.reason, r.count) for r in stats.discard_reasons] == [
        ("skills", 1),
        ("unspecified", 1),
    ]
    later = analytics.get_funnel_stats(session, since=date(2026, 9, 22))
    assert later.steps[0].count == 6


def test_reopened_at_the_same_instant_still_reopens(session: Session) -> None:
    h = History(session)
    failure = {"failures": [{"filter": "location", "reason": "x"}]}
    # Mismo `occurred_at` que el cierre, registrado después: la proyección lo pone detrás.
    h.job(
        h.ats,
        _t(1),
        "data engineer",
        ("extracted", _t(1, 11)),
        ("hard_filter_failed", _t(1, 12), failure),
        ("reopened", _t(1, 12)),
    )
    h.job(h.ats, _t(1), "data analyst", ("duplicate_detected", _t(1, 12)),
          ("reopened", _t(1, 12)))  # fmt: skip
    stats = analytics.get_funnel_stats(session)
    assert stats.duplicates_excluded == 0
    assert [s.count for s in stats.steps[:2]] == [2, 1]


def test_empty_database(session: Session) -> None:
    stats = analytics.get_funnel_stats(session)
    assert [s.count for s in stats.steps] == [0] * 8
    assert all(s.rate_from_previous is None and s.rate_from_start is None for s in stats.steps)
    assert stats.by_source == stats.by_title == stats.by_week == []
    assert stats.response_time.median_days is None
    assert stats.discard_reasons == stats.hard_filter_failures == []


def test_by_week_cuts_at_madrid_midnight_across_the_clock_change(session: Session) -> None:
    """Cada semana empieza el lunes a las 00:00 en Madrid, también la del cambio de hora."""
    h = History(session)
    for seen in (
        datetime(2026, 9, 20, 21, 59, tzinfo=UTC),  # domingo 23:59 en Madrid (UTC+2): W38
        datetime(2026, 9, 20, 22, 0, tzinfo=UTC),  # lunes 00:00: W39
        datetime(2026, 10, 25, 22, 59, tzinfo=UTC),  # domingo 23:59 tras el cambio (UTC+1): W43
        datetime(2026, 10, 25, 23, 0, tzinfo=UTC),  # lunes 26, 00:00: W44
        datetime(2027, 1, 3, 23, 30, tzinfo=UTC),  # lunes 4 de enero: 2027-W01
    ):
        h.job(h.ats, seen, None)
    weeks = {w.week: w.found for w in analytics.get_funnel_stats(session).by_week}
    assert {week: n for week, n in weeks.items() if n} == {
        "2026-W38": 1, "2026-W39": 1, "2026-W43": 1, "2026-W44": 1, "2027-W01": 1,
    }  # fmt: skip
    assert len(weeks) == 17  # de la 38 a la 53 de 2026 y la 1 de 2027, sin huecos


def test_extraction_copies_its_title_to_its_column() -> None:
    assert JobExtraction(data={"title_normalized": "data engineer"}).title_normalized == (
        "data engineer"
    )
    assert JobExtraction(data={"title_normalized": 7}).title_normalized is None
    assert JobExtraction(data={}).title_normalized is None


def test_flow_says_where_each_sent_application_stopped(session: Session) -> None:
    h = History(session)
    sent = ("applied_manually", _t(2))
    h.job(h.ats, _t(1), "espera", sent)
    h.job(h.ats, _t(1), "espera 2", sent)
    h.job(h.ats, _t(1), "caducada", sent, ("expired", _t(3)))
    h.job(h.ats, _t(1), "rechazo", sent, ("rejected", _t(3)))
    h.job(h.ats, _t(1), "habla", sent, ("reply_received", _t(3)))
    h.job(h.ats, _t(1), "entrevista", sent, ("interview_scheduled", _t(3)))
    h.job(h.ats, _t(1), "oferta", sent, ("offer_received", _t(3)))
    h.job(h.ats, _t(1), "retirada", sent, ("offer_received", _t(3)), ("withdrawn", _t(4)))
    h.job(h.ats, _t(1), "aceptada", sent, ("offer_received", _t(3)), ("accepted", _t(4)))
    # Sin enviar: no cuenta en el recorrido.
    h.job(h.ats, _t(1), "sin enviar", ("extracted", _t(1, 11)), ("approved", _t(2)))

    flow = analytics.get_funnel_flow(session)
    assert {(s.step, s.outcome): s.count for s in flow.stops} == {
        ("applied", "open"): 2,
        ("applied", "expired"): 1,
        ("replied", "rejected"): 1,
        ("replied", "open"): 1,
        ("interview", "open"): 1,
        ("offer", "open"): 1,
        ("offer", "withdrawn"): 1,
    }
    counts = {s.step: s.count for s in flow.steps}
    assert counts["applied"] == 9
    assert counts["accepted"] == 1
    # Cada enviada está en una sola rama, o aceptada.
    assert sum(s.count for s in flow.stops) + counts["accepted"] == counts["applied"]


def test_flow_a_reopened_application_counts_as_open(session: Session) -> None:
    h = History(session)
    h.job(h.ats, _t(1), "x", ("applied_manually", _t(2)), ("expired", _t(3)), ("reopened", _t(4)))
    stops = analytics.get_funnel_flow(session).stops
    assert [(s.step, s.outcome, s.count) for s in stops] == [("applied", "open", 1)]


def test_flow_respects_the_period_and_an_empty_database(session: Session) -> None:
    assert analytics.get_funnel_flow(session).stops == []
    h = History(session)
    h.job(h.ats, _t(1), "vieja", ("applied_manually", _t(2)))
    assert analytics.get_funnel_flow(session, date(2026, 10, 1)).stops == []
    assert len(analytics.get_funnel_flow(session, date(2026, 8, 1)).stops) == 1
