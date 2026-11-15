from datetime import datetime
from typing import Any

from sqlalchemy import JSON, String, Text
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
    action: Mapped[str] = mapped_column(String(16))  # create, save, undo, upload, delete
    hash_before: Mapped[str | None] = mapped_column(String(64))  # sha256 del fichero
    hash_after: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ProfileSuggestion(Base):
    """Propuesta del agente para un campo del perfil (fase 41.2), que el usuario usa o descarta.

    `field`: el campo (`summary.en`); `source`: el texto del que sale, para avisar si cambió;
    `status`: pending | used | discarded | replaced. Nunca se escribe en el perfil desde aquí.
    """

    __tablename__ = "profile_suggestions"

    id: Mapped[int] = mapped_column(primary_key=True)
    field: Mapped[str] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    agent_name: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
