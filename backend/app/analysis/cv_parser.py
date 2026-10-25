"""CV file validation, text extraction and section detection.

The goal is reliable, explainable structure, not deep understanding:
- the file type is decided by its bytes, never its name;
- text is extracted and normalised into `text`, the single reference that all
  character offsets point into (`text[start:end]` is always the exact passage);
- sections are found from a dictionary of common headings (and Word heading
  styles); anything that can't be placed is reported as "unrecognized";
- problems are reported as warnings instead of being guessed around.
"""

import io
import re
import zipfile
from dataclasses import dataclass, field
from enum import StrEnum

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_PDF_PAGES = 20
MAX_DOCX_ENTRIES = 2_000
MAX_DOCX_UNCOMPRESSED = 30 * 1024 * 1024  # zip-bomb guard
MIN_USEFUL_TEXT = 40  # characters; below this the extraction is treated as failed


class FileKind(StrEnum):
    PDF = "pdf"
    DOCX = "docx"


MIME_TYPES = {
    FileKind.PDF: "application/pdf",
    FileKind.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class SectionType(StrEnum):
    HEADER = "header"  # text before the first heading: usually name and contact details
    SUMMARY = "summary"
    EDUCATION = "education"
    SKILLS = "skills"
    EXPERIENCE = "experience"
    INTERNSHIP = "internship"
    PROJECTS = "projects"
    CERTIFICATIONS = "certifications"
    ACHIEVEMENTS = "achievements"
    OTHER_EXPERIENCE = "other_experience"
    OTHER = "other"
    UNRECOGNIZED = "unrecognized"


class ParseStatus(StrEnum):
    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"


class UnsupportedFile(ValueError):
    """The bytes are not a PDF or DOCX we can safely read. Message is user-facing."""


# Normalised heading text → section type. Matching is exact after normalisation.
HEADINGS: dict[str, SectionType] = {}
for section_type, names in {
    SectionType.SUMMARY: ["summary", "professional summary", "profile", "professional profile", "objective",
                          "career objective", "about me", "about"],
    SectionType.EDUCATION: ["education", "academic background", "academic qualifications", "education and training",
                            "educational background", "academics", "qualifications"],
    SectionType.SKILLS: ["skills", "technical skills", "core skills", "key skills", "skills and tools",
                         "technologies", "tools and technologies", "tech stack", "technical proficiencies",
                         "competencies", "core competencies", "programming languages", "skills and interests"],
    SectionType.EXPERIENCE: ["experience", "work experience", "professional experience", "employment",
                             "employment history", "work history", "career history", "relevant experience"],
    SectionType.INTERNSHIP: ["internship", "internships", "internship experience"],
    SectionType.PROJECTS: ["projects", "personal projects", "academic projects", "selected projects",
                           "project experience", "key projects", "side projects", "university projects"],
    SectionType.CERTIFICATIONS: ["certifications", "certificates", "certification", "licenses and certifications",
                                 "courses and certifications", "courses", "training", "online courses"],
    SectionType.ACHIEVEMENTS: ["achievements", "awards", "honors", "honours", "awards and achievements",
                               "accomplishments", "awards and honors", "honors and awards", "competitions"],
    SectionType.OTHER_EXPERIENCE: ["volunteering", "volunteer experience", "leadership", "extracurricular activities",
                                   "extracurricular", "activities", "leadership and activities",
                                   "research experience", "teaching experience", "publications"],
    SectionType.OTHER: ["languages", "interests", "hobbies", "references", "contact", "personal information",
                        "personal details", "additional information"],
}.items():
    for name in names:
        HEADINGS[name] = section_type

BULLET = re.compile(r"^\s*([•●▪■◦○◆►▸‣⁃–—\-*·]|\d{1,2}[.)])\s+")


@dataclass
class Passage:
    text: str
    char_start: int
    char_end: int


@dataclass
class Section:
    section_type: SectionType
    heading: str | None
    char_start: int
    char_end: int
    passages: list[Passage] = field(default_factory=list)


@dataclass
class ParsedCV:
    text: str
    status: ParseStatus
    sections: list[Section]
    warnings: list[str]


# --- file type and extraction --------------------------------------------------------


def detect_kind(data: bytes) -> FileKind:
    """Decides the file type from its content. Raises UnsupportedFile otherwise."""
    if data.startswith(b"%PDF-"):
        return FileKind.PDF
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = set(archive.namelist())
        except zipfile.BadZipFile:
            raise UnsupportedFile("The file looks like a ZIP archive but is damaged.") from None
        if "word/document.xml" in names and "[Content_Types].xml" in names:
            return FileKind.DOCX
        raise UnsupportedFile("This archive isn't a Word document. Upload a PDF or DOCX file.")
    if data.startswith(b"\xd0\xcf\x11\xe0"):
        raise UnsupportedFile("Old .doc files aren't supported. Save it as .docx or PDF and upload that.")
    raise UnsupportedFile("Only PDF and DOCX files are supported.")


def _check_docx_safe(data: bytes) -> None:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_DOCX_ENTRIES or sum(e.file_size for e in entries) > MAX_DOCX_UNCOMPRESSED:
            raise UnsupportedFile("This Word file is unusually large inside and can't be processed safely.")


def _clean_line(line: str) -> str:
    # Non-breaking and other odd spaces become normal spaces; runs collapse.
    return re.sub(r"[ \t  -​ 　]+", " ", line).strip()


def extract_pdf(data: bytes) -> tuple[list[tuple[str, bool]], list[str]]:
    """Returns (lines, warnings). The bool marks lines known to be headings (never for PDF)."""
    warnings: list[str] = []
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise UnsupportedFile("This PDF is password-protected. Remove the password and upload it again.")
        pages = reader.pages
        if len(pages) > MAX_PDF_PAGES:
            warnings.append(f"Only the first {MAX_PDF_PAGES} pages were read.")
        lines: list[tuple[str, bool]] = []
        for page in list(pages)[:MAX_PDF_PAGES]:
            for raw in (page.extract_text() or "").splitlines():
                lines.append((_clean_line(raw), False))
    except UnsupportedFile:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError) as error:
        raise UnsupportedFile("The PDF couldn't be read. It may be damaged.") from error
    return lines, warnings


