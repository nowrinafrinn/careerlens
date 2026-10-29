import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import SkillGap, User
from app.models.learning import Level
from tests.conftest import act_as, sign_up
from tests.test_analyses import ready_application, run
from tests.test_journals_questions import application, journal


def requirement(analysis: dict, fragment: str) -> dict:
    return next(r for r in analysis["requirements"] if fragment in r["text"])


def self_report(client: TestClient, requirement_id: str, value: str) -> None:
    assert client.patch(f"/api/v1/requirements/{requirement_id}", json={"self_report": value}).status_code == 200


def gap_from_requirement(client: TestClient, requirement_id: str, **body):
    return client.post(f"/api/v1/requirements/{requirement_id}/skill-gap", json=body)


# --- gaps only from real evidence ---------------------------------------------------------


def test_not_found_in_cv_alone_never_creates_a_gap(ada: TestClient) -> None:
    analysis = run(ada, ready_application(ada)["id"]).json()
    kubernetes = requirement(analysis, "Kubernetes")
    assert kubernetes["evidence_status"] == "not_found_in_cv"

    response = gap_from_requirement(ada, kubernetes["id"])

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "self_report_required"
    assert ada.get("/api/v1/skill-gaps").json() == []


def test_gap_from_requirement_after_the_candidate_says_so(ada: TestClient) -> None:
    analysis = run(ada, ready_application(ada)["id"]).json()
    kubernetes = requirement(analysis, "Kubernetes")
    self_report(ada, kubernetes["id"], "do_not_have")

    gap = gap_from_requirement(ada, kubernetes["id"]).json()

    assert gap["skill_name"] == "Kubernetes"
    assert gap["gap_type"] == "unclassified"  # the candidate diagnoses it, not the app
    assert gap["importance"] == "medium"  # it was a preferred requirement
    assert gap["status"] == "open"
    [evidence] = gap["evidence"]
    assert evidence["basis"] == "user_confirmed"
    assert evidence["requirement_text"] == "Experience with Kubernetes"
    assert evidence["company_name"] == "PayFlow"
    # The analysis now shows the link.
    latest = ada.get(f"/api/v1/analyses/{analysis['id']}").json()
    assert requirement(latest, "Kubernetes")["skill_gap_id"] == gap["id"]


def test_same_skill_from_two_jobs_is_one_gap_with_two_sources(ada: TestClient) -> None:
    first = run(ada, ready_application(ada)["id"]).json()
    second_app = ada.post(
        "/api/v1/applications",
        json={"company_name": "Globex", "position_title": "Platform Engineer",
              "job_description": "Requirements\n- Experience with kubernetes in production",
              "cv_version_id": first["cv_version"]["id"]},
    ).json()
    second = run(ada, second_app["id"]).json()
    for analysis, fragment in [(first, "Kubernetes"), (second, "kubernetes")]:
        req = requirement(analysis, fragment)
        self_report(ada, req["id"], "learning")
        gap = gap_from_requirement(ada, req["id"]).json()

    gaps = ada.get("/api/v1/skill-gaps").json()
    assert len(gaps) == 1
    assert gaps[0]["evidence_count"] == 2
    assert gaps[0]["application_count"] == 2
    assert gaps[0]["importance"] == "high"  # raised by the required line in the second job
    assert {e["company_name"] for e in ada.get(f"/api/v1/skill-gaps/{gap['id']}").json()["evidence"]} == {"PayFlow", "Globex"}


def test_adding_the_same_requirement_twice_or_after_a_rerun_adds_no_duplicate(ada: TestClient) -> None:
    app = ready_application(ada)
    first = run(ada, app["id"]).json()
    req = requirement(first, "Kubernetes")
    self_report(ada, req["id"], "do_not_have")
    gap_from_requirement(ada, req["id"])
    gap_from_requirement(ada, req["id"])

    second = run(ada, app["id"]).json()  # self-report carries over to the new requirement row
    gap = gap_from_requirement(ada, requirement(second, "Kubernetes")["id"]).json()

    assert gap["evidence_count"] == 1
    assert requirement(second, "Kubernetes")["skill_gap_id"] == gap["id"]


def test_gap_from_a_question_needs_a_recorded_difficulty(ada: TestClient) -> None:
    entry = journal(ada, application(ada))
    struggled = next(q for q in entry["questions"] if q["response_quality"] == "partial")
    confident = next(q for q in entry["questions"] if q["response_quality"] == "confident")

    refused = ada.post(f"/api/v1/questions/{confident['id']}/skill-gap", json={})
    assert (refused.status_code, refused.json()["error"]["code"]) == (422, "no_difficulty_recorded")

    gap = ada.post(f"/api/v1/questions/{struggled['id']}/skill-gap", json={}).json()
    assert gap["skill_name"] == "Databases"  # the question's topic
    [evidence] = gap["evidence"]
    assert evidence["basis"] == "recorded_outcome"
    assert evidence["question_text"] == "How does a B-tree index speed up queries?"
    assert evidence["journal_id"] == entry["id"]
    assert ada.get(f"/api/v1/questions/{struggled['id']}").json()["skill_gap_id"] == gap["id"]


