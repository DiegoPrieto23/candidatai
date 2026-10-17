"""Evaluación del matching: precision, recall y F1 frente a casos etiquetados a mano.

Casos en JSONL, uno por línea: `{"id", "job_fixture": {"title", "extraction"}, "label", "note"?}`
con `label` ∈ {`encaja`, `no_encaja`}. La semilla (`evals/matching/*.jsonl`, casos inventados) se
evalúa contra el perfil de `demo/`; los casos propios (`data/evals/*.jsonl`) contra tu perfil.
La app predice «encaja» si la oferta pasa los filtros duros y su score llega al umbral de triaje.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import REPO_ROOT
from app.core.policies import Policies
from app.core.validation import describe_error
from app.models.base import utcnow
from app.schemas.llm_io import JobExtraction
from app.schemas.profile import CandidateProfile
from app.services.matching import hard_filters, scorer
from app.services.matching.embeddings import Embedder

SEED_DIR = REPO_ROOT / "evals" / "matching"
CURVE_STEP = 5

Label = Literal["encaja", "no_encaja"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JobFixture(_Strict):
    title: str = Field(min_length=1)  # el título tal cual (los filtros de palabras lo miran)
    extraction: JobExtraction


class EvalCase(_Strict):
    id: str = Field(min_length=1)
    job_fixture: JobFixture
    label: Label
    note: str | None = None


class EvalFileError(ValueError):
    """Un fichero de casos no es válido; el mensaje dice la línea y el campo."""


class CaseResult(BaseModel):
    id: str
    source: str
    label: Label
    predicted: Label
    score: int
    passed_filters: bool
    failures: list[str]  # motivos de los filtros duros


class Metrics(BaseModel):
    tp: int
    fp: int
    fn: int
    tn: int
    precision: float | None  # None si no se predice ningún «encaja»
    recall: float | None  # None si no hay ningún «encaja» etiquetado
    f1: float | None


class CurvePoint(BaseModel):
    threshold: int
    metrics: Metrics


class Source(BaseModel):
    path: str
    profile: str
    cases: int


class EvalReport(BaseModel):
    created_at: datetime
    threshold: int
    embeddings_model: str | None  # None: score sin similitud semántica
    sources: list[Source]
    metrics: Metrics
    curve: list[CurvePoint]
    cases: list[CaseResult]
    notes: list[str]


def load_cases(path: Path) -> list[EvalCase]:
    """Lee un JSONL de casos. Las líneas vacías y las que empiezan por `#` se ignoran."""
    cases: list[EvalCase] = []
    ids: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        where = f"{path.name}, línea {number}"
        try:
            case = EvalCase.model_validate(json.loads(line))
        except json.JSONDecodeError as exc:
            raise EvalFileError(f"{where}: JSON no válido ({exc.msg}).") from exc
        except ValidationError as exc:
            error = exc.errors(include_url=False)[0]
            field = ".".join(str(p) for p in error["loc"]) or "(caso)"
            _, reason = describe_error(error)
            raise EvalFileError(f"{where}: {field}: {reason}") from exc
        if case.id in ids:
            raise EvalFileError(f"{where}: id repetido «{case.id}».")
        ids.add(case.id)
        cases.append(case)
    return cases


def _predict(passed: bool, score: int, threshold: int) -> Label:
    return "encaja" if passed and score >= threshold else "no_encaja"


def metrics(pairs: list[tuple[Label, Label]]) -> Metrics:
    """`pairs`: (etiqueta, predicción)."""
    tp = sum(1 for label, pred in pairs if label == pred == "encaja")
    fp = sum(1 for label, pred in pairs if label == "no_encaja" and pred == "encaja")
    fn = sum(1 for label, pred in pairs if label == "encaja" and pred == "no_encaja")
    tn = len(pairs) - tp - fp - fn
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else (0.0 if precision is not None and recall is not None else None)
    )
    rounded = [None if v is None else round(v, 4) for v in (precision, recall, f1)]
    return Metrics(
        tp=tp, fp=fp, fn=fn, tn=tn, precision=rounded[0], recall=rounded[1], f1=rounded[2]
    )


def evaluate(
    batches: list[tuple[Source, CandidateProfile, list[EvalCase]]],
    policies: Policies,
    embedder: Embedder | None,
    notes: list[str] | None = None,
    semantic_notes: bool = True,
) -> EvalReport:
    """Puntúa todos los casos y calcula las métricas con el umbral actual y la curva por umbral.

    `semantic_notes`: recoger los avisos de similitud semántica del scorer (p. ej. «instala el
    extra»); no tiene sentido si se ha desactivado a propósito.
    """
    threshold = policies.scoring.triage_threshold
    results: list[CaseResult] = []
    notes = list(notes or [])
    for source, profile, cases in batches:
        for case in cases:
            fixture = case.job_fixture
            # Sin `company`: los casos del eval no tienen empresa, así que `exclude_signals` solo
            # mira la extracción (no los patrones del nombre).
            filters = hard_filters.evaluate(
                fixture.title, fixture.extraction, profile, policies.hard_filters
            )
            result = scorer.score(
                fixture.title, fixture.extraction, profile, policies.scoring, embedder
            )
            for note in result.breakdown.notes:
                if semantic_notes and "semántica" in note and note not in notes:
                    notes.append(note)
            results.append(
                CaseResult(
                    id=case.id,
                    source=source.path,
                    label=case.label,
                    predicted=_predict(filters.passed, result.score, threshold),
                    score=result.score,
                    passed_filters=filters.passed,
                    failures=[f.reason for f in filters.failures],
                )
            )
    curve = [
        CurvePoint(
            threshold=t,
            metrics=metrics([(r.label, _predict(r.passed_filters, r.score, t)) for r in results]),
        )
        for t in range(0, 101, CURVE_STEP)
    ]
    return EvalReport(
        created_at=utcnow(),
        threshold=threshold,
        embeddings_model=embedder.model_name if embedder else None,
        sources=[source for source, _, _ in batches],
        metrics=metrics([(r.label, r.predicted) for r in results]),
        curve=curve,
        cases=results,
        notes=notes,
    )


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def to_markdown(report: EvalReport) -> str:
    m = report.metrics
    model = report.embeddings_model or "sin embeddings"
    lines = [
        "# Evaluación del matching",
        "",
        f"- Fecha: {report.created_at:%Y-%m-%d %H:%M} UTC",
        f"- Umbral de triaje: {report.threshold}",
        f"- Modelo semántico: {model}",
        *(f"- Casos: {s.cases} de `{s.path}` contra {s.profile}" for s in report.sources),
        "",
        "## Con el umbral actual",
        "",
        "| Precision | Recall | F1 | VP | FP | FN | VN |",
        "|---|---|---|---|---|---|---|",
        f"| {_fmt(m.precision)} | {_fmt(m.recall)} | {_fmt(m.f1)} | {m.tp} | {m.fp} | {m.fn} "
        f"| {m.tn} |",
        "",
        "## Curva por umbral",
        "",
        "| Umbral | Precision | Recall | F1 |",
        "|---|---|---|---|",
        *(
            f"| {p.threshold} | {_fmt(p.metrics.precision)} | {_fmt(p.metrics.recall)} "
            f"| {_fmt(p.metrics.f1)} |"
            for p in report.curve
        ),
        "",
        "## Errores con el umbral actual",
        "",
    ]
    wrong = [c for c in report.cases if c.label != c.predicted]
    if not wrong:
        lines.append("Ninguno.")
    for case in wrong:
        why = "; ".join(case.failures) if case.failures else f"score {case.score}"
        lines.append(f"- `{case.id}` ({case.source}): etiqueta {case.label}, predice "
                     f"{case.predicted} — {why}")  # fmt: skip
    if report.notes:
        lines += ["", "## Notas", "", *(f"- {n}" for n in report.notes)]
    return "\n".join(lines) + "\n"


def save_report(report: EvalReport, reports_dir: Path) -> tuple[Path, Path]:
    """Guarda el informe en JSON y en Markdown. Devuelve las dos rutas."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    stem = f"matching-{report.created_at:%Y%m%d-%H%M%S}"
    json_path, md_path = reports_dir / f"{stem}.json", reports_dir / f"{stem}.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    md_path.write_text(to_markdown(report), encoding="utf-8")
    return json_path, md_path


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def run(
    include_seed: bool = True,
    profile_path: Path | None = None,
    use_embeddings: bool = True,
) -> EvalReport:
    """Evalúa la semilla (contra el perfil de demo) y `data/evals/*.jsonl` (contra tu perfil)."""
    from app.core.config import get_settings
    from app.core.policies import get_policies
    from app.services import profile as profiles
    from app.services.matching import embeddings

    batches: list[tuple[Source, CandidateProfile, list[EvalCase]]] = []
    notes: list[str] = []
    if include_seed:
        demo = profiles.load_from_yaml(profiles.EXAMPLE_PATH)
        for path in sorted(SEED_DIR.glob("*.jsonl")):
            cases = load_cases(path)
            batches.append(
                (
                    Source(path=_relative(path), profile="perfil de demo", cases=len(cases)),
                    demo,
                    cases,
                )
            )
    user_files = sorted(get_settings().evals_dir.glob("*.jsonl"))
    if user_files:
        path = profile_path or profiles.default_path()
        if path.is_file():
            own = profiles.load_from_yaml(path)
            for file in user_files:
                cases = load_cases(file)
                source = Source(path=_relative(file), profile=_relative(path), cases=len(cases))
                batches.append((source, own, cases))
        else:
            notes.append(f"Hay casos en data/evals/ pero no existe {path}: no se han evaluado.")
    if not any(cases for _, _, cases in batches):
        raise EvalFileError("No hay casos que evaluar (ni semilla ni data/evals/*.jsonl).")
    embedder = embeddings.get_embedder() if use_embeddings else None
    if not use_embeddings:
        notes.append("Evaluación sin similitud semántica (--no-embeddings).")
    return evaluate(batches, get_policies(), embedder, notes, semantic_notes=use_embeddings)
