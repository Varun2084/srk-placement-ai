"""Core data model. Every student-linked row carries institute_id for scoping."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now():
    return datetime.now(timezone.utc)


class Institute(Base):
    __tablename__ = "institutes"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)  # SRKCESM, SRKCP
    name: Mapped[str] = mapped_column(String(200))
    programmes: Mapped[list["Programme"]] = relationship(back_populates="institute")


class Programme(Base):
    __tablename__ = "programmes"
    id: Mapped[int] = mapped_column(primary_key=True)
    institute_id: Mapped[int] = mapped_column(ForeignKey("institutes.id"))
    code: Mapped[str] = mapped_column(String(20))  # BTECH, DIPLOMA, MBA, BPHARM, DPHARM
    name: Mapped[str] = mapped_column(String(120))
    stream: Mapped[str] = mapped_column(String(20))  # engineering|polytechnic|pharmacy|management
    branches: Mapped[list] = mapped_column(JSON, default=list)
    institute: Mapped[Institute] = relationship(back_populates="programmes")


class Employer(Base):
    __tablename__ = "employers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    sector: Mapped[str] = mapped_column(String(100), default="")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(20))  # admin|tpo|coordinator|student|employer
    institute_id: Mapped[int | None] = mapped_column(ForeignKey("institutes.id"), nullable=True)
    employer_id: Mapped[int | None] = mapped_column(ForeignKey("employers.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Student(Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    institute_id: Mapped[int] = mapped_column(ForeignKey("institutes.id"), index=True)
    programme_id: Mapped[int] = mapped_column(ForeignKey("programmes.id"))
    roll_no: Mapped[str] = mapped_column(String(40))
    branch: Mapped[str] = mapped_column(String(80), default="")
    passing_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Academic fields: "verified" values come from the college ERP / coordinator.
    cgpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    aggregate_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    active_backlogs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tenth_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    twelfth_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    gap_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    academics_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_minor: Mapped[bool] = mapped_column(Boolean, default=False)
    guardian_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship()
    programme: Mapped[Programme] = relationship()
    institute: Mapped[Institute] = relationship()
    resumes: Mapped[list["ResumeDocument"]] = relationship(back_populates="student", order_by="ResumeDocument.id")


class ResumeDocument(Base):
    __tablename__ = "resumes"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    institute_id: Mapped[int] = mapped_column(ForeignKey("institutes.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    mime: Mapped[str] = mapped_column(String(100))
    stored_path: Mapped[str] = mapped_column(String(500))
    text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="uploaded")  # uploaded|parsed|failed|quarantined
    error: Mapped[str] = mapped_column(Text, default="")
    injection_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String(10), default="en")
    parser_version: Mapped[str] = mapped_column(String(20), default="")
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    student: Mapped[Student] = relationship(back_populates="resumes")
    fields: Mapped[list["ExtractedField"]] = relationship(cascade="all, delete-orphan")
    skills: Mapped[list["SkillEvidence"]] = relationship(cascade="all, delete-orphan")


class ExtractedField(Base):
    __tablename__ = "extracted_fields"
    id: Mapped[int] = mapped_column(primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), index=True)
    field: Mapped[str] = mapped_column(String(50))
    value: Mapped[str] = mapped_column(String(500))
    span_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    span_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snippet: Mapped[str] = mapped_column(String(500), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    corrected_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class SkillEvidence(Base):
    __tablename__ = "skill_evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), index=True)
    skill: Mapped[str] = mapped_column(String(100), index=True)  # canonical skill id
    label: Mapped[str] = mapped_column(String(120))
    section: Mapped[str] = mapped_column(String(40))  # skills|projects|experience|certifications|education|other
    snippet: Mapped[str] = mapped_column(String(500))
    span_start: Mapped[int] = mapped_column(Integer)
    span_end: Mapped[int] = mapped_column(Integer)


class Drive(Base):
    __tablename__ = "drives"
    id: Mapped[int] = mapped_column(primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("employers.id"))
    title: Mapped[str] = mapped_column(String(200))
    job_family: Mapped[str] = mapped_column(String(80))
    stream: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text, default="")
    institute_ids: Mapped[list] = mapped_column(JSON, default=list)
    programme_codes: Mapped[list] = mapped_column(JSON, default=list)
    branches: Mapped[list] = mapped_column(JSON, default=list)  # empty = any
    passing_years: Mapped[list] = mapped_column(JSON, default=list)
    min_cgpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_aggregate_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_backlogs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_gap_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    required_skills: Mapped[list] = mapped_column(JSON, default=list)
    preferred_skills: Mapped[list] = mapped_column(JSON, default=list)
    weights: Mapped[dict] = mapped_column(JSON, default=dict)
    weights_approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|open|closed
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    employer: Mapped[Employer] = relationship()


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    drive_id: Mapped[int] = mapped_column(ForeignKey("drives.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    institute_id: Mapped[int] = mapped_column(ForeignKey("institutes.id"), index=True)
    # applied -> (review) shortlisted | on_hold | not_selected -> approved -> shared -> interview -> offered
    status: Mapped[str] = mapped_column(String(20), default="applied")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    drive: Mapped[Drive] = relationship()
    student: Mapped[Student] = relationship()


class MatchRun(Base):
    __tablename__ = "match_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    drive_id: Mapped[int] = mapped_column(ForeignKey("drives.id"), index=True)
    drive_version: Mapped[int] = mapped_column(Integer)
    rubric_version: Mapped[str] = mapped_column(String(20))
    parser_version: Mapped[str] = mapped_column(String(20))
    taxonomy_version: Mapped[str] = mapped_column(String(20))
    criteria_snapshot: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class MatchResult(Base):
    __tablename__ = "match_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    match_run_id: Mapped[int] = mapped_column(ForeignKey("match_runs.id"), index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    resume_id: Mapped[int | None] = mapped_column(ForeignKey("resumes.id"), nullable=True)
    gates: Mapped[list] = mapped_column(JSON)
    gate_status: Mapped[str] = mapped_column(String(20))  # pass|fail|needs_verification
    score: Mapped[float] = mapped_column(Float)
    breakdown: Mapped[dict] = mapped_column(JSON)
    criteria: Mapped[list] = mapped_column(JSON)
    confidence: Mapped[str] = mapped_column(String(10))
    completeness: Mapped[float] = mapped_column(Float)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    explanation: Mapped[str] = mapped_column(Text)


class HumanReview(Base):
    __tablename__ = "human_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    ai_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_override: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    reviewer: Mapped[User] = relationship()


class ConsentRecord(Base):
    __tablename__ = "consents"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # platform|employer_share
    employer_id: Mapped[int | None] = mapped_column(ForeignKey("employers.id"), nullable=True)
    granted: Mapped[bool] = mapped_column(Boolean)
    version: Mapped[str] = mapped_column(String(40))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_role: Mapped[str] = mapped_column(String(20), default="")
    action: Mapped[str] = mapped_column(String(80), index=True)
    object_type: Mapped[str] = mapped_column(String(40))
    object_id: Mapped[str] = mapped_column(String(40))
    institute_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
