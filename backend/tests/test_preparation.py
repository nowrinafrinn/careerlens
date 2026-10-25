"""Unit tests for the preparation suggestion generator (no database)."""

from app.analysis.evidence import assess
from app.analysis.jd_extractor import extract_requirements
from app.analysis.preparation import EvidenceIn, GapIn, QuestionIn, RequirementIn, SuggestionKind, suggest
from app.models.enums import RoundType
from tests.test_requirement_analysis import SAMPLE_JD, sample_passages


def requirement_inputs(self_reports: dict[str, str] | None = None) -> list[RequirementIn]:
    passages = {p.id: p for p in sample_passages()}
    out = []
    for i, req in enumerate(extract_requirements(SAMPLE_JD)):
        result = assess(req.text, req.category, req.terms, req.match_mode, list(passages.values()))
        out.append(
            RequirementIn(
                id=f"r{i}",
                text=req.text,
                category=req.category,
                importance=req.importance,
                status=result.status,
                self_report=next((v for k, v in (self_reports or {}).items() if k in req.text), "unknown"),
                terms=req.terms,
                evidence=[
                    EvidenceIn(passages[link.passage_id].text, passages[link.passage_id].section_type, link.relevance, link.matched_terms)
                    for link in result.evidence
                ],
            )
        )
    return out


def titles(suggestions) -> list[str]:
    return [s.title for s in suggestions]


def test_every_suggestion_explains_why_and_questions_are_labelled_practice() -> None:
    suggestions = suggest(requirement_inputs(), [], [], RoundType.TECHNICAL_INTERVIEW)

    assert suggestions
    for s in suggestions:
        assert s.why
        if "question" in s.title.lower() and s.title.startswith("Practice question"):
            assert s.is_practice_question
            assert "not a question the employer is known to ask" in s.detail


def test_demonstrated_skill_becomes_a_question_about_your_own_project() -> None:
    suggestions = suggest(requirement_inputs(), [], [], None)

    postgres = next(s for s in suggestions if "PostgreSQL in:" in s.title)
    assert postgres.kind == SuggestionKind.PROJECT_QUESTION
    assert "Designed a PostgreSQL schema" in postgres.title
    assert "your own role" in postgres.detail
    assert postgres.requirement_id is not None
    # One question per demonstrated skill, not a second near-duplicate per passage.
    assert sum(1 for s in suggestions if "Designed a PostgreSQL schema" in s.title) == 1


def test_listed_only_skill_means_reviewing_fundamentals() -> None:
    suggestions = suggest(requirement_inputs(), [], [], None)

    docker = next(s for s in suggestions if s.title == "Review Docker fundamentals")
    assert docker.kind == SuggestionKind.REVIEW_TOPIC
    assert "partly shown" in docker.why


def test_missing_skill_means_an_honest_answer_not_a_bluff() -> None:
    suggestions = suggest(requirement_inputs(), [], [], None)

    kubernetes = next(s for s in suggestions if s.title == "Prepare an honest answer about Kubernetes")
    assert kubernetes.kind == SuggestionKind.CHALLENGING_AREA
    assert "Don't overstate it" in kubernetes.detail
    learning = suggest(requirement_inputs({"Kubernetes": "learning"}), [], [], None)
    assert "how you're learning it" in next(s for s in learning if "Kubernetes" in s.title).detail


def test_responsibilities_become_star_practice() -> None:
    suggestions = suggest(requirement_inputs(), [], [], None)

    star = [s for s in suggestions if s.kind == SuggestionKind.BEHAVIORAL_QUESTION]
    assert "Practice question (STAR): “Tell me about a time you had to build and maintain REST APIs for our merchant dashboard.”" in titles(star)
    communication = next(s for s in star if "communication" in s.why)
    assert "explain something technical" in communication.title


def test_round_type_adds_a_format_tip() -> None:
    assessment = suggest([], [], [], RoundType.ONLINE_ASSESSMENT)
    hr = suggest([], [], [], RoundType.HR_INTERVIEW)

    assert titles(assessment) == ["Do one timed practice set under test conditions"]
    assert assessment[0].why == "This round is an online assessment."
    assert titles(hr) == ["Prepare a 60-second introduction and why this role"]
    assert hr[0].why == "This round is an HR interview."
    assert suggest([], [], [], None) == []


def test_open_gaps_and_unfinished_questions_are_included_with_their_source() -> None:
    gaps = [GapIn("g1", "SQL window functions", "knowledge", 1)]
    questions = [QuestionIn("q1", "Write a query returning each customer's second order", "SQL window functions", "to_practice")]

    suggestions = suggest([], gaps, questions, None)

    gap = next(s for s in suggestions if s.kind == SuggestionKind.GAP_PRACTICE)
    assert (gap.skill_gap_id, gap.title) == ("g1", "Work on your SQL window functions gap before this round")
    assert "(knowledge)" in gap.why
    revisit = next(s for s in suggestions if s.kind == SuggestionKind.REVISIT_QUESTION)
    assert revisit.question_id == "q1"
    assert revisit.title.startswith("Re-attempt:")


def test_suggestions_are_ordered_by_priority_and_never_duplicated() -> None:
    suggestions = suggest(requirement_inputs(), [GapIn("g1", "Docker", "unclassified", 1)], [], RoundType.TECHNICAL_INTERVIEW)

    priorities = [s.priority for s in suggestions]
    assert priorities == sorted(priorities)
    assert len(titles(suggestions)) == len(set(titles(suggestions)))
