from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, utcnow


class UserPrompt(Base):
    """Un aviso para que hagas algo en el navegador (resolver un captcha, iniciar sesión…).

    Lo crea el agente al buscar ofertas o el worker en una candidatura asistida; la UI lo enseña en
    un pop-up y tú lo contestas («Ya está» o «Saltar»). Si nadie contesta antes de `expires_at`,
    caduca y quien lo pidió sigue sin ello. Nunca se resuelve un captcha por ti.
    """

    __tablename__ = "user_prompts"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(24))  # captcha | anti_bot | login_required
    message: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(2000))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"))
    attempt_id: Mapped[int | None] = mapped_column(ForeignKey("application_attempts.id"))
    # pending | done | skipped | expired
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    answered_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
