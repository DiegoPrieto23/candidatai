"""Una pasada por las alertas de correo: lee lo nuevo, da de alta sus ofertas y lo anota.

1. Lee los correos nuevos (por `Message-ID`, tabla `email_messages`) de cada buzón activo
   (`mail_sources`, fase 27.4: IMAP o una carpeta `data/inbox/<nombre>/`), uno detrás de otro y
   con un tope de tiempo, y de `data/inbox/`. El fallo de un buzón no frena a los demás: se anota
   en su `last_error`. El mismo correo recibido en dos buzones cuenta una vez.
2. Saca las ofertas de cada correo con el parser de su plataforma.
3. Las que ya están (por `platform` + `external_id`) se cuentan y no se tocan. De las nuevas, si la
   plataforma permite descargar la página (`platforms.can_fetch`), se intenta el alta completa;
   si no (LinkedIn) o si la descarga falla, entra como resumen en `pending_detail`.
4. Anota cada correo en `email_messages` (solo su `Message-ID`, nunca el cuerpo) y la pasada en
   `source_runs`.

Toda la red (IMAP y páginas) va antes de escribir, para no bloquear SQLite mientras se descarga.
El texto de los correos no es confiable: pasa por la detección de riesgo al guardar cada oferta.
No se aplica el HTML del correo a esa detección: casi todas las alertas llevan texto oculto
legítimo (el «preheader»), y marcaría `hidden_text` en todas.
"""

import functools
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.policies import get_policies
from app.models import EmailMessage, Source, SourceRun
from app.models.base import utcnow
from app.schemas.sources import Issue
from app.services import ingest, mail_sources, platforms
from app.services.ingestion.email.mailboxes import (
    ImapFactory,
    MailboxError,
    RawMail,
    read_imap,
    read_local,
)
from app.services.ingestion.email.message import AlertMessage, parse_message
from app.services.ingestion.email.parsers import parse_alert
from app.services.ingestion.email.parsers.base import AlertItem

logger = logging.getLogger(__name__)

# Tope de una pasada por todos los buzones: los que no quepan se leen en la siguiente.
POLL_BUDGET_SECONDS = 300

SOURCE_KIND = "email_alerts"
SOURCE_NAME = "Alertas por correo"

Fetcher = Callable[[str], str]


class EmailPollResult(BaseModel):
    source_id: int
    run_id: int
    messages: int  # correos nuevos procesados
    found: int  # ofertas anunciadas en ellos
    created: int
    summaries: int  # de las nuevas, cuántas entraron como resumen (`pending_detail`)
    existing: int  # ya estaban
    job_ids: list[int]
    errors: list[Issue]
    message: str


@dataclass
class _Pending:
    """Una oferta nueva lista para guardar, con su página si se pudo descargar."""

    item: AlertItem
    page: ingest.ParsedPage | None = None
    html: str | None = None


@dataclass
class _Mail:
    message: AlertMessage
    origin: str
    items: list[_Pending] = field(default_factory=list)
    found: int = 0


def email_source(session: Session) -> Source:
    source = session.scalars(select(Source).where(Source.kind == SOURCE_KIND).limit(1)).first()
    if source is None:
        source = Source(kind=SOURCE_KIND, name=SOURCE_NAME, config={}, active=True)
        session.add(source)
        session.flush()
    return source


def _is_known(session: Session, message_id: str) -> bool:
    stmt = select(EmailMessage.id).where(EmailMessage.message_id == message_id).limit(1)
    return session.scalars(stmt).first() is not None


def _read_mail(
    session: Session,
    imap_factory: ImapFactory | None,
    errors: list[Issue],
    clock: Callable[[], float] = time.monotonic,
) -> list[RawMail]:
    settings = get_settings()
    mails: list[RawMail] = []
    days = get_policies().email_alerts.summary_expire_days
    deadline = clock() + POLL_BUDGET_SECONDS
    for row in mail_sources.active_sources(session):
        try:
            if clock() > deadline:
                raise MailboxError(
                    "time_budget", "No dio tiempo en esta pasada: se leerá en la siguiente."
                )
            if row.kind == "folder":
                try:
                    mails.extend(read_local(settings.inbox_dir / row.folder))
                except OSError as exc:
                    raise MailboxError(
                        "inbox_error",
                        f"No se pudo leer data/inbox/{row.folder}/ ({type(exc).__name__}).",
                    ) from None
            else:
                account = mail_sources.account_of(row)
                known = functools.partial(_is_known, session)
                mails.extend(read_imap(account, known, days, imap_factory))
        except MailboxError as exc:
            message = f"{row.label}: {exc.message}"
            errors.append(Issue(code=exc.code, message=message, item=row.label))
            mail_sources.mark(row, exc)
        else:
            mail_sources.mark(row, None)
    try:
        mails.extend(read_local(settings.inbox_dir))
    except OSError as exc:
        errors.append(
            Issue(
                code="inbox_error",
                message=f"No se pudo leer data/inbox/ ({type(exc).__name__}).",
            )
        )
    return mails


def _fetch_detail(pending: _Pending, fetch: Fetcher) -> None:
    """Intenta la página completa de la oferta. Si no se puede, queda como resumen."""
    try:
        html = fetch(pending.item.url)
        page = ingest.parse_page(html)
    except (ingest.IngestError, httpx.HTTPError) as exc:
        logger.info("Sin detalle de %s: %s", pending.item.url, exc)
        return
    if len(page.text) >= ingest.MIN_TEXT_CHARS:
        pending.page, pending.html = page, html


