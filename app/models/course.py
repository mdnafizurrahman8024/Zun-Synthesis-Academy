from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (CheckConstraint("status IN ('upcoming', 'active', 'closed')", name="ck_course_status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    program_slug: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="upcoming", index=True)
    syllabus: Mapped[list] = mapped_column(JSON, default=list)
    instructor: Mapped[str] = mapped_column(String(160), default="")
    schedule: Mapped[str] = mapped_column(String(300), default="")
    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    regular_price_cents: Mapped[int] = mapped_column(Integer, default=0)
    offer_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discount_badge_text: Mapped[str] = mapped_column(String(60), default="")
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    aid_requests: Mapped[list["FinancialAidRequest"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    payments: Mapped[list["PaymentHistory"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    certificates: Mapped[list["Certificate"]] = relationship(back_populates="course", cascade="all, delete-orphan")
