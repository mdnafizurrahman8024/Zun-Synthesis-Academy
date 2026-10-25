from html import escape

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Certificate, Enrollment, FinancialAidRequest, PaymentHistory, StudentUser, UserProfile
from app.schemas.courses import UserProfileUpdate
from app.security import require_student

router = APIRouter(prefix="/api/students/me", tags=["student dashboard"])
public_router = APIRouter(tags=["certificate verification"])


@router.get("/dashboard")
def dashboard(student: StudentUser = Depends(require_student), db: Session = Depends(get_db)) -> dict:
    if student.profile is None:
        student.profile = UserProfile()
        db.commit()
        db.refresh(student)
    enrollments = db.scalars(
        select(Enrollment)
        .where(Enrollment.student_id == student.id)
        .options(selectinload(Enrollment.course), selectinload(Enrollment.progress))
        .order_by(Enrollment.created_at.desc())
    ).all()
    payments = db.scalars(
        select(PaymentHistory)
        .where(PaymentHistory.student_id == student.id)
        .options(selectinload(PaymentHistory.course))
        .order_by(PaymentHistory.created_at.desc())
    ).all()
    certificates = db.scalars(
        select(Certificate)
        .where(Certificate.student_id == student.id)
        .options(selectinload(Certificate.course))
        .order_by(Certificate.issued_at.desc())
    ).all()
    aid_requests = db.scalars(
        select(FinancialAidRequest)
        .where(FinancialAidRequest.student_id == student.id)
        .options(selectinload(FinancialAidRequest.course))
        .order_by(FinancialAidRequest.created_at.desc())
    ).all()
    return {
        "student": {"id": student.id, "full_name": student.full_name, "email": student.email},
        "profile": {"bio": student.profile.bio, "program_interest": student.profile.program_interest, "timezone": student.profile.timezone},
        "courses": [
            {
                "enrollment_id": item.id,
                "course": {"id": item.course.id, "title": item.course.title, "slug": item.course.slug, "status": item.course.status, "schedule": item.course.schedule},
                "progress_percent": item.progress.progress_percent if item.progress else 0,
                "completed": bool(item.progress and item.progress.progress_percent >= 100),
                "enrolled_at": item.created_at.isoformat(),
            }
            for item in enrollments
        ],
        "payments": [
            {
                "id": item.id,
                "course_title": item.course.title,
                "invoice_number": item.invoice_number,
                "amount_cents": item.amount_cents,
                "currency": item.currency,
                "status": item.status,
                "created_at": item.created_at.isoformat(),
                "paid_at": item.paid_at.isoformat() if item.paid_at else None,
            }
            for item in payments
        ],
        "certificates": [
            {
                "id": item.id,
                "course_title": item.course.title,
                "verification_code": item.verification_code,
                "issued_at": item.issued_at.isoformat(),
                "verify_url": f"/api/certificates/{item.verification_code}",
            }
            for item in certificates
        ],
        "financial_aid": [
            {
                "id": item.id,
                "course_title": item.course.title,
                "requested_amount_cents": item.requested_amount_cents,
                "status": item.status,
                "review_note": item.review_note,
                "created_at": item.created_at.isoformat(),
            }
            for item in aid_requests
        ],
    }


@router.patch("/profile")
def update_profile(
    body: UserProfileUpdate,
    student: StudentUser = Depends(require_student),
    db: Session = Depends(get_db),
) -> dict:
    profile = student.profile
    if profile is None:
        profile = UserProfile(student_id=student.id)
        db.add(profile)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    return {"bio": profile.bio, "program_interest": profile.program_interest, "timezone": profile.timezone}


