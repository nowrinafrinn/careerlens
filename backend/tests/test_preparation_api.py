from fastapi.testclient import TestClient

from tests.conftest import act_as, sign_up
from tests.test_analyses import ready_application, run
from tests.test_journals_questions import add_round, application


def prep(client: TestClient, application_id: str, round_id: str | None = None):
    params = {"round_id": round_id} if round_id else {}
    return client.get(f"/api/v1/applications/{application_id}/preparation", params=params)


def by_title(body: dict, start: str) -> dict:
    return next(s for s in body["suggestions"] if s["title"].startswith(start))


def test_without_an_analysis_only_round_tips_are_offered(ada: TestClient) -> None:
    app = application(ada)
    rnd = add_round(ada, app["id"], "online_assessment", "OA")

    body = prep(ada, app["id"], rnd["id"]).json()

    assert body["analysis_id"] is None
    assert "No requirement analysis yet" in body["note"]
    assert [s["title"] for s in body["suggestions"]] == ["Do one timed practice set under test conditions"]


def test_suggestions_use_the_analysis_gaps_and_question_bank(ada: TestClient) -> None:
    app = ready_application(ada)
    analysis = run(ada, app["id"]).json()
    rnd = add_round(ada, app["id"], "technical_interview")
    kubernetes = next(r for r in analysis["requirements"] if "Kubernetes" in r["text"])
    ada.patch(f"/api/v1/requirements/{kubernetes['id']}", json={"self_report": "learning"})
    gap = ada.post(f"/api/v1/requirements/{kubernetes['id']}/skill-gap", json={}).json()
    question = ada.post(
        "/api/v1/questions",
        json={"text": "How would you index a large PostgreSQL table?", "topic": "PostgreSQL", "response_quality": "partial"},
    ).json()

    body = prep(ada, app["id"], rnd["id"]).json()

    assert body["analysis_id"] == analysis["id"]
    assert body["analysis_is_stale"] is False
    assert by_title(body, "Practise solving problems out loud")["kind"] == "round_format"
    project = by_title(body, "Practice question: “Walk me through how you used PostgreSQL")
    assert project["is_practice_question"] is True
    assert project["requirement_id"] is not None
    assert by_title(body, "Work on your Kubernetes gap")["skill_gap_id"] == gap["id"]
    assert by_title(body, "Re-attempt:")["question_id"] == question["id"]
    assert all(s["why"] for s in body["suggestions"])
    assert all(s["saved_task_id"] is None for s in body["suggestions"])


def test_saved_suggestions_are_marked_per_round(ada: TestClient) -> None:
    app = ready_application(ada)
    run(ada, app["id"])
    first = add_round(ada, app["id"], "technical_interview", "Tech 1")
    second = add_round(ada, app["id"], "technical_interview", "Tech 2")
    suggestion = by_title(prep(ada, app["id"], first["id"]).json(), "Review Docker fundamentals")

    task = ada.post(
        "/api/v1/tasks",
        json={"kind": "preparation", "title": suggestion["title"], "description": suggestion["detail"],
              "why": suggestion["why"], "application_id": app["id"], "recruitment_round_id": first["id"],
              "job_requirement_id": suggestion["requirement_id"]},
    ).json()

    assert by_title(prep(ada, app["id"], first["id"]).json(), "Review Docker fundamentals")["saved_task_id"] == task["id"]
    assert by_title(prep(ada, app["id"], second["id"]).json(), "Review Docker fundamentals")["saved_task_id"] is None
    checklist = ada.get("/api/v1/tasks", params={"kind": "preparation", "recruitment_round_id": first["id"]}).json()
    assert [t["title"] for t in checklist] == ["Review Docker fundamentals"]
    assert checklist[0]["round_name"] == "Tech 1"


def test_own_checklist_items_work_without_any_suggestions(ada: TestClient) -> None:
    app = application(ada)
    rnd = add_round(ada, app["id"], "hr_interview", "HR")

    task = ada.post(
        "/api/v1/tasks",
        json={"kind": "preparation", "title": "Research the company's products", "recruitment_round_id": rnd["id"]},
    ).json()

    assert task["application_id"] == app["id"]  # filled in from the round
    done = ada.patch(f"/api/v1/tasks/{task['id']}", json={"status": "completed"}).json()
    assert done["status"] == "completed"


def test_stale_analysis_is_flagged(ada: TestClient) -> None:
    app = ready_application(ada)
    run(ada, app["id"])
    ada.patch(f"/api/v1/applications/{app['id']}", json={"job_description": "Requirements\n- Kafka"})

    body = prep(ada, app["id"]).json()

    assert body["analysis_is_stale"] is True
    assert "out of date" in body["note"]


def test_round_must_belong_to_the_application(ada: TestClient) -> None:
    first, second = application(ada), application(ada, "Globex")
    other = add_round(ada, second["id"])

    response = prep(ada, first["id"], other["id"])

    assert (response.status_code, response.json()["error"]["code"]) == (422, "round_not_in_application")


def test_other_users_cannot_see_preparation(client: TestClient) -> None:
    ada_token = sign_up(client, "ada@example.com")
    app = ready_application(client)
    run(client, app["id"])
    sign_up(client, "grace@example.com")

    assert prep(client, app["id"]).status_code == 404

    act_as(client, ada_token)
    assert prep(client, app["id"]).status_code == 200
