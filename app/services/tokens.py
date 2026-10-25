from datetime import datetime, timedelta, timezone

import jwt

from app.settings import settings


def create_access_token(email: str, role: str = "admin") -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": email, "role": role, "iat": now, "exp": now + timedelta(minutes=settings.jwt_expire_minutes)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
