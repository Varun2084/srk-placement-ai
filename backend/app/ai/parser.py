"""Deterministic resume parser: sections, key fields and skill evidence with source spans.

Every extracted value keeps the character span it came from so a reviewer can see,
and correct, exactly where it was read.
"""
import re
from dataclasses import dataclass, field

from .taxonomy import TAXONOMY

PARSER_VERSION = "parser-1.0"

SECTION_HEADINGS = {
    "education": ["education", "academic qualification", "academic qualifications", "academics", "educational qualification", "qualification"],
    "skills": ["skills", "technical skills", "key skills", "core competencies", "skill set", "software skills", "professional skills"],
    "projects": ["projects", "academic projects", "project work", "major project", "minor project", "final year project"],
    "experience": ["experience", "work experience", "internship", "internships", "industrial training", "training", "summer internship", "vocational training", "practical training", "employment history"],
    "certifications": ["certifications", "certificates", "courses", "certification", "online courses", "workshops"],
    "achievements": ["achievements", "awards", "extra curricular", "extra-curricular activities", "activities", "positions of responsibility"],
    "personal": ["personal details", "personal information", "declaration", "hobbies", "languages known"],
    "summary": ["summary", "objective", "career objective", "profile", "about me"],
}

# Evidence strength per section: work you did counts more than a keyword list.
SECTION_WEIGHT = {
    "projects": 1.0,
    "experience": 1.0,
    "certifications": 0.8,
    "skills": 0.6,
    "education": 0.5,
    "achievements": 0.5,
    "summary": 0.4,
    "other": 0.4,
    "personal": 0.0,
}


@dataclass
class Section:
    name: str
    start: int
    end: int


@dataclass
class Field:
    field: str
    value: str
    start: int | None
    end: int | None
    snippet: str
    confidence: float


@dataclass
class Evidence:
    skill: str
    label: str
    section: str
    snippet: str
    start: int
    end: int


@dataclass
class ParsedResume:
    sections: list[Section]
    fields: list[Field] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)


def _heading_pattern():
    names = sorted({h for hs in SECTION_HEADINGS.values() for h in hs}, key=len, reverse=True)
    alt = "|".join(re.escape(n) for n in names)
    return re.compile(rf"^[ \t]*(?:[#*\-\d.]+\s*)?({alt})\s*[:\-]?\s*$", re.I | re.M)


_HEADING_RE = _heading_pattern()


def split_sections(text: str) -> list[Section]:
    marks = []
    for m in _HEADING_RE.finditer(text):
        heading = m.group(1).lower()
        for name, hs in SECTION_HEADINGS.items():
            if heading in hs:
                marks.append((m.start(), name))
                break
    sections = []
    if not marks or marks[0][0] > 0:
        sections.append(Section("other", 0, marks[0][0] if marks else len(text)))
    for i, (pos, name) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        sections.append(Section(name, pos, end))
    return sections


def section_at(sections: list[Section], pos: int) -> str:
    for s in sections:
        if s.start <= pos < s.end:
            return s.name
    return "other"


def _snippet(text: str, start: int, end: int, pad: int = 90) -> str:
    """The line holding the match, trimmed to whole words if the line is long."""
    a = text.rfind("\n", 0, start) + 1
    b = text.find("\n", end)
    b = len(text) if b == -1 else b
    pre, post = "", ""
    if start - a > pad:
        a = text.find(" ", start - pad, start) + 1 or start - pad
        pre = "…"
    if b - end > pad:
        cut = text.rfind(" ", end, end + pad)
        b = cut if cut > end else end + pad
        post = "…"
    return pre + re.sub(r"\s+", " ", text[a:b]).strip(" -•*") + post


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}\b")
CGPA_RE = re.compile(r"(?:cgpa|sgpa|cpi|gpa)\s*[:\-]?\s*(?:of\s*)?(\d{1,2}(?:\.\d{1,2})?)\s*(?:/\s*10)?", re.I)
CGPA_RE2 = re.compile(r"(\d(?:\.\d{1,2})?)\s*/\s*10\b")
PCT_RE = re.compile(r"(\d{2}(?:\.\d{1,2})?)\s*%")
YEAR_RE = re.compile(r"\b(20[1-3]\d)\b")
BACKLOG_RE = re.compile(r"(\d+|no|nil|zero)\s+(?:active\s+)?backlogs?|backlogs?\s*[:\-]\s*(\d+|nil|none|no)", re.I)


