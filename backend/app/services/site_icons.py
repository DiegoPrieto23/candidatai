"""Iconos de los portales y empresas de «Dónde buscar», servidos por la app (fase 35).

Antes los pedía tu navegador a cada web cada vez que abrías la página, y cada empresa que sigues
veía una visita desde tu IP. Ahora la app descarga el icono una vez, lo guarda en `data/icons/` y lo
sirve desde su API:
- Es una lectura pública, como `check_job_open`: sin cookies, sin sesión y sin nada tuyo.
- Con las guardas de la ingesta: nunca a la red local ni a LinkedIn, también en las redirecciones.
- Solo imágenes PNG, ICO, GIF, JPEG o WebP, reconocidas por su contenido y de pocos KB. SVG no:
  servido desde la app podría ejecutar código.
- Un icono vale `ICON_TTL`. Si una web no tiene ninguno, no se vuelve a preguntar hasta pasado
  `MISS_TTL`. Sin red no se apunta «sin icono»: se reintenta en la siguiente visita. Si había uno
  caducado, se sigue sirviendo y no se reintenta hasta pasado `MISS_TTL`.
"""

import contextlib
import os
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from app.core.config import get_settings
from app.services import ingest, liveness

ICON_TTL = 30 * 24 * 3600.0
MISS_TTL = 24 * 3600.0
MAX_ICON_BYTES = 256_000
TIMEOUT = httpx.Timeout(5.0, connect=3.0)

# Portales que no sirven su icono en `/favicon.ico`.
KNOWN_ICONS: dict[str, str] = {
    "tecnoempleo.com": "https://www.tecnoempleo.com/graficos/logo_te_192.png",
    "glassdoor.es": "https://www.glassdoor.com/favicon.ico",
    "glassdoor.com": "https://www.glassdoor.com/favicon.ico",
}

