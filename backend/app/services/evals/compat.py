"""Matriz de compatibilidad automatizada (fase 24.6): `cai eval compat --agent <a> [--model <m>]`.

Sobre una demo propia (`data-demo-compat-<agente>-<modelo>/`, con `cai demo seed --compat`):

1. `process-jobs` y `assess-fit` en segundo plano con ese agente y modelo (`agent_runs`, el mismo
   camino que el botón, ejecutado aquí mismo y no por el worker);
2. aprueba las 5 ofertas de la matriz y marca como «No la tengo» las obligatorias que falten (lo
   que contestaría el usuario), solo en esa demo;
3. `generate-cv` de cada una;
4. mide: campos de la extracción iguales a los esperados (`COMPARED_FIELDS`, los 11 de la 12.3),
   valoraciones guardadas, las 7 comprobaciones de `cai eval cv`, tiempo, turnos y tokens.

Con `cases=N` (`--cases N`), solo las N primeras ofertas de `jobs.txt`, en su propia demo y su
propio resultado: para comprobar con poco cupo si un agente funciona.

Guarda `evals/compat/results/<fecha>-<agente>-<modelo>.json` y regenera `evals/compat/REPORT.md`.
Si el agente no puede hacer un paso en segundo plano (no tiene, o el techo no le cabe), para ahí y
devuelve los pasos manuales; después, `--approve` (aprobar en la demo) y `--import` (medir lo que
hizo el agente) completan el resultado.

La app no llama a ningún modelo (ADR-001): lanza el agente de la persona, como los botones.
"""

import json
import re
import time
from collections import Counter
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings
from app.core.db import session_scope
from app.models import AgentRun, Event
from app.models.base import utcnow
from app.schemas.llm_io import JobExtraction
from app.services import (
    agent_launch,
    agent_registry,
    agent_runner,
    agent_runs,
    agent_usage,
    demo,
    events,
)
from app.services import skill_gaps as gaps
from app.services.agent_launch import LaunchError
from app.services.evals import cv as cv_eval
from app.services.extractions import ExtractionNotFoundError, get_extraction
from app.services.matching import service as matching
from app.services.matching.skills import alias_index, canonical
from app.services.pipeline import EventType, Stage

RESULTS_DIR = REPO_ROOT / "evals" / "compat" / "results"
REPORT_PATH = REPO_ROOT / "evals" / "compat" / "REPORT.md"
STEPS: tuple[agent_launch.ActionId, ...] = ("process-jobs", "assess-fit", "generate-cv")
COMPARED_FIELDS: tuple[str, ...] = (
    "title_normalized",
    "seniority",
    "years_experience_min",
    "remote_mode",
    "locations",
    "languages_required",
    "salary",
    "must_have_skills",
    "nice_to_have_skills",
    "domain",
    "posting_language",
)
StepMode = Literal["background", "manual", "not_run"]
RunExecutor = Callable[[float | None], Any]  # `agent_runner.run_next`


class CompatError(Exception):
    pass


class RunSummary(BaseModel):
    run_id: int
    job_id: int | None = None
    status: str
    seconds: float | None = None
    turns: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    error: str | None = None


class StepResult(BaseModel):
    action: str
    mode: StepMode
    reason: str | None = None  # por qué no fue en segundo plano
    runs: list[RunSummary] = []


class FieldScore(BaseModel):
    case: str
    job_id: int | None
    extracted: bool
    equal: int = 0
    total: int = len(COMPARED_FIELDS)
    different: list[str] = []


class CvSummary(BaseModel):
    evaluated: int
    passed: int
    checks_passed: dict[str, int]
    cases: dict[str, str]  # caso → estado