def extract_docx(data: bytes) -> tuple[list[tuple[str, bool]], list[str]]:
    _check_docx_safe(data)
    try:
        document = Document(io.BytesIO(data))
    except Exception as error:  # python-docx raises a variety of errors on malformed files
        raise UnsupportedFile("The Word document couldn't be read. It may be damaged.") from error

    lines: list[tuple[str, bool]] = []
    for block in document.iter_inner_content():
        if isinstance(block, Paragraph):
            style = (block.style.name if block.style is not None else "") or ""
            is_heading = style.lower().startswith(("heading", "title"))
            for raw in block.text.splitlines():
                lines.append((_clean_line(raw), is_heading))
        elif isinstance(block, Table):
            # Tables are read row by row; cells in a row are joined with " | ".
            for row in block.rows:
                cells: list[str] = []
                for cell in row.cells:
                    text = _clean_line(" ".join(cell.text.splitlines()))
                    if text and (not cells or cells[-1] != text):  # merged cells repeat
                        cells.append(text)
                if cells:
                    lines.append((" | ".join(cells), False))
    return lines, []


# --- structure -----------------------------------------------------------------------


def normalize_heading(line: str) -> str:
    text = line.lower().replace("&", " and ")
    text = re.sub(r"[^a-z ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def heading_type(line: str) -> SectionType | None:
    if len(line) > 60 or len(line.split()) > 6:
        return None
    return HEADINGS.get(normalize_heading(line))


def _build_text(lines: list[tuple[str, bool]]) -> tuple[str, list[tuple[int, int, bool]]]:
    """Joins non-empty lines with "\\n". Returns the text and (start, end, is_heading) per line."""
    parts: list[str] = []
    spans: list[tuple[int, int, bool]] = []
    position = 0
    for line, is_heading in lines:
        if not line:
            continue
        if parts:
            position += 1  # the "\n" separator
        parts.append(line)
        spans.append((position, position + len(line), is_heading))
        position += len(line)
    return "\n".join(parts), spans


def _split_passages(text: str, line_spans: list[tuple[int, int]]) -> list[Passage]:
    """One passage per bullet or line. A line that starts in lowercase continues the
    bullet above it (PDF extraction wraps long bullets onto several lines)."""
    passages: list[Passage] = []
    current_is_bullet = False
    for start, end in line_spans:
        line = text[start:end]
        bullet = BULLET.match(line)
        if bullet:
            start += bullet.end()  # the passage text excludes the bullet symbol
            current_is_bullet = True
            passages.append(Passage(text[start:end], start, end))
        elif passages and current_is_bullet and line[:1].islower():
            last = passages[-1]
            passages[-1] = Passage(text[last.char_start:end], last.char_start, end)
        else:
            current_is_bullet = False
            passages.append(Passage(line, start, end))
    return [p for p in passages if p.text.strip()]


def structure(lines: list[tuple[str, bool]]) -> tuple[str, list[Section]]:
    text, spans = _build_text(lines)
    sections: list[Section] = []
    body: list[tuple[int, int]] = []
    current: Section | None = None

    def close() -> None:
        if current is not None:
            current.passages = _split_passages(text, body)
            if body:
                current.char_end = body[-1][1]
            sections.append(current)

    for start, end, styled_heading in spans:
        line = text[start:end]
        known = heading_type(line)
        if known is not None or (styled_heading and len(line.split()) <= 6):
            close()
            current = Section(known or SectionType.UNRECOGNIZED, line, start, end)
            body = []
            continue
        if current is None:
            current = Section(SectionType.HEADER, None, start, end)
        body.append((start, end))
    close()
    return text, [s for s in sections if s.passages or s.heading]


def _warnings_for(sections: list[Section]) -> list[str]:
    types = {s.section_type for s in sections}
    recognized = types - {SectionType.HEADER, SectionType.UNRECOGNIZED}
    warnings: list[str] = []
    if not recognized:
        warnings.append(
            "No section headings were recognized, so the text is listed as it was found. "
            "You can assign a section type to each block below."
        )
    if SectionType.UNRECOGNIZED in types and recognized:
        warnings.append("Some headings weren't recognized. Check those blocks and set their section type.")
    for expected, label in [
        (SectionType.SKILLS, "skills"),
        (SectionType.EDUCATION, "education"),
    ]:
        if recognized and expected not in types:
            warnings.append(
                f"No {label} section was found. That doesn't mean it's missing from your CV: "
                "it may be under a different heading. Set the section type if so."
            )
    return warnings


def parse_cv(data: bytes) -> tuple[FileKind, ParsedCV]:
    """Validates and parses a CV. Raises UnsupportedFile for files that can't be accepted.

    A readable file with no usable text (e.g. a scanned PDF) is accepted with
    status FAILED, so the user sees why instead of a silent empty result.
    """
    kind = detect_kind(data)
    lines, warnings = extract_pdf(data) if kind == FileKind.PDF else extract_docx(data)
    text, sections = structure(lines)

    if len(text) < MIN_USEFUL_TEXT:
        hint = (
            " It may be a scanned image; text recognition (OCR) isn't supported. "
            "Export the CV from your editor as a text-based PDF or DOCX."
            if kind == FileKind.PDF
            else ""
        )
        return kind, ParsedCV(text, ParseStatus.FAILED, sections, [f"Almost no text could be extracted.{hint}"])

    recognized = {s.section_type for s in sections} - {SectionType.HEADER, SectionType.UNRECOGNIZED}
    if not recognized:
        # No headings at all: the leading block is the whole CV, not just contact details.
        for section in sections:
            if section.section_type == SectionType.HEADER:
                section.section_type = SectionType.UNRECOGNIZED
    warnings += _warnings_for(sections)
    status = ParseStatus.OK if len(recognized) >= 2 and SectionType.UNRECOGNIZED not in {
        s.section_type for s in sections
    } else ParseStatus.PARTIAL
    return kind, ParsedCV(text, status, sections, warnings)
