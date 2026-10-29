"""AI-assisted analysis: validation of model output, consent, fallback, retries.

No test talks to a real AI service: providers are fakes that answer the
actual prompt the app builds.
"""

import json
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from google.genai import errors

from app.ai import evidence as ai
from app.ai.gemini import GeminiProvider
from app.ai.provider import AIProviderError, get_ai_provider
from app.analysis.cv_parser import SectionType
from app.analysis.evidence import EvidenceStatus, PassageInput, Relevance
from app.main import app
from tests.test_analyses import find, ready_application

PASSAGES = [
    PassageInput("id-header", "Rafi Ahmed · rafi@example.com · +880 1700 000000", SectionType.HEADER),
    PassageInput("id-skills", "Languages: Python, TypeScript, SQL", SectionType.SKILLS),
    PassageInput("id-intern", "Built REST endpoints with FastAPI for an internal reporting tool.", SectionType.EXPERIENCE),
]
REQUIREMENTS = [
    ai.RequirementInput("r1", "Experience with FastAPI", "tool", "required", ["FastAPI"]),
    ai.RequirementInput("r2", "2+ years of Python", "technical_skill", "required", ["Python"]),
]


def request() -> ai.Request:
    return ai.build_request(REQUIREMENTS, PASSAGES)


def key_of(req: ai.Request, passage_id: str) -> str:
    return next(k for k, p in req.passages.items() if p.id == passage_id)


def verdict(requirement_id: str, status: str, evidence: list[dict] | None = None, **extra) -> dict:
    return {"requirement_id": requirement_id, "status": status, "rationale": extra.pop("rationale", "The CV shows this."),
            "suggested_action": extra.pop("suggested_action", "Keep it on the CV."), "evidence": evidence or [], **extra}


def answer(*verdicts: dict) -> str:
    return json.dumps({"assessments": list(verdicts)})


# --- the prompt -------------------------------------------------------------------------


def test_contact_details_are_never_sent_to_the_model() -> None:
    req = request()

    assert "rafi@example.com" not in req.prompt and "+880" not in req.prompt
    assert {p.id for p in req.passages.values()} == {"id-skills", "id-intern"}
    assert '"r1"' in req.prompt and "Experience with FastAPI" in req.prompt


# --- validation -------------------------------------------------------------------------


def test_a_valid_verdict_is_used_with_real_passage_ids() -> None:
    req = request()
    intern = key_of(req, "id-intern")

    result = ai.validate(answer(
        verdict("r1", "demonstrated", [{"passage_id": intern, "quote": "built REST   endpoints with “FastAPI”",
                                        "relevance": "direct", "note": "Used in an internship."}]),
        verdict("r2", "partially_demonstrated", [{"passage_id": key_of(req, "id-skills"), "quote": "Python",
                                                  "relevance": "listed", "note": ""}],
                rationale="Python is listed but the CV doesn't show 2 years of use."),
    ), req)

    assert result.rejected == {}
    first = result.assessments["r1"]
    assert first.status == EvidenceStatus.DEMONSTRATED
    assert [(e.passage_id, e.relevance, e.matched_terms) for e in first.evidence] == [("id-intern", Relevance.DIRECT, ["FastAPI"])]
    assert result.assessments["r2"].evidence[0].note == "Quoted: “Python”"  # empty note → the quote itself


def test_citing_a_passage_that_does_not_exist_rejects_the_verdict() -> None:
    result = ai.validate(answer(
        verdict("r1", "demonstrated", [{"passage_id": "p99", "quote": "FastAPI", "relevance": "direct", "note": ""}]),
    ), request())

    assert result.rejected["r1"] == "it cited a passage that isn't in this CV"
    assert "r1" not in result.assessments


def test_a_quote_that_is_not_in_the_passage_rejects_the_verdict() -> None:
    req = request()
    result = ai.validate(answer(
        verdict("r1", "demonstrated", [{"passage_id": key_of(req, "id-intern"), "quote": "Led a team of five on FastAPI",
                                        "relevance": "direct", "note": ""}]),
    ), req)

    assert result.rejected["r1"] == "it quoted text that isn't in the passage it cited"


@pytest.mark.parametrize(
    ("status", "relevance", "reason"),
    [
        ("demonstrated", "listed", "without citing a passage that shows it in use"),
        ("not_found_in_cv", "listed", "while citing a passage that mentions it"),
    ],
)
def test_a_status_must_be_backed_by_its_citations(status: str, relevance: str, reason: str) -> None:
    req = request()
    result = ai.validate(answer(
        verdict("r2", status, [{"passage_id": key_of(req, "id-skills"), "quote": "Python", "relevance": relevance, "note": ""}]),
    ), req)

    assert reason in result.rejected["r2"]


