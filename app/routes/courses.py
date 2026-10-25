from datetime import datetime, timedelta, timezone
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Certificate, Course, CourseProgress, Enrollment, FinancialAidRequest, PaymentHistory, StudentUser, VisitEvent
from app.schemas.courses import (
    CourseCreate,
    CourseStatusUpdate,
    CourseUpdate,
    EnrollmentCreate,
    FinancialAidCreate,
    FinancialAidReview,
    ProgressUpdate,
)
from app.security import require_admin, require_student
from app.services.course_html import sanitize_course_html

router = APIRouter(prefix="/api", tags=["courses"])


def serialize_course(course: Course) -> dict:
    regular_price = course.regular_price_cents or course.price_cents
    offer_price = course.offer_price_cents
    has_offer = offer_price is not None and offer_price < regular_price
    return {
        "id": course.id,
        "slug": course.slug,
        "program_slug": course.program_slug,
        "title": course.title,
        "description": sanitize_course_html(course.description),
        "status": course.status,
        "syllabus": course.syllabus or [],
        "instructor": course.instructor,
        "schedule": course.schedule,
        "price_cents": offer_price if has_offer else regular_price,
        "regular_price_cents": regular_price,
        "offer_price_cents": offer_price if has_offer else None,
        "discount_badge_text": course.discount_badge_text if has_offer else "",
        "has_offer": has_offer,
        "currency": course.currency,
        "created_at": course.created_at.isoformat() if course.created_at else None,
        "updated_at": course.updated_at.isoformat() if course.updated_at else None,
    }


def serialize_aid_request(request: FinancialAidRequest) -> dict:
    return {
        "id": request.id,
        "student": {"id": request.student.id, "full_name": request.student.full_name, "email": request.student.email},
        "course": {"id": request.course.id, "title": request.course.title, "slug": request.course.slug},
        "requested_amount_cents": request.requested_amount_cents,
        "reason": request.reason,
        "status": request.status,
        "review_note": request.review_note,
        "created_at": request.created_at.isoformat() if request.created_at else None,
        "reviewed_at": request.reviewed_at.isoformat() if request.reviewed_at else None,
    }


def resolve_course_prices(regular_price: int, offer_price: int | None) -> tuple[int, int | None]:
    if offer_price is not None and offer_price > regular_price:
        raise HTTPException(status_code=422, detail="Offer price cannot exceed the regular price")
    effective_price = offer_price if offer_price is not None and offer_price < regular_price else regular_price
    return effective_price, offer_price if effective_price != regular_price else None


@router.get("/stats")
def live_stats(db: Session = Depends(get_db)) -> dict:
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
    return {
        "registered_students": db.scalar(select(func.count()).select_from(StudentUser)) or 0,
        "active_courses": db.scalar(select(func.count()).select_from(Course).where(Course.status == "active")) or 0,
        "course_enrollments": db.scalar(select(func.count()).select_from(Enrollment).where(Enrollment.status == "enrolled")) or 0,
        "visits_last_24_hours": db.scalar(select(func.count()).select_from(VisitEvent).where(VisitEvent.occurred_at >= since)) or 0,
    }


