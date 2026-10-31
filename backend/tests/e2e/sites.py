"""Las webs de terceros de las E2E, servidas en 127.0.0.1 y contando lo que reciben.

- **El ATS de la oferta** (`http://ats.ejemplo.test/...`): la app no descarga direcciones locales
  (guarda contra SSRF), así que este servidor hace además de proxy (`HTTP_PROXY` de la app) y solo
  responde por ese dominio inventado. El resto de lo que pase por el proxy se corta, como el proxy
  muerto del arnés: nada sale a internet.
- **El formulario de candidatura** (`/formulario`): cuenta cada envío (`POST`), para comprobar que
  rellenar no envía nada y que el envío confirmado llega una sola vez.
"""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

FIXTURES = Path(__file__).parents[1] / "fixtures" / "e2e"
ATS_HOST = "ats.ejemplo.test"
JOB_PATH = "/ofertas/analytics-engineer-4821"
FORM_PATH = "/formulario"
SUBMIT_PATH = "/formulario/enviar"


class Sites:
    def __init__(self) -> None:
        self.posts: list[str] = []
        self.job_downloads = 0
        sites = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: Any) -> None:
                pass

            def _send(self, status: int, body: str) -> None:
                data = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _cut(self) -> None:
                # Como un proxy muerto: sin respuesta.
                self.close_connection = True

            def do_CONNECT(self) -> None:  # noqa: N802 - nombre de http.server
                self._cut()  # HTTPS por el proxy: nunca

            def do_GET(self) -> None:  # noqa: N802
                parts = urlsplit(self.path)
                if parts.scheme:  # petición de proxy: `GET http://host/ruta`
                    if parts.hostname == ATS_HOST and parts.path == JOB_PATH:
                        sites.job_downloads += 1
                        self._send(200, (FIXTURES / "oferta-ats.html").read_text(encoding="utf-8"))
                    elif parts.hostname == ATS_HOST:
                        self._send(404, "<h1>404</h1>")
                    else:
                        self._cut()
                    return
                if parts.path == FORM_PATH:
                    self._send(200, (FIXTURES / "formulario-ats.html").read_text(encoding="utf-8"))
                else:
                    self._send(404, "<h1>404</h1>")

            def do_POST(self) -> None:  # noqa: N802
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                path = urlsplit(self.path).path
                sites.posts.append(path)
                if path == SUBMIT_PATH:
                    self._send(200, "<h1>¡Gracias por tu candidatura!</h1>")
                else:
                    self._send(404, "<h1>404</h1>")

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def __enter__(self) -> "Sites":
        self._thread.start()
        return self

    def __exit__(self, *_exc: Any) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self._httpd.server_address[1]}"

    @property
    def job_url(self) -> str:
        return f"http://{ATS_HOST}{JOB_PATH}"

    @property
    def form_url(self) -> str:
        return f"{self.base}{FORM_PATH}"

    def app_env(self) -> dict[str, str]:
        """Lo que la app necesita para llegar aquí: el proxy y la candidatura contra 127.0.0.1."""
        return {
            "HTTP_PROXY": self.base,
            "CAI_APPLIER_ALLOW_LOOPBACK": "true",
        }