def test_partly_shown_needs_a_citation() -> None:
    result = ai.validate(answer(verdict("r2", "partially_demonstrated")), request())

    assert "without citing a passage" in result.rejected["r2"]


def test_invented_figures_reject_the_verdict() -> None:
    req = request()
    result = ai.validate(answer(
        verdict("r1", "demonstrated", [{"passage_id": key_of(req, "id-intern"), "quote": "FastAPI", "relevance": "direct", "note": ""}],
                rationale="Built FastAPI services handling 2 million requests a day."),
        # "2" is in the requirement text ("2+ years"), so it may be repeated.
        verdict("r2", "needs_verification", rationale="Whether you have 2 years of Python can't be read from the CV."),
    ), req)

    assert result.rejected["r1"] == "it mentioned figures that aren't in the requirement or the cited passages"
    assert "r2" in result.assessments


def test_missing_unknown_and_repeated_ids_are_never_guessed() -> None:
    req = request()
    result = ai.validate(answer(
        verdict("r9", "needs_verification"),
        verdict("r2", "needs_verification", rationale="First answer."),
        verdict("r2", "not_found_in_cv", rationale="Second answer."),
    ), req)

    assert result.assessments["r2"].rationale == "First answer."
    assert result.rejected == {"r1": "it didn't return a verdict for this requirement"}


@pytest.mark.parametrize("raw", ["not json", "{}", '{"assessments": [{"requirement_id": "r1", "status": "excellent"}]}'])
def test_malformed_output_is_rejected_as_a_whole(raw: str) -> None:
    with pytest.raises(ai.AIOutputError):
        ai.validate(raw, request())


# --- consent and availability -------------------------------------------------------------


class FakeProvider:
    name = "Fake AI"
    model = "fake-1"

    def __init__(self, respond: Callable[[str], str]):
        self.respond = respond
        self.prompts: list[str] = []

    def generate_json(self, system: str, prompt: str, schema: dict) -> str:
        self.prompts.append(prompt)
        return self.respond(prompt)


@pytest.fixture
def use_provider():
    def install(provider):
        app.dependency_overrides[get_ai_provider] = lambda: provider
        return provider

    yield install
    app.dependency_overrides.pop(get_ai_provider, None)


def run_ai(client: TestClient, application_id: str):
    return client.post(f"/api/v1/applications/{application_id}/analyses", params={"method": "ai"})


def test_ai_needs_consent_and_a_configured_provider(ada: TestClient, use_provider) -> None:
    application = ready_application(ada)

    use_provider(None)
    assert ada.get("/api/v1/ai/status").json()["available"] is False
    ada.patch("/api/v1/users/me/ai-consent", json={"consent": True})
    response = run_ai(ada, application["id"])
    assert (response.status_code, response.json()["error"]["code"]) == (503, "ai_unavailable")

    fake = use_provider(FakeProvider(lambda prompt: answer()))
    ada.patch("/api/v1/users/me/ai-consent", json={"consent": False})
    response = run_ai(ada, application["id"])
    assert (response.status_code, response.json()["error"]["code"]) == (403, "ai_consent_required")
    assert fake.prompts == []  # nothing was sent without consent


def test_consent_can_be_given_and_withdrawn(ada: TestClient, use_provider) -> None:
    use_provider(FakeProvider(lambda prompt: answer()))

    given = ada.patch("/api/v1/users/me/ai-consent", json={"consent": True}).json()
    status = ada.get("/api/v1/ai/status").json()
    withdrawn = ada.patch("/api/v1/users/me/ai-consent", json={"consent": False}).json()

    assert given["ai_processing_consent_at"] is not None
    assert status["available"] and status["consented"] and status["provider"] == "Fake AI"
    assert "Fake AI" in status["data_sent"] and "contact details" in status["data_sent"]
    assert withdrawn["ai_processing_consent_at"] is None


# --- running an AI analysis ---------------------------------------------------------------


def _model_answer(prompt: str) -> str:
    """Answers like a model would: valid for the FastAPI line, a bad citation for PostgreSQL."""
    payload = json.loads(prompt.split("\n\n", 1)[1])
    fastapi_passage = next(p["id"] for p in payload["cv_passages"] if "FastAPI" in p["text"])
    verdicts = []
    for requirement in payload["requirements"]:
        if "FastAPI" in requirement["text"]:
            verdicts.append(verdict(requirement["id"], "demonstrated", [
                {"passage_id": fastapi_passage, "quote": "Built REST endpoints with FastAPI", "relevance": "direct",
                 "note": "Shown in the internship."}], rationale="The internship shows FastAPI in use."))
        elif "PostgreSQL" in requirement["text"]:
            verdicts.append(verdict(requirement["id"], "demonstrated", [
                {"passage_id": "p404", "quote": "PostgreSQL", "relevance": "direct", "note": ""}]))
        else:
            verdicts.append(verdict(requirement["id"], "needs_verification", rationale="The CV can't show this on its own.",
                                    suggested_action="Decide for yourself and mark it."))
    return answer(*verdicts)