def _summary_text(item: AlertItem) -> str:
    label = platforms.PLATFORM_LABELS.get(item.platform, item.platform)
    lines = [item.title, item.company or "", item.location or ""]
    note = f"(Resumen de una alerta por correo de {label}: falta la descripción de la oferta.)"
    return "\n".join([*(line for line in lines if line), "", note])


def _store(session: Session, source: Source, pending: _Pending, result: EmailPollResult) -> bool:
    """Guarda una oferta. `False` si falló la base de datos: el correo se reintentará."""
    item, page = pending.item, pending.page
    company = (page.company if page else None) or item.company
    if not company:
        result.errors.append(
            Issue(
                code="invalid_item",
                message=f"El correo no dice la empresa de «{item.title}».",
                item=item.url,
            )
        )
        return True
    try:
        with session.begin_nested():
            stored = ingest.store_job(
                session,
                source=source,
                title=(page.title if page else None) or item.title,
                company=company,
                text=page.text if page else _summary_text(item),
                url=item.url,
                location=(page.location if page else None) or item.location,
                posted_at=page.posted_at if page else None,
                html=pending.html,
                external_id=item.external_id,
                platform=item.platform,
                detail_level="full" if page else "summary",
            )
    except ingest.IngestError as exc:
        result.errors.append(Issue(code="store_failed", message=str(exc), item=item.url))
        return True
    except SQLAlchemyError as exc:
        logger.warning("No se pudo guardar la oferta %s", item.url, exc_info=True)
        result.errors.append(
            Issue(
                code="store_failed",
                message=f"Error de base de datos ({type(exc).__name__}).",
                item=item.url,
            )
        )
        return False
    if not stored.created:
        result.existing += 1
        return True
    result.created += 1
    result.job_ids.append(stored.job_id)
    if page is None:
        result.summaries += 1
    return True


def poll_email(
    session: Session,
    actor: str = "user",
    *,
    imap_factory: ImapFactory | None = None,
    fetch: Fetcher = ingest.fetch_page,
) -> EmailPollResult:
    """Procesa los correos de alertas nuevos. Procesar dos veces el mismo correo no crea nada."""
    source = email_source(session)
    run = SourceRun(source_id=source.id, actor=actor, started_at=utcnow(), errors=[])
    result = EmailPollResult(
        source_id=source.id,
        run_id=0,
        messages=0,
        found=0,
        created=0,
        summaries=0,
        existing=0,
        job_ids=[],
        errors=[],
        message="",
    )
    errors = result.errors  # la misma lista (Pydantic copia la que se le pasa)

    # 1. Red: correos y páginas, sin escribir nada.
    mails: list[_Mail] = []
    seen: set[str] = set()
    for raw in _read_mail(session, imap_factory, errors):
        try:
            message = parse_message(raw.raw)
        except Exception:  # un correo roto no para a los demás
            logger.warning("Correo ilegible: %s", raw.origin, exc_info=True)
            errors.append(
                Issue(code="invalid_message", message="Correo ilegible.", item=raw.origin)
            )
            continue
        if message.message_id in seen or _is_known(session, message.message_id):
            continue
        seen.add(message.message_id)
        mail = _Mail(message, raw.origin)
        platform, items = parse_alert(message)
        mail.found = len(items)
        if not items and platform is not None:
            # Un correo de una plataforma conocida sin ofertas: puede que haya cambiado el formato.
            errors.append(
                Issue(
                    code="no_jobs_found",
                    message=f"No se encontraron ofertas en un correo de {platform} "
                    f"(«{message.subject[:80]}»). Si era una alerta, puede que haya cambiado su "
                    "formato.",
                    item=raw.origin,
                )
            )
        for item in items:
            if ingest.find_by_platform(session, item.platform, item.external_id) is not None:
                result.existing += 1
                continue
            pending = _Pending(item)
            if platforms.can_fetch(item.platform):
                _fetch_detail(pending, fetch)
            mail.items.append(pending)
        mails.append(mail)

    # 2. Escritura: ofertas y correos procesados.
    for mail in mails:
        stored = [_store(session, source, pending, result) for pending in mail.items]
        if not all(stored):
            continue  # sin anotar el `Message-ID`: la próxima pasada lo reintenta
        session.add(
            EmailMessage(
                message_id=mail.message.message_id,
                source_id=source.id,
                received_at=mail.message.received_at,
                jobs_found=mail.found,
                processed_at=utcnow(),
            )
        )
        result.messages += 1
        result.found += mail.found

    run.finished_at = utcnow()
    run.found = result.found
    run.after_filters = result.found
    run.created = result.created
    run.errors = [issue.model_dump() for issue in errors]
    session.add(run)
    # La pasada cuenta salvo que falle `data/inbox/` o todos los buzones: uno roto no la frena.
    boxes = {row.label for row in mail_sources.active_sources(session)}
    failed = {issue.item for issue in errors if issue.item in boxes}
    if not any(issue.item is None for issue in errors) and not (boxes and failed == boxes):
        source.last_run_at = run.started_at
    session.flush()
    result.run_id = run.id
    result.message = _describe(result)
    return result


def _describe(result: EmailPollResult) -> str:
    if not result.messages:
        text = f"{SOURCE_NAME}: ningún correo nuevo"
    else:
        correos = "correo nuevo" if result.messages == 1 else "correos nuevos"
        text = (
            f"{SOURCE_NAME}: {result.messages} {correos}, {result.found} ofertas, "
            f"{result.created} nuevas"
        )
        if result.summaries:
            text += f" ({result.summaries} como resumen)"
        if result.existing:
            text += f", {result.existing} ya estaban"
    if result.errors:
        text += f"; {len(result.errors)} avisos"
    return text + "."