class CompatResult(BaseModel):
    created_at: datetime
    agent: str
    display_name: str
    open_source: bool
    local_models: bool | None
    model: str | None
    preset: str | None
    data_dir: str
    imported: bool  # medido con `--import` (algún paso a mano)
    steps: list[StepResult]
    extraction: list[FieldScore]
    fields_equal: int
    fields_total: int
    assessed: int
    verdicts: dict[str, int]
    cv: CvSummary
    seconds: float | None
    turns: int | None
    tokens: int | None
    cost_usd: float | None
    complete: bool  # todas extraídas, valoradas y con CV medido
    cases: int | None = None  # solo las N primeras ofertas (`--cases`); `None`, todas
    manual_steps: list[str] = []


# --- Carpeta y agente --------------------------------------------------------------------------


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "-", text.lower()).strip("-.")[:60] or "x"


def model_slug(model: str | None, preset: str | None) -> str:
    return slug(model) if model else (f"preset-{slug(preset)}" if preset else "default")


def cases_slug(cases: int | None) -> str:
    return "" if cases is None else f"-{cases}-oferta{'s' if cases > 1 else ''}"


def data_dir(agent: str, model: str | None, preset: str | None, cases: int | None = None) -> Path:
    return REPO_ROOT / (
        f"data-demo-compat-{slug(agent)}-{model_slug(model, preset)}{cases_slug(cases)}"
    )


def _check_cases(cases: int | None) -> None:
    total = len(cv_eval.load_compat_cases())
    if cases is not None and not 1 <= cases <= total:
        raise CompatError(f"--cases tiene que ir de 1 a {total}.")


def _spec(agent: str) -> agent_registry.AgentSpec:
    try:
        spec = agent_registry.get(agent)
    except agent_registry.ManifestError as exc:
        raise CompatError(str(exc)) from exc
    if spec is None:
        raise CompatError(f"No hay ningún agente «{agent[:40]}» en el manifiesto.")
    return spec


def _check_model(spec: agent_registry.AgentSpec, model: str | None, preset: str | None) -> None:
    from app.services.agent_prefs import model_problem

    if (problem := model_problem(spec, model, preset)) is not None:
        raise CompatError(problem)


# --- Pasos -------------------------------------------------------------------------------------


def _case_jobs(session: Session) -> dict[str, int]:
    """Las ofertas de la matriz que hay en la demo (todas, o las N primeras con `--cases`)."""
    found: dict[str, int] = {}
    for case in cv_eval.load_compat_cases():
        if (job := cv_eval._case_job(session, case.id)) is not None:
            found[case.id] = job.id
    return found


def _summary(row: AgentRun) -> RunSummary:
    usage = agent_usage.normalize_usage(row.usage)  # también las filas de antes de la 25.4
    seconds = (
        (row.finished_at - row.started_at).total_seconds()
        if row.finished_at and row.started_at
        else None
    )

    def number(key: str) -> Any:
        value = usage.get(key)
        return value if isinstance(value, int | float) and not isinstance(value, bool) else None

    return RunSummary(
        run_id=row.id,
        job_id=row.job_id,
        status=row.status,
        seconds=round(seconds, 1) if seconds is not None else None,
        turns=number("turns"),
        input_tokens=number("input_tokens"),
        output_tokens=number("output_tokens"),
        cost_usd=number("cost_usd"),
        error=(row.error or "")[:300] or None,
    )


def _blocked(
    action: agent_launch.ActionId, agent: str, model: str | None, preset: str | None
) -> str | None:
    """Por qué el agente no puede hacer el paso en segundo plano (o `None`)."""
    try:
        with session_scope() as session:
            _, res = agent_launch.choose(
                session, action, agent=agent, model=model, preset=preset, mode="background"
            )
    except (LaunchError, agent_registry.ManifestError) as exc:
        return str(exc)
    return res.blocked


