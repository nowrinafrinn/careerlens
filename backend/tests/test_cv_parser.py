"""Unit tests for the pure CV parser: no database, no HTTP."""

import io
import zipfile

import pytest

from app.analysis.cv_parser import (
    FileKind,
    ParseStatus,
    SectionType,
    UnsupportedFile,
    detect_kind,
    heading_type,
    parse_cv,
)
from tests.cv_files import SAMPLE_CV_LINES, make_docx, make_pdf


def sections_by_type(parsed) -> dict[SectionType, list[str]]:
    return {s.section_type: [p.text for p in s.passages] for s in parsed.sections}


def assert_offsets_point_at_text(parsed) -> None:
    """The core provenance guarantee: every offset slices out exactly the stored text."""
    for section in parsed.sections:
        for passage in section.passages:
            assert parsed.text[passage.char_start : passage.char_end] == passage.text


# --- file type detection ---------------------------------------------------------------


def test_detects_pdf_and_docx_by_content() -> None:
    assert detect_kind(make_pdf(["hello"])) == FileKind.PDF
    assert detect_kind(make_docx([("hello", None)])) == FileKind.DOCX


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"Just some text pretending to be a PDF", "Only PDF and DOCX"),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100, "Old .doc"),
        (b"PK\x03\x04 broken zip", "damaged"),
    ],
)
def test_rejects_files_that_are_not_pdf_or_docx(data: bytes, message: str) -> None:
    with pytest.raises(UnsupportedFile, match=message):
        detect_kind(data)


def test_rejects_zip_that_is_not_a_word_document() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("notes.txt", "hello")
    with pytest.raises(UnsupportedFile, match="isn't a Word document"):
        detect_kind(buffer.getvalue())


# --- headings ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("TECHNICAL SKILLS", SectionType.SKILLS),
        ("Skills & Tools:", SectionType.SKILLS),
        ("Work Experience", SectionType.EXPERIENCE),
        ("Licenses & Certifications", SectionType.CERTIFICATIONS),
        ("Internships", SectionType.INTERNSHIP),
        ("Honors & Achievements", SectionType.ACHIEVEMENTS),
        ("HONOURS AND AWARDS", SectionType.ACHIEVEMENTS),
        ("Scholarships & Awards", SectionType.ACHIEVEMENTS),
        ("Built tools that improved developer experience", None),  # a sentence, not a heading
        ("Experience with Docker and Kubernetes in production", None),
    ],
)
def test_heading_recognition(line: str, expected: SectionType | None) -> None:
    assert heading_type(line) == expected


# --- PDF -------------------------------------------------------------------------------


def test_pdf_cv_is_split_into_sections_and_passages() -> None:
    kind, parsed = parse_cv(make_pdf(SAMPLE_CV_LINES))

    assert kind == FileKind.PDF
    assert parsed.status == ParseStatus.OK
    found = sections_by_type(parsed)
    assert list(found) == [
        SectionType.HEADER,
        SectionType.SUMMARY,
        SectionType.EDUCATION,
        SectionType.SKILLS,
        SectionType.EXPERIENCE,
        SectionType.PROJECTS,
    ]
    assert found[SectionType.HEADER][0] == "Rafi Ahmed"
    assert found[SectionType.SKILLS] == ["Languages: Python, TypeScript, SQL", "Tools: Docker, Git, PostgreSQL"]
    assert_offsets_point_at_text(parsed)


def test_wrapped_bullet_lines_are_joined_and_bullet_symbol_dropped() -> None:
    _, parsed = parse_cv(make_pdf(SAMPLE_CV_LINES))

    experience = sections_by_type(parsed)[SectionType.EXPERIENCE]
    assert experience == [
        "Software Engineering Intern, Example Tech Ltd, Jun-Aug 2024",
        "Built REST endpoints with FastAPI for an internal reporting tool,\nreducing manual report preparation.",
        "Wrote pytest tests for the data import module.",
    ]


def test_pdf_without_text_is_accepted_but_marked_failed() -> None:
    _, parsed = parse_cv(make_pdf([]))

    assert parsed.status == ParseStatus.FAILED
    assert "scanned image" in parsed.warnings[0]


# --- DOCX ------------------------------------------------------------------------------


def test_docx_uses_heading_styles_and_reads_tables() -> None:
    data = make_docx(
        [
            ("Nadia Karim", "Title"),
            ("nadia@example.com", None),
            ("Education", "Heading 1"),
            ("BSc Computer Science, Example University", None),
            ("Open Source", "Heading 1"),  # styled as a heading but not in the dictionary
            ("Contributed documentation fixes to an open-source library.", None),
            ("Skills", "Heading 1"),
        ],
        table=[["Python", "SQL"], ["Docker", "Git"]],
    )

    kind, parsed = parse_cv(data)

    assert kind == FileKind.DOCX
    types = [s.section_type for s in parsed.sections]
    assert SectionType.UNRECOGNIZED in types  # "Open Source" kept, not guessed
    found = sections_by_type(parsed)
    assert found[SectionType.SKILLS] == ["Python | SQL", "Docker | Git"]
    assert parsed.status == ParseStatus.PARTIAL
    assert any("weren't recognized" in w for w in parsed.warnings)
    assert_offsets_point_at_text(parsed)


def test_cv_without_any_headings_is_unrecognized_not_contact_details() -> None:
    _, parsed = parse_cv(make_docx([("I build backend services in Python and enjoy testing them.", None)]))

    assert [s.section_type for s in parsed.sections] == [SectionType.UNRECOGNIZED]
    assert parsed.status == ParseStatus.PARTIAL
    assert "No section headings were recognized" in parsed.warnings[0]


def test_missing_skills_section_warns_without_claiming_skills_are_absent() -> None:
    _, parsed = parse_cv(
        make_docx(
            [
                ("Education", "Heading 1"),
                ("BSc Computer Science, Example University", None),
                ("Experience", "Heading 1"),
                ("Backend intern working with Python and PostgreSQL.", None),
            ]
        )
    )

    warning = next(w for w in parsed.warnings if "skills" in w)
    assert "doesn't mean it's missing" in warning


def test_oversized_docx_contents_are_rejected() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "a" * (31 * 1024 * 1024))  # compresses to almost nothing
    with pytest.raises(UnsupportedFile, match="unusually large"):
        parse_cv(buffer.getvalue())
