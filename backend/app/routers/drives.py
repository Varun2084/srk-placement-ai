from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..ai.taxonomy import TAXONOMY
from ..db import get_db
from ..models import (
    Application,
    ConsentRecord,
    Drive,
    Employer,
    HumanReview,
    MatchResult,
    MatchRun,
    Programme,
    Student,
    User,
)
from ..security import GROUP_WIDE, current_user, ensure_institute, require, scoped_institute_ids
from ..services import current_resume, run_matching
from .students import student_out

router = APIRouter(prefix="/api", tags=["drives"])

REVIEW_DECISIONS = {"shortlisted", "on_hold", "not_selected"}
STREAMS = {"engineering", "polytechnic", "pharmacy", "management"}


class DriveIn(BaseModel):
    employer_id: int | None = None
    employer_name: str | None = None
    title: str = Field(..., min_length=3, max_length=200)
    job_family: str
    stream: str
    description: str = ""
    institute_ids: list[int] = []
    programme_codes: list[str] = []
    branches: list[str] = []
    passing_years: list[int] = []
    min_cgpa: float | None = Field(None, ge=0, le=10)
    min_aggregate_pct: float | None = Field(None, ge=0, le=100)
    max_backlogs: int | None = Field(None, ge=0)
    max_gap_years: int | None = Field(None, ge=0)
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    weights: dict[str, int] = {}
    status: str = "draft"

    @field_validator("stream")
    @classmethod
    def _stream(cls, v):
        if v not in STREAMS:
            raise ValueError(f"stream must be one of {sorted(STREAMS)}")
        return v

    @field_validator("required_skills", "preferred_skills")
    @classmethod
    def _skills(cls, v):
        bad = [s for s in v if s not in TAXONOMY["skills"]]
        if bad:
            raise ValueError(f"unknown skills: {bad}")
        return v

    @field_validator("weights")
    @classmethod
    def _weights(cls, v):
        if set(v) - {"required", "preferred", "context"}:
            raise ValueError("weights keys: required, preferred, context")
        if any(x < 0 or x > 100 for x in v.values()):
            raise ValueError("weights must be 0-100")
        return v


def drive_out(d: Drive, db: Session, user: User) -> dict:
    scope = scoped_institute_ids(user)
    q = select(Application.status, func.count()).where(Application.drive_id == d.id)
    if scope is not None and user.role == "coordinator":
        q = q.where(Application.institute_id.in_(scope))
    counts = dict(db.execute(q.group_by(Application.status)).all())
    return {
        "id": d.id,
        "employer": {"id": d.employer.id, "name": d.employer.name, "sector": d.employer.sector},
        "title": d.title,
        "job_family": d.job_family,
        "job_family_label": TAXONOMY["job_families"].get(d.stream, {}).get(d.job_family, {}).get("label", d.job_family),
        "stream": d.stream,
        "description": d.description,
        "institute_ids": d.institute_ids,
        "programme_codes": d.programme_codes,
        "branches": d.branches,
        "passing_years": d.passing_years,
        "min_cgpa": d.min_cgpa,
        "min_aggregate_pct": d.min_aggregate_pct,
        "max_backlogs": d.max_backlogs,
        "max_gap_years": d.max_gap_years,
        "required_skills": d.required_skills,
        "preferred_skills": d.preferred_skills,
        "weights": d.weights,
        "weights_approved": d.weights_approved_by is not None,
        "status": d.status,
        "version": d.version,
        "counts": counts,
        "created_at": d.created_at.isoformat(),
    }


def _visible(d: Drive, user: User, student: Student | None = None) -> bool:
    if user.role in GROUP_WIDE:
        return True
    if user.role == "coordinator":
        return not d.institute_ids or user.institute_id in d.institute_ids
    if user.role == "employer":
        return d.employer_id == user.employer_id
    if user.role == "student" and student:
        return (
            d.status == "open"
            and (not d.institute_ids or student.institute_id in d.institute_ids)
            and (not d.programme_codes or student.programme.code in d.programme_codes)
            and (not d.branches or any(b.lower() == (student.branch or "").lower() for b in d.branches))
        )
    return False


def _get_drive(db: Session, did: int, user: User) -> Drive:
    d = db.get(Drive, did)
    student = db.scalar(select(Student).where(Student.user_id == user.id)) if user.role == "student" else None
    if not d or not _visible(d, user, student):
        raise HTTPException(404, "Drive not found")
    return d


