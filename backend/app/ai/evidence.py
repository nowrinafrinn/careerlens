"""AI-assisted evidence assessment: the prompt, the output schema, and the
validator that decides which AI verdicts may be used.

The model sees each requirement and the CV's passages under short ids
("r1", "p1"). Every verdict it returns is checked here:

- it may only cite passages that exist in this CV, and each quote must
  actually appear in the passage it cites;
- its status must be backed by its citations (e.g. "demonstrated" needs a
  passage showing the skill in use);
- it may not mention figures that appear neither in the requirement nor in
  the passages it cites.

A verdict that fails any check is dropped, and that requirement keeps the
rule engine's result. Output that isn't valid JSON for the schema at all is
rejected as a whole. Nothing partial or unchecked reaches the candidate.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ValidationError

from app.analysis.cv_parser import SectionType
from app.analysis.evidence import Assessment, EvidenceLink, EvidenceStatus, PassageInput, Relevance

# The header (text before the first heading) holds the name and contact
# details. The model doesn't need them to judge skills, so they're never sent.
_NOT_SENT = {SectionType.HEADER}

SYSTEM = """You compare a job's requirements with passages from one candidate's CV.
For each requirement, decide what the CV *shows*, citing only the passages given.

Statuses:
- demonstrated: a passage shows the skill or experience being used (a role, project or achievement).
- partially_demonstrated: the CV shows part of it, or only names it (e.g. in a skills list) without showing use.
- not_found_in_cv: no passage mentions it. This says nothing about the candidate's ability.
- needs_verification: it can't be judged from a CV (e.g. soft skills, availability); the candidate must say.

Rules:
- Cite passages by their id, with a short quote copied exactly from that passage.
- relevance per citation: direct (shown in use), listed (only named), related (a related skill is used), possible (unclear; a person should judge).
- "demonstrated" needs at least one direct citation. "not_found_in_cv" may not have direct or listed citations.
- Never invent experience, employers, numbers, dates or results. Only mention numbers that appear in the requirement or the passages you cite.
- Describe the CV, not the person: write "the CV doesn't show X", never "you lack X".
- rationale: one or two plain sentences. suggested_action: one practical, honest next step.
- Return one assessment for every requirement id, and nothing else."""

STATUSES = [s.value for s in EvidenceStatus]
RELEVANCES = [r.value for r in Relevance]

# Written out by hand (no $refs) so any JSON-schema-capable model accepts it.
SCHEMA = {
    "type": "object",
    "properties": {
        "assessments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "requirement_id": {"type": "string"},
                    "status": {"type": "string", "enum": STATUSES},
                    "rationale": {"type": "string"},
                    "missing_details": {"type": ["string", "null"]},
                    "suggested_action": {"type": "string"},
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "passage_id": {"type": "string"},
                                "quote": {"type": "string"},
                                "relevance": {"type": "string", "enum": RELEVANCES},
                                "note": {"type": "string"},
                            },
                            "required": ["passage_id", "quote", "relevance", "note"],
                        },
                    },
                },
                "required": ["requirement_id", "status", "rationale", "suggested_action", "evidence"],
            },
        }
    },
    "required": ["assessments"],
}


class _Citation(BaseModel):
    passage_id: str
    quote: str
    relevance: Literal["direct", "listed", "related", "possible"]
    note: str = ""


class _Verdict(BaseModel):
    requirement_id: str
    status: Literal["demonstrated", "partially_demonstrated", "not_found_in_cv", "needs_verification"]
    rationale: str
    missing_details: str | None = None
    suggested_action: str
    evidence: list[_Citation] = []


class _Output(BaseModel):
    assessments: list[_Verdict]


class AIOutputError(Exception):
    """The model's answer can't be used at all (not JSON, or not the schema)."""


@dataclass
class RequirementInput:
    key: str  # "r1", "r2"… as shown to the model
    text: str
    category: str
    importance: str
    terms: list[str]


@dataclass
class Request:
    requirements: list[RequirementInput]
    passages: dict[str, PassageInput]  # "p1" → the real passage
    prompt: str


@dataclass
class Result:
    assessments: dict[str, Assessment] = field(default_factory=dict)  # by requirement key
    rejected: dict[str, str] = field(default_factory=dict)  # requirement key → why the AI verdict wasn't used


def build_request(requirements: list[RequirementInput], passages: list[PassageInput]) -> Request:
    sent = [p for p in passages if p.section_type not in _NOT_SENT]
    by_key = {f"p{i}": p for i, p in enumerate(sent, start=1)}
    payload = {
        "requirements": [
            {"id": r.key, "text": r.text, "category": r.category, "importance": r.importance} for r in requirements
        ],
        "cv_passages": [{"id": key, "section": p.section_type.value, "text": p.text} for key, p in by_key.items()],
    }
    prompt = "Assess every requirement against these CV passages.\n\n" + json.dumps(payload, ensure_ascii=False)
    return Request(requirements, by_key, prompt)


_QUOTE_MARKS = re.compile(r"[\"'“”‘’`]")


def _normalise(text: str) -> str:
    """For comparing a quote with its passage: case, spacing and quote marks don't count."""
    return re.sub(r"\s+", " ", _QUOTE_MARKS.sub("", text.lower())).strip()


