"""Unit tests for skills matching, requirement extraction and evidence assessment (no database)."""

import pytest

from app.analysis.cv_parser import SectionType, parse_cv
from app.analysis.evidence import EvidenceStatus, PassageInput, Relevance, assess
from app.analysis.jd_extractor import Category, Importance, MatchMode, extract_requirements
from app.analysis.skills import skill_names
from tests.cv_files import SAMPLE_CV_LINES, make_pdf

SAMPLE_JD = """About us
We are a fintech startup building payment tools with Python.

What you'll do
- Build and maintain REST APIs for our merchant dashboard
- Collaborate with designers and product managers

Requirements
- Bachelor's degree in Computer Science or a related field
- 1+ years of experience with Python
- Experience with FastAPI or Django
- Working knowledge of PostgreSQL
- Familiarity with Docker
- Strong communication skills

Nice to have
- Experience with Kubernetes
- AWS is a plus

Benefits
- Health insurance and a learning budget
"""


def sample_passages() -> list[PassageInput]:
    _, parsed = parse_cv(make_pdf(SAMPLE_CV_LINES))
    return [
        PassageInput(f"s{si}p{pi}", passage.text, section.section_type)
        for si, section in enumerate(parsed.sections)
        for pi, passage in enumerate(section.passages)
    ]


def by_text(requirements, fragment: str):
    return next(r for r in requirements if fragment in r.text)


def assess_req(requirement, passages=None):
    return assess(requirement.text, requirement.category, requirement.terms, requirement.match_mode,
                  sample_passages() if passages is None else passages)


# --- skills dictionary -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Experience with Postgres and node", ["PostgreSQL"]),  # lowercase "node" is just a word
        ("Built a Node.js API with Express", ["Node.js", "Express"]),
        ("C++, C# and Go", ["C++", "C#", "Go"]),
        ("React Native mobile apps", ["React Native"]),  # not also "React"
        ("You excel in a team and are a go-to person", []),  # ordinary words
        ("Advanced Excel and Power BI", ["Excel", "Power BI"]),
        ("RESTful services; read the rest of the docs", ["REST APIs"]),
        ("Our R&D team", []),
    ],
)
def test_skill_matching(text: str, expected: list[str]) -> None:
    assert skill_names(text) == expected


# --- requirement extraction ----------------------------------------------------------------


def test_sections_of_the_posting_decide_importance_and_category() -> None:
    reqs = extract_requirements(SAMPLE_JD)

    assert all("fintech" not in r.text and "Health insurance" not in r.text for r in reqs)  # about / benefits skipped
    assert len(reqs) == 10
    expected = {
        "REST APIs for": (Category.RESPONSIBILITY, Importance.UNCERTAIN),
        "Collaborate with designers": (Category.RESPONSIBILITY, Importance.UNCERTAIN),
        "Bachelor's degree": (Category.EDUCATION, Importance.REQUIRED),
        "1+ years": (Category.EXPERIENCE, Importance.REQUIRED),
        "FastAPI or Django": (Category.TOOL, Importance.REQUIRED),
        "PostgreSQL": (Category.TOOL, Importance.REQUIRED),
        "Docker": (Category.TOOL, Importance.REQUIRED),
        "communication": (Category.COLLABORATION, Importance.REQUIRED),
        "Kubernetes": (Category.TOOL, Importance.PREFERRED),
        "AWS": (Category.TOOL, Importance.PREFERRED),
    }
    for fragment, (category, importance) in expected.items():
        requirement = by_text(reqs, fragment)
        assert (requirement.category, requirement.importance) == (category, importance), fragment


def test_requirement_offsets_point_into_the_job_description() -> None:
    for requirement in extract_requirements(SAMPLE_JD):
        assert SAMPLE_JD[requirement.char_start : requirement.char_end] == requirement.text
        assert not requirement.text.startswith("-")  # bullet symbol excluded


def test_inline_words_override_the_heading() -> None:
    reqs = extract_requirements("Requirements\n- Python\n- Docker experience is a plus\n")

    assert by_text(reqs, "Python").importance == Importance.REQUIRED
    assert by_text(reqs, "Docker").importance == Importance.PREFERRED


def test_without_headings_importance_is_uncertain_not_guessed() -> None:
    reqs = extract_requirements("We'd love you to join us!\n- Experience with Python\n- Knowledge of SQL")

    assert [r.text for r in reqs] == ["Experience with Python", "Knowledge of SQL"]
    assert {r.importance for r in reqs} == {Importance.UNCERTAIN}