def test_ai_analysis_uses_valid_verdicts_and_explains_every_fallback(ada: TestClient, use_provider) -> None:
    application = ready_application(ada)
    fake = use_provider(FakeProvider(_model_answer))
    ada.patch("/api/v1/users/me/ai-consent", json={"consent": True})

    response = run_ai(ada, application["id"])

    assert response.status_code == 201, response.text
    analysis = response.json()
    assert analysis["method"] == "ai"
    fastapi = find(analysis, "FastAPI")
    assert (fastapi["assessed_by"], fastapi["evidence_status"]) == ("ai", "demonstrated")
    assert fastapi["evidence_rationale"] == "The internship shows FastAPI in use."
    assert "FastAPI" in fastapi["evidence"][0]["passage_text"]
    postgres = find(analysis, "PostgreSQL")
    assert postgres["assessed_by"] == "rule_engine"  # bad citation → the rule engine's verdict
    assert analysis["notes"][0].startswith("CV evidence was judged by Fake AI (fake-1)")
    assert any("PostgreSQL" in note and "cited a passage that isn't in this CV" in note for note in analysis["notes"])
    assert "rafi@example.com" not in fake.prompts[0]  # the CV's contact header isn't sent


def test_provider_failure_falls_back_to_the_rule_engine_with_a_note(ada: TestClient, use_provider) -> None:
    application = ready_application(ada)

    def fail(prompt: str) -> str:
        raise AIProviderError("The AI service's rate limit was reached. Try again in a minute.")

    use_provider(FakeProvider(fail))
    ada.patch("/api/v1/users/me/ai-consent", json={"consent": True})

    analysis = run_ai(ada, application["id"]).json()

    assert analysis["method"] == "rule_engine"
    assert {r["assessed_by"] for r in analysis["requirements"]} == {"rule_engine"}
    assert analysis["notes"] == ["The AI service's rate limit was reached. Try again in a minute. This analysis used the rule engine instead."]


def test_correcting_a_category_hands_the_verdict_back_to_the_rule_engine(ada: TestClient, use_provider) -> None:
    application = ready_application(ada)
    use_provider(FakeProvider(_model_answer))
    ada.patch("/api/v1/users/me/ai-consent", json={"consent": True})
    fastapi = find(run_ai(ada, application["id"]).json(), "FastAPI")

    updated = ada.patch(f"/api/v1/requirements/{fastapi['id']}", json={"category": "technical_skill"}).json()

    assert updated["assessed_by"] == "rule_engine"


# --- Gemini provider retries --------------------------------------------------------------


class _Response:
    text = '{"assessments": []}'


class _Models:
    def __init__(self, outcomes: list):
        self.outcomes = outcomes
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _Client:
    def __init__(self, outcomes: list):
        self.models = _Models(outcomes)


def gemini(outcomes: list, sleeps: list[float]) -> GeminiProvider:
    return GeminiProvider(api_key="test", model="gemini-test", max_attempts=3, sleep=sleeps.append, client=_Client(outcomes))


def api_error(code: int) -> errors.APIError:
    return errors.APIError(code, {"error": {"code": code, "message": "x", "status": "X"}})


def test_gemini_retries_rate_limits_with_backoff() -> None:
    sleeps: list[float] = []
    provider = gemini([api_error(429), api_error(503), _Response()], sleeps)

    assert provider.generate_json("s", "p", {}) == '{"assessments": []}'
    assert sleeps == [1, 2]


def test_gemini_gives_up_after_its_attempts_with_a_safe_reason() -> None:
    sleeps: list[float] = []
    provider = gemini([api_error(429)] * 3, sleeps)

    with pytest.raises(AIProviderError, match="rate limit"):
        provider.generate_json("s", "p", {})
    assert sleeps == [1, 2]


def test_gemini_does_not_retry_a_rejected_key() -> None:
    sleeps: list[float] = []
    provider = gemini([api_error(403)], sleeps)

    with pytest.raises(AIProviderError, match="rejected the API key"):
        provider.generate_json("s", "p", {})
    assert sleeps == [] and provider._client.models.calls == 1
