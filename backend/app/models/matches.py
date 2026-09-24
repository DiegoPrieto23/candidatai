from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, utcnow


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (CheckConstraint("score >= 0 AND score <= 100", name="score_range"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    profile_version_id: Mapped[int] = mapped_column(ForeignKey("profile_versions.id"))
    hard_filters: Mapped[dict[str, Any]] = mapped_column(JSON)
    score: Mapped[int]
    breakdown: Mapped[dict[str, Any]] = mapped_column(JSON)
    assessment: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
