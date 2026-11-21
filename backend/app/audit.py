from sqlalchemy.orm import Session

from .models import AuditEvent, User


def log(
    db: Session,
    actor: User | None,
    action: str,
    object_type: str,
    object_id,
    institute_id: int | None = None,
    **detail,
) -> None:
    db.add(
        AuditEvent(
            actor_id=actor.id if actor else None,
            actor_role=actor.role if actor else "system",
            action=action,
            object_type=object_type,
            object_id=str(object_id),
            institute_id=institute_id,
            detail=detail,
        )
    )