def test_question_without_topic_needs_a_skill_name(ada: TestClient) -> None:
    question = ada.post("/api/v1/questions", json={"text": "Explain CAP", "response_quality": "could_not_answer"}).json()

    assert ada.post(f"/api/v1/questions/{question['id']}/skill-gap", json={}).json()["error"]["code"] == "skill_name_required"
    gap = ada.post(f"/api/v1/questions/{question['id']}/skill-gap", json={"skill_name": "Distributed systems"}).json()
    assert gap["skill_name"] == "Distributed systems"


def test_manual_gap_records_the_reason_and_names_are_case_insensitive(ada: TestClient) -> None:
    created = ada.post("/api/v1/skill-gaps", json={"skill_name": "System design", "reason": "Never practised it."})
    assert created.status_code == 201
    assert created.json()["evidence"][0]["note"] == "Never practised it."

    clash = ada.post("/api/v1/skill-gaps", json={"skill_name": "SYSTEM DESIGN", "reason": "x"})
    assert (clash.status_code, clash.json()["error"]["code"]) == (409, "gap_exists")


def test_database_enforces_one_gap_per_skill_but_allows_different_skills(db: Session, client: TestClient) -> None:
    sign_up(client, "ada@example.com")
    user = db.query(User).one()
    db.add_all([SkillGap(user_id=user.id, skill_name="SQL", importance=Level.HIGH),
                SkillGap(user_id=user.id, skill_name="Docker", importance=Level.LOW)])
    db.flush()  # two different skills: fine

    db.add(SkillGap(user_id=user.id, skill_name="sql", importance=Level.LOW))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# --- the candidate's diagnosis and reassessment --------------------------------------------


def test_gap_type_is_set_by_the_candidate_and_status_only_by_reassessment(ada: TestClient) -> None:
    gap = ada.post("/api/v1/skill-gaps", json={"skill_name": "SQL", "reason": "Struggled in an OA."}).json()

    updated = ada.patch(f"/api/v1/skill-gaps/{gap['id']}", json={"gap_type": "speed", "priority": 1}).json()
    assert (updated["gap_type"], updated["priority"]) == ("speed", 1)

    refused = ada.patch(f"/api/v1/skill-gaps/{gap['id']}", json={"status": "resolved"})
    assert refused.status_code == 422


def test_reassessments_keep_history_and_cite_attempts(ada: TestClient) -> None:
    gap = ada.post("/api/v1/skill-gaps", json={"skill_name": "SQL window functions", "reason": "Couldn't answer in OA."}).json()
    task = ada.post("/api/v1/tasks", json={"title": "Solve 5 window-function problems", "skill_gap_id": gap["id"]}).json()
    task = ada.post(f"/api/v1/tasks/{task['id']}/attempts", json={"outcome": "partial", "duration_minutes": 40}).json()
    task = ada.post(f"/api/v1/tasks/{task['id']}/attempts", json={"outcome": "solid", "duration_minutes": 25}).json()
    solid_attempt = task["attempts"][-1]["id"]

    url = f"/api/v1/skill-gaps/{gap['id']}/reassessments"
    ada.post(url, json={"new_status": "improving", "confidence": "medium", "summary": "Getting there."})
    final = ada.post(url, json={"new_status": "resolved", "confidence": "high", "summary": "Solved all five quickly.",
                                "task_attempt_id": solid_attempt}).json()

    assert final["status"] == "resolved"
    assert [(r["previous_status"], r["new_status"]) for r in final["reassessments"]] == [
        ("open", "improving"),
        ("improving", "resolved"),
    ]
    assert final["reassessments"][-1]["cited"] == "Task “Solve 5 window-function problems”: solid, 25 min"


def test_reassessment_can_cite_a_question_reattempt(ada: TestClient) -> None:
    entry = journal(ada, application(ada))
    question = entry["questions"][0]
    gap = ada.post(f"/api/v1/questions/{question['id']}/skill-gap", json={}).json()
    retry = ada.post(f"/api/v1/questions/{question['id']}/attempts", json={"response_quality": "confident"}).json()

    # The gap lists the re-attempt so the reassessment form can offer it as a citation.
    citable = ada.get(f"/api/v1/skill-gaps/{gap['id']}").json()["question_attempts"]
    assert [(a["id"], a["question_text"], a["response_quality"]) for a in citable] == [
        (retry["attempts"][-1]["id"], question["text"], "confident")
    ]

    final = ada.post(
        f"/api/v1/skill-gaps/{gap['id']}/reassessments",
        json={"new_status": "improving", "confidence": "medium", "summary": "Answered it this time.",
              "question_attempt_id": retry["attempts"][-1]["id"]},
    ).json()

    assert final["reassessments"][0]["cited"] == "Question “How does a B-tree index speed up queries?”: answered confidently"


