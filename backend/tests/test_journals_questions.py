from fastapi.testclient import TestClient

from tests.conftest import act_as, sign_up


def application(client: TestClient, company: str = "Acme", position: str = "Backend Engineer") -> dict:
    response = client.post("/api/v1/applications", json={"company_name": company, "position_title": position})
    assert response.status_code == 201, response.text
    return response.json()


def add_round(client: TestClient, application_id: str, round_type: str = "technical_interview", name: str = "Tech interview") -> dict:
    response = client.post(f"/api/v1/applications/{application_id}/rounds", json={"name": name, "round_type": round_type})
    assert response.status_code == 201, response.text
    return response.json()


def journal(client: TestClient, app: dict, rnd: dict | None = None, **fields) -> dict:
    payload = {
        "application_id": app["id"],
        "round_id": rnd["id"] if rnd else None,
        "template": "interview",
        "occurred_on": "2026-10-20",
        "responses": {"what_happened": "45 minutes with two engineers.", "struggled_to_explain": "Database indexing"},
        "interviewer_feedback": "Said my API design answer was solid.",
        "user_interpretation": "I think the indexing answer cost me.",
        "questions": [
            {"text": "How does a B-tree index speed up queries?", "topic": "Databases", "difficulty": "medium",
             "original_answer": "It keeps keys sorted so lookups are logarithmic.", "response_quality": "partial",
             "confidence": 2, "time_spent_minutes": 6, "difficulty_reason": "Couldn't explain page splits."},
            {"text": "Design a REST API for orders", "topic": "API design", "response_quality": "confident", "confidence": 4},
        ],
        **fields,
    }
    response = client.post("/api/v1/journals", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def search(client: TestClient, **params) -> dict:
    response = client.get("/api/v1/questions", params=params)
    assert response.status_code == 200, response.text
    return response.json()


# --- templates and journals ----------------------------------------------------------------


def test_templates_list_their_prompts(ada: TestClient) -> None:
    templates = {t["template"]: t for t in ada.get("/api/v1/journal-templates").json()}

    assert set(templates) == {"technical_assessment", "written_exam", "interview", "general"}
    interview_keys = [p["key"] for p in templates["interview"]["prompts"]]
    assert "struggled_to_explain" in interview_keys and "project_questions" in interview_keys
    technical_keys = [p["key"] for p in templates["technical_assessment"]["prompts"]]
    assert technical_keys[:5] == ["what_happened", "topics", "confident", "partial", "could_not_answer"]


def test_journal_records_questions_and_keeps_feedback_apart_from_interpretation(ada: TestClient) -> None:
    app = application(ada)
    rnd = add_round(ada, app["id"])

    entry = journal(ada, app, rnd)

    assert entry["round_name"] == "Tech interview"
    assert entry["company_name"] == "Acme"
    assert entry["interviewer_feedback"] == "Said my API design answer was solid."
    assert entry["user_interpretation"] == "I think the indexing answer cost me."
    assert [q["text"] for q in entry["questions"]] == [
        "How does a B-tree index speed up queries?",
        "Design a REST API for orders",
    ]
    first = entry["questions"][0]
    assert (first["journal_id"], first["round_id"], first["application_id"]) == (entry["id"], rnd["id"], app["id"])


def test_journal_is_added_to_the_application_history(ada: TestClient) -> None:
    app = application(ada)
    rnd = add_round(ada, app["id"])
    journal(ada, app, rnd)

    event = ada.get(f"/api/v1/applications/{app['id']}/timeline").json()[-1]

    assert event["event_type"] == "journal_recorded"
    assert event["new_value"] == {"template": "interview", "round_name": "Tech interview", "question_count": 2}


def test_answers_must_match_the_templates_prompts(ada: TestClient) -> None:
    app = application(ada)

    response = ada.post(
        "/api/v1/journals",
        json={"application_id": app["id"], "template": "general", "responses": {"struggled_to_explain": "x"}},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_prompt"


def test_round_must_belong_to_the_application(ada: TestClient) -> None:
    first, second = application(ada), application(ada, "Globex")
    other_round = add_round(ada, second["id"])

    response = ada.post(
        "/api/v1/journals", json={"application_id": first["id"], "round_id": other_round["id"], "template": "general"}
    )

    assert (response.status_code, response.json()["error"]["code"]) == (422, "round_not_in_application")


def test_an_application_can_have_several_journals(ada: TestClient) -> None:
    app = application(ada)
    journal(ada, app, questions=[])
    journal(ada, app, template="general", responses={"what_happened": "Recruiter call"}, questions=[])

    assert len(ada.get("/api/v1/journals", params={"application_id": app["id"]}).json()) == 2


def test_deleting_a_journal_keeps_its_questions(ada: TestClient) -> None:
    entry = journal(ada, application(ada))

    assert ada.delete(f"/api/v1/journals/{entry['id']}").status_code == 204

    bank = search(ada)
    assert bank["total"] == 2
    assert all(q["journal_id"] is None for q in bank["items"])


# --- question bank ----------------------------------------------------------------------


def test_partial_and_unanswered_questions_default_to_to_practice(ada: TestClient) -> None:
    entry = journal(ada, application(ada))

    statuses = {q["text"]: q["practice_status"] for q in entry["questions"]}

    assert statuses["How does a B-tree index speed up queries?"] == "to_practice"
    assert statuses["Design a REST API for orders"] == "new"


def test_search_and_filters(ada: TestClient) -> None:
    acme = application(ada, "Acme", "Backend Engineer")
    globex = application(ada, "Globex", "Data Analyst")
    journal(ada, acme, add_round(ada, acme["id"], "technical_interview"))
    ada.post("/api/v1/journals", json={
        "application_id": globex["id"], "round_id": add_round(ada, globex["id"], "online_assessment", "OA")["id"],
        "template": "technical_assessment",
        "questions": [{"text": "Write SQL to find duplicate emails", "topic": "SQL", "difficulty": "easy",
                       "response_quality": "could_not_answer"}],
    })
    ada.post("/api/v1/questions", json={"text": "Explain the CAP theorem", "topic": "Distributed systems",
                                        "response_quality": "not_attempted", "asked_on": "2026-09-01"})

    assert search(ada)["total"] == 4
    assert [q["text"] for q in search(ada, q="b-tree")["items"]] == ["How does a B-tree index speed up queries?"]
    assert search(ada, q="sql")["items"][0]["topic"] == "SQL"  # topic matches too
    assert search(ada, company="glob")["items"][0]["company_name"] == "Globex"
    assert search(ada, position="backend")["total"] == 2
    assert search(ada, round_type="online_assessment")["items"][0]["round_name"] == "OA"
    assert search(ada, topic="api")["items"][0]["text"] == "Design a REST API for orders"
    assert search(ada, difficulty="medium")["total"] == 1
    assert search(ada, response_quality="could_not_answer")["total"] == 1
    assert search(ada, practice_status="to_practice")["total"] == 2
    assert [q["text"] for q in search(ada, date_to="2026-09-30")["items"]] == ["Explain the CAP theorem"]
    assert search(ada, q="%")["total"] == 0  # wildcards are literal

    facets = ada.get("/api/v1/questions/facets").json()
    assert facets["companies"] == ["Acme", "Globex"]
    assert facets["topics"] == ["API design", "Databases", "Distributed systems", "SQL"]


def test_original_answer_cannot_be_changed(ada: TestClient) -> None:
    question = journal(ada, application(ada))["questions"][0]

    response = ada.patch(f"/api/v1/questions/{question['id']}", json={"original_answer": "A better answer"})

    assert response.status_code == 422
    unchanged = ada.get(f"/api/v1/questions/{question['id']}").json()
    assert unchanged["original_answer"] == "It keeps keys sorted so lookups are logarithmic."


def test_verified_solution_is_stored_separately(ada: TestClient) -> None:
    question = journal(ada, application(ada))["questions"][0]

    body = ada.patch(
        f"/api/v1/questions/{question['id']}",
        json={"verified_solution": "Balanced tree of pages; splits keep it balanced.", "topic": "Indexing"},
    ).json()

    assert body["verified_solution"].startswith("Balanced tree")
    assert body["original_answer"] == "It keeps keys sorted so lookups are logarithmic."
    assert body["ai_suggestion"] is None
    assert body["topic"] == "Indexing"


def test_reattempts_are_recorded_and_comparable_with_the_original(ada: TestClient) -> None:
    question = journal(ada, application(ada))["questions"][0]
    url = f"/api/v1/questions/{question['id']}/attempts"

    ada.post(url, json={"answer": "Sorted pages, logarithmic lookups.", "response_quality": "partial", "confidence": 3, "time_spent_minutes": 5})
    response = ada.post(url, json={"answer": "Balanced pages; splits and merges.", "response_quality": "confident", "confidence": 4, "time_spent_minutes": 3})

    assert response.status_code == 201
    body = response.json()
    assert body["attempt_count"] == 2
    assert [a["response_quality"] for a in body["attempts"]] == ["partial", "confident"]
    assert body["latest_attempt"]["confidence"] == 4
    # The original is untouched, so the comparison is honest.
    assert (body["response_quality"], body["confidence"], body["time_spent_minutes"]) == ("partial", 2, 6)


def test_an_attempt_starts_practice_but_never_marks_comfortable(ada: TestClient) -> None:
    question = journal(ada, application(ada))["questions"][0]

    body = ada.post(f"/api/v1/questions/{question['id']}/attempts", json={"response_quality": "confident"}).json()
    assert body["practice_status"] == "practicing"

    body = ada.post(f"/api/v1/questions/{question['id']}/attempts", json={"response_quality": "confident"}).json()
    assert body["practice_status"] == "practicing"

    marked = ada.patch(f"/api/v1/questions/{question['id']}", json={"practice_status": "comfortable"}).json()
    assert marked["practice_status"] == "comfortable"


def test_invalid_confidence_is_rejected(ada: TestClient) -> None:
    response = ada.post("/api/v1/questions", json={"text": "Q", "response_quality": "partial", "confidence": 9})

    assert response.status_code == 422


# --- isolation -------------------------------------------------------------------------


def test_other_users_cannot_see_or_use_journals_and_questions(client: TestClient) -> None:
    ada_token = sign_up(client, "ada@example.com")
    app = application(client)
    entry = journal(client, app, add_round(client, app["id"]))
    question_id = entry["questions"][0]["id"]
    sign_up(client, "grace@example.com")

    assert client.get("/api/v1/journals").json() == []
    assert client.get("/api/v1/journals", params={"application_id": app["id"]}).status_code == 404
    assert client.get(f"/api/v1/journals/{entry['id']}").status_code == 404
    assert client.patch(f"/api/v1/journals/{entry['id']}", json={"follow_up_actions": "x"}).status_code == 404
    assert client.delete(f"/api/v1/journals/{entry['id']}").status_code == 404
    assert client.post("/api/v1/journals", json={"application_id": app["id"], "template": "general"}).status_code == 404
    assert search(client)["total"] == 0
    assert client.get("/api/v1/questions/facets").json()["companies"] == []
    assert client.get(f"/api/v1/questions/{question_id}").status_code == 404
    assert client.patch(f"/api/v1/questions/{question_id}", json={"topic": "x"}).status_code == 404
    assert client.post(f"/api/v1/questions/{question_id}/attempts", json={"response_quality": "confident"}).status_code == 404
    assert client.post("/api/v1/questions", json={"text": "Q", "response_quality": "partial", "application_id": app["id"]}).status_code == 404

    act_as(client, ada_token)
    assert search(client)["total"] == 2