@router.get("/courses")
def public_courses(
    status_filter: str | None = Query(default=None, alias="status"),
    program_slug: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    query = select(Course).order_by(Course.id)
    if status_filter:
        if status_filter not in {"upcoming", "active", "closed"}:
            raise HTTPException(status_code=422, detail="Invalid course status")
        query = query.where(Course.status == status_filter)
    if program_slug:
        query = query.where(Course.program_slug == program_slug)
    return [serialize_course(course) for course in db.scalars(query).all()]


@router.post("/courses/{course_id}/enroll", status_code=201)
def enroll(
    course_id: int,
    body: EnrollmentCreate,
    student: StudentUser = Depends(require_student),
    db: Session = Depends(get_db),
) -> dict:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if course.status == "closed":
        raise HTTPException(status_code=409, detail="Enrollment is closed for this course")
    if db.scalar(select(Enrollment.id).where(Enrollment.course_id == course.id, Enrollment.student_id == student.id)):
        raise HTTPException(status_code=409, detail="You are already enrolled in this course")
    approved_aid = db.scalar(
        select(FinancialAidRequest).where(
            FinancialAidRequest.course_id == course.id,
            FinancialAidRequest.student_id == student.id,
            FinancialAidRequest.status == "approved",
        )
    )
    aid_amount = min(approved_aid.requested_amount_cents, course.price_cents) if approved_aid else 0
    remaining_amount = max(course.price_cents - aid_amount, 0)
    if remaining_amount > 0 and not body.mock_payment_confirmed:
        raise HTTPException(status_code=402, detail="Confirm the mock checkout to complete enrollment")
    enrollment = Enrollment(
        course_id=course.id,
        student_id=student.id,
        status="enrolled",
        payment_status="free" if course.price_cents == 0 else ("aid_approved" if remaining_amount == 0 else ("mock_paid_with_aid" if approved_aid else "mock_paid")),
        aid_amount_cents=aid_amount,
        amount_paid_cents=remaining_amount if body.mock_payment_confirmed else 0,
    )
    db.add(enrollment)
    if remaining_amount > 0 and body.mock_payment_confirmed:
        db.flush()
        db.add(PaymentHistory(
            student_id=student.id,
            course_id=course.id,
            enrollment_id=enrollment.id,
            invoice_number=f"ZSA-{uuid.uuid4().hex[:16].upper()}",
            amount_cents=remaining_amount,
            currency=course.currency,
            status="paid",
            payment_method="mock",
            paid_at=datetime.now(timezone.utc),
        ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="You are already enrolled in this course")
    db.refresh(enrollment)
    return {"id": enrollment.id, "course_id": course.id, "status": enrollment.status, "payment_status": enrollment.payment_status, "aid_amount_cents": enrollment.aid_amount_cents, "amount_paid_cents": enrollment.amount_paid_cents}


@router.post("/courses/{course_id}/checkout", status_code=201)
def create_mock_checkout(
    course_id: int,
    student: StudentUser = Depends(require_student),
    db: Session = Depends(get_db),
) -> dict:
    course = db.get(Course, course_id)
    if not course or course.status == "closed":
        raise HTTPException(status_code=404, detail="An open course was not found")
    if course.price_cents <= 0:
        raise HTTPException(status_code=400, detail="Free courses use direct enrollment")
    if db.scalar(select(Enrollment.id).where(Enrollment.course_id == course.id, Enrollment.student_id == student.id)):
        raise HTTPException(status_code=409, detail="You are already enrolled in this course")
    approved_aid = db.scalar(
        select(FinancialAidRequest).where(
            FinancialAidRequest.course_id == course.id,
            FinancialAidRequest.student_id == student.id,
            FinancialAidRequest.status == "approved",
        )
    )
    remaining_amount = max(course.price_cents - (approved_aid.requested_amount_cents if approved_aid else 0), 0)
    if remaining_amount <= 0:
        raise HTTPException(status_code=409, detail="Your approved aid covers the full course fee; use direct enrollment")
    payment = db.scalar(
        select(PaymentHistory).where(
            PaymentHistory.course_id == course.id,
            PaymentHistory.student_id == student.id,
            PaymentHistory.status == "pending",
        )
    )
    if payment is None:
        payment = PaymentHistory(
            student_id=student.id,
            course_id=course.id,
            invoice_number=f"ZSA-{uuid.uuid4().hex[:16].upper()}",
            amount_cents=remaining_amount,
            currency=course.currency,
            status="pending",
            payment_method="mock",
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
    elif payment.amount_cents != remaining_amount:
        payment.amount_cents = remaining_amount
        db.commit()
    return {"payment_id": payment.id, "invoice_number": payment.invoice_number, "amount_cents": payment.amount_cents, "currency": payment.currency, "status": payment.status}


@router.post("/payments/{payment_id}/mock-confirm")
def confirm_mock_payment(
    payment_id: int,
    student: StudentUser = Depends(require_student),
    db: Session = Depends(get_db),
) -> dict:
    payment = db.scalar(
        select(PaymentHistory).where(PaymentHistory.id == payment_id, PaymentHistory.student_id == student.id)
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment was not found")
    if payment.status == "paid" and payment.enrollment_id:
        return {"payment_id": payment.id, "enrollment_id": payment.enrollment_id, "status": payment.status}
    if payment.status != "pending":
        raise HTTPException(status_code=409, detail="This payment cannot be confirmed")
    course = db.get(Course, payment.course_id)
    if not course or course.status == "closed":
        raise HTTPException(status_code=409, detail="Enrollment is closed for this course")
    approved_aid = db.scalar(
        select(FinancialAidRequest).where(
            FinancialAidRequest.course_id == course.id,
            FinancialAidRequest.student_id == student.id,
            FinancialAidRequest.status == "approved",
        )
    )
    aid_amount = min(approved_aid.requested_amount_cents, course.price_cents) if approved_aid else 0
    remaining_amount = max(course.price_cents - aid_amount, 0)
    if remaining_amount == 0:
        enrollment = Enrollment(
            student_id=student.id,
            course_id=course.id,
            status="enrolled",
            payment_status="aid_approved",
            aid_amount_cents=aid_amount,
            amount_paid_cents=0,
        )
        db.add(enrollment)
        payment.status = "waived"
        payment.amount_cents = 0
        payment.enrollment = enrollment
        payment.paid_at = None
        db.commit()
        return {"payment_id": payment.id, "enrollment_id": enrollment.id, "status": payment.status}
    payment.amount_cents = remaining_amount
    enrollment = Enrollment(
        student_id=student.id,
        course_id=course.id,
        status="enrolled",
        payment_status="mock_paid_with_aid" if approved_aid else "mock_paid",
        aid_amount_cents=aid_amount,
        amount_paid_cents=remaining_amount,
    )
    db.add(enrollment)
    db.flush()
    payment.status = "paid"
    payment.paid_at = datetime.now(timezone.utc)
    payment.enrollment_id = enrollment.id
    db.commit()
    return {"payment_id": payment.id, "enrollment_id": enrollment.id, "status": payment.status}


@router.get("/students/me/enrollments")
def my_enrollments(student: StudentUser = Depends(require_student), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Enrollment).where(Enrollment.student_id == student.id).order_by(Enrollment.created_at.desc())).all()
    return [{"id": row.id, "course": serialize_course(row.course), "status": row.status, "payment_status": row.payment_status} for row in rows]


@router.post("/courses/{course_id}/financial-aid", status_code=201)
def apply_for_aid(
    course_id: int,
    body: FinancialAidCreate,
    student: StudentUser = Depends(require_student),
    db: Session = Depends(get_db),
) -> dict:
    course = db.get(Course, course_id)
    if not course or course.status == "closed":
        raise HTTPException(status_code=404, detail="An open course was not found")
    if body.requested_amount_cents > course.price_cents:
        raise HTTPException(status_code=422, detail="Requested aid cannot exceed the course fee")
    pending = db.scalar(
        select(FinancialAidRequest.id).where(
            FinancialAidRequest.course_id == course.id,
            FinancialAidRequest.student_id == student.id,
            FinancialAidRequest.status == "pending",
        )
    )
    if pending:
        raise HTTPException(status_code=409, detail="You already have a pending request for this course")
    request = FinancialAidRequest(
        course_id=course.id,
        student_id=student.id,
        requested_amount_cents=body.requested_amount_cents,
        reason=body.reason,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return {"id": request.id, "status": request.status, "course_id": course.id}


@router.get("/courses/{course_id}/financial-aid/me")
def my_course_aid_status(
    course_id: int,
    student: StudentUser = Depends(require_student),
    db: Session = Depends(get_db),
) -> dict:
    aid = db.scalar(
        select(FinancialAidRequest)
        .where(FinancialAidRequest.course_id == course_id, FinancialAidRequest.student_id == student.id)
        .order_by(FinancialAidRequest.created_at.desc())
    )
    return {"status": aid.status if aid else None, "requested_amount_cents": aid.requested_amount_cents if aid else 0}


@router.get("/admin/courses")
def admin_list_courses(_: object = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    return [serialize_course(course) for course in db.scalars(select(Course).order_by(Course.id)).all()]


@router.post("/admin/courses", status_code=201)
def admin_create_course(body: CourseCreate, _: object = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    values = body.model_dump()
    effective_price, offer_price = resolve_course_prices(values["regular_price_cents"], values["offer_price_cents"])
    values["price_cents"] = effective_price
    values["offer_price_cents"] = offer_price
    values["description"] = sanitize_course_html(values["description"])
    course = Course(**values)
    db.add(course)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Course slug already exists")
    db.refresh(course)
    return serialize_course(course)


@router.put("/admin/courses/{course_id}")
def admin_update_course(course_id: int, body: CourseUpdate, _: object = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    values = body.model_dump(exclude_unset=True)
    regular_price = values.get("regular_price_cents", course.regular_price_cents or course.price_cents)
    if regular_price is None:
        raise HTTPException(status_code=422, detail="Regular price cannot be null")
    offer_price = values["offer_price_cents"] if "offer_price_cents" in values else course.offer_price_cents
    effective_price, offer_price = resolve_course_prices(regular_price, offer_price)
    course.regular_price_cents = regular_price
    course.offer_price_cents = offer_price
    course.price_cents = effective_price
    for field, value in values.items():
        if field in {"regular_price_cents", "offer_price_cents"} or value is None:
            continue
        setattr(course, field, sanitize_course_html(value) if field == "description" else value)
    db.commit()
    db.refresh(course)
    return serialize_course(course)


@router.patch("/admin/courses/{course_id}/status")
def admin_update_course_status(course_id: int, body: CourseStatusUpdate, _: object = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    course.status = body.status
    db.commit()
    db.refresh(course)
    return serialize_course(course)


@router.delete("/admin/courses/{course_id}", status_code=204, response_class=Response)
def admin_delete_course(course_id: int, _: object = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    db.delete(course)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin/enrollments")
def admin_list_enrollments(_: object = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Enrollment).options(selectinload(Enrollment.course), selectinload(Enrollment.student), selectinload(Enrollment.progress)).order_by(Enrollment.created_at.desc())).all()
    return [
        {
            "id": row.id,
            "student": {"id": row.student.id, "full_name": row.student.full_name, "email": row.student.email},
            "course": {"id": row.course.id, "title": row.course.title},
            "status": row.status,
            "payment_status": row.payment_status,
            "aid_amount_cents": row.aid_amount_cents,
            "amount_paid_cents": row.amount_paid_cents,
            "progress_percent": row.progress.progress_percent if row.progress else 0,
            "completed": bool(row.progress and row.progress.progress_percent >= 100),
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.patch("/admin/enrollments/{enrollment_id}/progress")
def admin_update_course_progress(
    enrollment_id: int,
    body: ProgressUpdate,
    _: object = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    enrollment = db.scalar(
        select(Enrollment)
        .where(Enrollment.id == enrollment_id)
        .options(selectinload(Enrollment.progress), selectinload(Enrollment.course), selectinload(Enrollment.student))
    )
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    if enrollment.progress is None:
        enrollment.progress = CourseProgress(progress_percent=body.progress_percent)
    else:
        enrollment.progress.progress_percent = body.progress_percent
    if body.progress_percent >= 100:
        enrollment.progress.completed_at = enrollment.progress.completed_at or datetime.now(timezone.utc)
        certificate = db.scalar(select(Certificate.id).where(Certificate.enrollment_id == enrollment.id))
        if certificate is None:
            db.add(Certificate(
                enrollment_id=enrollment.id,
                student_id=enrollment.student_id,
                course_id=enrollment.course_id,
                verification_code=secrets.token_urlsafe(24),
            ))
    elif db.scalar(select(Certificate.id).where(Certificate.enrollment_id == enrollment.id)):
        raise HTTPException(status_code=409, detail="Completed courses with issued certificates cannot be moved back to incomplete")
    db.commit()
    return {"enrollment_id": enrollment.id, "progress_percent": enrollment.progress.progress_percent, "completed": enrollment.progress.progress_percent >= 100}


@router.get("/admin/financial-aid")
def admin_list_aid_requests(_: object = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(FinancialAidRequest).order_by(FinancialAidRequest.created_at.desc())).all()
    return [serialize_aid_request(row) for row in rows]


@router.patch("/admin/financial-aid/{request_id}")
def admin_review_aid_request(
    request_id: int,
    body: FinancialAidReview,
    _: object = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    aid_request = db.get(FinancialAidRequest, request_id)
    if not aid_request:
        raise HTTPException(status_code=404, detail="Financial aid request not found")
    if aid_request.status != "pending":
        raise HTTPException(status_code=409, detail="This request has already been reviewed")
    aid_request.status = body.status
    aid_request.review_note = body.review_note
    aid_request.reviewed_at = datetime.now(timezone.utc)
    if body.status == "approved":
        pending_payments = db.scalars(
            select(PaymentHistory).where(
                PaymentHistory.student_id == aid_request.student_id,
                PaymentHistory.course_id == aid_request.course_id,
                PaymentHistory.status == "pending",
            )
        ).all()
        remaining_amount = max(aid_request.course.price_cents - aid_request.requested_amount_cents, 0)
        for payment in pending_payments:
            if remaining_amount == 0:
                payment.status = "waived"
                payment.amount_cents = 0
            else:
                payment.amount_cents = remaining_amount
    db.commit()
    db.refresh(aid_request)
    return serialize_aid_request(aid_request)