@router.get("/drives")
def list_drives(db: Session = Depends(get_db), user: User = Depends(current_user)):
    student = db.scalar(select(Student).where(Student.user_id == user.id)) if user.role == "student" else None
    drives = [d for d in db.scalars(select(Drive).order_by(Drive.id.desc())).all() if _visible(d, user, student)]
    out = []
    for d in drives:
        item = drive_out(d, db, user)
        if student:
            app = db.scalar(select(Application).where(Application.drive_id == d.id, Application.student_id == student.id))
            item["my_application"] = app.status if app else None
            item["counts"] = {}
            item["my_share_consent"] = bool(
                db.scalar(select(ConsentRecord).where(
                    ConsentRecord.student_id == student.id, ConsentRecord.kind == "employer_share",
                    ConsentRecord.employer_id == d.employer_id, ConsentRecord.granted.is_(True)))
            )
        out.append(item)
    return out


@router.get("/drives/{did}")
def get_drive(did: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return drive_out(_get_drive(db, did, user), db, user)


@router.post("/drives")
def create_drive(body: DriveIn, db: Session = Depends(get_db), user: User = Depends(require("admin", "tpo", "coordinator"))):
    if user.role == "coordinator":
        if not body.institute_ids:
            body.institute_ids = [user.institute_id]
        if body.institute_ids != [user.institute_id]:
            raise HTTPException(403, "Coordinators can create drives only for their own institute")
    if body.employer_id:
        employer = db.get(Employer, body.employer_id)
        if not employer:
            raise HTTPException(404, "Employer not found")
    elif body.employer_name:
        employer = Employer(name=body.employer_name.strip())
        db.add(employer)
        db.flush()
    else:
        raise HTTPException(400, "employer_id or employer_name is required")
    data = body.model_dump(exclude={"employer_id", "employer_name"})
    d = Drive(**data, employer_id=employer.id, created_by=user.id)
    if user.role in GROUP_WIDE and d.weights:
        d.weights_approved_by = user.id
    db.add(d)
    db.flush()
    audit.log(db, user, "drive.create", "drive", d.id, None, criteria=data)
    db.commit()
    return drive_out(d, db, user)


@router.patch("/drives/{did}")
def update_drive(did: int, body: DriveIn, db: Session = Depends(get_db), user: User = Depends(require("admin", "tpo", "coordinator"))):
    d = _get_drive(db, did, user)
    if user.role == "coordinator" and body.institute_ids != [user.institute_id]:
        raise HTTPException(403, "Coordinators can edit drives only for their own institute")
    before = drive_out(d, db, user)
    data = body.model_dump(exclude={"employer_id", "employer_name"})
    weights_changed = data["weights"] != d.weights
    for k, v in data.items():
        setattr(d, k, v)
    d.version += 1
    if weights_changed:
        d.weights_approved_by = user.id if user.role in GROUP_WIDE else None
    audit.log(db, user, "drive.update", "drive", d.id, None, version=d.version, before=before, after=data)
    db.commit()
    return drive_out(d, db, user)


@router.post("/drives/{did}/approve-weights")
def approve_weights(did: int, db: Session = Depends(get_db), user: User = Depends(require("admin", "tpo"))):
    d = _get_drive(db, did, user)
    d.weights_approved_by = user.id
    audit.log(db, user, "drive.weights_approved", "drive", d.id, None, weights=d.weights, version=d.version)
    db.commit()
    return drive_out(d, db, user)


@router.post("/drives/{did}/apply")
def apply(did: int, db: Session = Depends(get_db), user: User = Depends(require("student"))):
    d = _get_drive(db, did, user)
    s = db.scalar(select(Student).where(Student.user_id == user.id))
    if not s.consent_at:
        raise HTTPException(400, "Accept the privacy notice first")
    existing = db.scalar(select(Application).where(Application.drive_id == d.id, Application.student_id == s.id))
    if existing:
        return {"status": existing.status}
    a = Application(drive_id=d.id, student_id=s.id, institute_id=s.institute_id)
    db.add(a)
    audit.log(db, user, "application.create", "drive", d.id, s.institute_id)
    db.commit()
    return {"status": a.status}


@router.post("/drives/{did}/share-consent")
def share_consent(did: int, granted: bool = True, db: Session = Depends(get_db), user: User = Depends(require("student"))):
    d = _get_drive(db, did, user)
    s = db.scalar(select(Student).where(Student.user_id == user.id))
    db.add(ConsentRecord(student_id=s.id, kind="employer_share", employer_id=d.employer_id, granted=granted, version="share-v1"))
    audit.log(db, user, "consent.employer_share", "student", s.id, s.institute_id, employer_id=d.employer_id, granted=granted)
    db.commit()
    return {"ok": True, "granted": granted}


@router.post("/drives/{did}/enrol-eligible")
def enrol_programme_students(did: int, db: Session = Depends(get_db), user: User = Depends(require("admin", "tpo", "coordinator"))):
    """Add every consented student of the drive's institutes and programmes to the drive.
    Eligibility is then checked by gates and reviewed by people; nobody is filtered out here."""
    d = _get_drive(db, did, user)
    scope = scoped_institute_ids(user)
    stmt = select(Student).join(Programme)
    if d.institute_ids:
        stmt = stmt.where(Student.institute_id.in_(d.institute_ids))
    if scope is not None:
        stmt = stmt.where(Student.institute_id.in_(scope))
    if d.programme_codes:
        stmt = stmt.where(Programme.code.in_(d.programme_codes))
    added = 0
    for s in db.scalars(stmt).all():
        if not s.consent_at:
            continue
        if db.scalar(select(Application).where(Application.drive_id == d.id, Application.student_id == s.id)):
            continue
        db.add(Application(drive_id=d.id, student_id=s.id, institute_id=s.institute_id))
        added += 1
    audit.log(db, user, "drive.enrol", "drive", d.id, None, added=added)
    db.commit()
    return {"added": added}


@router.post("/drives/{did}/match")
def match(did: int, db: Session = Depends(get_db), user: User = Depends(require("admin", "tpo", "coordinator"))):
    d = _get_drive(db, did, user)
    if d.weights and not d.weights_approved_by:
        raise HTTPException(400, "Custom weights must be approved by the TPO before matching")
    run = run_matching(db, d, user, scoped_institute_ids(user))
    db.commit()
    return {"run_id": run.id}


def _latest_results(db: Session, d: Drive, user: User) -> list[tuple[Application, MatchResult | None]]:
    scope = scoped_institute_ids(user)
    q = select(Application).where(Application.drive_id == d.id)
    if scope is not None:
        q = q.where(Application.institute_id.in_(scope))
    apps = db.scalars(q).all()
    out = []
    for a in apps:
        res = db.scalar(
            select(MatchResult).where(MatchResult.application_id == a.id).order_by(MatchResult.id.desc()).limit(1)
        )
        out.append((a, res))
    return out


@router.get("/drives/{did}/queue")
def review_queue(did: int, db: Session = Depends(get_db), user: User = Depends(require("admin", "tpo", "coordinator"))):
    d = _get_drive(db, did, user)
    rows = _latest_results(db, d, user)
    rows.sort(key=lambda t: ({"pass": 0, "needs_verification": 1, "fail": 2}.get(t[1].gate_status if t[1] else "", 3), -(t[1].score if t[1] else 0)))
    run = None
    items = []
    for rank, (a, r) in enumerate(rows, start=1):
        if r and not run:
            run = db.get(MatchRun, r.match_run_id)
        reviews = db.scalars(select(HumanReview).where(HumanReview.application_id == a.id).order_by(HumanReview.id)).all()
        share = db.scalar(select(ConsentRecord).where(
            ConsentRecord.student_id == a.student_id, ConsentRecord.kind == "employer_share",
            ConsentRecord.employer_id == d.employer_id).order_by(ConsentRecord.id.desc()).limit(1))
        items.append({
            "application_id": a.id,
            "rank": rank if r else None,
            "status": a.status,
            "student": student_out(a.student, user),
            "share_consent": bool(share and share.granted),
            "result": None if not r else {
                "score": r.score, "gate_status": r.gate_status, "gates": r.gates, "breakdown": r.breakdown,
                "criteria": r.criteria, "confidence": r.confidence, "completeness": r.completeness,
                "warnings": r.warnings, "explanation": r.explanation, "match_run_id": r.match_run_id,
            },
            "reviews": [
                {"decision": h.decision, "reason": h.reason, "by": h.reviewer.name, "override": h.is_override,
                 "ai_score": h.ai_score, "at": h.created_at.isoformat()} for h in reviews
            ],
        })
    return {
        "drive": drive_out(d, db, user),
        "run": None if not run else {
            "id": run.id, "rubric": run.rubric_version, "parser": run.parser_version,
            "taxonomy": run.taxonomy_version, "drive_version": run.drive_version, "at": run.created_at.isoformat(),
        },
        "items": items,
        "notice": "Scores rank the review order only. Every decision is made and recorded by a person.",
    }


class ReviewIn(BaseModel):
    decision: str
    reason: str = Field(..., min_length=5, max_length=1000)


@router.post("/applications/{aid}/review")
def review(aid: int, body: ReviewIn, db: Session = Depends(get_db), user: User = Depends(require("admin", "tpo", "coordinator"))):
    if body.decision not in REVIEW_DECISIONS:
        raise HTTPException(400, f"decision must be one of {sorted(REVIEW_DECISIONS)}")
    a = db.get(Application, aid)
    if not a:
        raise HTTPException(404, "Application not found")
    ensure_institute(user, a.institute_id)
    if a.status in {"approved", "shared", "interview", "offered"} and user.role not in GROUP_WIDE:
        raise HTTPException(403, "Already approved by TPO; only the TPO can change it")
    res = db.scalar(select(MatchResult).where(MatchResult.application_id == a.id).order_by(MatchResult.id.desc()).limit(1))
    # An override is a decision that goes against what the AI evidence suggested.
    override = bool(res) and (
        (body.decision == "shortlisted" and (res.gate_status == "fail" or res.score < 40))
        or (body.decision == "not_selected" and res.gate_status != "fail" and res.score >= 60)
    )
    db.add(HumanReview(application_id=a.id, reviewer_id=user.id, decision=body.decision, reason=body.reason,
                       ai_score=res.score if res else None, is_override=override))
    before = a.status
    a.status = body.decision
    audit.log(db, user, "application.review", "application", a.id, a.institute_id, before=before,
              after=body.decision, reason=body.reason, override=override,
              match_run_id=res.match_run_id if res else None, ai_score=res.score if res else None)
    db.commit()
    return {"status": a.status, "override": override}


@router.post("/drives/{did}/approve-shortlist")
def approve_shortlist(did: int, db: Session = Depends(get_db), user: User = Depends(require("admin", "tpo"))):
    """TPO approves coordinator shortlists. Profiles are shared with the employer only
    for students who consented to share with this employer."""
    d = _get_drive(db, did, user)
    apps = db.scalars(select(Application).where(Application.drive_id == d.id, Application.status.in_(["shortlisted", "approved"]))).all()
    shared, waiting = 0, 0
    for a in apps:
        consent = db.scalar(select(ConsentRecord).where(
            ConsentRecord.student_id == a.student_id, ConsentRecord.kind == "employer_share",
            ConsentRecord.employer_id == d.employer_id).order_by(ConsentRecord.id.desc()).limit(1))
        if consent and consent.granted:
            a.status = "shared"
            shared += 1
        else:
            a.status = "approved"
            waiting += 1
        audit.log(db, user, "application.approve", "application", a.id, a.institute_id, status=a.status)
    db.commit()
    return {"shared": shared, "awaiting_student_consent": waiting}


@router.get("/employer/drives/{did}/candidates")
def employer_candidates(did: int, db: Session = Depends(get_db), user: User = Depends(require("employer"))):
    d = _get_drive(db, did, user)
    apps = db.scalars(select(Application).where(Application.drive_id == d.id, Application.status.in_(["shared", "interview", "offered"]))).all()
    out = []
    for a in apps:
        s = a.student
        res = db.scalar(select(MatchResult).where(MatchResult.application_id == a.id).order_by(MatchResult.id.desc()).limit(1))
        r = current_resume(s)
        out.append({
            "application_id": a.id,
            "status": a.status,
            "name": s.user.name,
            "institute": s.institute.code,
            "programme": s.programme.name,
            "branch": s.branch,
            "passing_year": s.passing_year,
            "cgpa": s.cgpa if s.academics_verified else None,
            "aggregate_pct": s.aggregate_pct if s.academics_verified else None,
            "academics_verified": s.academics_verified,
            "evidence": [c for c in (res.criteria if res else []) if c["status"] != "not_evidenced"],
            "resume_id": r.id if r else None,
        })
    audit.log(db, user, "employer.view_candidates", "drive", d.id, None, count=len(out))
    db.commit()
    return {"drive": {"id": d.id, "title": d.title, "employer": d.employer.name}, "candidates": out}


class StageIn(BaseModel):
    status: str


@router.post("/applications/{aid}/stage")
def set_stage(aid: int, body: StageIn, db: Session = Depends(get_db), user: User = Depends(require("admin", "tpo", "employer"))):
    if body.status not in {"interview", "offered", "not_selected"}:
        raise HTTPException(400, "status must be interview, offered or not_selected")
    a = db.get(Application, aid)
    if not a or a.status not in {"shared", "interview", "offered"}:
        raise HTTPException(404, "Application not found")
    if user.role == "employer" and a.drive.employer_id != user.employer_id:
        raise HTTPException(404, "Application not found")
    before, a.status = a.status, body.status
    audit.log(db, user, "application.stage", "application", a.id, a.institute_id, before=before, after=body.status)
    db.commit()
    return {"status": a.status}
