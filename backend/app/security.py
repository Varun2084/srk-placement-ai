"""Authentication, role checks and institute scoping."""
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Student, User

ROLES = {"admin", "tpo", "coordinator", "student", "employer"}
GROUP_WIDE = {"admin", "tpo"}
STAFF = {"admin", "tpo", "coordinator"}

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"pbkdf2${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 200_000)
    return hmac.compare_digest(digest.hex(), digest_hex)


def create_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiry_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User inactive")
    return user


def require(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot do this")
        return user

    return dep


def can_see_institute(user: User, institute_id: int) -> bool:
    return user.role in GROUP_WIDE or (user.role == "coordinator" and user.institute_id == institute_id)


def ensure_institute(user: User, institute_id: int) -> None:
    if not can_see_institute(user, institute_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Outside your institute scope")


def ensure_student_access(user: User, student: Student) -> None:
    """Students see themselves; coordinators their institute; TPO/admin everyone."""
    if user.role == "student":
        if student.user_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your profile")
        return
    if user.role in STAFF:
        ensure_institute(user, student.institute_id)
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")


def scoped_institute_ids(user: User, requested: list[int] | None = None) -> list[int] | None:
    """None means all institutes (group-wide roles)."""
    if user.role in GROUP_WIDE:
        return requested or None
    if user.role == "coordinator":
        return [user.institute_id]
    return []
