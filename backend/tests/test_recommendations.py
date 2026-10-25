"""Unit tests for the CV recommendation generator (no database)."""

import pytest

from app.analysis.cv_parser import SectionType
from app.analysis.evidence import PassageInput, Relevance, assess
from app.analysis.jd_extractor import extract_requirements
from app.analysis.recommendations import (
    ChangeType,
    EvidenceInput,
    Kind,
    RequirementInput,
    _without_term,
    generate,
    generate_all,
    new_numbers,
)
from tests.test_requirement_analysis import SAMPLE_JD, sample_passages


def requirement_inputs(self_reports: dict[str, str] | None = None, passages=None) -> list[RequirementInput]:
    """Runs the real extractor and matcher, then shapes the result for the generator."""
    passages = sample_passages() if passages is None else passages
    by_id = {p.id: p for p in passages}
    inputs = []
    for req in extract_requirements(SAMPLE_JD):
        result = assess(req.text, req.category, req.terms, req.match_mode, passages)
        self_report = next((v for k, v in (self_reports or {}).items() if k in req.text), "unknown")
        inputs.append(
            RequirementInput(
                text=req.text,
                category=req.category,
                importance=req.importance,
                status=result.status,
                self_report=self_report,
                terms=req.terms,
                match_mode=req.match_mode,
                evidence=[
                    EvidenceInput(link.passage_id, by_id[link.passage_id].text, by_id[link.passage_id].section_type,
                                  link.relevance, link.matched_terms, link.note)
                    for link in result.evidence
                ],
            )
        )
    return inputs


def drafts_for(fragment: str, self_reports=None, passages=None):
    req = next(r for r in requirement_inputs(self_reports, passages) if fragment in r.text)
    return generate(req)


# --- the honesty rules -----------------------------------------------------------------------


@pytest.mark.parametrize("self_report", ["unknown", "have_not_on_cv", "do_not_have", "learning"])
def test_suggestions_never_contain_numbers_missing_from_the_original(self_report: str) -> None:
    reports = {"": self_report}  # same self-report on every requirement
    for _, draft in generate_all(requirement_inputs(reports)):
        assert new_numbers(draft.original_text, draft.suggested_text) == [], draft


def test_every_suggested_rewrite_lists_assumptions() -> None:
    for self_report in ["unknown", "have_not_on_cv", "do_not_have"]:
        for _, draft in generate_all(requirement_inputs({"": self_report})):
            if draft.suggested_text:
                assert draft.assumptions, draft.title


def test_rewrite_keeps_the_original_words_and_only_adds_gaps() -> None:
    [draft] = [d for d in drafts_for("PostgreSQL") if d.change_type == ChangeType.REWRITE_PASSAGE]

    assert draft.kind == Kind.PRESENTATION
    assert draft.original_text == "Designed a PostgreSQL schema with Alembic migrations."
    assert draft.suggested_text.startswith("Designed a PostgreSQL schema with Alembic migrations [")
    # Everything added is a bracketed gap, not a claim.
    added = draft.suggested_text.removeprefix("Designed a PostgreSQL schema with Alembic migrations")
    assert added.replace("[for what purpose or in which project]", "").replace(
        "[and what changed as a result]", ""
    ).strip(" ,.") == ""


def test_bullet_that_already_states_a_result_gets_no_rewrite() -> None:
    passages = [PassageInput("p1", "Built a PostgreSQL-backed API, reducing report time.", SectionType.PROJECTS)]

    drafts = drafts_for("PostgreSQL", passages=passages)

    assert [d for d in drafts if d.change_type == ChangeType.REWRITE_PASSAGE] == []


# --- the four kinds -------------------------------------------------------------------------


def test_listed_only_skill_is_an_unverified_claim_needing_an_example() -> None:
    [draft] = drafts_for("Docker")

    assert (draft.kind, draft.change_type) == (Kind.UNVERIFIED_CLAIM, ChangeType.ADD_BULLET)
    assert draft.original_text == "Tools: Docker, Git, PostgreSQL"
    assert "[What you did] using Docker" in draft.suggested_text
    assert any("actually used Docker" in a for a in draft.assumptions)


