"""CV improvement suggestions, derived from an analysed requirement.

The aim is to communicate real experience better, never to make the
candidate look more impressive than they are:
- rewrites only restructure the original text and add [bracketed gaps] for
  the candidate to fill; they never state an outcome or a number;
- "possible capability gap" is only raised when the candidate said so;
- a skill the candidate says they don't have is flagged for removal, not
  dressed up.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum

from app.analysis.cv_parser import SectionType
from app.analysis.evidence import EvidenceStatus, Relevance
from app.analysis.jd_extractor import Category, Importance, MatchMode


class Kind(StrEnum):
    PRESENTATION = "presentation"  # the experience is there, but poorly communicated
    EVIDENCE_GAP = "evidence_gap"  # not enough in the CV to judge
    POTENTIAL_CAPABILITY_GAP = "potential_capability_gap"  # the candidate says they don't have it (yet)
    UNVERIFIED_CLAIM = "unverified_claim"  # claimed without anything to back it up


class ChangeType(StrEnum):
    REWRITE_PASSAGE = "rewrite_passage"
    ADD_BULLET = "add_bullet"
    REMOVE_OR_VERIFY = "remove_or_verify"
    NO_CV_CHANGE = "no_cv_change"


# Words that suggest a bullet already says what came of the work.
_OUTCOME = re.compile(
    r"\d|\b(reduc|improv|increas|decreas|sav|cut|faster|enabl|allow|result|led to|help|grew|won|achiev|"
    r"deliver|launch|adopt|used by|so that|which)\w*",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")

_TRUTH = "Every detail you add is true, and you could talk about it in an interview."
_NO_NUMBERS = "Don't add numbers you can't back up. A plain description of the result is fine."


@dataclass
class EvidenceInput:
    passage_id: str
    passage_text: str
    section_type: SectionType
    relevance: Relevance
    matched_terms: list[str]
    note: str = ""


@dataclass
class RequirementInput:
    text: str
    category: Category
    importance: Importance
    status: EvidenceStatus
    self_report: str  # "unknown" | "have_not_on_cv" | "do_not_have" | "learning"
    terms: list[str]
    match_mode: MatchMode
    evidence: list[EvidenceInput] = field(default_factory=list)


@dataclass
class Draft:
    kind: Kind
    change_type: ChangeType
    title: str
    rationale: str
    passage_id: str | None = None
    original_text: str | None = None
    suggested_text: str | None = None
    assumptions: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)

    def key(self) -> tuple:
        return (self.kind, self.change_type, self.passage_id, tuple(sorted(self.terms)), self.title)


def numbers_in(text: str | None) -> set[str]:
    return set(_NUMBER.findall(text or ""))


def new_numbers(original: str | None, text: str | None) -> list[str]:
    """Numbers in `text` that weren't in `original`: these need checking before use."""
    return sorted(numbers_in(text) - numbers_in(original))


def _importance_phrase(importance: Importance) -> str:
    return {
        Importance.REQUIRED: "lists it as required",
        Importance.PREFERRED: "lists it as preferred",
        Importance.UNCERTAIN: "mentions it",
    }[importance]


def _without_term(passage: str, term: str) -> str | None:
    """The passage with `term` removed from a comma/semicolon list, or None if that isn't safe."""
    pattern = re.compile(rf"(?<![\w+#.]){re.escape(term)}(?![\w+#])", re.IGNORECASE)
    if len(pattern.findall(passage)) != 1:
        return None
    result = re.sub(rf"\s*{pattern.pattern}\s*(,|;|\|)\s*", " ", passage, count=1, flags=re.IGNORECASE)
    if result == passage:
        result = re.sub(rf"\s*(,|;|\||and)\s*{pattern.pattern}", "", passage, count=1, flags=re.IGNORECASE)
    result = re.sub(r":\s+", ": ", result).strip()
    return None if result == passage or result.endswith(":") else result


