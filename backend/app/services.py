"""Application services: resume processing and match runs."""
import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit
from .ai import extract, parser
from .ai.matcher import (
    CONTEXT_SECTIONS,
    RUBRIC_VERSION,
    StudentFacts,
    completeness,
    confidence_label,
    evaluate_gates,
    explain,
    score_candidate,
)
from .ai.providers import get_similarity
from .ai.taxonomy import TAXONOMY_VERSION, skill_label
from .config import settings
from .models import (
    Application,
    Drive,
    ExtractedField,
    MatchResult,
    MatchRun,
    ResumeDocument,
    SkillEvidence,
    Student,
    User,
)


def process_resume(db: Session, student: Student, filename: str, data: bytes, actor: User) -> ResumeDocument:
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise extract.ExtractionError(f"File is larger than {settings.max_upload_mb} MB")
    kind = extract.detect_kind(filename, data)
    sha = hashlib.sha256(data).hexdigest()
    safe_name = f"{uuid.uuid4().hex}.{kind}"  # never trust the uploaded name on disk
    path = settings.upload_dir / safe_name

    doc = ResumeDocument(
        student_id=student.id,
        institute_id=student.institute_id,
        filename=filename[:255],
        sha256=sha,
        mime=kind,
        stored_path=str(path),
        parser_version=parser.PARSER_VERSION,
    )
    threat = extract.basic_malware_screen(kind, data)
    if threat:
        doc.status, doc.error, doc.is_current = "quarantined", threat, False
        db.add(doc)
        db.flush()
        audit.log(db, actor, "resume.quarantined", "resume", doc.id, student.institute_id, reason=threat)
        return doc

    path.write_bytes(data)
    try:
        text = extract.extract_text(kind, data)
    except extract.ExtractionError as e:
        doc.status, doc.error, doc.is_current = "failed", str(e), False
        db.add(doc)
        db.flush()
        audit.log(db, actor, "resume.failed", "resume", doc.id, student.institute_id, reason=str(e))
        return doc

    for old in student.resumes:
        old.is_current = False
    doc.text = text
    doc.language = extract.detect_language(text)
    doc.injection_flag = bool(extract.detect_injection(text))
    parsed = parser.parse(text)
    for f in parsed.fields:
        doc.fields.append(
            ExtractedField(field=f.field, value=f.value, span_start=f.start, span_end=f.end, snippet=f.snippet[:500], confidence=f.confidence)
        )
    for e in parsed.evidence:
        doc.skills.append(
            SkillEvidence(skill=e.skill, label=e.label, section=e.section, snippet=e.snippet[:500], span_start=e.start, span_end=e.end)
        )
    doc.status = "parsed"
    db.add(doc)
    db.flush()
    audit.log(
        db, actor, "resume.parsed", "resume", doc.id, student.institute_id,
        parser=parser.PARSER_VERSION, skills=len(parsed.evidence), injection_flag=doc.injection_flag,
    )
    return doc


def current_resume(student: Student) -> ResumeDocument | None:
    for r in reversed(student.resumes):
        if r.is_current and r.status == "parsed":
            return r
    return None


def declared_values(resume: ResumeDocument | None) -> dict:
    out = {}
    if not resume:
        return out
    for f in resume.fields:
        try:
            if f.field in {"cgpa", "aggregate_pct", "tenth_pct", "twelfth_pct"}:
                out[f.field] = float(f.value)
            elif f.field in {"active_backlogs", "passing_year"}:
                out[f.field] = int(f.value)
        except ValueError:
            continue
    return out


def evidence_dicts(resume: ResumeDocument | None) -> list[dict]:
    if not resume:
        return []
    return [
        {"skill": s.skill, "section": s.section, "snippet": s.snippet, "span_start": s.span_start, "span_end": s.span_end}
        for s in resume.skills
    ]


def drive_criteria(drive: Drive) -> dict:
    return {
        "institute_ids": drive.institute_ids,
        "programme_codes": drive.programme_codes,
        "branches": drive.branches,
        "passing_years": drive.passing_years,
        "min_cgpa": drive.min_cgpa,
        "min_aggregate_pct": drive.min_aggregate_pct,
        "max_backlogs": drive.max_backlogs,
        "max_gap_years": drive.max_gap_years,
        "required_skills": drive.required_skills,
        "preferred_skills": drive.preferred_skills,
        "weights": drive.weights,
        "description": drive.description,
    }


def run_matching(db: Session, drive: Drive, actor: User, institute_ids: list[int] | None) -> MatchRun:
    criteria = drive_criteria(drive)
    sim = get_similarity()
    run = MatchRun(
        drive_id=drive.id,
        drive_version=drive.version,
        rubric_version=RUBRIC_VERSION,
        parser_version=parser.PARSER_VERSION,
        taxonomy_version=f"{TAXONOMY_VERSION}/{sim.name}",
        criteria_snapshot=criteria,
        created_by=actor.id,
    )
    db.add(run)
    db.flush()

    q = select(Application).where(Application.drive_id == drive.id)
    if institute_ids is not None:
        q = q.where(Application.institute_id.in_(institute_ids))
    apps = db.scalars(q).all()

    resumes = {a.id: current_resume(a.student) for a in apps}

    def context_text(r):
        if not r:
            return ""
        secs = parser.split_sections(r.text)
        return " ".join(r.text[s.start:s.end] for s in secs if s.name in CONTEXT_SECTIONS)

    corpus = [context_text(r) for r in resumes.values()]
    sim.fit(corpus + [drive.description])
    jd_text = drive.description + " " + " ".join(skill_label(s) for s in drive.required_skills + drive.preferred_skills)

    for app in apps:
        st = app.student
        r = resumes[app.id]
        declared = declared_values(r)
        facts = StudentFacts(
            institute_id=st.institute_id,
            programme_code=st.programme.code,
            branch=st.branch,
            passing_year=st.passing_year or declared.get("passing_year"),
            cgpa=st.cgpa,
            aggregate_pct=st.aggregate_pct,
            active_backlogs=st.active_backlogs,
            gap_years=st.gap_years,
            verified=st.academics_verified,
            declared=declared,
        )
        gates, gate_status = evaluate_gates(criteria, facts)
        ev = evidence_dicts(r)
        ctx = sim.similarity(jd_text, context_text(r)) if r else 0.0
        score, breakdown, crit = score_candidate(criteria, ev, ctx)
        sections = {s.name for s in parser.split_sections(r.text)} if r else set()
        complete = completeness(facts, sections, len({e["skill"] for e in ev}), r is not None)
        warnings = []
        if not r:
            warnings.append("no parsed resume on file")
        if r and r.injection_flag:
            warnings.append("resume contains instruction-like text aimed at screening software; review manually")
        if not st.academics_verified:
            warnings.append("academic record not yet verified by coordinator")
        if r and not ({"projects", "experience"} & sections):
            warnings.append("no projects or internship section detected")
        db.add(
            MatchResult(
                match_run_id=run.id,
                application_id=app.id,
                resume_id=r.id if r else None,
                gates=gates,
                gate_status=gate_status,
                score=score,
                breakdown=breakdown,
                criteria=crit,
                confidence=confidence_label(complete, bool(r and r.injection_flag)),
                completeness=complete,
                warnings=warnings,
                explanation=explain(gate_status, gates, crit, warnings),
            )
        )
    audit.log(db, actor, "match.run", "drive", drive.id, None, run_id=run.id, applications=len(apps),
              rubric=RUBRIC_VERSION, parser=parser.PARSER_VERSION)
    return run
