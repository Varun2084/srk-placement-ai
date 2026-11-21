import csv
import io
from collections import Counter, defaultdict

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import Application, AuditEvent, HumanReview, MatchResult, Student, User
from ..security import require, scoped_institute_ids
from ..services import current_resume

router = APIRouter(prefix="/api", tags=["reports"])

FUNNEL = ["applied", "shortlisted", "approved", "shared", "interview", "offered"]
REACHED = {
    "applied": set(FUNNEL) | {"on_hold", "not_selected"},
    "shortlisted": {"shortlisted", "approved", "shared", "interview", "offered"},
    "approved": {"approved", "shared", "interview", "offered"},
    "shared": {"shared", "interview", "offered"},
    "interview": {"interview", "offered"},
    "offered": {"offered"},
}


@router.get("/reports/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(require("admin", "tpo", "coordinator"))):
    scope = scoped_institute_ids(user)
    sq = select(Student)
    aq = select(Application)
    if scope is not None:
        sq = sq.where(Student.institute_id.in_(scope))
        aq = aq.where(Application.institute_id.in_(scope))
    students = db.scalars(sq).all()
    apps = db.scalars(aq).all()

    by_prog = defaultdict(lambda: {"students": 0, "consented": 0, "resume_parsed": 0, "verified": 0, "offered": 0})
    offered_students = {a.student_id for a in apps if a.status == "offered"}
    for s in students:
        key = f"{s.institute.code} · {s.programme.code}"
        row = by_prog[key]
        row["students"] += 1
        row["consented"] += bool(s.consent_at)
        row["resume_parsed"] += current_resume(s) is not None
        row["verified"] += s.academics_verified
        row["offered"] += s.id in offered_students

    statuses = Counter(a.status for a in apps)
    funnel = [{"stage": st, "count": sum(c for k, c in statuses.items() if k in REACHED[st])} for st in FUNNEL]

    app_ids = [a.id for a in apps]
    reviews = db.scalars(select(HumanReview).where(HumanReview.application_id.in_(app_ids))).all() if app_ids else []
    overrides = sum(r.is_override for r in reviews)

    # Fairness monitor: shortlist rate by institute and programme among reviewed applications.
    groups = defaultdict(lambda: {"reviewed": 0, "shortlisted": 0})
    for a in apps:
        if a.status in {"applied"}:
            continue
        g = groups[f"{a.student.institute.code} · {a.student.programme.code}"]
        g["reviewed"] += 1
        g["shortlisted"] += a.status in REACHED["shortlisted"]
    fairness = [
        {"group": k, **v, "rate": round(v["shortlisted"] / v["reviewed"], 2) if v["reviewed"] else None}
        for k, v in sorted(groups.items())
    ]
    rates = [f["rate"] for f in fairness if f["rate"] is not None and f["reviewed"] >= 5]
    flag = bool(rates) and max(rates) > 0 and min(rates) / max(rates) < 0.8

    return {
        "programmes": [{"group": k, **v} for k, v in sorted(by_prog.items())],
        "funnel": funnel,
        "reviews": {"total": len(reviews), "overrides": overrides},
        "fairness": {"groups": fairness, "four_fifths_flag": flag,
                     "note": "Flag means one group's shortlist rate is below 80% of the highest; investigate, do not auto-correct."},
    }


@router.get("/reports/placements.csv")
def placements_csv(db: Session = Depends(get_db), user: User = Depends(require("admin", "tpo", "coordinator"))):
    scope = scoped_institute_ids(user)
    q = select(Application)
    if scope is not None:
        q = q.where(Application.institute_id.in_(scope))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["institute", "programme", "branch", "roll_no", "student", "employer", "drive", "status"])
    for a in db.scalars(q).all():
        s = a.student
        w.writerow([s.institute.code, s.programme.code, s.branch, s.roll_no, s.user.name, a.drive.employer.name, a.drive.title, a.status])
    audit.log(db, user, "export.placements_csv", "report", "placements", None)
    db.commit()
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=placements.csv"})


@router.get("/audit")
def audit_log(limit: int = 200, db: Session = Depends(get_db), user: User = Depends(require("admin", "tpo"))):
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(min(limit, 1000))).all()
    names = {u.id: u.name for u in db.scalars(select(User)).all()}
    return [
        {"id": e.id, "at": e.at.isoformat(), "actor": names.get(e.actor_id, "system"), "role": e.actor_role,
         "action": e.action, "object": f"{e.object_type}:{e.object_id}", "institute_id": e.institute_id, "detail": e.detail}
        for e in rows
    ]
