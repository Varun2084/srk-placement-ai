"""Account management: staff/employer accounts and bulk student import from CSV."""
import csv
import io
import secrets

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import Employer, Institute, Programme, Student, User
from ..security import current_user, hash_password, require, verify_password

router = APIRouter(prefix="/api", tags=["admin"])

CSV_COLUMNS = ["name", "email", "roll_no", "institute", "programme", "branch", "passing_year",
               "cgpa", "aggregate_pct", "active_backlogs", "date_of_birth_under_18"]


def temp_password() -> str:
    return secrets.token_urlsafe(9)


class PasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


@router.post("/auth/change-password")
def change_password(body: PasswordIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(400, "Current password is wrong")
    user.password_hash = hash_password(body.new_password)
    audit.log(db, user, "auth.password_changed", "user", user.id, user.institute_id)
    db.commit()
    return {"ok": True}


class UserIn(BaseModel):
    email: str = Field(..., min_length=5, max_length=200)
    name: str = Field(..., min_length=2, max_length=200)
    role: str
    institute_id: int | None = None
    employer_name: str | None = None


@router.get("/admin/users")
def list_users(db: Session = Depends(get_db), user: User = Depends(require("admin", "tpo"))):
    rows = db.scalars(select(User).where(User.role != "student").order_by(User.role, User.name)).all()
    emps = {e.id: e.name for e in db.scalars(select(Employer)).all()}
    return [{"id": u.id, "email": u.email, "name": u.name, "role": u.role, "institute_id": u.institute_id,
             "employer": emps.get(u.employer_id), "active": u.active} for u in rows]


@router.post("/admin/users")
def create_user(body: UserIn, db: Session = Depends(get_db), actor: User = Depends(require("admin", "tpo"))):
    if body.role not in {"admin", "tpo", "coordinator", "employer"}:
        raise HTTPException(400, "role must be admin, tpo, coordinator or employer (students: use CSV import)")
    if body.role == "admin" and actor.role != "admin":
        raise HTTPException(403, "Only an admin can create admins")
    email = body.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    u = User(email=email, name=body.name.strip(), role=body.role, password_hash="")
    if body.role == "coordinator":
        if not body.institute_id or not db.get(Institute, body.institute_id):
            raise HTTPException(400, "Coordinators need an institute")
        u.institute_id = body.institute_id
    if body.role == "employer":
        if not body.employer_name:
            raise HTTPException(400, "Employer accounts need employer_name")
        emp = db.scalar(select(Employer).where(Employer.name == body.employer_name.strip()))
        if not emp:
            emp = Employer(name=body.employer_name.strip())
            db.add(emp)
            db.flush()
        u.employer_id = emp.id
    pw = temp_password()
    u.password_hash = hash_password(pw)
    db.add(u)
    db.flush()
    audit.log(db, actor, "user.create", "user", u.id, u.institute_id, role=u.role)
    db.commit()
    return {"id": u.id, "email": u.email, "temporary_password": pw}


@router.post("/admin/users/{uid}/reset-password")
def reset_password(uid: int, db: Session = Depends(get_db), actor: User = Depends(require("admin", "tpo", "coordinator"))):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "User not found")
    if actor.role == "coordinator" and not (u.role == "student" and u.institute_id == actor.institute_id):
        raise HTTPException(403, "Coordinators can reset passwords of their own students only")
    if u.role == "admin" and actor.role != "admin":
        raise HTTPException(403, "Only an admin can reset an admin")
    pw = temp_password()
    u.password_hash = hash_password(pw)
    audit.log(db, actor, "user.password_reset", "user", u.id, u.institute_id)
    db.commit()
    return {"email": u.email, "temporary_password": pw}


@router.get("/admin/students/template.csv")
def template(user: User = Depends(require("admin", "tpo", "coordinator"))):
    sample = ",".join(CSV_COLUMNS) + "\nRahul Tiwari,rahul.tiwari@example.com,SRK23CS001,SRKCESM,BTECH,Computer Science,2027,7.8,,0,no\n"
    return StreamingResponse(iter([sample]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=students_template.csv"})


def _num(v: str, kind=float):
    v = (v or "").strip()
    return kind(v) if v else None


@router.post("/admin/students/import")
async def import_students(file: UploadFile = File(...), db: Session = Depends(get_db),
                          actor: User = Depends(require("admin", "tpo", "coordinator"))):
    """Bulk-create student accounts from the college list. Academic values in the CSV come
    from the college record, so they are marked verified. Returns a CSV of login passwords."""
    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    missing = {"name", "email", "roll_no", "institute", "programme"} - set(reader.fieldnames or [])
    if missing:
        raise HTTPException(400, f"CSV is missing columns: {sorted(missing)}")
    insts = {i.code.upper(): i for i in db.scalars(select(Institute)).all()}
    progs = {(p.institute_id, p.code.upper()): p for p in db.scalars(select(Programme)).all()}
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["row", "email", "status", "temporary_password"])
    created = skipped = 0
    for n, row in enumerate(reader, start=2):
        email = (row.get("email") or "").lower().strip()
        try:
            inst = insts.get((row.get("institute") or "").upper().strip())
            if not inst:
                raise ValueError("unknown institute (use SRKCESM or SRKCP)")
            if actor.role == "coordinator" and inst.id != actor.institute_id:
                raise ValueError("outside your institute")
            prog = progs.get((inst.id, (row.get("programme") or "").upper().strip()))
            if not prog:
                raise ValueError("unknown programme for this institute")
            if not email or "@" not in email:
                raise ValueError("invalid email")
            if db.scalar(select(User).where(User.email == email)):
                skipped += 1
                w.writerow([n, email, "already exists", ""])
                continue
            pw = temp_password()
            u = User(email=email, name=(row.get("name") or "").strip()[:200], role="student",
                     institute_id=inst.id, password_hash=hash_password(pw))
            db.add(u)
            db.flush()
            cgpa, pct, bl = _num(row.get("cgpa")), _num(row.get("aggregate_pct")), _num(row.get("active_backlogs"), int)
            db.add(Student(
                user_id=u.id, institute_id=inst.id, programme_id=prog.id,
                roll_no=(row.get("roll_no") or "").strip()[:40], branch=(row.get("branch") or "").strip()[:80],
                passing_year=_num(row.get("passing_year"), int), cgpa=cgpa, aggregate_pct=pct, active_backlogs=bl,
                academics_verified=any(v is not None for v in (cgpa, pct, bl)),
                is_minor=(row.get("date_of_birth_under_18") or "").strip().lower() in {"yes", "y", "1", "true"},
            ))
            created += 1
            w.writerow([n, email, "created", pw])
        except ValueError as e:
            w.writerow([n, email, f"error: {e}", ""])
    audit.log(db, actor, "students.import", "students", "csv", actor.institute_id, created=created, skipped=skipped)
    db.commit()
    return {"created": created, "skipped": skipped, "result_csv": out.getvalue()}