_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def _check(verdict: _Verdict, requirement: RequirementInput, passages: dict[str, PassageInput]) -> Assessment | str:
    """An Assessment the app can use, or the reason the verdict was rejected."""
    cited: list[tuple[_Citation, PassageInput]] = []
    for citation in verdict.evidence:
        passage = passages.get(citation.passage_id)
        if passage is None:
            return "it cited a passage that isn't in this CV"
        quote = _normalise(citation.quote)
        if len(quote) < 4 or quote not in _normalise(passage.text):
            return "it quoted text that isn't in the passage it cited"
        cited.append((citation, passage))

    relevances = {c.relevance for c, _ in cited}
    if verdict.status == "demonstrated" and "direct" not in relevances:
        return "it said the CV demonstrates this without citing a passage that shows it in use"
    if verdict.status == "partially_demonstrated" and not cited:
        return "it said the CV partly shows this without citing a passage"
    if verdict.status == "not_found_in_cv" and relevances & {"direct", "listed"}:
        return "it said this isn't in the CV while citing a passage that mentions it"

    rationale = verdict.rationale.strip()
    action = verdict.suggested_action.strip()
    missing = (verdict.missing_details or "").strip() or None
    if not rationale or not action or len(rationale) > 700 or len(action) > 500 or len(missing or "") > 500:
        return "its explanation was empty or too long"

    allowed = set(_NUMBER.findall(requirement.text))
    for _, passage in cited:
        allowed |= set(_NUMBER.findall(passage.text))
    for text in (rationale, action, missing or ""):
        if set(_NUMBER.findall(text)) - allowed:
            return "it mentioned figures that aren't in the requirement or the cited passages"

    links: dict[str, EvidenceLink] = {}
    for citation, passage in cited:
        lowered = passage.text.lower()
        links.setdefault(
            passage.id,
            EvidenceLink(
                passage_id=passage.id,
                relevance=Relevance(citation.relevance),
                matched_terms=[t for t in requirement.terms if t.lower() in lowered],
                note=(citation.note.strip() or f"Quoted: “{citation.quote.strip()}”")[:300],
            ),
        )
    return Assessment(
        status=EvidenceStatus(verdict.status),
        rationale=rationale,
        missing_details=missing,
        suggested_action=action,
        evidence=list(links.values()),
    )


def validate(raw: str, request: Request) -> Result:
    try:
        output = _Output.model_validate_json(raw)
    except ValidationError as exc:
        raise AIOutputError("The AI's answer wasn't in the expected format.") from exc

    by_key = {r.key: r for r in request.requirements}
    result = Result()
    seen: set[str] = set()
    for verdict in output.assessments:
        requirement = by_key.get(verdict.requirement_id)
        if requirement is None or verdict.requirement_id in seen:
            continue  # unknown or repeated ids are ignored, never guessed at
        seen.add(verdict.requirement_id)
        checked = _check(verdict, requirement, request.passages)
        if isinstance(checked, str):
            result.rejected[requirement.key] = checked
        else:
            result.assessments[requirement.key] = checked
    for key in by_key.keys() - seen:
        result.rejected[key] = "it didn't return a verdict for this requirement"
    return result
