"""Position-specific preparation suggestions.

Built from what is on record for this application: its requirements and
their CV evidence, the candidate's open skill gaps, past questions, and the
round type. Every suggestion says why it was made. Generated questions are
practice questions: they are never presented as what the employer will ask.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum

from app.analysis.cv_parser import SectionType
from app.analysis.evidence import EvidenceStatus, Relevance
from app.analysis.jd_extractor import Category, Importance
from app.models.enums import RoundType


class SuggestionKind(StrEnum):
    PROJECT_QUESTION = "project_question"  # explain your own work
    REVIEW_TOPIC = "review_topic"
    PRACTICE_QUESTION = "practice_question"
    BEHAVIORAL_QUESTION = "behavioral_question"  # STAR
    CHALLENGING_AREA = "challenging_area"  # little or no evidence: prepare an honest answer
    GAP_PRACTICE = "gap_practice"
    REVISIT_QUESTION = "revisit_question"
    ROUND_FORMAT = "round_format"


@dataclass
class EvidenceIn:
    passage_text: str
    section_type: SectionType
    relevance: Relevance
    terms: list[str]


@dataclass
class RequirementIn:
    id: str
    text: str
    category: Category
    importance: Importance
    status: EvidenceStatus
    self_report: str
    terms: list[str]
    evidence: list[EvidenceIn] = field(default_factory=list)


@dataclass
class GapIn:
    id: str
    skill_name: str
    gap_type: str
    priority: int


@dataclass
class QuestionIn:
    id: str
    text: str
    topic: str | None
    practice_status: str


@dataclass
class Suggestion:
    kind: SuggestionKind
    title: str
    detail: str
    why: str
    priority: int  # 1 = do first
    is_practice_question: bool = False
    requirement_id: str | None = None
    skill_gap_id: str | None = None
    question_id: str | None = None


_IMPORTANCE_PRIORITY = {Importance.REQUIRED: 1, Importance.PREFERRED: 3, Importance.UNCERTAIN: 3}
_PRACTICE_NOTE = "A practice question generated from the job description, not a question the employer is known to ask."

_ROUND_TIPS: dict[RoundType, tuple[str, str]] = {
    RoundType.ONLINE_ASSESSMENT: (
        "Do one timed practice set under test conditions",
        "Match the expected time limit and work without notes, so pacing isn't a surprise.",
    ),
    RoundType.WRITTEN_EXAM: (
        "Check the exam format and practise pacing",
        "Find out the sections and time allowed if you can, then practise a full timed paper.",
    ),
    RoundType.TECHNICAL_INTERVIEW: (
        "Practise solving problems out loud",
        "Interviewers usually follow your reasoning, not just the answer. Talk through one or two problems aloud.",
    ),
    RoundType.HR_INTERVIEW: (
        "Prepare a 60-second introduction and why this role",
        "Cover who you are, what you've built, and why this company and position specifically.",
    ),
    RoundType.MANAGERIAL_INTERVIEW: (
        "Prepare examples of prioritising and handling disagreement",
        "Managers often ask how you plan work, deal with conflict, and take feedback.",
    ),
    RoundType.CV_SCREENING: (
        "Check the CV you sent matches this job",
        "Use the requirement analysis and CV suggestions to make sure your strongest evidence is visible.",
    ),
    RoundType.FINAL_DECISION: (
        "Prepare your questions and practical details",
        "Have your own questions about the team and role ready, and know your availability and expectations.",
    ),
}

# Written out, because no article rule gets "an HR interview" right.
_ROUND_NAMES = {
    RoundType.CV_SCREENING: "a CV screening",
    RoundType.ONLINE_ASSESSMENT: "an online assessment",
    RoundType.WRITTEN_EXAM: "a written exam",
    RoundType.TECHNICAL_INTERVIEW: "a technical interview",
    RoundType.HR_INTERVIEW: "an HR interview",
    RoundType.MANAGERIAL_INTERVIEW: "a managerial interview",
    RoundType.FINAL_DECISION: "the final decision",
    RoundType.OTHER: "a recruitment round",
}

_STAR_PROMPTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"communicat|present|explain|stakeholder", re.I), "Describe a time you had to explain something technical to someone without your background."),
    (re.compile(r"team|collaborat|cross-functional", re.I), "Tell me about a time you disagreed with a teammate. How did you resolve it?"),
    (re.compile(r"lead|mentor|ownership", re.I), "Tell me about a time you took ownership of something without being asked."),
    (re.compile(r"problem|analytical|debug", re.I), "Describe the hardest problem you've solved recently. How did you approach it?"),
    (re.compile(r"learn|curious|adapt", re.I), "Tell me about a time you had to learn something new quickly."),
    (re.compile(r"detail|quality", re.I), "Tell me about a mistake you caught (or made). What did you change afterwards?"),
]


def _short(text: str, limit: int = 70) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _as_time_you(responsibility: str) -> str:
    """'Build and maintain REST APIs' -> 'had to build and maintain REST APIs'."""
    text = responsibility.strip().rstrip(".")
    first, _, rest = text.partition(" ")
    if first.isupper():  # an acronym: keep it
        return f"worked on {text}"
    return f"had to {first.lower()} {rest}".strip()


def suggest(
    requirements: list[RequirementIn],
    gaps: list[GapIn],
    questions: list[QuestionIn],
    round_type: RoundType | None,
) -> list[Suggestion]:
    out: list[Suggestion] = []
    seen_titles: set[str] = set()

    def add(s: Suggestion) -> None:
        if s.title not in seen_titles:
            seen_titles.add(s.title)
            out.append(s)

    if round_type in _ROUND_TIPS:
        title, detail = _ROUND_TIPS[round_type]
        add(Suggestion(SuggestionKind.ROUND_FORMAT, title, detail, f"This round is {_ROUND_NAMES[round_type]}.", 2))

    for r in requirements:
        priority = _IMPORTANCE_PRIORITY[r.importance]
        if r.category == Category.RESPONSIBILITY:
            add(
                Suggestion(
                    SuggestionKind.BEHAVIORAL_QUESTION,
                    f"Practice question (STAR): “Tell me about a time you {_as_time_you(r.text)}.”",
                    "Answer with Situation, Task, Action, Result, using a real example. " + _PRACTICE_NOTE,
                    f"The posting lists this responsibility: “{_short(r.text)}”.",
                    3,
                    True,
                    requirement_id=r.id,
                )
            )
            continue
        if r.category == Category.COLLABORATION:
            prompt = next((q for pattern, q in _STAR_PROMPTS if pattern.search(r.text)), None)
            add(
                Suggestion(
                    SuggestionKind.BEHAVIORAL_QUESTION,
                    f"Practice question (STAR): “{prompt or f'Describe a situation that shows: {_short(r.text, 60)}.'}”",
                    "Prepare one real example and practise telling it in about two minutes. " + _PRACTICE_NOTE,
                    f"The posting asks for: “{_short(r.text)}”.",
                    priority,
                    True,
                    requirement_id=r.id,
                )
            )
            continue
        if not r.terms:
            continue

        direct = [e for e in r.evidence if e.relevance == Relevance.DIRECT]
        for term in r.terms:
            used = [e for e in direct if term in e.terms]
            if used:
                passage = used[0].passage_text
                add(
                    Suggestion(
                        SuggestionKind.PROJECT_QUESTION,
                        f"Practice question: “Walk me through how you used {term} in: {_short(passage, 60)}”",
                        "Be ready to explain what you built, your own role, why you chose it, what was hard, and what "
                        "you'd do differently. Interviewers often probe the work that matches their requirements. "
                        + _PRACTICE_NOTE,
                        f"Your CV shows {term} in use, and the job {'requires' if r.importance == Importance.REQUIRED else 'mentions'} it.",
                        priority,
                        True,
                        requirement_id=r.id,
                    )
                )
            elif any(term in e.terms for e in r.evidence if e.relevance in (Relevance.LISTED, Relevance.RELATED)):
                add(
                    Suggestion(
                        SuggestionKind.REVIEW_TOPIC,
                        f"Review {term} fundamentals",
                        f"Your CV names {term} or something related but doesn't show it in use, so expect questions "
                        f"that check depth. Practice question: “What is {term} used for, and what are its trade-offs?”",
                        f"“{_short(r.text)}”: {('partly shown' if r.status == EvidenceStatus.PARTIALLY_DEMONSTRATED else 'not demonstrated')} in your CV.",
                        priority,
                        True,
                        requirement_id=r.id,
                    )
                )
            elif r.status == EvidenceStatus.NOT_FOUND_IN_CV or not r.evidence:
                learning = r.self_report == "learning"
                add(
                    Suggestion(
                        SuggestionKind.CHALLENGING_AREA,
                        f"Prepare an honest answer about {term}",
                        (
                            f"If {term} comes up, say what you know and how you're learning it."
                            if learning
                            else f"Your CV doesn't mention {term}. If it comes up, be honest about your experience "
                            "and explain how you'd get up to speed. Don't overstate it."
                        ),
                        f"The job {'requires' if r.importance == Importance.REQUIRED else 'mentions'} {term}, and this CV doesn't show it.",
                        priority + 1,
                        requirement_id=r.id,
                    )
                )

    for gap in sorted(gaps, key=lambda g: g.priority):
        kind = gap.gap_type.replace("_", " ")
        add(
            Suggestion(
                SuggestionKind.GAP_PRACTICE,
                f"Work on your {gap.skill_name} gap before this round",
                "Open its page in your learning plan, do one focused practice session, and log it.",
                f"{gap.skill_name} is an open gap in your learning plan" + (f" ({kind})" if gap.gap_type != "unclassified" else "") + " and relevant to this job.",
                min(gap.priority, 3),
                skill_gap_id=gap.id,
            )
        )

    for q in questions:
        add(
            Suggestion(
                SuggestionKind.REVISIT_QUESTION,
                f"Re-attempt: “{_short(q.text, 80)}”",
                "Answer it from memory first, then compare with your earlier attempts on the question's page.",
                f"You recorded this question before, on {q.topic or 'a related topic'}, and haven't marked it comfortable.",
                2,
                question_id=q.id,
            )
        )

    out.sort(key=lambda s: s.priority)
    return out
