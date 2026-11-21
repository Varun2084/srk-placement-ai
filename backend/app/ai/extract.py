"""Text extraction from uploaded files. Treats every file as untrusted input."""
import io
import re

ALLOWED = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
}
EXT_TO_KIND = {".pdf": "pdf", ".docx": "docx", ".txt": "txt"}


class ExtractionError(Exception):
    pass


def detect_kind(filename: str, data: bytes) -> str:
    """Decide the file type from its magic bytes, not just its name."""
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"PK\x03\x04") and filename.lower().endswith(".docx"):
        return "docx"
    if filename.lower().endswith(".txt"):
        try:
            data.decode("utf-8")
            return "txt"
        except UnicodeDecodeError:
            pass
    raise ExtractionError("Unsupported or mismatched file type. Upload a PDF, DOCX or TXT resume.")


def basic_malware_screen(kind: str, data: bytes) -> str | None:
    """Cheap structural checks. Plug a real scanner (e.g. ClamAV) in production."""
    if kind == "pdf" and re.search(rb"/(JavaScript|JS|Launch|EmbeddedFile)\b", data):
        return "PDF contains active content (JavaScript/Launch/EmbeddedFile)"
    if kind == "docx" and b"vbaProject.bin" in data:
        return "Document contains macros"
    return None


def extract_text(kind: str, data: bytes) -> str:
    if kind == "pdf":
        import pdfplumber

        parts = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            if len(pdf.pages) > 10:
                raise ExtractionError("Resume has more than 10 pages")
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        text = "\n".join(parts)
        if len(text.strip()) < 30:
            # Scanned resume: OCR hook. Install Tesseract and enable here.
            raise ExtractionError(
                "No text layer found (scanned PDF). Upload a text-based PDF or enable OCR."
            )
        return text
    if kind == "docx":
        import docx

        d = docx.Document(io.BytesIO(data))
        lines = [p.text for p in d.paragraphs]
        for table in d.tables:
            for row in table.rows:
                lines.append(" | ".join(c.text for c in row.cells))
        return "\n".join(lines)
    if kind == "txt":
        return data.decode("utf-8", errors="replace")
    raise ExtractionError("Unsupported type")


def detect_language(text: str) -> str:
    devanagari = len(re.findall(r"[ऀ-ॿ]", text))
    letters = len(re.findall(r"[A-Za-zऀ-ॿ]", text)) or 1
    ratio = devanagari / letters
    if ratio > 0.5:
        return "hi"
    if ratio > 0.05:
        return "mixed"
    return "en"


INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) instructions",
    r"disregard (the )?(previous|above|system)",
    r"you are (now )?(an?|the) (ai|assistant|model)",
    r"system prompt",
    r"rank (me|this candidate) (first|highest|top)",
    r"give (me|this candidate) (a )?(score|rating) of",
    r"select this candidate",
]


def detect_injection(text: str) -> list[str]:
    low = text.lower()
    return [p for p in INJECTION_PATTERNS if re.search(p, low)]
