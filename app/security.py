import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AdminUser, StudentUser
from app.settings import settings

bearer = HTTPBearer(auto_error=False)


def _claims(credentials: HTTPAuthorizationCredentials | None) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Valid bearer token required", headers={"WWW-Authenticate": "Bearer"})
    try:
        return jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> AdminUser:
    claims = _claims(credentials)
    if claims.get("role") not in {"admin", "super_admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    admin = db.scalar(select(AdminUser).where(AdminUser.email == claims.get("sub")))
    if not admin or not admin.is_active:
        raise HTTPException(status_code=401, detail="Admin account is unavailable")
    return admin


def require_super_admin(admin: AdminUser = Depends(require_admin)) -> AdminUser:
    if admin.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super Admin access required")
    return admin


def require_student(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> StudentUser:
    claims = _claims(credentials)
    if claims.get("role") != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student account required")
    student = db.scalar(select(StudentUser).where(StudentUser.email == claims.get("sub")))
    if not student:
        raise HTTPException(status_code=401, detail="Student account is unavailable")
    return student
