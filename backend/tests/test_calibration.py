"""Fase 20: calibración del score con un histórico sintético de candidaturas enviadas."""

from datetime import date, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Contact, Document, DocumentRender, Job, Match, ProfileVersion
from app.services import analytics, events
from app.services.analytics import Calibration, CalibrationGroup, wilson_interval
from tests.test_analytics import History, _t


class Sent(History):
    """El histórico del embudo más lo que se sabía al enviar: score, veredicto, CV, carta…"""

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self.profile = ProfileVersion(data={}, content_hash="calibracion")
        session.add(self.profile)
        session.flush()

    def step(
        self, job: Job, kind: str, when: datetime, payload: dict[str, Any] | None = None
    ) -> None:
        actor = "agent" if kind == "fit_assessed" else "user"
        events.record(self.session, job.id, kind, actor, payload=payload or {}, occurred_at=when)
        self.session.flush()

    def match(self, job: Job, score: int, at: datetime) -> None:
        self.session.add(
            Match(
                job_id=job.id,
                profile_version_id=self.profile.id,
                hard_filters={"passed": True, "failures": []},
                score=score,
                breakdown={},
                created_at=at,
            )
        )
        self.session.flush()

    def document(self, job: Job, kind: str, at: datetime) -> Document:
        doc = Document(
            job_id=job.id,
            profile_version_id=self.profile.id,
            kind=kind,
            language="es",
            content={},
            created_at=at,
        )
        self.session.add(doc)
        self.session.flush()
        return doc

    def cv(self, job: Job, template: str, at: datetime) -> dict[str, Any]:
        """CV con un render de esa plantilla; devuelve el payload del envío que lo apunta."""
        render = DocumentRender(
            document_id=self.document(job, "cv", at).id,
            template_id=template,
            template_hash="h",
            options={},
            pages=1,
            selected=True,
        )
        self.session.add(render)
        self.session.flush()
        return {"render_id": render.id}

    def referral(self, job: Job, status: str) -> None:
        self.session.add(Contact(job_id=job.id, name="Ana Demo", referral=status))
        self.session.flush()


def _job(h: Sent, source: Any, seen: datetime, platform: str | None = None) -> Job:
    job = h.job(source, seen, "data engineer", ("extracted", seen), ("approved", seen))
    job.platform = platform
    return job


@pytest.fixture
def history(session: Session) -> Sent:
    h = Sent(session)
    ats, alerts = h.ats, h.alerts

    # 1 · Score 90, fuerte, `clasica`, carta antes del envío, referencia dada, LinkedIn.
    #     Enviada a las 10 h del alta (0-1 días). Respuesta y entrevista.
    j1 = _job(h, ats, _t(1, 10), "linkedin")
    h.match(j1, 90, _t(1, 11))
    h.step(j1, "fit_assessed", _t(1, 12), {"verdict": "strong"})
    h.document(j1, "cover_letter", _t(1, 15))
    h.step(j1, "applied_manually", _t(1, 20), h.cv(j1, "clasica", _t(1, 14)))
    h.step(j1, "reply_received", _t(3))
    h.step(j1, "interview_scheduled", _t(5))
    h.referral(j1, "given")

    # 2 · Score 88 al enviar (un recálculo posterior de 50 no cuenta), fuerte, `clasica`, sin
    #     carta. Justo 2 días hasta el envío (2-3 días). Rechazada: respuesta sin entrevista.
    j2 = _job(h, ats, _t(2, 10), "linkedin")
    h.match(j2, 88, _t(2, 11))
    h.step(j2, "fit_assessed", _t(2, 12), {"verdict": "strong"})
    h.step(j2, "applied_manually", _t(4, 10), h.cv(j2, "clasica", _t(2, 13)))
    h.match(j2, 50, _t(5))
    h.step(j2, "rejected", _t(6))

    # 3 · Score 70, posible (un «fuerte» después del envío no cuenta), `ats-simple`, carta
    #     escrita después del envío (cuenta como sin carta), sin portal. 5 días. Esperando.
    j3 = _job(h, alerts, _t(3))
    h.match(j3, 70, _t(3, 11))
    h.step(j3, "fit_assessed", _t(3, 12), {"verdict": "possible"})
    h.step(j3, "applied_manually", _t(8), h.cv(j3, "ats-simple", _t(3, 13)))
    h.document(j3, "cover_letter", _t(10))
    h.step(j3, "fit_assessed", _t(11), {"verdict": "strong"})

    # 4 · Sin score antes del envío: vale el primero después (55). Sin valorar, sin CV de la
    #     app, InfoJobs, referencia pedida. 16 días. Retirada sin respuesta.
    j4 = _job(h, alerts, _t(4), "infojobs")
    h.step(j4, "applied_manually", _t(20))
    h.match(j4, 55, _t(21))
    h.match(j4, 95, _t(22))
    h.step(j4, "withdrawn", _t(25))
    h.referral(j4, "requested")

    # 5 · Sin ningún match, débil, `clasica`, carta, LinkedIn. 23 horas (0-1 días). Entrevista
    #     sin `reply_received` (cuenta como respuesta).
    j5 = _job(h, ats, _t(5, 10), "linkedin")
    h.step(j5, "fit_assessed", _t(5, 11), {"verdict": "weak"})
    h.document(j5, "cover_letter", _t(5, 12))
    h.step(j5, "applied_manually", _t(6, 9), h.cv(j5, "clasica", _t(5, 12)))
    h.step(j5, "interview_scheduled", _t(9))

    # 6 · Aprobada y no enviada: no entra.
    j6 = _job(h, ats, _t(6), "linkedin")
    h.match(j6, 95, _t(6, 11))
    h.step(j6, "fit_assessed", _t(6, 12), {"verdict": "strong"})
    return h