def extract_fields(text: str, sections: list[Section]) -> list[Field]:
    out: list[Field] = []

    # Name: first non-empty line that looks like a name (2-4 alphabetic words).
    for m in re.finditer(r"^[ \t]*([A-Za-z][A-Za-z.]+(?:[ \t]+[A-Za-z][A-Za-z.]+){1,3})[ \t]*$", text, re.M):
        cand = m.group(1)
        if cand.lower() in {h for hs in SECTION_HEADINGS.values() for h in hs} or cand.lower().startswith(("curriculum", "resume")):
            continue
        out.append(Field("name", cand.strip(), m.start(1), m.end(1), cand, 0.7))
        break

    if m := EMAIL_RE.search(text):
        out.append(Field("email", m.group(0), m.start(), m.end(), m.group(0), 0.95))
    if m := PHONE_RE.search(text):
        out.append(Field("phone", re.sub(r"[\s-]", "", m.group(0)), m.start(), m.end(), m.group(0), 0.9))

    m = CGPA_RE.search(text) or CGPA_RE2.search(text)
    if m:
        val = float(m.group(1))
        if 0 < val <= 10:
            out.append(Field("cgpa", f"{val:.2f}", m.start(1), m.end(1), _snippet(text, m.start(), m.end()), 0.8))

    # Percentages inside the education section: label the 10th/12th/diploma lines.
    edu = [s for s in sections if s.name == "education"]
    scope = edu[0] if edu else Section("other", 0, len(text))
    for line_m in re.finditer(r"[^\n]+", text[scope.start:scope.end]):
        line = line_m.group(0)
        pct = PCT_RE.search(line)
        if not pct:
            continue
        low = line.lower()
        label = None
        if re.search(r"\b(10th|x\b|ssc|high school|matric)", low):
            label = "tenth_pct"
        elif re.search(r"\b(12th|xii|hsc|higher secondary|intermediate)", low):
            label = "twelfth_pct"
        elif re.search(r"diploma|b\.?\s?tech|b\.?\s?e\b|b\.?\s?pharm|d\.?\s?pharm|mba|degree|graduation|aggregate", low):
            label = "aggregate_pct"
        if label and float(pct.group(1)) <= 100:
            s = scope.start + line_m.start() + pct.start(1)
            out.append(Field(label, pct.group(1), s, s + len(pct.group(1)), line.strip()[:200], 0.75))

    years = [int(y) for y in YEAR_RE.findall(text[scope.start:scope.end])]
    if years:
        y = max(years)
        idx = text.find(str(y), scope.start)
        out.append(Field("passing_year", str(y), idx, idx + 4, _snippet(text, idx, idx + 4), 0.6))

    if m := BACKLOG_RE.search(text):
        raw = (m.group(1) or m.group(2) or "").lower()
        n = 0 if raw in {"no", "nil", "zero", "none"} else int(raw)
        out.append(Field("active_backlogs", str(n), m.start(), m.end(), m.group(0), 0.7))

    return out


def extract_skills(text: str, sections: list[Section]) -> list[Evidence]:
    low = text.lower()
    found: list[Evidence] = []
    for sid, info in TAXONOMY["skills"].items():
        for alias in info["aliases"]:
            pattern = r"(?<![\w+#.])" + re.escape(alias) + r"(?![\w+#])"
            for m in re.finditer(pattern, low):
                sec = section_at(sections, m.start())
                if sec == "personal":
                    continue
                found.append(Evidence(sid, info["label"], sec, _snippet(text, m.start(), m.end()), m.start(), m.end()))
    # Keep the strongest piece of evidence per (skill, section), max 3 per skill.
    best: dict[tuple[str, str], Evidence] = {}
    for e in found:
        best.setdefault((e.skill, e.section), e)
    per_skill: dict[str, list[Evidence]] = {}
    for e in sorted(best.values(), key=lambda e: -SECTION_WEIGHT.get(e.section, 0.4)):
        per_skill.setdefault(e.skill, [])
        if len(per_skill[e.skill]) < 3:
            per_skill[e.skill].append(e)
    return [e for lst in per_skill.values() for e in lst]


def parse(text: str) -> ParsedResume:
    sections = split_sections(text)
    return ParsedResume(sections, extract_fields(text, sections), extract_skills(text, sections))
