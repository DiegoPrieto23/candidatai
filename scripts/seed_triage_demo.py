"""Da de alta las 20 ofertas FICTICIAS de `evals/matching/seed.jsonl`, ya extraídas, para probar el
triaje sin gastar agente. Empresas inventadas; ningún dato real.

Uso (desde la raíz del repo, con la BD migrada):
    uv run --directory backend python ../scripts/seed_triage_demo.py

Respeta `JH_DATA_DIR`. Es idempotente: una oferta que ya existe no se vuelve a crear ni a extraer.
Las que no pasan los filtros duros de tu perfil quedan cerradas (se ven en la bandeja).
"""

import sys

from app.core import migrations
from app.core.config import REPO_ROOT, get_settings
from app.core.db import session_scope
from app.services import extractions, ingest
from app.services.matching.evaluation import SEED_DIR, load_cases

# Distintas de las de demo/jobs/ (Brétema, Lonxa): si ya diste de alta esas ofertas, la app
# tomaría las de aquí por duplicados de aquellas.
COMPANIES = (
    "Arnela Analytics", "Pazo Retail Tech", "Faro Logística", "Néboa Seguros", "Castro Data",
    "Ría Software", "Hórreo Labs", "Miño Energía", "Carballo Banca", "Illas Health",
    "Mareira Foods", "Rula Analytics", "Xeito Consulting", "Orballo Cloud", "Seixo Industria",
    "Lume Media", "Pedra Mobility", "Brisa Telecom", "Fervenza Games", "Toxo Retail",
)  # fmt: skip


def posting_text(title: str, company: str, case: object) -> str:
    ext = case.job_fixture.extraction  # type: ignore[attr-defined]
    lines = [
        f"{title} – {company} (empresa ficticia, oferta de prueba de Job Hunter)",
        "",
        "Qué harás:",
        *(f"- {r}" for r in ext.responsibilities or ["Trabajar con el equipo de datos."]),
        "",
        "Requisitos:",
        *(f"- {s}" for s in ext.must_have_skills),
        "",
        "Valorable:",
        *(f"- {s}" for s in ext.nice_to_have_skills or ["Ganas de aprender."]),
        "",
        f"Modalidad: {ext.remote_mode}. Ubicación: {', '.join(ext.locations) or 'sin indicar'}.",
    ]
    return "\n".join(lines)


def main() -> int:
    migrations.ensure_current()
    cases = load_cases(SEED_DIR / "seed.jsonl")
    created = skipped = duplicated = 0
    for case, company in zip(cases, COMPANIES, strict=True):
        fixture = case.job_fixture
        location = ", ".join(fixture.extraction.locations) or None
        with session_scope() as session:
            result = ingest.add_from_text(
                session,
                fixture.title,
                company,
                posting_text(fixture.title, company, case),
                location=location,
            )
            if not result.created:
                skipped += 1
                continue
            if result.duplicate_of is not None:
                # La app la cierra como duplicado de otra: no admite extracción.
                duplicated += 1
                print(
                    f"{result.job_id:>4}  {'closed':<15} {fixture.title} · {company} "
                    f"(duplicado de la oferta {result.duplicate_of}: sin extracción)"
                )
                continue
            saved = extractions.save_extraction(session, result.job_id, fixture.extraction)
            created += 1
            print(f"{result.job_id:>4}  {saved.stage:<15} {fixture.title} · {company}")
    data_dir = get_settings().data_dir
    shown = data_dir.relative_to(REPO_ROOT) if data_dir.is_relative_to(REPO_ROOT) else data_dir
    summary = f"{created} ofertas creadas, {skipped} ya existían"
    if duplicated:
        summary += f", {duplicated} cerradas como duplicado"
    print(f"\n{summary} (datos en {shown}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
