from pydantic import BaseModel, Field


class ContentCreate(BaseModel):
    kind: str = Field(min_length=1, max_length=40, pattern=r"^[a-zA-Z0-9_-]+$")
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    payload: dict = Field(default_factory=dict)


class ContentUpdate(BaseModel):
    kind: str | None = Field(default=None, min_length=1, max_length=40, pattern=r"^[a-zA-Z0-9_-]+$")
    slug: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    payload: dict | None = None


class TrackVisit(BaseModel):
    page_path: str = Field(default="/", max_length=300)


class AdminLogin(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=1, max_length=200)