def test_listed_skill_you_say_you_lack_is_flagged_for_removal() -> None:
    [draft] = drafts_for("Docker", self_reports={"Docker": "do_not_have"})

    assert (draft.kind, draft.change_type) == (Kind.UNVERIFIED_CLAIM, ChangeType.REMOVE_OR_VERIFY)
    assert draft.suggested_text == "Tools: Git, PostgreSQL"


def test_capability_gap_only_when_the_candidate_says_so() -> None:
    unknown = drafts_for("Kubernetes")
    lacking = drafts_for("Kubernetes", self_reports={"Kubernetes": "do_not_have"})
    has_it = drafts_for("Kubernetes", self_reports={"Kubernetes": "have_not_on_cv"})

    assert [(d.kind, d.change_type) for d in unknown] == [(Kind.EVIDENCE_GAP, ChangeType.NO_CV_CHANGE)]
    assert "doesn't mean you lack it" in unknown[0].rationale
    assert [(d.kind, d.change_type) for d in lacking] == [(Kind.POTENTIAL_CAPABILITY_GAP, ChangeType.NO_CV_CHANGE)]
    assert lacking[0].suggested_text is None  # never put an unowned skill on the CV
    assert [(d.kind, d.change_type) for d in has_it] == [(Kind.EVIDENCE_GAP, ChangeType.ADD_BULLET)]


def test_never_calls_it_a_capability_gap_without_the_candidates_word() -> None:
    for _, draft in generate_all(requirement_inputs()):
        assert draft.kind != Kind.POTENTIAL_CAPABILITY_GAP


def test_related_experience_is_an_evidence_gap() -> None:
    passages = [PassageInput("p1", "Built an inventory system on MySQL.", SectionType.PROJECTS)]

    [draft] = drafts_for("PostgreSQL", passages=passages)

    assert draft.kind == Kind.EVIDENCE_GAP
    assert "MySQL, which is related to PostgreSQL" in draft.rationale


def test_any_of_requirement_met_by_one_alternative_needs_nothing() -> None:
    assert [d for d in drafts_for("FastAPI or Django") if d.kind != Kind.PRESENTATION] == []


def test_any_of_requirement_with_nothing_asks_once_about_the_group() -> None:
    reqs = requirement_inputs()
    req = next(r for r in reqs if "FastAPI or Django" in r.text)
    req.evidence = []

    [draft] = generate(req)

    assert draft.title == "Do you have FastAPI or Django?"


def test_soft_skill_asks_for_one_real_example() -> None:
    [draft] = drafts_for("communication")

    assert (draft.kind, draft.change_type) == (Kind.EVIDENCE_GAP, ChangeType.ADD_BULLET)
    assert "Use a real situation." in draft.assumptions


def test_years_requirement_suggests_clear_dates() -> None:
    titles = [d.title for d in drafts_for("1+ years")]

    assert "Make dates and durations easy to see" in titles


def test_duplicates_across_requirements_are_removed() -> None:
    reqs = requirement_inputs()
    keys = [draft.key() for _, draft in generate_all(reqs + reqs)]

    assert len(keys) == len(set(keys))


# --- helpers --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("passage", "term", "expected"),
    [
        ("Tools: Docker, Git, PostgreSQL", "Docker", "Tools: Git, PostgreSQL"),
        ("Tools: Git, PostgreSQL, Docker", "Docker", "Tools: Git, PostgreSQL"),
        ("Tools: Git and Docker", "Docker", "Tools: Git"),
        ("Tools: Docker", "Docker", None),  # removing it would leave an empty line
        ("Docker, Docker Compose", "Docker", None),  # ambiguous: leave it to the person
    ],
)
def test_term_removal(passage: str, term: str, expected: str | None) -> None:
    assert _without_term(passage, term) == expected


def test_new_numbers_flags_only_added_figures() -> None:
    assert new_numbers("Cut build time from 10 to 4 minutes", "Cut build time by 60%, from 10 to 4 minutes") == ["60"]
    assert new_numbers(None, "Reduced costs") == []