# --- tasks ---------------------------------------------------------------------------


def test_task_is_traceable_and_practice_moves_it_in_progress(ada: TestClient) -> None:
    analysis = run(ada, ready_application(ada)["id"]).json()
    req = requirement(analysis, "Kubernetes")
    self_report(ada, req["id"], "learning")
    gap = gap_from_requirement(ada, req["id"]).json()

    task = ada.post(
        "/api/v1/tasks",
        json={"title": "Deploy a toy app to minikube", "skill_gap_id": gap["id"], "job_requirement_id": req["id"],
              "due_date": "2026-11-15"},
    ).json()
    assert task["kind"] == "learning"
    assert task["status"] == "planned"
    assert task["why"] == "Learning goal: Kubernetes."
    assert task["requirement_text"] == "Experience with Kubernetes"

    practised = ada.post(f"/api/v1/tasks/{task['id']}/attempts", json={"outcome": "struggled", "duration_minutes": 60}).json()
    assert practised["status"] == "in_progress"

    done = ada.patch(f"/api/v1/tasks/{task['id']}", json={"status": "needs_more_practice"}).json()
    assert done["status"] == "needs_more_practice"

    summary = ada.get("/api/v1/skill-gaps").json()[0]
    assert (summary["task_count"], summary["completed_task_count"]) == (1, 0)
    assert len(ada.get("/api/v1/tasks", params={"skill_gap_id": gap["id"]}).json()) == 1
    assert ada.get("/api/v1/tasks", params={"status": "completed"}).json() == []


def test_learning_plan_is_ordered_by_what_to_work_on_next(ada: TestClient) -> None:
    for name, priority in [("Docker", 3), ("SQL", 1), ("Kafka", 5)]:
        ada.post("/api/v1/skill-gaps", json={"skill_name": name, "priority": priority, "reason": "x"})
    done = next(g for g in ada.get("/api/v1/skill-gaps").json() if g["skill_name"] == "Kafka")
    ada.post(f"/api/v1/skill-gaps/{done['id']}/reassessments", json={"new_status": "resolved", "confidence": "high", "summary": "Done"})

    assert [g["skill_name"] for g in ada.get("/api/v1/skill-gaps").json()] == ["SQL", "Docker", "Kafka"]
    assert [g["skill_name"] for g in ada.get("/api/v1/skill-gaps", params={"status": "open"}).json()] == ["SQL", "Docker"]

    # An improving gap you rank higher still comes before an open one you rank lower.
    sql = next(g for g in ada.get("/api/v1/skill-gaps").json() if g["skill_name"] == "SQL")
    ada.post(f"/api/v1/skill-gaps/{sql['id']}/reassessments", json={"new_status": "improving", "confidence": "medium", "summary": "Better"})
    assert [g["skill_name"] for g in ada.get("/api/v1/skill-gaps").json()] == ["SQL", "Docker", "Kafka"]


# --- isolation -------------------------------------------------------------------------


def test_other_users_cannot_see_use_or_link_gaps_and_tasks(client: TestClient) -> None:
    ada_token = sign_up(client, "ada@example.com")
    gap = client.post("/api/v1/skill-gaps", json={"skill_name": "SQL", "reason": "x"}).json()
    task = client.post("/api/v1/tasks", json={"title": "Practise joins", "skill_gap_id": gap["id"]}).json()
    attempt = client.post(f"/api/v1/tasks/{task['id']}/attempts", json={"outcome": "solid"}).json()["attempts"][0]["id"]
    sign_up(client, "grace@example.com")
    own_gap = client.post("/api/v1/skill-gaps", json={"skill_name": "Go", "reason": "x"}).json()

    assert [g["skill_name"] for g in client.get("/api/v1/skill-gaps").json()] == ["Go"]
    assert client.get(f"/api/v1/skill-gaps/{gap['id']}").status_code == 404
    assert client.patch(f"/api/v1/skill-gaps/{gap['id']}", json={"priority": 1}).status_code == 404
    assert client.post(f"/api/v1/skill-gaps/{gap['id']}/reassessments", json={"new_status": "resolved", "confidence": "high", "summary": "x"}).status_code == 404
    assert client.get("/api/v1/tasks").json() == []
    assert client.patch(f"/api/v1/tasks/{task['id']}", json={"status": "completed"}).status_code == 404
    assert client.post("/api/v1/tasks", json={"title": "Steal", "skill_gap_id": gap["id"]}).status_code == 404
    # Nor cite someone else's attempt in their own reassessment.
    cited = client.post(f"/api/v1/skill-gaps/{own_gap['id']}/reassessments",
                        json={"new_status": "resolved", "confidence": "high", "summary": "x", "task_attempt_id": attempt})
    assert cited.status_code == 404

    act_as(client, ada_token)
    assert client.get("/api/v1/tasks").json()[0]["status"] == "in_progress"  # untouched by the other user
