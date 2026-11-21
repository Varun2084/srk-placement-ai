from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..ai.extract import ExtractionError
from ..ai.readiness import readiness_report
from ..config import settings
from ..db import get_db
from ..models import Application, ConsentRecord, ExtractedField, ResumeDocument, Student, User
from ..security import STAFF, current_user, ensure_student_access, require, scoped_institute_ids
from ..services import current_resume, declared_values, evidence_dicts, process_resume

router = APIRouter(prefix="/api", tags=["students"])

MASKED = "•••• (restricted)"


def resume_out(r: ResumeDocument | None) -> dict | None:
    if not r:
        return None
    return {
        "id": r.id,
        "filename": r.filename,
        "status": r.status,
        "error": r.error,
        "language": r.language,
        "injection_flag": r.injection_flag,
        "parser_version": r.parser_version,
        "uploaded_at": r.uploaded_at.isoformat(),
        "fields": [
            {
                "id": f.id, "field": f.field, "value": f.value, "snippet": f.snippet,
                "confidence": f.confidence, "verified": f.verified, "span": [f.span_start, f.span_end],
            }
            for f in r.fields
        ],
        "skills": [
            {"skill": s.skill, "label": s.label, "section": s.section, "snippet": s.snippet} for s in r.skills
        ],
    }


def student_out(s: Student, viewer: User, detail: bool = False) -> dict:
    r = current_resume(s)
    show_contact = viewer.role in {"admin", "tpo", "coordinator"} or viewer.id == s.user_id
    phone = next((f.value for f in (r.fields if r else []) if f.field == "phone"), None)
    out = {
        "id": s.id,
        "user_id": s.user_id,
        "name": s.user.name,
        "email": s.user.email if show_contact else MASKED,
        "phone": (phone if show_contact else MASKED) if phone else None,
        "roll_no": s.roll_no,
        "institute": s.institute.code,
        "institute_id": s.institute_id,
        "programme": s.programme.code,
        "programme_name": s.programme.name,
        "stream": s.programme.stream,
        "branch": s.branch,
        "passing_year": s.passing_year,
        "cgpa": s.cgpa,
        "aggregate_pct": s.aggregate_pct,
        "active_backlogs": s.active_backlogs,
        "tenth_pct": s.tenth_pct,
        "twelfth_pct": s.twelfth_pct,
        "gap_years": s.gap_years,
        "academics_verified": s.academics_verified,
        "consent": bool(s.consent_at),
        "is_minor": s.is_minor,
        "guardian_consent": s.guardian_consent,
        "resume_status": r.status if r else (s.resumes[-1].status if s.resumes else "none"),
        "skills_count": len({e.skill for e in r.skills}) if r else 0,
    }
    if detail:
        out["resume"] = resume_out(r)
        out["declared"] = declared_values(r)
        out["uploads"] = [
            {"id": d.id, "filename": d.filename, "status": d.status, "error": d.error, "uploaded_at": d.uploaded_at.isoformat()}
            for d in s.resumes
        ]
    return out


def _get_student(db: Session, sid: int) -> Student:
    s = db.get(Student, sid)
    if not s:
        raise HTTPException(404, "Student not found")
    return s


@router.get("/students")
def list_students(
    institute_id: int | None = None,
    programme: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require("admin", "tpo", "coordinator")),
):
    scope = scoped_institute_ids(user, [institute_id] if institute_id else None)
    stmt = select(Student)
    if scope is not None:
        stmt = stmt.where(Student.institute_id.in_(scope))
    rows = db.scalars(stmt).all()
    if programme:
        rows = [s for s in rows if s.programme.code == programme]
    if q:
        ql = q.lower()
        rows = [s for s in rows if ql in s.user.name.lower() or ql in s.roll_no.lower()]
    return [student_out(s, user) for s in rows]


@router.get("/students/me")
def my_profile(db: Session = Depends(get_db), user: User = Depends(require("student"))):
    s = db.scalar(select(Student).where(Student.user_id == user.id))
    if not s:
        raise HTTPException(404, "No student profile linked to this account")
    return student_out(s, user, detail=True)