_SIGNATURES: tuple[tuple[bytes, str, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\x00\x00\x01\x00", "image/x-icon", "ico"),
    (b"GIF87a", "image/gif", "gif"),
    (b"GIF89a", "image/gif", "gif"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
)
_MEDIA_TYPES = {ext: media for _sig, media, ext in _SIGNATURES} | {"webp": "image/webp"}
_HOST_RE = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")
# Segundos niveles que reparten dominios (`acme.co.uk`): ahí el dominio padre no es la empresa.
_SHARED_SUFFIXES = {"co", "com", "org", "net", "gov", "edu", "ac", "gob", "nom"}


@dataclass(frozen=True)
class Icon:
    content: bytes
    media_type: str


class Unreachable(Exception):
    """No hubo respuesta de la web (sin red, DNS, tiempo agotado): no se apunta como «sin icono»."""


Download = Callable[[str], bytes | None]


def image_type(content: bytes) -> str | None:
    """Extensión del fichero si es una imagen admitida, por sus primeros bytes."""
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    for signature, _media, ext in _SIGNATURES:
        if content.startswith(signature):
            return ext
    return None


def site_key(home: str) -> str | None:
    """`www.infojobs.net` → `infojobs.net`: el nombre del icono en la caché, si es un dominio."""
    host = (urlsplit(home).hostname or "").lower().removeprefix("www.")
    return host if _HOST_RE.match(host) else None


def candidates(home: str) -> list[str]:
    """Dónde probar el icono, en orden: el conocido, `/favicon.ico` y el de iOS. En un subdominio
    (`careers.acme.com`), también los del dominio principal."""
    parts = urlsplit(home)
    host = (parts.hostname or "").lower()
    key = host.removeprefix("www.")
    origins = [f"{parts.scheme}://{host}"]
    labels = key.split(".")
    base = ".".join(labels[-2:])
    shared = len(labels[-1]) == 2 and labels[-2] in _SHARED_SUFFIXES  # `co.uk`, `com.es`…
    if base != key and not shared:
        origins.append(f"{parts.scheme}://{base}")
    known = [KNOWN_ICONS[key]] if key in KNOWN_ICONS else []
    return known + [
        f"{o}{path}" for o in origins for path in ("/favicon.ico", "/apple-touch-icon.png")
    ]


def download(url: str) -> bytes | None:
    """El icono de `url`, o `None` si la web responde sin una imagen válida. `Unreachable` si no
    responde."""
    client = httpx.Client(
        timeout=TIMEOUT,
        headers={"User-Agent": ingest.USER_AGENT, "Accept": "image/*,*/*;q=0.5"},
        follow_redirects=True,
        event_hooks={"request": [ingest.check_request, liveness.check_resolved]},
    )
    try:
        with client, client.stream("GET", url) as response:
            if response.status_code != 200:
                return None
            content = b""
            for chunk in response.iter_bytes():
                content += chunk
                if len(content) > MAX_ICON_BYTES:
                    return None
    except ingest.IngestError:
        return None  # red local, LinkedIn o una URL rara: como si no tuviera icono
    except httpx.HTTPError as exc:
        raise Unreachable(str(exc)) from exc
    return content if image_type(content) else None


def _cached(folder: Path, key: str) -> Path | None:
    for ext in _MEDIA_TYPES:
        path = folder / f"{key}.{ext}"
        if path.is_file():
            return path
    return None


def _age(path: Path, now: float) -> float:
    return now - path.stat().st_mtime


def _write(path: Path, content: bytes) -> None:
    """Escribe y renombra: dos peticiones a la vez (la API las atiende en hilos) no dejan un fichero
    a medias. Si no se puede guardar, el icono se sirve igual y se descargará otra vez."""
    partial = path.with_name(f"{path.name}.{uuid.uuid4().hex}.part")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        partial.write_bytes(content)
        partial.replace(path)
    except OSError:
        partial.unlink(missing_ok=True)


def _icon(path: Path) -> Icon | None:
    """El icono guardado, o `None` si no se puede leer: en Windows, mientras otro hilo lo renombra
    (`_write`), abrirlo falla con «acceso denegado»."""
    try:
        return Icon(path.read_bytes(), _MEDIA_TYPES[path.suffix.lstrip(".")])
    except OSError:
        return None


def get_icon(home: str, *, fetch: Download = download, now: float | None = None) -> Icon | None:
    """El icono de la web `home` (`https://acme.com`): de la caché o, si no está o ha caducado,
    descargado una vez. `None` si no hay (la UI pone la inicial)."""
    key = site_key(home)
    if key is None:
        return None
    now = time.time() if now is None else now
    folder = get_settings().icons_dir
    cached = _cached(folder, key)
    if cached is not None and _age(cached, now) < ICON_TTL and (icon := _icon(cached)):
        return icon
    miss = folder / f"{key}.miss"
    if cached is None and miss.is_file() and _age(miss, now) < MISS_TTL:
        return None
    answered = False
    for url in candidates(home):
        try:
            content = fetch(url)
        except Unreachable:
            break  # sin red o con la web caída, los demás también tardarían en fallar
        answered = True
        ext = image_type(content) if content else None
        if content and ext:
            # Lo que otro hilo tenga abierto no se puede borrar en Windows: se queda para luego.
            with contextlib.suppress(OSError):
                if cached is not None and cached.suffix != f".{ext}":
                    cached.unlink(missing_ok=True)
                miss.unlink(missing_ok=True)
            _write(folder / f"{key}.{ext}", content)
            return Icon(content, _MEDIA_TYPES[ext])
    if cached is not None:
        # Caducado y sin uno nuevo: sirve el que había y no lo reintenta hasta pasado `MISS_TTL`.
        with contextlib.suppress(OSError):
            stamp = now - ICON_TTL + MISS_TTL
            os.utime(cached, (stamp, stamp))
        return _icon(cached)
    if answered:
        _write(miss, b"")
    return None
