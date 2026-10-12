"""Prepara un CV FICTICIO ya verificado para probar la sección «CV» de la UI sin gastar agente.

Usa la candidata, la oferta (`demo/jobs/01-data-engineer`) y la foto (`demo/photo.png`) de `demo/`,
y el mismo contenido de CV que los tests. Ningún dato real.

Uso (desde la raíz del repo), SIEMPRE con un directorio de datos aparte para no mezclarlo con el
tuyo:
    $env:CAI_DATA_DIR = "data/demo-cv"
    uv run --directory backend python ../scripts/seed_cv_demo.py

Necesita LibreOffice o Word (hace un render de verdad). Si el directorio ya tiene la oferta, no
hace nada.
"""

import shutil
import sys
import time

from app.core import migrations
from app.core.config import REPO_ROOT, get_settings
from app.core.db import session_scope
from app.schemas.cv import CvVerification
from app.services import events, extractions, ingest, profile
from app.services.documents import service
from tests.cv_support import demo_content
from tests.matching_support import demo_extraction

DEMO_JOB = REPO_ROOT / "demo" / "jobs" / "01-data-engineer.txt"


def main() -> int:
    data_dir = get_settings().data_dir
    if data_dir == (REPO_ROOT / "data").resolve():
        print('Usa un directorio aparte: $env:CAI_DATA_DIR = "data/demo-cv" (no tu data/).')
        return 1
    migrations.upgrade()
    photo = data_dir / "photo.png"
    if not photo.exists():
        shutil.copyfile(REPO_ROOT / "demo" / "photo.png", photo)

    text = DEMO_JOB.read_text(encoding="utf-8")
    with session_scope() as session:
        profile.import_profile(session, profile.EXAMPLE_PATH)
        added = ingest.add_from_text(
            session,
            "Data Engineer",
            "Brétema Analytics (ficticia)",
            text,
            location="Santiago de Compostela",
        )
        if not added.created:
            print(f"Ya preparado: oferta {added.job_id} en {data_dir}")
            return 0
        extractions.save_extraction(session, added.job_id, demo_extraction())
        events.record(session, added.job_id, "approved", "user")
        start = time.monotonic()
        saved = service.save_content(session, added.job_id, demo_content())
        seconds = time.monotonic() - start
        result = service.save_verification(
            session, saved.document_id, CvVerification(passed=True, issues=[])
        )
    render = saved.render
    print(f"Oferta {added.job_id} en «{result.stage}» ({data_dir})")
    photo_used = "sí" if render.options.photo else "no"
    print(
        f"Render {render.render_id}: {render.template_id}, foto {photo_used}, "
        f"{render.pages} pág., {seconds:.0f} s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
