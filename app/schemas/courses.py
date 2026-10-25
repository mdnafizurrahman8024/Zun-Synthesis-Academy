from typing import Literal

from pydantic import BaseModel, Field

CourseStatus = Literal["upcoming", "active", "closed"]


class CourseCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=120, pattern=r"^[a-zA-Z0-9_-]+$")
    program_slug: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=100000)
    status: CourseStatus = "upcoming"
    syllabus: list[str] = Field(default_factory=list, max_length=100)
    instructor: str = Field(default="", max_length=160)
    schedule: str = Field(default="", max_length=300)
    regular_price_cents: int = Field(default=0, ge=0, le=100_000_000)
    offer_price_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    discount_badge_text: str = Field(default="", max_length=60)
    currency: str = Field(default="USD", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")


class CourseUpdate(BaseModel):
    program_slug: str | None = Field(default=None, min_length=1, max_length=100)
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=100000)
    status: CourseStatus | None = None
    syllabus: list[str] | None = Field(default=None, max_length=100)
    instructor: str | None = Field(default=None, max_length=160)
    schedule: str | None = Field(default=None, max_length=300)
    regular_price_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    offer_price_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    discount_badge_text: str | None = Field(default=None, max_length=60)
    currency: str | None = Field(default=None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")


class CourseStatusUpdate(BaseModel):
    status: CourseStatus


class EnrollmentCreate(BaseModel):
    mock_payment_confirmed: bool = False


class FinancialAidCreate(BaseModel):
    requested_amount_cents: int = Field(ge=0, le=100_000_000)
    reason: str = Field(min_length=20, max_length=5000)


class FinancialAidReview(BaseModel):
    status: Literal["approved", "rejected"]
    review_note: str = Field(default="", max_length=2000)


class ProgressUpdate(BaseModel):
    progress_percent: int = Field(ge=0, le=100)


class UserProfileUpdate(BaseModel):
    bio: str = Field(default="", max_length=2000)
    program_interest: str = Field(default="", max_length=120)
    timezone: str = Field(default="", max_length=80)


class AdminAccountCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=12, max_length=200)


class AdminAccountUpdate(BaseModel):
    is_active: bool


class StudentRegister(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=12, max_length=200)


class StudentLogin(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)
