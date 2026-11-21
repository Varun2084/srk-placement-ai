from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..ai.taxonomy import TAXONOMY
from ..db import get_db
from ..models import Institute, Programme, User
from ..security import create_token, current_user, verify_password

router = APIRouter(prefix="/api", tags=["auth"])


class LoginIn(BaseModel):
    email: str
    password: str


def user_out(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "role": u.role,
        "institute_id": u.institute_id,
        "employer_id": u.employer_id,
    }


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower().strip()))
    if not user or not user.active or not verify_password(body.password, user.password_hash):
        audit.log(db, None, "auth.failed", "user", body.email[:60])
        db.commit()
        raise HTTPException(401, "Wrong email or password")
    audit.log(db, user, "auth.login", "user", user.id, user.institute_id)
    db.commit()
    return {"token": create_token(user), "user": user_out(user)}


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return user_out(user)


@router.get("/meta")
def meta(db: Session = Depends(get_db), user: User = Depends(current_user)):
    insts = db.scalars(select(Institute)).all()
    progs = db.scalars(select(Programme)).all()
    return {
        "institutes": [{"id": i.id, "code": i.code, "name": i.name} for i in insts],
        "programmes": [
            {"id": p.id, "institute_id": p.institute_id, "code": p.code, "name": p.name, "stream": p.stream, "branches": p.branches}
            for p in progs
        ],
        "skills": {k: v["label"] for k, v in TAXONOMY["skills"].items()},
        "job_families": TAXONOMY["job_families"],
    }