def _row(group: CalibrationGroup) -> tuple[str, int, int, int, int]:
    return (group.key, group.applied, group.replied, group.interview, group.awaiting)


def _rows(groups: list[CalibrationGroup]) -> list[tuple[str, int, int, int, int]]:
    return [_row(g) for g in groups]


def test_total_counts_only_sent_jobs(session: Session, history: Sent) -> None:
    cal = analytics.get_calibration(session)
    assert _row(cal.total) == ("total", 5, 3, 2, 1)
    assert cal.total.reply_rate.model_dump() == {"rate": 0.6, "low": 0.2307, "high": 0.8824}
    assert cal.total.interview_rate.model_dump() == {"rate": 0.4, "low": 0.1176, "high": 0.7693}
    assert cal.min_cases == 10
    assert cal.confidence == 0.95


def test_by_score_uses_the_score_at_send_time(session: Session, history: Sent) -> None:
    cal = analytics.get_calibration(session)
    assert [g.label for g in cal.by_score] == ["< 60", "60-74", "75-84", "≥ 85", "Sin score"]
    assert _rows(cal.by_score) == [
        ("lt60", 1, 0, 0, 0),  # 4: el primer score después del envío
        ("60_74", 1, 0, 0, 1),  # 3
        ("75_84", 0, 0, 0, 0),
        ("gte85", 2, 2, 1, 0),  # 1 y 2 (el recálculo de 50 no cuenta)
        ("none", 1, 1, 1, 0),  # 5
    ]
    empty = cal.by_score[2]
    assert empty.reply_rate.rate is None and empty.reply_rate.low is None
    assert cal.by_score[3].reply_rate.model_dump() == {"rate": 1.0, "low": 0.3424, "high": 1.0}


def test_by_verdict_ignores_assessments_after_sending(session: Session, history: Sent) -> None:
    cal = analytics.get_calibration(session)
    assert _rows(cal.by_verdict) == [
        ("strong", 2, 2, 1, 0),
        ("possible", 1, 0, 0, 1),
        ("weak", 1, 1, 1, 0),
        ("none", 1, 0, 0, 0),
    ]


def test_by_source_and_platform(session: Session, history: Sent) -> None:
    cal = analytics.get_calibration(session)
    ats, alerts = str(history.ats.id), str(history.alerts.id)
    assert _rows(cal.by_source) == [(ats, 3, 3, 2, 0), (alerts, 2, 0, 0, 1)]
    assert [g.label for g in cal.by_source] == ["Greenhouse Acme", "Alertas por correo"]
    assert _rows(cal.by_platform) == [
        ("linkedin", 3, 3, 2, 0),
        ("infojobs", 1, 0, 0, 0),
        ("none", 1, 0, 0, 1),
    ]
    assert cal.by_platform[-1].label == "Sin portal"


