"""El agente de las E2E, simulado: guarda lo que guardaría el agente de verdad con los comandos
`cai … --json`, que tienen la misma entrada y salida que las herramientas MCP (`save_extraction`,
`save_fit_assessment`, `save_cv_content`…). Y lecturas de la API para encontrar lo que la UI creó.
"""

import json
from typing import Any

import httpx
import yaml

from app.core.config import REPO_ROOT
from tests.e2e.harness import AppServer, run_cai
from tests.e2e.sites import FIXTURES

DEMO_SEED = REPO_ROOT / "demo" / "seed"


def api(server: AppServer, path: str, **params: Any) -> Any:
    response = httpx.get(f"{server.url}{path}", params=params, timeout=15, trust_env=False)
    response.raise_for_status()
    return response.json()


def find_job(server: AppServer, query: str) -> dict[str, Any]:
    body = api(server, "/jobs", q=query, limit=5)
    items: list[dict[str, Any]] = body["items"] if isinstance(body, dict) else body
    assert len(items) == 1, f"«{query}»: {len(items)} ofertas"
    return items[0]


def cai(server: AppServer, *args: str, payload: Any = None) -> dict[str, Any]:
    """`cai <args> [--file F] --json`; la entrada larga va en `data/tmp/`, como pide la CLI."""
    extra: list[str] = []
    if payload is not None:
        tmp = server.data_dir / "tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        path = tmp / f"e2e-{'-'.join(a for a in args if a.isalnum())}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        extra = ["--file", str(path)]
    result = run_cai(server.data_dir, *args, *extra, "--json")
    assert result.returncode == 0, f"cai {' '.join(args)}:\n{result.stdout}\n{result.stderr}"
    out: dict[str, Any] = json.loads(result.stdout)
    return out


def demo_cv_content() -> dict[str, Any]:
    """El contenido del primer CV de la demo: cita solo ids del perfil de ejemplo."""
    cvs = yaml.safe_load((DEMO_SEED / "cvs.yaml").read_text(encoding="utf-8"))
    content: dict[str, Any] = cvs[0]["content"]
    return content


def demo_extras() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load((DEMO_SEED / "extras.yaml").read_text(encoding="utf-8"))
    return data


def extraction(**changes: Any) -> dict[str, Any]:
    """Una extracción como la del rol `extractor` para la oferta de las E2E."""
    data: dict[str, Any] = {
        "title_normalized": "Analytics Engineer",
        "seniority": "mid",
        "years_experience_min": 2,
        "employment_type": "full_time",
        "remote_mode": "hybrid",
        "locations": ["A Coruña"],
        "languages_required": [{"language": "English", "level": "B2"}],
        "salary": {"min": 38000, "max": 44000, "currency": "EUR", "period": "year"},
        "must_have_skills": ["SQL", "dbt", "Snowflake", "Python"],
        "nice_to_have_skills": ["Power BI", "Docker"],
        "responsibilities": ["Modelar los datos de producto con dbt sobre Snowflake"],
        "domain": None,
        "posting_language": "es",
        "application_deadline": None,
        "red_flags": [],
        "injection_suspected": False,
        "injection_excerpt": None,
    }
    data.update(changes)
    return data


def text_of(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")
