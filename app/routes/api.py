from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AdminUser, ContentItem, VisitEvent
from app.security import require_admin
from app.schemas.content import AdminLogin, ContentCreate, ContentUpdate, TrackVisit
from app.services.auth import verify_password
from app.services.tokens import create_access_token
from app.settings import settings

router = APIRouter(prefix="/api")


def serialize_content(item: ContentItem) -> dict:
    return {
        "id": item.id,
        "kind": item.kind,
        "slug": item.slug,
        "payload": item.payload,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


@router.post("/admin/login")
def admin_login(body: AdminLogin, db: Session = Depends(get_db)) -> dict:
    email = body.email.strip().lower()
    password = body.password
    admin = db.scalar(select(AdminUser).where(AdminUser.email == email))
    if not admin or not admin.is_active or not isinstance(password, str) or not verify_password(password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {
        "access_token": create_access_token(admin.email, role=admin.role),
        "token_type": "bearer",
        "expires_in": settings.jwt_expire_minutes * 60,
        "admin": {"email": admin.email, "role": admin.role},
    }


@router.get("/admin/me")
def current_admin(admin: AdminUser = Depends(require_admin)) -> dict:
    return {"id": admin.id, "email": admin.email, "role": admin.role}


@router.get("/content")
def public_content(kind: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    query = select(ContentItem).order_by(ContentItem.id)
    if kind:
        query = query.where(ContentItem.kind == kind)
    return [serialize_content(item) for item in db.scalars(query).all()]


@router.post("/analytics/track", status_code=202)
def track_visit(body: TrackVisit, db: Session = Depends(get_db)) -> dict:
    path = body.page_path.strip()
    if not path.startswith("/") or path.startswith("//"):
        path = "/"
    # Deliberately store only a page path and server timestamp: no IP, cookies,
    # user agent, or other visitor identifier is collected.
    db.add(VisitEvent(page_path=path[:300]))
    db.commit()
    return {"accepted": True}


@router.get("/admin/content")
def list_content(_: AdminUser = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    return [serialize_content(item) for item in db.scalars(select(ContentItem).order_by(ContentItem.id)).all()]


@router.post("/admin/content", status_code=201)
def create_content(body: ContentCreate, _: AdminUser = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    item = ContentItem(kind=body.kind, slug=body.slug, payload=body.payload)
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That slug already exists for this content kind")
    db.refresh(item)
    return serialize_content(item)


@router.put("/admin/content/{item_id}")
def update_content(item_id: int, body: ContentUpdate, _: AdminUser = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    item = db.get(ContentItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    for field in ("kind", "slug", "payload"):
        value = getattr(body, field)
        if value is not None:
            setattr(item, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That slug already exists for this content kind")
    db.refresh(item)
    return serialize_content(item)


@router.delete("/admin/content/{item_id}", status_code=204, response_class=Response)
def delete_content(item_id: int, _: AdminUser = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    item = db.get(ContentItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin/analytics")
def analytics(_: AdminUser = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    last_hour = now - timedelta(hours=1)
    last_day = now - timedelta(days=1)
    total_hour = db.scalar(select(func.count()).select_from(VisitEvent).where(VisitEvent.occurred_at >= last_hour)) or 0
    total_day = db.scalar(select(func.count()).select_from(VisitEvent).where(VisitEvent.occurred_at >= last_day)) or 0
    popular = db.execute(
        select(VisitEvent.page_path, func.count().label("views"))
        .where(VisitEvent.occurred_at >= last_day)
        .group_by(VisitEvent.page_path)
        .order_by(func.count().desc())
        .limit(10)
    ).all()
    latest = db.scalars(select(VisitEvent).order_by(VisitEvent.occurred_at.desc()).limit(20)).all()
    return {
        "window": "rolling 24 hours",
        "visits_last_hour": total_hour,
        "visits_last_24_hours": total_day,
        "popular_pages": [{"page_path": path, "views": count} for path, count in popular],
        "recent_visits": [{"page_path": visit.page_path, "occurred_at": visit.occurred_at.isoformat()} for visit in latest],
    }