def _run(
    action: agent_launch.ActionId,
    job_id: int | None,
    agent: str,
    model: str | None,
    preset: str | None,
    execute: RunExecutor,
    timeout: float | None,
) -> RunSummary:
    with session_scope() as session:
        # La matriz mide todas sus ofertas: sin el umbral de score de la fase 25.4.
        run_id = agent_runs.start(
            session, action, job_id, agent=agent, model=model, preset=preset, min_score=0
        ).id
    execute(timeout)
    with session_scope() as session:
        row = session.get(AgentRun, run_id)
        assert row is not None
        if row.status in agent_runs.ACTIVE:  # el ejecutor no la tomó: no se deja en cola
            agent_runs.cancel(session, run_id)
            session.refresh(row)
        return _summary(row)


def approve(target: Path) -> list[str]:
    """Aprueba las ofertas de la matriz que están por revisar y marca como «No la tengo» las
    obligatorias que falten (lo que contestaría el usuario a `generate-cv`). Solo en una demo."""
    if not demo.is_demo_dir(target):
        raise CompatError(f"«{target.name}» no es una demo: no se aprueba nada fuera de ellas.")
    notes: list[str] = []
    with demo.use_data_dir(target, embeddings=False), session_scope() as session:
        if not get_settings().demo_mode:
            raise CompatError("La carpeta no está en modo demo.")
        for case, job_id in _case_jobs(session).items():
            stage = events.current_stage(session, job_id)
            if stage == Stage.PENDING_TRIAGE:
                events.add_user_event(session, job_id, EventType.APPROVED)
            elif stage not in (Stage.APPROVED, Stage.CV_READY):
                notes.append(f"{case}: en «{stage}», no se puede aprobar")
                continue
            for skill in matching.get_match(session, job_id).breakdown.must_have.missing:
                gaps.set_mark(session, skill, "gap")
    return notes


def manual_steps(
    agent: str,
    model: str | None,
    preset: str | None,
    target: Path,
    from_step: int,
    cases: int | None = None,
) -> list[str]:
    """Lo que tiene que hacer el usuario desde el paso `from_step` (0, 1 o 2)."""
    spec = _spec(agent)
    invoke = spec.info.invoke or "{skill} {args}"
    command = f"uv run --directory backend cai eval compat --agent {agent}"
    if model:
        command += f" --model {model}"
    elif preset:
        command += f" --preset {preset}"
    if cases is not None:
        command += f" --cases {cases}"
    with demo.use_data_dir(target, embeddings=False), session_scope() as session:
        ids = " ".join(str(j) for j in _case_jobs(session).values())
    lines = [
        f'En otra terminal, en la raíz del repo: $env:CAI_DATA_DIR = "{target.name}" y abre '
        f"{spec.info.display_name}"
        + (f" con el modelo {model or preset}" if model or preset else "")
        + ". Comprueba con get_status que dice demo_mode: true.",
    ]
    if invoke == "natural":  # sin sintaxis propia: se le pide el skill con una frase
        invoke = "«usa el skill {skill}{args}»"
        ids = f" con las ofertas {ids}" if ids else ""
    skill = {s: invoke.replace("{skill}", s) for s in STEPS}
    if from_step <= 0:
        lines.append(f"Procesa las ofertas: {skill['process-jobs'].replace('{args}', '').strip()}")
    if from_step <= 1:
        lines.append(f"Valora el encaje: {skill['assess-fit'].replace('{args}', '').strip()}")
        lines.append(f"Aprueba las ofertas de la matriz: {command} --approve")
    lines.append(
        f"Genera los CVs: {skill['generate-cv'].replace('{args}', ids).strip()} (si pregunta por "
        "skills que faltan, contesta que no las tienes)."
    )
    lines.append(f"Mide y guarda el resultado: {command} --import")
    return lines


# --- Medir -------------------------------------------------------------------------------------


def _norm(field: str, value: Any, index: dict[str, str]) -> Any:
    if field in ("must_have_skills", "nice_to_have_skills"):
        return sorted({canonical(v, index) for v in value or []})
    if field == "locations":
        return sorted({str(v).casefold().strip() for v in value or []})
    if field == "languages_required":
        return sorted(
            (str(item.get("language", "")).casefold(), str(item.get("level") or "").upper())
            for item in value or []
        )
    if isinstance(value, str):
        return value.casefold().strip()
    return value