@router.get("/payments/{payment_id}/invoice")
def download_invoice(
    payment_id: int,
    student: StudentUser = Depends(require_student),
    db: Session = Depends(get_db),
) -> Response:
    payment = db.scalar(
        select(PaymentHistory)
        .where(PaymentHistory.id == payment_id, PaymentHistory.student_id == student.id)
        .options(selectinload(PaymentHistory.course))
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice_html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Invoice {escape(payment.invoice_number)}</title>
    <style>body{{font:16px Arial,sans-serif;max-width:760px;margin:48px auto;padding:24px;color:#172033}}header{{border-bottom:3px solid #0ea5e9;padding-bottom:20px}}table{{width:100%;border-collapse:collapse;margin-top:32px}}td,th{{padding:14px;border-bottom:1px solid #ddd;text-align:left}}.total{{font-size:1.3rem;font-weight:bold}}</style></head><body>
    <header><h1>Zun Synthesis Academy</h1><p>Payment invoice</p></header><p><strong>Invoice:</strong> {escape(payment.invoice_number)}</p>
    <p><strong>Student:</strong> {escape(student.full_name)} · {escape(student.email)}</p><p><strong>Date:</strong> {escape(payment.created_at.isoformat())}</p>
    <table><tr><th>Course</th><th>Status</th><th>Amount</th></tr><tr><td>{escape(payment.course.title)}</td><td>{escape(payment.status)}</td><td>{escape(payment.currency)} {payment.amount_cents / 100:.2f}</td></tr></table>
    <p class="total">Total: {escape(payment.currency)} {payment.amount_cents / 100:.2f}</p><p>This is an account invoice record. Mock payments are not proof of a real payment.</p></body></html>"""
    return HTMLResponse(
        invoice_html,
        headers={"Content-Disposition": f'attachment; filename="{payment.invoice_number}.html"'},
    )


@router.get("/certificates/{certificate_id}/download")
def download_certificate(
    certificate_id: int,
    student: StudentUser = Depends(require_student),
    db: Session = Depends(get_db),
) -> Response:
    certificate = db.scalar(
        select(Certificate)
        .where(Certificate.id == certificate_id, Certificate.student_id == student.id)
        .options(selectinload(Certificate.course))
    )
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")
    student_name = escape(student.full_name)
    course_title = escape(certificate.course.title)
    issued = escape(certificate.issued_at.strftime("%B %d, %Y"))
    code = escape(certificate.verification_code)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="990" viewBox="0 0 1400 990">
      <rect width="1400" height="990" fill="#f8fafc"/><rect x="36" y="36" width="1328" height="918" rx="28" fill="white" stroke="#0ea5e9" stroke-width="8"/>
      <rect x="58" y="58" width="1284" height="874" rx="18" fill="none" stroke="#10b981" stroke-width="2"/>
      <text x="700" y="210" text-anchor="middle" font-family="Arial,sans-serif" font-size="34" fill="#0ea5e9" letter-spacing="8">ZUN SYNTHESIS ACADEMY</text>
      <text x="700" y="355" text-anchor="middle" font-family="Georgia,serif" font-size="58" fill="#0f172a">Certificate of Completion</text>
      <text x="700" y="455" text-anchor="middle" font-family="Arial,sans-serif" font-size="26" fill="#475569">This certifies that</text>
      <text x="700" y="545" text-anchor="middle" font-family="Georgia,serif" font-size="52" font-weight="bold" fill="#0ea5e9">{student_name}</text>
      <text x="700" y="625" text-anchor="middle" font-family="Arial,sans-serif" font-size="25" fill="#475569">has successfully completed</text>
      <text x="700" y="700" text-anchor="middle" font-family="Arial,sans-serif" font-size="35" font-weight="bold" fill="#0f172a">{course_title}</text>
      <text x="700" y="790" text-anchor="middle" font-family="Arial,sans-serif" font-size="23" fill="#475569">Issued {issued}</text>
      <text x="700" y="875" text-anchor="middle" font-family="Arial,sans-serif" font-size="16" fill="#64748b">Verification code: {code}</text>
    </svg>'''
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Content-Disposition": f'attachment; filename="ZSA-Certificate-{certificate.id}.svg"'},
    )


@public_router.get("/api/certificates/{verification_code}", response_class=HTMLResponse)
def verify_certificate(verification_code: str, db: Session = Depends(get_db)) -> HTMLResponse:
    certificate = db.scalar(
        select(Certificate)
        .where(Certificate.verification_code == verification_code)
        .options(selectinload(Certificate.student), selectinload(Certificate.course))
    )
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate could not be verified")
    return HTMLResponse(
        f"<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Verified Certificate</title>"
        f"<body style='font:16px Arial,sans-serif;background:#f1f5f9;padding:5vw;color:#0f172a'><main style='max-width:760px;margin:auto;background:white;padding:48px;border-radius:24px;border:3px solid #0ea5e9;text-align:center'>"
        f"<p style='color:#0ea5e9;font-weight:bold;letter-spacing:.15em'>ZUN SYNTHESIS ACADEMY</p><h1>Certificate Verified</h1>"
        f"<p>This certificate was issued to <strong>{escape(certificate.student.full_name)}</strong> for completing <strong>{escape(certificate.course.title)}</strong>.</p>"
        f"<p>Issued {escape(certificate.issued_at.strftime('%B %d, %Y'))}</p><small>Verification code: {escape(certificate.verification_code)}</small></main></body></html>"
    )
