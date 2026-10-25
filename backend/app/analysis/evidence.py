"""Compares one job requirement with the passages of a CV.

The verdict describes the CV, never the person:
- demonstrated: the CV shows the skill being used (experience, projects…);
- partially demonstrated: it is only listed, or only a related skill is used;
- not found in CV: the CV doesn't mention it. That is not evidence of absence;
- needs verification: text matching can't decide (soft skills, years, vague lines).

Every verdict comes with the passages it relied on and a plain explanation.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum

from app.analysis.cv_parser import SectionType
from app.analysis.jd_extractor import Category, MatchMode
from app.analysis.skills import SKILLS_BY_NAME, find_skills


class EvidenceStatus(StrEnum):
    DEMONSTRATED = "demonstrated"
    PARTIALLY_DEMONSTRATED = "partially_demonstrated"
    NOT_FOUND_IN_CV = "not_found_in_cv"
    NEEDS_VERIFICATION = "needs_verification"


class Relevance(StrEnum):
    DIRECT = "direct"  # the skill appears where it was used
    LISTED = "listed"  # the skill is named, but not shown in use
    RELATED = "related"  # a related skill is used
    POSSIBLE = "possible"  # shares wording with the requirement; a person should judge


# Sections that describe things you did (use), versus sections that list or summarise.
USAGE_SECTIONS = {
    SectionType.EXPERIENCE,
    SectionType.INTERNSHIP,
    SectionType.PROJECTS,
    SectionType.OTHER_EXPERIENCE,
    SectionType.ACHIEVEMENTS,
}
SECTION_NAMES = {
    SectionType.HEADER: "contact details",
    SectionType.SUMMARY: "summary",
    SectionType.EDUCATION: "education",
    SectionType.SKILLS: "skills list",
    SectionType.EXPERIENCE: "work experience",
    SectionType.INTERNSHIP: "internships",
    SectionType.PROJECTS: "projects",
    SectionType.CERTIFICATIONS: "certifications",
    SectionType.ACHIEVEMENTS: "achievements",
    SectionType.OTHER_EXPERIENCE: "other experience",
    SectionType.OTHER: "other sections",
    SectionType.UNRECOGNIZED: "an unrecognized block",
}
# Families too broad to call two members "related" (Java is not related experience for Python).
UNRELATED_FAMILIES = {"language", "markup", "query", "cs_fundamentals", "process", "testing"}

_FIELD_WORDS = re.compile(
    r"\b(computer science|software engineering|computer engineering|information technology|"
    r"electrical|electronics|mathematics|statistics|data science|engineering|physics)\b",
    re.IGNORECASE,
)
_PEOPLE_WORDS = re.compile(
    r"\b(team|collaborat\w*|present\w*|communicat\w*|mentor\w*|led|lead\w*|coordinat\w*|organi[sz]\w*|"
    r"stakeholders?|clients?|customers?|volunteer\w*)\b",
    re.IGNORECASE,
)
_STOPWORDS = {
    "with", "that", "this", "from", "have", "will", "your", "their", "into", "using", "used", "work", "working",
    "experience", "ability", "able", "knowledge", "understanding", "strong", "good", "excellent", "skills",
    "skill", "years", "year", "least", "plus", "including", "such", "other", "about", "across", "within",
    "should", "would", "must", "required", "preferred", "familiarity", "familiar", "proficiency", "proficient",
}


@dataclass
class PassageInput:
    id: str
    text: str
    section_type: SectionType


@dataclass
class EvidenceLink:
    passage_id: str
    relevance: Relevance
    matched_terms: list[str]
    note: str


@dataclass
class Assessment:
    status: EvidenceStatus
    rationale: str
    missing_details: str | None
    suggested_action: str
    evidence: list[EvidenceLink] = field(default_factory=list)


def _join(names: list[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z+#.]{3,}", text.lower()) if w not in _STOPWORDS}


class _CV:
    """Passages with the skills found in each, computed once per analysis."""

    def __init__(self, passages: list[PassageInput]) -> None:
        self.passages = passages
        self.skills = {p.id: {s.name for s, _, _ in find_skills(p.text)} for p in passages}

    def with_skill(self, name: str) -> list[PassageInput]:
        return [p for p in self.passages if name in self.skills[p.id]]


def _assess_term(cv: _CV, term: str) -> tuple[str, list[EvidenceLink], str]:
    """Returns (level, links, description) with level in direct/listed/related/missing."""
    hits = cv.with_skill(term)
    used = [p for p in hits if p.section_type in USAGE_SECTIONS]
    if used:
        where = _join(sorted({SECTION_NAMES[p.section_type] for p in used}))
        links = [EvidenceLink(p.id, Relevance.DIRECT, [term], f"{term} appears in your {SECTION_NAMES[p.section_type]}.") for p in used]
        return "direct", links, f"{term}: used in your {where}"
    if hits:
        where = _join(sorted({SECTION_NAMES[p.section_type] for p in hits}))
        links = [EvidenceLink(p.id, Relevance.LISTED, [term], f"{term} is named here, but not shown in use.") for p in hits]
        return "listed", links, f"{term}: named in your {where} only"

    family = SKILLS_BY_NAME[term].family
    if family and family not in UNRELATED_FAMILIES:
        relatives = [s for s in SKILLS_BY_NAME.values() if s.family == family and s.name != term]
        links: list[EvidenceLink] = []
        names: list[str] = []
        for relative in relatives:
            for p in cv.with_skill(relative.name):
                if p.section_type in USAGE_SECTIONS:
                    links.append(EvidenceLink(p.id, Relevance.RELATED, [relative.name], f"{relative.name} is related to {term}, not the same."))
                    if relative.name not in names:
                        names.append(relative.name)
        if links:
            return "related", links, f"{term}: not mentioned, but you've used related {_join(names)}"
    return "missing", [], f"{term}: not mentioned"


def _assess_terms(cv: _CV, terms: list[str], mode: MatchMode, category: Category) -> Assessment:
    results = [(term, *_assess_term(cv, term)) for term in terms]
    levels = [level for _, level, _, _ in results]
    evidence = [link for _, _, links, _ in results for link in links]
    rationale = "; ".join(description for _, _, _, description in results) + "."

    if mode == MatchMode.ANY:
        best = "direct" if "direct" in levels else "listed" if "listed" in levels else "related" if "related" in levels else "missing"
        levels_for_status = [best]
        rationale = "Any one of these is enough. " + rationale
    else:
        levels_for_status = levels

    if all(level == "direct" for level in levels_for_status):
        status = EvidenceStatus.DEMONSTRATED
    elif all(level == "missing" for level in levels_for_status):
        status = EvidenceStatus.NOT_FOUND_IN_CV
    else:
        status = EvidenceStatus.PARTIALLY_DEMONSTRATED

    gaps = [term for term, level, _, _ in results if level != "direct"] if mode == MatchMode.ALL else (
        [] if "direct" in levels else terms
    )
    missing_parts: list[str] = []
    listed = [t for t, level, _, _ in results if level == "listed" and t in gaps]
    related = [t for t, level, _, _ in results if level == "related" and t in gaps]
    absent = [t for t, level, _, _ in results if level == "missing" and t in gaps]
    if listed:
        missing_parts.append(f"{_join(listed)} {'is' if len(listed) == 1 else 'are'} named but no project or role shows how you used {'it' if len(listed) == 1 else 'them'}.")
    if related:
        missing_parts.append(f"Only related technology is shown for {_join(related)}.")
    if absent:
        missing_parts.append(
            f"{_join(absent)} {'is' if len(absent) == 1 else 'are'} not mentioned in this CV. "
            "That doesn't mean you lack it: the CV just doesn't show it."
        )

    if status == EvidenceStatus.DEMONSTRATED:
        action = "Check that the bullet says what you did and what came of it, not only which tools were involved."
    elif status == EvidenceStatus.NOT_FOUND_IN_CV:
        action = (
            "If you have this, add a real example to your CV and set your assessment to “I have this”. "
            "If you don't, mark “I don't have this” so it can become a learning goal."
        )
    else:
        action = "If you've used it in practice, add a bullet to a project or role describing what you did with it."

    if category == Category.EXPERIENCE and status == EvidenceStatus.DEMONSTRATED:
        status = EvidenceStatus.PARTIALLY_DEMONSTRATED
        missing_parts.append("The CV can't confirm how many years of experience you have.")
        action = "Make the dates of each role and project clear, so the duration is visible."

    return Assessment(status, rationale, " ".join(missing_parts) or None, action, evidence)


def _possible_matches(cv: _CV, requirement_text: str, sections: set[SectionType] | None = None) -> list[EvidenceLink]:
    wanted = _content_words(requirement_text)
    links = []
    for p in cv.passages:
        if sections is not None and p.section_type not in sections:
            continue
        shared = sorted(wanted & _content_words(p.text))
        if len(shared) >= 2:
            links.append(EvidenceLink(p.id, Relevance.POSSIBLE, [], f"Shares the words: {', '.join(shared[:4])}."))
    return links[:5]


def assess(
    requirement_text: str, category: Category, terms: list[str], mode: MatchMode, passages: list[PassageInput]
) -> Assessment:
    if not passages:
        return Assessment(
            EvidenceStatus.NEEDS_VERIFICATION,
            "The CV's text couldn't be read, so nothing could be checked.",
            None,
            "Upload a text-based PDF or DOCX version of your CV and run the analysis again.",
        )
    cv = _CV(passages)

    if terms:
        return _assess_terms(cv, terms, mode, category)

    if category == Category.EDUCATION:
        education = [p for p in passages if p.section_type == SectionType.EDUCATION]
        fields = {f.lower() for f in _FIELD_WORDS.findall(requirement_text)}
        matching = [p for p in education if any(f in p.text.lower() for f in fields)]
        if matching:
            links = [EvidenceLink(p.id, Relevance.DIRECT, sorted(fields), "Names the field of study asked for.") for p in matching]
            return Assessment(
                EvidenceStatus.DEMONSTRATED,
                "Your education section names the field of study this job asks for.",
                "The degree level and grades weren't checked.",
                "Make sure the degree, institution and dates are clearly stated.",
                links,
            )
        if education:
            return Assessment(
                EvidenceStatus.NEEDS_VERIFICATION,
                "You have an education section, but it doesn't name the field this requirement mentions.",
                "Check whether your degree counts as a “related field” for this employer.",
                "If your field is relevant, make the connection explicit (e.g. relevant coursework).",
                [EvidenceLink(p.id, Relevance.POSSIBLE, [], "Your education; compare it with the requirement.") for p in education],
            )
        return Assessment(
            EvidenceStatus.NOT_FOUND_IN_CV,
            "No education section was found in this CV.",
            "The CV doesn't show your education. That doesn't mean you lack the qualification.",
            "Add an education section, or set the section type if it was read under another heading.",
        )

    if category == Category.COLLABORATION:
        people = [p for p in passages if _PEOPLE_WORDS.search(p.text)]
        return Assessment(
            EvidenceStatus.NEEDS_VERIFICATION,
            "This is about how you work with people. Keyword matching can't judge it.",
            "A concrete example (who, what, outcome) is what demonstrates this, in the CV or an interview story.",
            "Pick one real situation that shows this and describe it in a bullet or a STAR interview answer.",
            [EvidenceLink(p.id, Relevance.POSSIBLE, [], "Mentions working with others; check whether it shows this.") for p in people[:5]],
        )

    possible = _possible_matches(cv, requirement_text, USAGE_SECTIONS)
    return Assessment(
        EvidenceStatus.NEEDS_VERIFICATION,
        (
            "No known skill terms in this requirement, so it couldn't be matched automatically. "
            + ("Some passages share wording with it." if possible else "No passages share its wording.")
        ),
        "Decide whether your experience covers this.",
        "If it does, make sure one bullet clearly shows it; then set your assessment.",
        possible,
    )
