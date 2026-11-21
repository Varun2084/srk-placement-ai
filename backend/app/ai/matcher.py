"""Eligibility gates + evidence-based scoring + explanations.

Design rules (from the roadmap):
- Gates use only objective, job-related fields. Missing data is "needs verification", never a fail.
- The score is a review aid. Nothing here rejects a student; a person decides.
- A skill not found is "not evidenced", not "absent".
- Protected attributes are never inputs: this module never reads gender, category, religion,
  photo, home town or marital status.
"""
from dataclasses import dataclass

from .parser import SECTION_WEIGHT
from .taxonomy import related, skill_label

RUBRIC_VERSION = "rubric-1.0"
DEFAULT_WEIGHTS = {"required": 60, "preferred": 20, "context": 20}
CONTEXT_SECTIONS = {"projects", "experience", "certifications"}


@dataclass
class StudentFacts:
    institute_id: int
    programme_code: str
    branch: str
    passing_year: int | None
    cgpa: float | None
    aggregate_pct: float | None
    active_backlogs: int | None
    gap_years: int | None
    verified: bool
    declared: dict  # values read from the resume, e.g. {"cgpa": 7.8}


def _gate(name, status, detail):
    return {"gate": name, "status": status, "detail": detail}


def _numeric_gate(name, label, threshold, verified_value, declared_value, verified, higher_is_better=True):
    if threshold is None:
        return None
    value, source = (verified_value, "verified") if (verified and verified_value is not None) else (None, None)
    if value is None and verified_value is not None:
        value, source = verified_value, "college record, unverified"
    if value is None and declared_value is not None:
        value, source = declared_value, "resume (student-declared)"
    if value is None:
        return _gate(name, "unknown", f"{label} not available; needs verification")
    ok = value >= threshold if higher_is_better else value <= threshold
    cmp = "≥" if higher_is_better else "≤"
    if not ok:
        return _gate(name, "fail", f"{label} {value} vs required {cmp} {threshold} ({source})")
    status = "pass" if source == "verified" else "unverified"
    return _gate(name, status, f"{label} {value} {cmp} {threshold} ({source})")


def evaluate_gates(drive: dict, s: StudentFacts) -> tuple[list[dict], str]:
    gates = []
    if drive.get("institute_ids"):
        ok = s.institute_id in drive["institute_ids"]
        gates.append(_gate("institute", "pass" if ok else "fail", "Institute is in this drive" if ok else "Institute not in this drive"))
    if drive.get("programme_codes"):
        ok = s.programme_code in drive["programme_codes"]
        gates.append(_gate("programme", "pass" if ok else "fail", f"Programme {s.programme_code}"))
    if drive.get("branches"):
        wanted = [b.lower() for b in drive["branches"]]
        ok = bool(s.branch) and any(w in s.branch.lower() or s.branch.lower() in w for w in wanted)
        gates.append(_gate("branch", "pass" if ok else ("unknown" if not s.branch else "fail"), f"Branch {s.branch or 'not set'}"))
    if drive.get("passing_years"):
        if s.passing_year is None:
            gates.append(_gate("passing_year", "unknown", "Passing year not set"))
        else:
            ok = s.passing_year in drive["passing_years"]
            gates.append(_gate("passing_year", "pass" if ok else "fail", f"Passing year {s.passing_year}"))
    d = s.declared
    for g in (
        _numeric_gate("cgpa", "CGPA", drive.get("min_cgpa"), s.cgpa, d.get("cgpa"), s.verified),
        _numeric_gate("aggregate_pct", "Aggregate %", drive.get("min_aggregate_pct"), s.aggregate_pct, d.get("aggregate_pct"), s.verified),
        _numeric_gate("backlogs", "Active backlogs", drive.get("max_backlogs"), s.active_backlogs, d.get("active_backlogs"), s.verified, higher_is_better=False),
        _numeric_gate("gap_years", "Gap years", drive.get("max_gap_years"), s.gap_years, None, s.verified, higher_is_better=False),
    ):
        if g:
            gates.append(g)
    statuses = {g["status"] for g in gates}
    if "fail" in statuses:
        overall = "fail"
    elif statuses & {"unknown", "unverified"}:
        overall = "needs_verification"
    else:
        overall = "pass"
    return gates, overall


