"""Set de evaluación del matching y `jh eval matching`."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app import cli
from app.core.config import get_settings
from app.core.policies import get_policies
from app.services import profile
from app.services.matching import evaluation
from app.services.matching.evaluation import EvalCase, EvalFileError, Source, load_cases, metrics
from tests.matching_support import FakeEmbedder, demo_extraction_data, demo_profile

runner = CliRunner()


def case_line(id: str, label: str = "encaja", **changes: object) -> str:
    extraction = {**demo_extraction_data("01-data-engineer"), **changes}
    fixture = {"title": "Data Engineer", "extraction": extraction}
    return json.dumps({"id": id, "job_fixture": fixture, "label": label}, ensure_ascii=False)


def write_user_cases(*lines: str, name: str = "mis-casos.jsonl") -> Path:
    evals_dir = get_settings().evals_dir
    evals_dir.mkdir(parents=True, exist_ok=True)
    path = evals_dir / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --- Semilla -------------------------------------------------------------------------------------


# Los errores con la configuración por defecto, explicados en evals/REPORT.md. Si cambia el
# scoring o los filtros y esta lista cambia, actualiza también el informe.
SEED_ERRORS = [
    "sales-engineer-data",
    "de-ourense-hybrid",
    "de-pontevedra-hybrid",
    "de-5-years",
    "ml-engineer-tabular",
    "profesor-sql",
    "preventa-datos",
]


def test_seed_has_eighty_balanced_cases() -> None:
    cases = load_cases(evaluation.SEED_DIR / "seed.jsonl")
    assert len(cases) == 80
    assert sum(c.label == "encaja" for c in cases) == 40
    assert len({c.id for c in cases}) == 80


def test_seed_results_with_demo_profile() -> None:
    report = evaluation.run(use_embeddings=False)
    assert len(report.cases) == 80
    assert report.embeddings_model is None
    assert report.sources == [
        Source(path="evals/matching/seed.jsonl", profile="perfil de demo", cases=80)
    ]
    m = report.metrics
    assert (m.tp, m.fp, m.fn, m.tn) == (38, 5, 2, 35)  # las cifras de evals/REPORT.md
    wrong = [c.id for c in report.cases if c.label != c.predicted]
    assert wrong == SEED_ERRORS
    assert report.notes == ["Evaluación sin similitud semántica (--no-embeddings)."]


def test_seed_discard_keyword_fixes_the_trap(monkeypatch: pytest.MonkeyPatch) -> None:
    policies = get_policies()
    fixed = policies.model_copy(
        update={
            "hard_filters": policies.hard_filters.model_copy(
                update={"discard_title_keywords": ["sales", "preventa", "formador"]}
            )
        }
    )
    batches = [
        (
            Source(path="seed", profile="demo", cases=80),
            demo_profile(),
            load_cases(evaluation.SEED_DIR / "seed.jsonl"),
        )
    ]
    report = evaluation.evaluate(batches, fixed, None)
    wrong = [c.id for c in report.cases if c.label != c.predicted]
    assert wrong == [
        c for c in SEED_ERRORS if c not in ("sales-engineer-data", "preventa-datos", "profesor-sql")
    ]


def test_curve_covers_every_threshold() -> None:
    report = evaluation.run(use_embeddings=False)
    assert [p.threshold for p in report.curve] == list(range(0, 101, 5))
    current = next(p for p in report.curve if p.threshold == report.threshold)
    assert current.metrics == report.metrics
    # Umbral 0: encaja todo lo que pasa los filtros (los dos de ubicación se pierden igual).
    assert report.curve[0].metrics.fn == 2


def test_semantic_notes_when_embeddings_missing() -> None:
    report = evaluation.run()
    assert report.notes == ["Similitud semántica desactivada (JH_EMBEDDINGS=off)."]


def test_with_fake_embedder() -> None:
    batches = [
        (
            Source(path="seed", profile="demo", cases=80),
            demo_profile(),
            load_cases(evaluation.SEED_DIR / "seed.jsonl"),
        )
    ]
    report = evaluation.evaluate(batches, get_policies(), FakeEmbedder())
    assert report.embeddings_model == "fake-bow"
    assert report.notes == []


# --- Métricas ------------------------------------------------------------------------------------


def test_metrics() -> None:
    pairs = [
        ("encaja", "encaja"),
        ("encaja", "no_encaja"),
        ("no_encaja", "encaja"),
        ("no_encaja", "no_encaja"),
        ("encaja", "encaja"),
    ]
    m = metrics(pairs)  # type: ignore[arg-type]
    assert (m.tp, m.fp, m.fn, m.tn) == (2, 1, 1, 1)
    assert (m.precision, m.recall, m.f1) == (0.6667, 0.6667, 0.6667)


def test_metrics_edge_cases() -> None:
    none_predicted = metrics([("encaja", "no_encaja")])
    assert (none_predicted.precision, none_predicted.recall, none_predicted.f1) == (None, 0.0, None)
    all_wrong = metrics([("encaja", "no_encaja"), ("no_encaja", "encaja")])
    assert (all_wrong.precision, all_wrong.recall, all_wrong.f1) == (0.0, 0.0, 0.0)
    no_positives = metrics([("no_encaja", "no_encaja")])
    assert (no_positives.precision, no_positives.recall) == (None, None)


# --- Casos propios -------------------------------------------------------------------------------


def test_user_cases_use_own_profile(tmp_path: Path) -> None:
    write_user_cases(case_line("mia-1"), "# comentario", "", case_line("mia-2", "no_encaja"))
    profile.init_profile()
    report = evaluation.run(include_seed=False, use_embeddings=False)
    assert [c.id for c in report.cases] == ["mia-1", "mia-2"]
    assert report.sources[0].profile.endswith("profile.yaml")
    assert report.cases[0].source.endswith("mis-casos.jsonl")


def test_user_cases_without_profile_are_skipped() -> None:
    write_user_cases(case_line("mia-1"))
    report = evaluation.run(use_embeddings=False)
    assert len(report.cases) == 80
    assert report.notes[0].startswith("Hay casos en data/evals/ pero no existe")


def test_no_cases_at_all() -> None:
    with pytest.raises(EvalFileError, match="No hay casos"):
        evaluation.run(include_seed=False)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("{no es json", "mis-casos.jsonl, línea 1: JSON no válido"),
        ('{"id": "x", "label": "encaja"}', "línea 1: job_fixture: Campo obligatorio."),
        (case_line("x", label="quizá"), "línea 1: label: Debe ser uno de: encaja, no_encaja."),
        (case_line("x") + "\n" + case_line("x"), "línea 2: id repetido «x»."),
    ],
)
def test_invalid_case_files(content: str, message: str) -> None:
    path = write_user_cases(content)
    with pytest.raises(EvalFileError, match=message):
        load_cases(path)


def test_case_model_is_strict() -> None:
    with pytest.raises(ValueError):
        EvalCase.model_validate(
            {"id": "x", "job_fixture": {"title": "T", "extraction": {}}, "label": "encaja", "x": 1}
        )


# --- Informe y CLI -------------------------------------------------------------------------------


def test_report_is_saved_as_json_and_markdown(tmp_path: Path) -> None:
    report = evaluation.run(use_embeddings=False)
    json_path, md_path = evaluation.save_report(report, tmp_path / "reports")
    assert json.loads(json_path.read_text(encoding="utf-8"))["metrics"]["recall"] == 0.95
    markdown = md_path.read_text(encoding="utf-8")
    assert "| 55 | 0.88 | 0.95 | 0.92 |" in markdown
    assert "`sales-engineer-data`" in markdown
    assert "Modelo semántico: sin embeddings" in markdown


def test_markdown_without_errors() -> None:
    report = evaluation.run(use_embeddings=False)
    report.cases = [c for c in report.cases if c.label == c.predicted]
    assert "## Errores con el umbral actual\n\nNinguno." in evaluation.to_markdown(report)


def test_cli_eval_matching_text() -> None:
    result = runner.invoke(cli.app, ["eval", "matching", "--no-embeddings"])
    assert result.exit_code == 0, result.output
    assert "Matching · 80 casos · umbral 55 · sin embeddings" in result.stdout
    assert "    55       0.88    0.95   0.92  <- actual" in result.stdout
    assert "sales-engineer-data: etiqueta no_encaja, predice encaja" in result.stdout
    reports = list((get_settings().evals_dir / "reports").glob("matching-*"))
    assert sorted(p.suffix for p in reports) == [".json", ".md"]


def test_cli_eval_matching_json() -> None:
    result = runner.invoke(cli.app, ["eval", "matching", "--json", "--no-embeddings"])
    out = json.loads(result.stdout)
    assert out["metrics"]["f1"] == 0.9157
    assert len(out["report_paths"]) == 2


def test_cli_eval_matching_bad_file() -> None:
    write_user_cases("{roto")
    profile.init_profile()
    result = runner.invoke(cli.app, ["eval", "matching", "--json"])
    assert result.exit_code == 1
    assert "JSON no válido" in json.loads(result.stdout)["error"]["message"]


def test_cli_eval_matching_with_profile_option(tmp_path: Path) -> None:
    write_user_cases(case_line("mia-1"))
    result = runner.invoke(
        cli.app,
        ["eval", "matching", "--no-seed", "--profile", "demo/profile.example.yaml", "--json"],
    )
    assert result.exit_code == 0, result.output
    out = json.loads(result.stdout)
    assert [c["id"] for c in out["cases"]] == ["mia-1"]
    assert out["sources"][0]["profile"] == "demo/profile.example.yaml"
