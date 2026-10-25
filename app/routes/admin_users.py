from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AdminUser
from app.schemas.courses import AdminAccountCreate, AdminAccountUpdate
from app.security import require_super_admin
from app.services.auth import hash_password

router = APIRouter(prefix="/api/admin/users", tags=["admin users"])


def serialize_admin(admin: AdminUser) -> dict:
    return {"id": admin.id, "email": admin.email, "role": admin.role, "is_active": admin.is_active, "created_at": admin.created_at.isoformat() if admin.created_at else None}


@router.get("")
def list_admins(_: AdminUser = Depends(require_super_admin), db: Session = Depends(get_db)) -> list[dict]:
    admins = db.scalars(select(AdminUser).order_by(AdminUser.id)).all()
    return [serialize_admin(admin) for admin in admins]


@router.post("", status_code=201)
def create_admin(body: AdminAccountCreate, _: AdminUser = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    email = body.email.strip().lower()
    if db.scalar(select(AdminUser.id).where(AdminUser.email == email)):
        raise HTTPException(status_code=409, detail="An admin with that email already exists")
    admin = AdminUser(email=email, password_hash=hash_password(body.password), role="admin", is_active=True)
    db.add(admin)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An admin with that email already exists")
    db.refresh(admin)
    return serialize_admin(admin)


@router.patch("/{admin_id}")
def update_admin(admin_id: int, body: AdminAccountUpdate, actor: AdminUser = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    admin = db.get(AdminUser, admin_id)
    if not admin:
        raise HTTPException(status_code=404, detail="Admin account not found")
    if admin.id == actor.id and not body.is_active:
        raise HTTPException(status_code=409, detail="You cannot deactivate your own account")
    if admin.role == "super_admin" and not body.is_active:
        active_supers = db.scalars(select(AdminUser.id).where(AdminUser.role == "super_admin", AdminUser.is_active.is_(True))).all()
        if len(active_supers) <= 1:
            raise HTTPException(status_code=409, detail="The last active Super Admin cannot be deactivated")
    admin.is_active = body.is_active
    db.commit()
    db.refresh(admin)
    return serialize_admin(admin)