def skill_strength(skill: str, evidence: list[dict]) -> dict:
    direct = [e for e in evidence if e["skill"] == skill]
    if direct:
        best = max(direct, key=lambda e: SECTION_WEIGHT.get(e["section"], 0.4))
        return {
            "skill": skill,
            "label": skill_label(skill),
            "status": "evidenced",
            "strength": SECTION_WEIGHT.get(best["section"], 0.4),
            "section": best["section"],
            "snippet": best["snippet"],
            "resume_span": [best["span_start"], best["span_end"]],
        }
    rel = [e for e in evidence if e["skill"] in related(skill)]
    if rel:
        best = max(rel, key=lambda e: SECTION_WEIGHT.get(e["section"], 0.4))
        return {
            "skill": skill,
            "label": skill_label(skill),
            "status": "related",
            "strength": round(0.4 * SECTION_WEIGHT.get(best["section"], 0.4), 2),
            "section": best["section"],
            "snippet": best["snippet"],
            "related_skill": skill_label(best["skill"]),
            "resume_span": [best["span_start"], best["span_end"]],
        }
    return {"skill": skill, "label": skill_label(skill), "status": "not_evidenced", "strength": 0.0}


def score_candidate(drive: dict, evidence: list[dict], context_similarity: float) -> tuple[float, dict, list[dict]]:
    weights = {**DEFAULT_WEIGHTS, **(drive.get("weights") or {})}
    total_w = sum(weights.values()) or 1
    req = [skill_strength(s, evidence) | {"kind": "required"} for s in drive.get("required_skills", [])]
    pref = [skill_strength(s, evidence) | {"kind": "preferred"} for s in drive.get("preferred_skills", [])]

    def mean(items):
        return sum(i["strength"] for i in items) / len(items) if items else 0.0

    # Similarity of TF-IDF vectors is small in absolute terms; 0.35+ is a strong overlap.
    ctx = min(1.0, context_similarity / 0.35)
    parts = {
        "required": round(weights["required"] * mean(req) * 100 / total_w, 1),
        "preferred": round(weights["preferred"] * mean(pref) * 100 / total_w, 1) if pref else 0.0,
        "context": round(weights["context"] * ctx * 100 / total_w, 1),
    }
    if not pref:  # redistribute so a drive without preferred skills is not capped
        scale = total_w / (total_w - weights["preferred"])
        parts = {k: round(v * scale, 1) for k, v in parts.items()}
    score = round(sum(parts.values()), 1)
    breakdown = {"weights": weights, "parts": parts, "context_similarity": round(context_similarity, 3)}
    return score, breakdown, req + pref


def completeness(facts: StudentFacts, sections: set[str], evidence_count: int, has_resume: bool) -> float:
    checks = [
        has_resume,
        facts.cgpa is not None or facts.aggregate_pct is not None or "cgpa" in facts.declared,
        facts.passing_year is not None,
        "projects" in sections or "experience" in sections,
        evidence_count >= 3,
        facts.verified,
    ]
    return round(sum(checks) / len(checks), 2)


def confidence_label(complete: float, injection: bool) -> str:
    if injection:
        return "low"
    return "high" if complete >= 0.8 else "medium" if complete >= 0.5 else "low"


def explain(gate_status: str, gates: list[dict], criteria: list[dict], warnings: list[str]) -> str:
    strong = [c["label"] for c in criteria if c["kind"] == "required" and c["status"] == "evidenced" and c["strength"] >= 0.8]
    listed = [c["label"] for c in criteria if c["kind"] == "required" and c["status"] == "evidenced" and c["strength"] < 0.8]
    rel = [f'{c["label"]} (via {c["related_skill"]})' for c in criteria if c["kind"] == "required" and c["status"] == "related"]
    missing = [c["label"] for c in criteria if c["kind"] == "required" and c["status"] == "not_evidenced"]
    lines = []
    if gate_status == "fail":
        failed = "; ".join(g["detail"] for g in gates if g["status"] == "fail")
        lines.append(f"Does not meet a drive eligibility rule: {failed}. A coordinator must confirm before any decision.")
    elif gate_status == "needs_verification":
        lines.append("Eligibility depends on data that still needs verification.")
    else:
        lines.append("Meets all eligibility rules on verified data.")
    if strong:
        lines.append("Shown in projects, internships or certificates: " + ", ".join(strong) + ".")
    if listed:
        lines.append("Listed as skills without project evidence: " + ", ".join(listed) + ".")
    if rel:
        lines.append("Related evidence only: " + ", ".join(rel) + ".")
    if missing:
        lines.append("Not evidenced in the resume (may still have the skill): " + ", ".join(missing) + ".")
    if warnings:
        lines.append("Check: " + "; ".join(warnings) + ".")
    return " ".join(lines)
