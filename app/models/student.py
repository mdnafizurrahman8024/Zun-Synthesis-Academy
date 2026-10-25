from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StudentUser(Base):
    __tablename__ = "student_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="student", cascade="all, delete-orphan")
    aid_requests: Mapped[list["FinancialAidRequest"]] = relationship(back_populates="student", cascade="all, delete-orphan")
    profile: Mapped["UserProfile"] = relationship(back_populates="student", cascade="all, delete-orphan", uselist=False)
    payments: Mapped[list["PaymentHistory"]] = relationship(back_populates="student", cascade="all, delete-orphan")
    certificates: Mapped[list["Certificate"]] = relationship(back_populates="student", cascade="all, delete-orphan")
