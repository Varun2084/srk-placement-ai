"""Student readiness report: how well the resume evidences each job family of the programme."""
from .matcher import skill_strength
from .taxonomy import TAXONOMY, job_families


def readiness_report(stream: str, evidence: list[dict]) -> dict:
    families = []
    for fid, fam in job_families(stream).items():
        core = [skill_strength(s, evidence) for s in fam["core"]]
        opt = [skill_strength(s, evidence) for s in fam["optional"]]
        core_score = sum(c["strength"] for c in core) / len(core) if core else 0
        opt_score = sum(c["strength"] for c in opt) / len(opt) if opt else 0
        pct = round((0.8 * core_score + 0.2 * opt_score) * 100)
        gaps = []
        for c in core + opt:
            if c["status"] == "not_evidenced" or c["strength"] < 0.8:
                gaps.append(
                    {
                        "skill": c["label"],
                        "priority": "core" if c in core else "optional",
                        "status": c["status"] if c["status"] != "evidenced" else "listed_only",
                        "action": TAXONOMY["skills"][c["skill"]]["suggest"]
                        if c["status"] == "not_evidenced"
                        else f'Add a project, internship or certificate that shows {c["label"]}',
                    }
                )
        families.append(
            {
                "job_family": fid,
                "label": fam["label"],
                "readiness_pct": pct,
                "band": "ready" if pct >= 70 else "developing" if pct >= 40 else "early",
                "core": core,
                "gaps": gaps,
            }
        )
    families.sort(key=lambda f: -f["readiness_pct"])
    return {
        "stream": stream,
        "families": families,
        "note": "Readiness reflects what the resume shows, not the student's ability. "
        "It is advice for the student and mentor and is never shared with employers.",
    }
