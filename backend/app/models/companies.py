from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    normalized_name: Mapped[str] = mapped_column(String(200), unique=True)
    ats_kind: Mapped[str | None] = mapped_column(String(32))
    ats_slug: Mapped[str | None] = mapped_column(String(200))
    watchlist: Mapped[bool] = mapped_column(default=False)
