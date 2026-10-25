from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VisitEvent(Base):
    __tablename__ = "visit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_path: Mapped[str] = mapped_column(String(300), index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