@router.get("/students/{sid}")
def get_student(sid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    s = _get_student(db, sid)
    ensure_student_access(user, s)
    audit.log(db, user, "student.view", "student", s.id, s.institute_id)
    db.commit()
    return student_out(s, user, detail=True)


class ConsentIn(BaseModel):
    granted: bool
    guardian_consent: bool | None = None


@router.post("/students/{sid}/consent")
def platform_consent(sid: int, body: ConsentIn, db: Session = Depends(get_db), user: User = Depends(require("student"))):
    s = _get_student(db, sid)
    ensure_student_access(user, s)
    if body.granted and s.is_minor and not (body.guardian_consent or s.guardian_consent):
        raise HTTPException(400, "Students under 18 need parent/guardian consent first")
    if body.guardian_consent is not None:
        s.guardian_consent = body.guardian_consent
    s.consent_at = datetime.now(timezone.utc) if body.granted else None
    s.consent_version = settings.consent_version if body.granted else None
    db.add(ConsentRecord(student_id=s.id, kind="platform", granted=body.granted, version=settings.consent_version))
    audit.log(db, user, "consent.platform", "student", s.id, s.institute_id, granted=body.granted)
    db.commit()
    return student_out(s, user, detail=True)


@router.post("/students/{sid}/resume")
async def upload_resume(
    sid: int, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(current_user)
):
    s = _get_student(db, sid)
    ensure_student_access(user, s)
    if not s.consent_at:
        raise HTTPException(400, "The student must accept the privacy notice before a resume is processed")
    data = await file.read()
    try:
        doc = process_resume(db, s, file.filename or "resume", data, user)
    except ExtractionError as e:
        audit.log(db, user, "resume.rejected", "student", s.id, s.institute_id, reason=str(e))
        db.commit()
        raise HTTPException(400, str(e))
    db.commit()
    db.refresh(s)
    if doc.status != "parsed":
        raise HTTPException(422, doc.error or "Could not process the file")
    return student_out(s, user, detail=True)


class AcademicsIn(BaseModel):
    branch: str | None = None
    passing_year: int | None = Field(None, ge=2000, le=2040)
    cgpa: float | None = Field(None, ge=0, le=10)
    aggregate_pct: float | None = Field(None, ge=0, le=100)
    active_backlogs: int | None = Field(None, ge=0, le=60)
    tenth_pct: float | None = Field(None, ge=0, le=100)
    twelfth_pct: float | None = Field(None, ge=0, le=100)
    gap_years: int | None = Field(None, ge=0, le=20)
    verified: bool = True


@router.patch("/students/{sid}/academics")
def verify_academics(
    sid: int, body: AcademicsIn, db: Session = Depends(get_db), user: User = Depends(require("admin", "tpo", "coordinator"))
):
    s = _get_student(db, sid)
    ensure_student_access(user, s)
    before = {k: getattr(s, k) for k in body.model_dump(exclude={"verified"})}
    for k, v in body.model_dump(exclude={"verified"}, exclude_unset=True).items():
        setattr(s, k, v)
    s.academics_verified = body.verified
    audit.log(db, user, "student.academics_verified", "student", s.id, s.institute_id,
              before=before, after=body.model_dump())
    db.commit()
    return student_out(s, user, detail=True)


class FieldFix(BaseModel):
    value: str = Field(..., max_length=500)


@router.patch("/resumes/{rid}/fields/{fid}")
def correct_field(rid: int, fid: int, body: FieldFix, db: Session = Depends(get_db), user: User = Depends(current_user)):
    r = db.get(ResumeDocument, rid)
    f = db.get(ExtractedField, fid)
    if not r or not f or f.resume_id != r.id:
        raise HTTPException(404, "Field not found")
    ensure_student_access(user, r.student)
    old = f.value
    f.value, f.corrected_by = body.value.strip(), user.id
    f.verified = user.role in STAFF  # a student's correction is still student-declared
    f.confidence = 1.0
    audit.log(db, user, "resume.field_corrected", "resume", r.id, r.institute_id, field=f.field, before=old, after=f.value)
    db.commit()
    return {"ok": True, "field": f.field, "value": f.value, "verified": f.verified}


@router.get("/students/{sid}/readiness")
def readiness(sid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    s = _get_student(db, sid)
    ensure_student_access(user, s)
    return readiness_report(s.programme.stream, evidence_dicts(current_resume(s)))


@router.get("/resumes/{rid}/file")
def download_resume(rid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    r = db.get(ResumeDocument, rid)
    if not r or r.status != "parsed":
        raise HTTPException(404, "Not found")
    if user.role == "employer":
        apps =db.scalars(select(Application).where(Application.student_id == r.student_id)).all()
        if not any(a.drive.employer_id == user.employer_id and a.status in {"shared", "interview", "offered"} for a in apps):
            raise HTTPException(403, "Not shared with your organisation")
    else:
        ensure_student_access(user, r.student)
    audit.log(db, user, "resume.download", "resume", r.id, r.institute_id)
    db.commit()
    path = Path(r.stored_path)
    if not path.exists():
        raise HTTPException(404, "File missing")
    return FileResponse(path, filename=r.filename, media_type="application/octet-stream")