def compare_extraction(expected: JobExtraction, got: JobExtraction) -> tuple[int, list[str]]:
    index = alias_index()
    exp, found = expected.model_dump(mode="json"), got.model_dump(mode="json")
    different = [
        field
        for field in COMPARED_FIELDS
        if _norm(field, exp.get(field), index) != _norm(field, found.get(field), index)
    ]
    return len(COMPARED_FIELDS) - len(different), different


def _verdict(session: Session, job_id: int) -> str | None:
    row = session.scalars(
        select(Event)
        .where(Event.job_id == job_id, Event.type == EventType.FIT_ASSESSED)
        .order_by(Event.id.desc())
        .limit(1)
    ).first()
    return str(row.payload.get("verdict")) if row and row.payload else None


def measure(
    target: Path,
    agent: str,
    model: str | None,
    preset: str | None,
    steps: list[StepResult],
    imported: bool,
    cases: int | None = None,
) -> CompatResult:
    spec = _spec(agent)
    expected = {c.id: c for c in cv_eval.load_compat_cases()}
    with demo.use_data_dir(target, embeddings=False), session_scope() as session:
        jobs = _case_jobs(session)
        scores: list[FieldScore] = []
        verdicts: Counter[str] = Counter()
        for case_id, job_id in jobs.items():
            try:
                got = get_extraction(session, job_id)
            except ExtractionNotFoundError:
                scores.append(FieldScore(case=case_id, job_id=job_id, extracted=False))
            else:
                equal, different = compare_extraction(expected[case_id].extraction, got.extraction)
                scores.append(
                    FieldScore(
                        case=case_id,
                        job_id=job_id,
                        extracted=True,
                        equal=equal,
                        different=different,
                    )
                )
            if (verdict := _verdict(session, job_id)) is not None:
                verdicts[verdict] += 1
        report = cv_eval.evaluate(session, cases=[expected[c] for c in jobs])
        if imported:  # lo que hizo a mano: las ejecuciones en segundo plano que haya
            rows = session.scalars(select(AgentRun).order_by(AgentRun.id)).all()
            known = {r.run_id for s in steps for r in s.runs}
            for row in rows:
                step = next((s for s in steps if s.action == row.action), None)
                if step is not None and row.id not in known:
                    step.runs.append(_summary(row))
    runs = [r for s in steps for r in s.runs]

    def total(key: str) -> Any:
        values = [getattr(r, key) for r in runs if getattr(r, key) is not None]
        return sum(values) if values else None

    tokens = [
        (r.input_tokens or 0) + (r.output_tokens or 0)
        for r in runs
        if r.input_tokens is not None or r.output_tokens is not None
    ]
    seconds = total("seconds")
    return CompatResult(
        created_at=utcnow(),
        agent=agent,
        display_name=spec.info.display_name,
        open_source=spec.info.open_source,
        local_models=spec.capabilities.local_models,
        model=model,
        preset=preset,
        data_dir=target.name,
        imported=imported,
        steps=steps,
        extraction=scores,
        fields_equal=sum(s.equal for s in scores),
        fields_total=len(scores) * len(COMPARED_FIELDS),
        assessed=sum(verdicts.values()),
        verdicts=dict(sorted(verdicts.items())),
        cv=CvSummary(
            evaluated=report.evaluated,
            passed=report.passed,
            checks_passed=dict(report.checks_passed),
            cases={c.id: c.status for c in report.cases},
        ),
        seconds=round(seconds, 1) if seconds is not None else None,
        turns=total("turns"),
        tokens=sum(tokens) if tokens else None,
        cost_usd=total("cost_usd"),
        complete=bool(scores)
        and all(s.extracted for s in scores)
        and sum(verdicts.values()) >= len(scores)
        and report.evaluated == len(scores),
        cases=cases,
    )


# --- Ejecutar ----------------------------------------------------------------------------------