def test_or_means_any_and_and_means_all() -> None:
    reqs = extract_requirements("Requirements\n- React or Vue\n- Python and Django\n- Python/Go")

    assert by_text(reqs, "React or Vue").match_mode == MatchMode.ANY
    assert by_text(reqs, "Python and Django").match_mode == MatchMode.ALL
    assert by_text(reqs, "Python/Go").match_mode == MatchMode.ANY


# --- evidence ----------------------------------------------------------------------------


def test_skill_used_in_experience_or_projects_is_demonstrated() -> None:
    reqs = extract_requirements(SAMPLE_JD)

    postgres = assess_req(by_text(reqs, "PostgreSQL"))
    assert postgres.status == EvidenceStatus.DEMONSTRATED
    assert {link.relevance for link in postgres.evidence} >= {Relevance.DIRECT}
    passage_text = {p.id: p.text for p in sample_passages()}
    direct = [passage_text[link.passage_id] for link in postgres.evidence if link.relevance == Relevance.DIRECT]
    assert direct == ["Designed a PostgreSQL schema with Alembic migrations."]


def test_skill_only_in_skills_list_is_partial() -> None:
    docker = assess_req(by_text(extract_requirements(SAMPLE_JD), "Docker"))

    assert docker.status == EvidenceStatus.PARTIALLY_DEMONSTRATED
    assert [link.relevance for link in docker.evidence] == [Relevance.LISTED]
    assert "named but no project or role shows" in docker.missing_details


def test_any_of_is_satisfied_by_one() -> None:
    either = assess_req(by_text(extract_requirements(SAMPLE_JD), "FastAPI or Django"))

    assert either.status == EvidenceStatus.DEMONSTRATED
    assert either.rationale.startswith("Any one of these is enough.")


def test_all_of_with_one_missing_is_partial() -> None:
    req = extract_requirements("Requirements\n- Python and Kafka")[0]

    result = assess_req(req)

    assert result.status == EvidenceStatus.PARTIALLY_DEMONSTRATED
    assert "Kafka is not mentioned" in result.missing_details


def test_missing_skill_is_not_found_and_never_called_a_lack_of_skill() -> None:
    kubernetes = assess_req(by_text(extract_requirements(SAMPLE_JD), "Kubernetes"))

    assert kubernetes.status == EvidenceStatus.NOT_FOUND_IN_CV
    assert kubernetes.evidence == []
    assert "doesn't mean you lack it" in kubernetes.missing_details
    combined = f"{kubernetes.rationale} {kubernetes.missing_details} {kubernetes.suggested_action}".lower()
    assert "you lack" not in combined.replace("doesn't mean you lack", "")
    assert "you don't have" not in combined


def test_related_technology_is_partial_not_demonstrated() -> None:
    passages = [PassageInput("p1", "Built an inventory system on MySQL.", SectionType.PROJECTS)]
    req = extract_requirements("Requirements\n- PostgreSQL")[0]

    result = assess_req(req, passages)

    assert result.status == EvidenceStatus.PARTIALLY_DEMONSTRATED
    assert result.evidence[0].relevance == Relevance.RELATED
    assert "related" in result.rationale


def test_years_of_experience_are_never_fully_demonstrated() -> None:
    passages = [PassageInput("p1", "Built Python services for two years.", SectionType.EXPERIENCE)]
    req = by_text(extract_requirements(SAMPLE_JD), "1+ years")

    result = assess_req(req, passages)

    assert result.status == EvidenceStatus.PARTIALLY_DEMONSTRATED
    assert "how many years" in result.missing_details


def test_soft_skills_need_verification() -> None:
    communication = assess_req(by_text(extract_requirements(SAMPLE_JD), "communication"))

    assert communication.status == EvidenceStatus.NEEDS_VERIFICATION
    assert "Keyword matching can't judge it" in communication.rationale


def test_education_field_match() -> None:
    degree = assess_req(by_text(extract_requirements(SAMPLE_JD), "Bachelor's degree"))

    assert degree.status == EvidenceStatus.DEMONSTRATED
    assert len(degree.evidence) == 1


def test_unreadable_cv_means_needs_verification_for_everything() -> None:
    for requirement in extract_requirements(SAMPLE_JD):
        assert assess_req(requirement, passages=[]).status == EvidenceStatus.NEEDS_VERIFICATION