def _outcome_rewrite(passage: str) -> str:
    """Keeps the original wording and adds gaps for purpose and result. Adds no facts."""
    base = passage.rstrip().rstrip(".;,")
    return f"{base} [for what purpose or in which project], [and what changed as a result]."


def _new_bullet(term: str) -> str:
    return f"[What you did] using {term} in [which project, course or role], [and what came of it]."


def generate(requirement: RequirementInput) -> list[Draft]:
    """Suggestions for one requirement. Responsibilities only yield presentation tips."""
    drafts: list[Draft] = []
    r = requirement

    direct = [e for e in r.evidence if e.relevance == Relevance.DIRECT]
    direct_terms = {t for e in direct for t in e.matched_terms}

    # A. Shown in use, but the bullet doesn't say what came of it.
    for e in direct:
        if e.section_type == SectionType.EDUCATION or _OUTCOME.search(e.passage_text):
            continue
        drafts.append(
            Draft(
                Kind.PRESENTATION,
                ChangeType.REWRITE_PASSAGE,
                "Say what this work was for and what came of it",
                f"This bullet shows {', '.join(e.matched_terms) or 'relevant work'}, which the job asks for, but not "
                "its purpose or result. Recruiters read results as evidence of how well you used a skill.",
                e.passage_id,
                e.passage_text,
                _outcome_rewrite(e.passage_text),
                ["Fill each [gap] only with what really happened; delete any you can't fill.", _NO_NUMBERS],
                list(e.matched_terms),
            )
        )

    if r.category == Category.RESPONSIBILITY:
        return drafts

    def listed_for(term: str) -> list[EvidenceInput]:
        return [e for e in r.evidence if e.relevance == Relevance.LISTED and term in e.matched_terms]

    def related_for(term: str) -> list[EvidenceInput]:
        # The matcher's note names the requirement term a related skill stands in for.
        return [e for e in r.evidence if e.relevance == Relevance.RELATED and f"related to {term}," in e.note]

    # Which terms need a suggestion.
    terms = [t for t in r.terms if t not in direct_terms]
    if r.match_mode == MatchMode.ANY and r.terms:
        if direct_terms:
            terms = []  # one demonstrated alternative is enough
        else:
            partly = [t for t in r.terms if listed_for(t) or related_for(t)]
            # Suggest for the alternatives that are partly there; if none are, ask about the group once.
            terms = partly or [" or ".join(r.terms)]

    for term in terms:
        listed = listed_for(term)
        related = related_for(term)

        # B. Listed with nothing to back it up.
        if listed:
            e = listed[0]
            if r.self_report == "do_not_have":
                drafts.append(
                    Draft(
                        Kind.UNVERIFIED_CLAIM,
                        ChangeType.REMOVE_OR_VERIFY,
                        f"Your CV lists {term}, but you said you don't have it",
                        "A listed skill invites interview questions about it. If you can't use it yet, it's safer "
                        "to remove it until you can.",
                        e.passage_id,
                        e.passage_text,
                        _without_term(e.passage_text, term),
                        [f"You really can't use {term} at a basic level yet."],
                        [term],
                    )
                )
            else:
                drafts.append(
                    Draft(
                        Kind.UNVERIFIED_CLAIM,
                        ChangeType.ADD_BULLET,
                        f"Back up {term} with an example",
                        f"{term} appears in your {('skills list' if e.section_type == SectionType.SKILLS else 'CV')}, "
                        "but no role or project shows how you used it. The job "
                        f"{_importance_phrase(r.importance)}, so a concrete example matters.",
                        e.passage_id,
                        e.passage_text,
                        _new_bullet(term),
                        [f"You have actually used {term} in a real project, course or job.", _TRUTH, _NO_NUMBERS],
                        [term],
                    )
                )
            continue

        # C. Only related experience.
        if related:
            names = sorted({t for e in related for t in e.matched_terms})
            has_it = r.self_report == "have_not_on_cv"
            drafts.append(
                Draft(
                    Kind.EVIDENCE_GAP,
                    ChangeType.ADD_BULLET if has_it else ChangeType.NO_CV_CHANGE,
                    f"Clarify your {term} experience",
                    f"Your CV shows {', '.join(names)}, which is related to {term} but not the same. A reader may not "
                    "make the connection." + ("" if has_it else f" If you've used {term} itself, say so."),
                    related[0].passage_id,
                    related[0].passage_text,
                    _new_bullet(term) if has_it else None,
                    ([f"You confirmed you have used {term}.", _TRUTH] if has_it else []),
                    [term],
                )
            )
            continue

        # D. Not in the CV at all.
        if r.self_report == "have_not_on_cv":
            drafts.append(
                Draft(
                    Kind.EVIDENCE_GAP,
                    ChangeType.ADD_BULLET,
                    f"Add your {term} experience to the CV",
                    f"You said you have {term}, but this CV doesn't show it, and the job "
                    f"{_importance_phrase(r.importance)}.",
                    suggested_text=_new_bullet(term),
                    assumptions=[f"You confirmed you have {term}.", _TRUTH, _NO_NUMBERS],
                    terms=[term],
                )
            )
        elif r.self_report in ("do_not_have", "learning"):
            drafts.append(
                Draft(
                    Kind.POTENTIAL_CAPABILITY_GAP,
                    ChangeType.NO_CV_CHANGE,
                    f"{term} may be worth learning",
                    f"The job {_importance_phrase(r.importance)}, and you said "
                    + ("you're learning it." if r.self_report == "learning" else "you don't have it yet.")
                    + " Don't add it to your CV until you can show real use. This can become a learning goal.",
                    terms=[term],
                )
            )
        else:
            drafts.append(
                Draft(
                    Kind.EVIDENCE_GAP,
                    ChangeType.NO_CV_CHANGE,
                    f"Do you have {term}?",
                    f"This CV doesn't mention {term}. That doesn't mean you lack it. Set your assessment on the "
                    "requirement: if you have it, CareerLens will suggest how to show it.",
                    terms=[term],
                )
            )

    # E. Things text matching can't settle.
    if not r.terms and r.status == EvidenceStatus.NEEDS_VERIFICATION:
        possible = [e for e in r.evidence if e.relevance == Relevance.POSSIBLE]
        if r.category == Category.COLLABORATION:
            drafts.append(
                Draft(
                    Kind.EVIDENCE_GAP,
                    ChangeType.ADD_BULLET,
                    "Show one real example of this",
                    "Soft skills are judged by examples, not by naming them. One concrete situation in a bullet "
                    "(or a prepared interview story) is stronger than listing the skill.",
                    suggested_text="[Situation]: [what you did, and with whom], [what came of it].",
                    assumptions=["Use a real situation.", _TRUTH],
                )
            )
        elif possible:
            e = possible[0]
            drafts.append(
                Draft(
                    Kind.PRESENTATION,
                    ChangeType.NO_CV_CHANGE,
                    "Make the link to this requirement explicit",
                    "This passage may be relevant, but the connection isn't obvious from the wording. If it does "
                    "cover the requirement, consider using the posting's own terms where they're accurate.",
                    e.passage_id,
                    e.passage_text,
                )
            )

    # F. Durations.
    if r.category == Category.EXPERIENCE and r.status == EvidenceStatus.PARTIALLY_DEMONSTRATED:
        drafts.append(
            Draft(
                Kind.PRESENTATION,
                ChangeType.NO_CV_CHANGE,
                "Make dates and durations easy to see",
                "The job asks for a length of experience, which a reader judges from your dates. Give each role, "
                "internship and project clear start and end months.",
            )
        )

    return drafts


def generate_all(requirements: list[RequirementInput]) -> list[tuple[int, Draft]]:
    """(requirement index, draft) pairs, with duplicates across requirements removed."""
    seen: set[tuple] = set()
    out: list[tuple[int, Draft]] = []
    for index, requirement in enumerate(requirements):
        for draft in generate(requirement):
            if draft.key() in seen:
                continue
            seen.add(draft.key())
            out.append((index, draft))
    return out
