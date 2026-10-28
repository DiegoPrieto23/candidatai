from datetime import datetime
from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, utcnow


class ProfileVersion(Base):
    __tablename__ = "profile_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ProfileEdit(Base):
    """Auditoría de lo que el usuario guarda desde la UI (fase 25.7): qué y cuándo, sin el texto.

    `target`: `profile` (una sección de `data/profile.yaml`), `context` (un fichero de
    `data/contexto/`), `style_sample` (una muestra de `data/documentos/estilo/`) o `document` (tu CV
    o tu exportación de LinkedIn, en `data/documentos/cv/` o `linkedin/`).
    """

    __tablename__ = "profile_edits"

    id: Mapped[int] = mapped_column(primary_key=True)
    target: Mapped[str] = mapped_column(String(16))
    section: Mapped[str | None] = mapped_column(String(128))  # sección, fichero o muestra
    action: Mapped[str] = mapped_column(String(16))  # save, undo, upload, delete
    hash_before: Mapped[str | None] = mapped_column(String(64))  # sha256 del fichero
    hash_after: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
