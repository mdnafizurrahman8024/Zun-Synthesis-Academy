from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StudentUser, UserProfile
from app.schemas.courses import StudentLogin, StudentRegister
from app.services.auth import hash_password, verify_password
from app.services.tokens import create_access_token
from app.settings import settings

router = APIRouter(prefix="/api/students", tags=["students"])


def student_session(student: StudentUser) -> dict:
    return {
        "access_token": create_access_token(student.email, role="student"),
        "token_type": "bearer",
        "expires_in": settings.jwt_expire_minutes * 60,
        "student": {"id": student.id, "full_name": student.full_name, "email": student.email},
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_student(body: StudentRegister, db: Session = Depends(get_db)) -> dict:
    email = body.email.strip().lower()
    if db.scalar(select(StudentUser.id).where(StudentUser.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    student = StudentUser(full_name=body.full_name.strip(), email=email, password_hash=hash_password(body.password))
    student.profile = UserProfile()
    db.add(student)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    db.refresh(student)
    return student_session(student)


@router.post("/login")
def login_student(body: StudentLogin, db: Session = Depends(get_db)) -> dict:
    student = db.scalar(select(StudentUser).where(StudentUser.email == body.email.strip().lower()))
    if not student or not verify_password(body.password, student.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return student_session(student)
