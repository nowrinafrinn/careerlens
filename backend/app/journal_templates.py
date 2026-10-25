"""Structured prompts for recruitment journals.

Defined in code (not the database) so the form, the validation and the
history all agree. The API serves them at GET /journal-templates.
"""

from dataclasses import dataclass
from enum import StrEnum


class JournalTemplate(StrEnum):
    TECHNICAL_ASSESSMENT = "technical_assessment"
    WRITTEN_EXAM = "written_exam"
    INTERVIEW = "interview"
    GENERAL = "general"


@dataclass(frozen=True)
class Prompt:
    key: str
    question: str
    hint: str = ""


_WHAT_HAPPENED = Prompt("what_happened", "What happened during this round?", "Format, length, who was there, how it went overall.")
_TOPICS = Prompt("topics", "What questions or topics came up?", "Record individual questions below, too.")
_CONFIDENT = Prompt("confident", "Which could you answer confidently?")
_PARTIAL = Prompt("partial", "Which could you answer only partly?")
_COULD_NOT = Prompt("could_not_answer", "Which couldn't you answer?")
_CAUSE = Prompt(
    "cause_of_difficulty",
    "What caused the difficulty?",
    "Not knowing the concept, not applying it, running out of time, not recalling it, or explaining it.",
)
_LEARNED = Prompt("learned_about_preparation", "What did this show about your current preparation?")
_DIFFERENTLY = Prompt("do_differently", "What would you do differently next time?")
_NEXT = Prompt("next_actions", "What specific things will you do before the next round?")

TEMPLATES: dict[JournalTemplate, dict] = {
    JournalTemplate.TECHNICAL_ASSESSMENT: {
        "label": "Technical assessment",
        "description": "Online tests, coding challenges, take-home tasks.",
        "prompts": [_WHAT_HAPPENED, _TOPICS, _CONFIDENT, _PARTIAL, _COULD_NOT, _CAUSE, _LEARNED, _DIFFERENTLY, _NEXT],
    },
    JournalTemplate.WRITTEN_EXAM: {
        "label": "Written exam",
        "description": "Written or aptitude exams, often timed.",
        "prompts": [
            Prompt("what_happened", "What happened during the exam?", "Sections, time limit, how you paced it."),
            _TOPICS, _CONFIDENT, _PARTIAL, _COULD_NOT, _CAUSE, _LEARNED, _DIFFERENTLY, _NEXT,
        ],
    },
    JournalTemplate.INTERVIEW: {
        "label": "Interview",
        "description": "Technical, HR or managerial interviews.",
        "prompts": [
            Prompt("what_happened", "What happened during the interview?", "Who interviewed you, the structure, the tone."),
            _TOPICS,
            Prompt("struggled_to_explain", "Which topics did you struggle to explain?"),
            Prompt("project_questions", "What were you asked about your own projects?"),
            _CAUSE, _LEARNED, _DIFFERENTLY, _NEXT,
        ],
    },
    JournalTemplate.GENERAL: {
        "label": "General note",
        "description": "Anything else worth recording about this application.",
        "prompts": [_WHAT_HAPPENED, _LEARNED, _DIFFERENTLY, _NEXT],
    },
}


def prompt_keys(template: JournalTemplate) -> set[str]:
    return {prompt.key for prompt in TEMPLATES[template]["prompts"]}
