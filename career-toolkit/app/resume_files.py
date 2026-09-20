"""
Resume file handling:
  - extract_text(): pull plain text out of an uploaded .pdf or .docx
  - build_resume_docx(): turn generated resume text into a clean, ATS-safe
    .docx (headings + paragraphs + bullets only -- no tables, text boxes,
    or columns, which is what trips up ATS parsers)
"""
import io

from docx import Document
from docx.shared import Pt
from pypdf import PdfReader

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB is plenty for a resume


class ResumeFileError(RuntimeError):
    """Raised for any problem reading an upload or building a docx."""


def extract_text(filename: str, content: bytes) -> str:
    if len(content) > MAX_UPLOAD_BYTES:
        raise ResumeFileError("That file is too large (5 MB max).")
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return _extract_pdf(content)
    if name.endswith(".docx"):
        return _extract_docx(content)
    raise ResumeFileError("Only .pdf and .docx files are supported.")


def _extract_pdf(content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # noqa: BLE001 -- pypdf can raise several internal error types
        raise ResumeFileError(f"Couldn't read that PDF: {exc}") from exc
    text = "\n".join(pages).strip()
    if not text:
        raise ResumeFileError(
            "No text found in that PDF -- it's likely a scanned image rather than real text. "
            "Paste your resume text into the box instead."
        )
    return text


def _extract_docx(content: bytes) -> str:
    try:
        doc = Document(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001
        raise ResumeFileError(f"Couldn't read that Word file: {exc}") from exc
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    parts.append(cell.text)
    text = "\n".join(parts).strip()
    if not text:
        raise ResumeFileError("That Word file appears to be empty.")
    return text


def build_docx_from_text(text: str) -> bytes:
    """Heuristic plain-text-to-docx conversion: a line in all caps or
    starting with '#' becomes a heading; a line starting with a bullet
    character becomes a bulleted paragraph; everything else is a normal
    paragraph. Used for both resumes (headings + bullets) and cover letters
    (plain paragraphs) -- good enough for the simple, structured output the
    prompts ask Gemini for, not a general Markdown parser."""
    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        heading_text = line.lstrip("#").strip()
        looks_like_heading = line.startswith("#") or (
            heading_text.isupper() and 1 <= len(heading_text.split()) <= 5
        )
        if looks_like_heading:
            display = heading_text.title() if heading_text.isupper() else heading_text
            doc.add_heading(display, level=2)
        elif line[:2] in ("- ", "* ") or line[:2] == "\u2022 ":
            doc.add_paragraph(line[2:].strip(), style="List Bullet")
        else:
            doc.add_paragraph(line)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