def run(
    agent: str,
    model: str | None = None,
    preset: str | None = None,
    *,
    target: Path | None = None,
    execute: RunExecutor | None = None,
    timeout: float | None = None,
    progress: Callable[[str], None] = lambda _msg: None,
    cases: int | None = None,
) -> CompatResult:
    """Recorre la matriz con el agente. `execute`: quien ejecuta la ejecución en cola (por
    defecto, `agent_runner.run_next`); `timeout`: segundos por ejecución (si no, la política);
    `cases`: solo las N primeras ofertas."""
    spec = _spec(agent)
    _check_model(spec, model, preset)
    _check_cases(cases)
    execute = execute or agent_runner.run_next
    target = target or data_dir(agent, model, preset, cases)
    progress(f"Demo nueva en {target.name}…")
    try:
        demo.seed(target, force=True, compat=True, compat_cases=cases)
    except demo.DemoSeedError as exc:
        raise CompatError(str(exc)) from exc
    steps: list[StepResult] = []
    manual: list[str] = []
    with demo.use_data_dir(target, embeddings=False):
        for index, action in enumerate(STEPS):
            if index == 2:
                notes = approve(target)
                progress(
                    "Aprobadas las ofertas de la matriz."
                    + (f" ({'; '.join(notes)})" if notes else "")
                )
            reason = _blocked(action, agent, model, preset)
            if reason is not None:
                steps.append(StepResult(action=action, mode="manual", reason=reason))
                steps += [StepResult(action=a, mode="not_run") for a in STEPS[index + 1 :]]
                manual = manual_steps(agent, model, preset, target, index, cases)
                break
            step = StepResult(action=action, mode="background")
            steps.append(step)
            if action == "generate-cv":
                with session_scope() as session:
                    job_ids = list(_case_jobs(session).values())
            else:
                job_ids = [None]  # type: ignore[list-item]
            for job_id in job_ids:
                progress(
                    f"{action}{f' (oferta {job_id})' if job_id else ''} con "
                    f"{spec.info.display_name}…"
                )
                started = time.monotonic()
                try:
                    summary = _run(action, job_id, agent, model, preset, execute, timeout)
                except LaunchError as exc:
                    summary = RunSummary(run_id=0, job_id=job_id, status="failed", error=str(exc))
                step.runs.append(summary)
                progress(f"  {summary.status} en {time.monotonic() - started:.0f} s")
    result = measure(target, agent, model, preset, steps, imported=False, cases=cases)
    result.manual_steps = manual
    return result


def import_results(
    agent: str,
    model: str | None = None,
    preset: str | None = None,
    *,
    target: Path | None = None,
    cases: int | None = None,
) -> CompatResult:
    """Mide una demo de la matriz en la que el agente trabajó a mano."""
    spec = _spec(agent)
    _check_model(spec, model, preset)
    _check_cases(cases)
    target = target or data_dir(agent, model, preset, cases)
    if not demo.is_demo_dir(target) or not (target / "candidatai.db").is_file():
        raise CompatError(
            f"No hay una demo de la matriz en «{target.name}»: lanza antes "
            f"`cai eval compat --agent {agent}` (o `cai demo seed --dir {target.name} --compat`)."
        )
    steps = [StepResult(action=a, mode="manual") for a in STEPS]
    return measure(target, agent, model, preset, steps, imported=True, cases=cases)


# --- Guardar e informe -------------------------------------------------------------------------


def save(
    result: CompatResult, results_dir: Path | None = None, report_path: Path | None = None
) -> Path:
    results_dir = results_dir or RESULTS_DIR
    report_path = report_path or REPORT_PATH
    results_dir.mkdir(parents=True, exist_ok=True)
    model = model_slug(result.model, result.preset) + cases_slug(result.cases)
    name = f"{result.created_at:%Y-%m-%d}-{slug(result.agent)}-{model}.json"
    path = results_dir / name
    path.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    report_path.write_text(to_markdown(load_results(results_dir)), encoding="utf-8")
    return path


