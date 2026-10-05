"""Soporte de los tests de la candidatura asistida (fase 11).

`FormServer` sirve los formularios ficticios de `tests/fixtures/applier/` en `127.0.0.1` (sin red
externa) y cuenta cada envío (`POST`) que recibe: así se comprueba que rellenar no envía nada y que
el envío confirmado llega exactamente una vez.
"""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Company, Document, DocumentRender, Job, Source
from app.schemas.llm_io import JobExtraction
from app.services import events, extractions
from app.services import profile as profile_service
from app.services.applier.fields import Applicant, FillData, PackageAnswer
from tests.agent_support import extraction

FORMS = Path(__file__).parent / "fixtures" / "applier"
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"

# Respuesta de cada envío: (estado, cabeceras, cuerpo).
_REPLIES: dict[str, tuple[int, dict[str, str], str]] = {
    "/greenhouse/submit": (302, {"Location": "/greenhouse/confirmation"}, ""),
    "/lever/submit": (302, {"Location": "/lever/thanks"}, ""),
    "/silent/submit": (200, {}, "<p>Recibido.</p>"),
}
_PAGES = {
    "/greenhouse/confirmation": "<h1>Application submitted</h1>",
    "/lever/thanks": "<h1>Application submitted!</h1>",
}
_DEFAULT_REPLY = (200, {}, "<h1>¡Gracias por tu candidatura!</h1>")


class FormServer:
    def __init__(self) -> None:
        self.posts: list[str] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: Any) -> None:
                pass

            def _send(self, status: int, body: str, headers: dict[str, str] | None = None) -> None:
                data = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                for key, value in (headers or {}).items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:  # noqa: N802 - nombre de http.server
                path = self.path.split("?")[0]
                if path in _PAGES:
                    self._send(200, _PAGES[path])
                    return
                if path == "/silent":
                    html = (FORMS / "simple.html").read_text(encoding="utf-8")
                    self._send(200, html.replace("/simple/submit", "/silent/submit"))
                    return
                file = FORMS / (path.strip("/") + ".html")
                if file.is_file():
                    self._send(200, file.read_text(encoding="utf-8"))
                else:
                    self._send(404, "<h1>404</h1>")

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                self.rfile.read(length)
                path = self.path.split("?")[0]
                server.posts.append(path)
                status, headers, body = _REPLIES.get(path, _DEFAULT_REPLY)
                self._send(status, body, headers)

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def __enter__(self) -> "FormServer":
        self._thread.start()
        return self

    def __exit__(self, *_exc: Any) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self._httpd.server_address[1]}/{path.lstrip('/')}"


def fill_data(tmp: Path, **changes: Any) -> FillData:
    """Datos ficticios de la candidata demo, con PDFs mínimos de CV y carta."""
    resume = tmp / "CV-Lucia-Varela.pdf"
    letter = tmp / "Carta-Lucia-Varela.pdf"
    resume.write_bytes(PDF)
    letter.write_bytes(PDF)
    data: dict[str, Any] = {
        "applicant": Applicant(
            full_name="Lucía Varela Otero",
            first_name="Lucía",
            last_name="Varela Otero",
            email="lucia.varela@example.com",
            phone="+34 600 000 000",
            linkedin="https://www.linkedin.com/in/lucia-varela-demo",
            github="https://github.com/lucia-varela-demo",
            city="Vigo",
        ),
        "resume": resume,
        "letter_pdf": letter,
        "letter_text": "Estimado equipo:\n\nMe interesa el puesto.\n\nUn saludo,\nLucía",
        "answers": [
            PackageAnswer(
                question="Are you legally authorized to work in Spain?",
                answer="Yes, I am an EU citizen.",
                needs_user_input=False,
            ),
            PackageAnswer(
                question="Why do you want to work at Acme?",
                answer="Because I enjoy building data platforms.",
                needs_user_input=False,
            ),
            PackageAnswer(
                question="What are your salary expectations?", answer="", needs_user_input=True
            ),
            PackageAnswer(
                question="Will you now or in the future require visa sponsorship?",
                answer="No, I do not need sponsorship.",
                needs_user_input=False,
            ),
            PackageAnswer(
                question="Are you willing to work from our Vigo office?",
                answer="Yes",
                needs_user_input=False,
            ),
        ],
    }
    data.update(changes)
    return FillData(**data)


ANSWERS_CONTENT = {
    "answers": [
        {
            "question": "¿Cuándo podrías incorporarte?",
            "answer": "",
            "evidence": [],
            "needs_user_input": True,
        }
    ]
}


def cv_ready_job(session: Session, url: str, company: str = "Acme Analytics") -> int:
    """Oferta en `cv_ready` con un CV verificado y su PDF elegido, sin pasar por el motor de CV."""
    profile_service.import_profile(session, profile_service.EXAMPLE_PATH)
    source = Source(kind="manual_text", name="Manual")
    company_row = Company(name=company, normalized_name=company.lower())
    session.add_all([source, company_row])
    session.flush()
    job = Job(
        source_id=source.id,
        company_id=company_row.id,
        url=url,
        title="Data Engineer",
        raw_text="Texto de ejemplo.",
        fingerprint=f"fp-{url}",
    )
    session.add(job)
    session.flush()
    events.record(session, job.id, "found", "system")
    extractions.save_extraction(
        session, job.id, JobExtraction.model_validate(extraction(locations=["Vigo"]))
    )
    events.record(session, job.id, "approved", "user")
    version = profile_service.current(session).profile_version_id
    doc = Document(
        job_id=job.id,
        profile_version_id=version,
        kind="cv",
        language="es",
        content={},
        verification={"passed": True},
    )
    session.add(doc)
    session.flush()
    relative = f"cvs/{job.id}/{doc.id}/CV-Lucia-Varela.pdf"
    pdf = get_settings().data_dir / relative
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(PDF)
    render = DocumentRender(
        document_id=doc.id,
        template_id="ats-simple",
        template_hash="x",
        options={},
        pdf_path=relative,
        pages=1,
        selected=True,
    )
    session.add(render)
    session.flush()
    payload = {"document_id": doc.id, "render_id": render.id, "too_long": False}
    events.record(session, job.id, "cv_generated", "agent", payload={"document_id": doc.id})
    events.record(session, job.id, "cv_rendered", "system", payload=payload)
    events.record(
        session, job.id, "cv_verified", "agent", payload={"document_id": doc.id, "passed": True}
    )
    session.add(
        Document(
            job_id=job.id,
            profile_version_id=version,
            kind="answers",
            language="es",
            content=ANSWERS_CONTENT,
        )
    )
    session.flush()
    assert events.current_stage(session, job.id) == "cv_ready"
    return job.id
