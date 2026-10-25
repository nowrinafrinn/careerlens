"""Turns a job description into a list of requirements.

Rule-based and explainable: section headings in the posting decide whether a
line is required, preferred or a responsibility; words inside a line can
override that; known skills are picked out with `skills.find_skills`. When
nothing says how important a line is, it is "uncertain" rather than guessed.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum

from app.analysis.cv_parser import BULLET
from app.analysis.skills import SKILLS_BY_NAME, find_skills


class Importance(StrEnum):
    REQUIRED = "required"
    PREFERRED = "preferred"
    UNCERTAIN = "uncertain"


class Category(StrEnum):
    TECHNICAL_SKILL = "technical_skill"
    TOOL = "tool"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    PROJECT = "project"
    COLLABORATION = "collaboration"
    RESPONSIBILITY = "responsibility"
    OTHER = "other"


class MatchMode(StrEnum):
    ALL = "all"  # "Python and Django": both needed
    ANY = "any"  # "React or Vue": either is enough


class _Context(StrEnum):
    REQUIRED = "required"
    PREFERRED = "preferred"
    RESPONSIBILITY = "responsibility"
    IGNORE = "ignore"


_HEADINGS: dict[str, _Context] = {}
for context, names in {
    _Context.REQUIRED: [
        "requirements", "requirement", "qualifications", "required qualifications", "minimum qualifications",
        "basic qualifications", "what were looking for", "what we are looking for", "what youll need",
        "what you need", "what you will need", "you have", "who you are", "must have", "must haves",
        "required skills", "skills", "skills and experience", "requirements and qualifications", "your profile",
        "about you", "key skills", "technical skills", "what you bring", "experience and skills",
    ],
    _Context.PREFERRED: [
        "nice to have", "nice to haves", "preferred qualifications", "preferred skills", "bonus points", "bonus",
        "pluses", "good to have", "desirable", "preferred", "its a plus if you have", "extra credit",
        "additional qualifications", "desired skills",
    ],
    _Context.RESPONSIBILITY: [
        "responsibilities", "key responsibilities", "what youll do", "what you will do", "your role", "the role",
        "role", "duties", "job duties", "day to day", "in this role you will", "your responsibilities",
        "job description", "role description", "what you will be doing", "what youll be doing",
    ],
    _Context.IGNORE: [
        "about us", "about the company", "who we are", "benefits", "perks", "what we offer", "why join us",
        "compensation", "salary", "how to apply", "equal opportunity", "our values", "location", "about the team",
        "our benefits", "perks and benefits", "application process",
    ],
}.items():
    for name in names:
        _HEADINGS[name] = context

_PREFERRED_WORDS = re.compile(
    r"\b(nice to have|a plus|is a plus|are a plus|bonus|preferred|preferably|ideally|desirable|advantageous|"
    r"good to have|would be great|beneficial)\b",
    re.IGNORECASE,
)
_REQUIRED_WORDS = re.compile(r"\b(must|required|requirement|essential|mandatory|minimum)\b", re.IGNORECASE)
_EDUCATION = re.compile(
    r"\b(degree|bachelor'?s?|master'?s?|b\.?\s?sc|m\.?\s?sc|phd|diploma|graduate|undergraduate|university)\b",
    re.IGNORECASE,
)
_YEARS = re.compile(r"\b\d+\s*\+?\s*(?:-\s*\d+\s*)?(?:years?|yrs)\b", re.IGNORECASE)
_COLLABORATION = re.compile(
    r"\b(communicat\w*|teamwork|team player|collaborat\w*|interpersonal|problem[- ]solving|self[- ]motivated|"
    r"attention to detail|english|presentation|stakeholders?|independently|fast learner|willing(?:ness)? to learn|"
    r"curious|curiosity|ownership|leadership|mentor\w*)\b",
    re.IGNORECASE,
)
_PROJECT = re.compile(r"\b(projects?|portfolio|github profile|open[- ]source)\b", re.IGNORECASE)
# Lines without a heading context only count if they read like a requirement.
_REQUIREMENT_LIKE = re.compile(
    r"\b(experience|knowledge|proficien\w*|familiar\w*|understanding|skills?|ability|degree|required|must)\b",
    re.IGNORECASE,
)


@dataclass
class ExtractedRequirement:
    text: str
    char_start: int
    char_end: int
    category: Category
    importance: Importance
    terms: list[str] = field(default_factory=list)  # canonical skill names
    match_mode: MatchMode = MatchMode.ALL


def _normalize_heading(line: str) -> str:
    text = line.lower().replace("&", " and ").replace("’", "").replace("'", "")
    text = re.sub(r"[^a-z ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _heading_context(line: str) -> _Context | None:
    if len(line) > 70 or len(line.split()) > 8:
        return None
    normalized = _normalize_heading(line)
    if normalized in _HEADINGS:
        return _HEADINGS[normalized]
    if line.rstrip().endswith(":"):
        # "Requirements for this role:" and similar: match on a known phrase inside.
        for name in sorted(_HEADINGS, key=len, reverse=True):
            if len(name) > 4 and name in normalized:
                return _HEADINGS[name]
    return None


def _lines(text: str) -> list[tuple[int, int]]:
    """(start, end) of each non-blank line, with surrounding spaces trimmed."""
    spans = []
    for match in re.finditer(r"[^\r\n]+", text):
        line = match.group(0)
        stripped = line.strip()
        if stripped:
            start = match.start() + (len(line) - len(line.lstrip()))
            spans.append((start, start + len(stripped)))
    return spans


def _importance(context: _Context | None, line: str) -> Importance:
    if _PREFERRED_WORDS.search(line):
        return Importance.PREFERRED
    if context == _Context.REQUIRED or _REQUIRED_WORDS.search(line):
        return Importance.REQUIRED
    if context == _Context.PREFERRED:
        return Importance.PREFERRED
    return Importance.UNCERTAIN


def _category(context: _Context | None, line: str, terms: list[str]) -> Category:
    if context == _Context.RESPONSIBILITY:
        return Category.RESPONSIBILITY
    if _EDUCATION.search(line):
        return Category.EDUCATION
    if _YEARS.search(line):
        return Category.EXPERIENCE
    if terms:
        kinds = {SKILLS_BY_NAME[t].kind for t in terms}
        return Category.TOOL if kinds == {"tool"} else Category.TECHNICAL_SKILL
    if _COLLABORATION.search(line):
        return Category.COLLABORATION
    if _PROJECT.search(line):
        return Category.PROJECT
    return Category.OTHER


def _match_mode(line: str, found: list[tuple[int, int]]) -> MatchMode:
    if len(found) < 2:
        return MatchMode.ALL
    between = line[found[0][0] : found[-1][1]]
    return MatchMode.ANY if re.search(r"\b(or|either)\b|/", between, re.IGNORECASE) else MatchMode.ALL


def extract_requirements(job_description: str) -> list[ExtractedRequirement]:
    requirements: list[ExtractedRequirement] = []
    context: _Context | None = None

    for start, end in _lines(job_description):
        line = job_description[start:end]
        heading = _heading_context(line)
        if heading is not None:
            context = heading
            continue
        if context == _Context.IGNORE:
            continue

        bullet = BULLET.match(line)
        if bullet:
            start += bullet.end()
            line = job_description[start:end]
        if len(line) < 4 or not re.search(r"[A-Za-z]{3}", line):
            continue
        if context is None and not bullet and not _REQUIREMENT_LIKE.search(line):
            continue  # an intro paragraph, not a requirement

        found = find_skills(line)
        terms: list[str] = []
        for skill, _, _ in found:
            if skill.name not in terms:
                terms.append(skill.name)
        requirements.append(
            ExtractedRequirement(
                text=line,
                char_start=start,
                char_end=end,
                category=_category(context, line, terms),
                importance=_importance(context, line),
                terms=terms,
                match_mode=_match_mode(line, [(s, e) for _, s, e in found]),
            )
        )
    return requirements