def load_results(results_dir: Path | None = None) -> list[CompatResult]:
    results_dir = results_dir or RESULTS_DIR
    found = []
    for path in sorted(results_dir.glob("*.json")) if results_dir.is_dir() else []:
        try:
            found.append(CompatResult.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        except ValueError:
            continue  # un fichero roto no tumba el informe
    return found


def _label(result: CompatResult) -> str:
    model = result.model or (f"preset {result.preset}" if result.preset else "modelo por defecto")
    cases = "" if result.cases is None else f" · {result.cases} oferta{'s' * (result.cases > 1)}"
    return f"{result.display_name} · {model}{cases}"


def _cell(value: Any, suffix: str = "") -> str:
    return "—" if value is None else f"{value}{suffix}"


def to_markdown(results: list[CompatResult]) -> str:
    lines = [
        "# Matriz de compatibilidad",
        "",
        "Generado por `cai eval compat` (fase 24.6): las 5 ofertas de `evals/compat/jobs.txt` con",
        "`process-jobs`, `assess-fit` y `generate-cv`, medidas igual para todos. Un resultado por",
        "agente y modelo en `evals/compat/results/`. No lo edites a mano: se regenera.",
        "Las columnas «· N oferta(s)» son pasadas cortas (`--cases N`): solo las N primeras.",
        "Los tokens no cuentan los leídos de la caché, que cada agente informa a su manera.",
        "",
    ]
    if not results:
        return "\n".join([*lines, "Todavía no hay resultados.", ""])
    latest: dict[tuple[str, str], CompatResult] = {}
    for result in sorted(results, key=lambda r: r.created_at):
        key = model_slug(result.model, result.preset) + cases_slug(result.cases)
        latest[(result.agent, key)] = result
    shown = list(latest.values())
    header = ["", *(_label(r) for r in shown)]
    lines += ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]

    def row(title: str, cells: list[str]) -> None:
        lines.append(f"| {title} | " + " | ".join(cells) + " |")

    row("Fecha", [f"{r.created_at:%Y-%m-%d}" for r in shown])
    row("Open-source", ["sí" if r.open_source else "no" for r in shown])
    row(
        "Cómo",
        [
            "a mano (`--import`)"
            if r.imported
            else ", ".join(
                f"{s.action}: {'2.º plano' if s.mode == 'background' else s.mode}" for s in r.steps
            )
            for r in shown
        ],
    )
    row("Extracción (campos iguales)", [f"{r.fields_equal}/{r.fields_total}" for r in shown])
    row(
        "Valoraciones",
        [f"{r.assessed}/{len(r.extraction)} {dict(r.verdicts) or ''}".strip() for r in shown],
    )
    row(
        "CVs que pasan `eval cv`",
        [f"{r.cv.passed}/{r.cv.evaluated} de {len(r.extraction)}" for r in shown],
    )
    for name, label in cv_eval.CHECKS.items():
        row(f"· {label}", [str(r.cv.checks_passed.get(name, 0)) for r in shown])
    row("Tiempo", [_cell(r.seconds and round(r.seconds / 60, 1), " min") for r in shown])
    row("Turnos", [_cell(r.turns) for r in shown])
    row("Tokens (entrada + salida)", [_cell(r.tokens) for r in shown])
    row("Completa", ["sí" if r.complete else "no" for r in shown])
    differences = [
        f"- {_label(r)} · `{s.case}`: {', '.join(s.different)}"
        for r in shown
        for s in r.extraction
        if s.different
    ]
    if differences:
        lines += ["", "## Campos de la extracción distintos", "", *differences]
    failures = [
        f"- {_label(r)} · {s.action}: {run.status}" + (f" ({run.error})" if run.error else "")
        for r in shown
        for s in r.steps
        for run in s.runs
        if run.status != "done"
    ]
    if failures:
        lines += ["", "## Ejecuciones que no terminaron bien", "", *failures]
    return "\n".join(lines) + "\n"