def test_by_signal_counts_each_signal_and_none(session: Session, history: Sent) -> None:
    # Fase 25.3: la 1 (respuesta y entrevista) es temporal y de agencia; la 3 (esperando), temporal.
    sent = list(session.scalars(select(Job).order_by(Job.id)))
    sent[0].signals = {
        "fixed_term": {"origin": "extraction"},
        "employer_hidden": {"reason": "agency"},
    }
    sent[2].signals = {"fixed_term": {"origin": "extraction"}, "reposted": {"count": 2}}
    session.flush()
    groups = {g.key: _row(g) for g in analytics.get_calibration(session).by_signal}
    assert list(groups) == [
        "salary_range_wide", "employer_hidden", "fixed_term", "stale_repost", "ai_screening", "none"
    ]  # fmt: skip
    assert groups["fixed_term"] == ("fixed_term", 2, 1, 1, 1)
    assert groups["employer_hidden"] == ("employer_hidden", 1, 1, 1, 0)
    assert groups["salary_range_wide"] == ("salary_range_wide", 0, 0, 0, 0)
    assert groups["none"] == ("none", 3, 2, 1, 0)  # `reposted` (fase 16) no es de oferta dudosa


def test_by_template_letter_referral_and_days(session: Session, history: Sent) -> None:
    cal = analytics.get_calibration(session)
    assert _rows(cal.by_template) == [
        ("clasica", 3, 3, 2, 0),
        ("ats-simple", 1, 0, 0, 1),
        ("none", 1, 0, 0, 0),
    ]
    assert cal.by_template[-1].label == "Sin CV de la app"
    assert _rows(cal.by_cover_letter) == [("with", 2, 2, 2, 0), ("without", 3, 1, 0, 1)]
    assert _rows(cal.by_referral) == [
        ("given", 1, 1, 1, 0),
        ("requested", 1, 0, 0, 0),
        ("none", 3, 2, 1, 1),
    ]
    assert _rows(cal.by_days_to_apply) == [
        ("0_1", 2, 2, 2, 0),
        ("2_3", 1, 1, 0, 0),  # justo 2 días
        ("4_7", 1, 0, 0, 1),
        ("8_plus", 1, 0, 0, 0),
    ]


def test_low_data_below_min_cases(session: Session, history: Sent) -> None:
    assert all(g.low_data for g in analytics.get_calibration(session).by_score)
    cal = analytics.get_calibration(session, min_cases=2)
    assert [g.low_data for g in cal.by_score] == [True, True, True, False, True]
    assert not cal.total.low_data


def test_since_filters_by_first_send_from_local_midnight(session: Session, history: Sent) -> None:
    # 8 de septiembre a las 00:00 en Madrid = 7 a las 22:00 UTC: entran la 3 y la 4.
    cal = analytics.get_calibration(session, since=date(2026, 9, 8))
    assert cal.since == date(2026, 9, 8)
    assert _row(cal.total) == ("total", 2, 0, 0, 1)
    assert [g.key for g in cal.by_source] == [str(history.alerts.id)]


def test_empty_database(session: Session) -> None:
    cal = analytics.get_calibration(session)
    assert isinstance(cal, Calibration)
    assert _row(cal.total) == ("total", 0, 0, 0, 0)
    assert cal.total.reply_rate.rate is None
    assert len(cal.by_score) == 5 and all(g.applied == 0 for g in cal.by_score)
    assert cal.by_source == cal.by_platform == cal.by_template == []


@pytest.mark.parametrize(
    ("successes", "n", "expected"),
    [
        (0, 10, (0.0, 0.0, 0.2775)),
        (10, 10, (1.0, 0.7225, 1.0)),
        (3, 5, (0.6, 0.2307, 0.8824)),
        (1, 2, (0.5, 0.0945, 0.9055)),
    ],
)
def test_wilson_interval(successes: int, n: int, expected: tuple[float, float, float]) -> None:
    interval = wilson_interval(successes, n)
    assert (interval.rate, interval.low, interval.high) == expected


def test_wilson_without_cases() -> None:
    assert wilson_interval(0, 0).model_dump() == {"rate": None, "low": None, "high": None}


def test_cli_text_output(
    session: Session, history: Sent, capsys: pytest.CaptureFixture[str]
) -> None:
    from app.cli import _render_calibration

    _render_calibration(analytics.get_calibration(session, min_cases=2))
    out = capsys.readouterr().out
    assert "Candidaturas enviadas: 5" in out
    assert "≥ 85" in out and "2 enviadas · respuesta 100% [34%-100%] · entrevista 50%" in out
    assert "75-84" not in out  # sin envíos, no se lista
    assert "Sin CV de la app" in out and "(pocos datos)" in out
