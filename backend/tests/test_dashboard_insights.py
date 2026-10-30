from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from tests.conftest import act_as, sign_up
from tests.test_analyses import run, upload_cv
from tests.test_journals_questions import application, journal
from tests.test_requirement_analysis import SAMPLE_JD


def iso(dt: datetime) -> str:
    return dt.isoformat()


def dashboard(client: TestClient, today: str | None = None) -> dict:
    response = client.get("/api/v1/dashboard", params={"today": today} if today else {})
    assert response.status_code == 200, response.text
    return response.json()


def insights(client: TestClient) -> dict:
    response = client.get("/api/v1/insights")
    assert response.status_code == 200, response.text
    return response.json()


def analysed_app(client: TestClient, cv_id: str, company: str, jd: str = SAMPLE_JD) -> dict:
    app = client.post(
        "/api/v1/applications",
        json={"company_name": company, "position_title": "Backend Engineer", "job_description": jd, "cv_version_id": cv_id},
    ).json()
    run(client, app["id"])
    return app


# --- dashboard -----------------------------------------------------------------------


def test_deadlines_are_upcoming_then_need_attention_based_on_your_today(ada: TestClient) -> None:
    ada.post("/api/v1/applications", json={"company_name": "Acme", "position_title": "Engineer", "deadline": "2026-11-10"})
    ada.post("/api/v1/applications", json={"company_name": "Applied Co", "position_title": "Engineer",
                                           "deadline": "2026-11-01", "status": "applied"})

    before = dashboard(ada, "2026-11-05")
    after = dashboard(ada, "2026-11-12")

    assert [d["company_name"] for d in before["upcoming_deadlines"]] == ["Acme"]
    assert before["needs_attention"] == []
    assert [(i["kind"], i["company_name"]) for i in after["needs_attention"]] == [("deadline_passed", "Acme")]


def test_rounds_upcoming_passed_pending_and_follow_ups(ada: TestClient) -> None:
    app = application(ada)
    now = datetime.now(UTC)
    soon = ada.post(f"/api/v1/applications/{app['id']}/rounds",
                    json={"name": "Tech", "round_type": "technical_interview", "scheduled_at": iso(now + timedelta(days=2))}).json()
    ada.post(f"/api/v1/applications/{app['id']}/rounds",
             json={"name": "OA", "round_type": "online_assessment", "scheduled_at": iso(now - timedelta(days=1))})
    ada.post(f"/api/v1/applications/{app['id']}/rounds",
             json={"name": "HR", "round_type": "hr_interview", "status": "completed",
                   "follow_up_date": (now + timedelta(days=1)).date().isoformat()})
    ada.post(f"/api/v1/applications/{app['id']}/rounds",
             json={"name": "Screening", "round_type": "cv_screening", "status": "completed", "result": "passed"})
    for title, status in [("Review SQL", "completed"), ("Mock interview", "planned")]:
        task = ada.post("/api/v1/tasks", json={"kind": "preparation", "title": title, "recruitment_round_id": soon["id"]}).json()
        ada.patch(f"/api/v1/tasks/{task['id']}", json={"status": status})

    body = dashboard(ada, now.date().isoformat())

    [upcoming] = body["upcoming_rounds"]
    assert (upcoming["round_name"], upcoming["prep_done"], upcoming["prep_total"]) == ("Tech", 1, 2)
    assert [(i["kind"], i["round_name"]) for i in body["needs_attention"]] == [("round_passed", "OA")]
    assert [p["round_name"] for p in body["pending_results"]] == ["HR"]  # completed, result unknown
    assert [f["round_name"] for f in body["follow_ups"]] == ["HR"]


def test_overdue_tasks_and_open_tasks_by_priority(ada: TestClient) -> None:
    ada.post("/api/v1/tasks", json={"title": "Low priority", "priority": 5})
    ada.post("/api/v1/tasks", json={"title": "Overdue", "priority": 2, "due_date": "2026-10-01"})
    ada.post("/api/v1/tasks", json={"title": "Urgent", "priority": 1})

    body = dashboard(ada, "2026-10-26")

    assert [t["title"] for t in body["top_tasks"]] == ["Urgent", "Overdue", "Low priority"]
    assert [(i["kind"], i["title"]) for i in body["needs_attention"]] == [("task_overdue", "Overdue")]


def test_closed_and_archived_applications_stay_off_the_dashboard(ada: TestClient) -> None:
    rejected = ada.post("/api/v1/applications", json={"company_name": "Old", "position_title": "x", "status": "rejected",
                                                      "deadline": "2026-10-01"}).json()
    archived = ada.post("/api/v1/applications", json={"company_name": "Shelved", "position_title": "x", "deadline": "2026-10-01"}).json()
    ada.post(f"/api/v1/applications/{archived['id']}/archive")

    body = dashboard(ada, "2026-10-26")

    assert body["needs_attention"] == []
    assert body["application_counts"] == {}
    assert rejected["status"] == "rejected"


def test_closed_outcomes_are_counted_apart_from_active_applications(ada: TestClient) -> None:
    for company, status in [("Offer Co", "offer"), ("No Co", "rejected"), ("Live Co", "applied")]:
        ada.post("/api/v1/applications", json={"company_name": company, "position_title": "Engineer", "status": status})

    body = dashboard(ada)

    assert body["application_counts"] == {"applied": 1}
    assert body["outcome_counts"] == {"offer": 1, "rejected": 1}


def test_latest_cv_is_summarised_once_one_exists(ada: TestClient) -> None:
    assert dashboard(ada)["latest_cv"] is None

    cv = upload_cv(ada)
    latest = dashboard(ada)["latest_cv"]

    assert latest["cv_version_id"] == cv["id"]
    assert latest["version_number"] == 1
    assert latest["section_count"] > 0
    assert latest["is_confirmed"] is False


def test_analyses_show_coverage_and_what_needs_your_input(ada: TestClient) -> None:
    cv = upload_cv(ada)
    app = analysed_app(ada, cv["id"], "PayFlow")

    [item] = dashboard(ada)["analyses"]
    # Required and not fully shown: years of Python, Docker, communication (none assessed yet).
    assert (item["coverage_percent"], item["needs_your_input"], item["is_stale"]) == (50, 3, False)

    latest = ada.get(f"/api/v1/applications/{app['id']}/analyses/latest").json()
    docker = next(r for r in latest["requirements"] if "Docker" in r["text"])
    ada.patch(f"/api/v1/requirements/{docker['id']}", json={"self_report": "have_not_on_cv"})
    assert dashboard(ada)["analyses"][0]["needs_your_input"] == 2


def test_learning_and_journals_on_the_dashboard(ada: TestClient) -> None:
    entry = journal(ada, application(ada), None)
    question = entry["questions"][0]
    gap = ada.post(f"/api/v1/questions/{question['id']}/skill-gap", json={}).json()
    ada.post(f"/api/v1/skill-gaps/{gap['id']}/reassessments", json={"new_status": "improving", "confidence": "low", "summary": "Better"})

    body = dashboard(ada)

    assert body["questions_to_practice_total"] == 1
    assert body["recent_journals"][0]["journal_id"] == entry["id"]
    assert body["gap_counts"] == {"improving": 1}
    assert body["recent_reassessments"][0]["skill_name"] == "Databases"


def test_dashboard_only_shows_your_own_records(client: TestClient) -> None:
    sign_up(client, "ada@example.com")
    client.post("/api/v1/applications", json={"company_name": "Acme", "position_title": "x", "deadline": "2026-10-01"})
    client.post("/api/v1/tasks", json={"title": "Mine", "due_date": "2026-10-01"})
    sign_up(client, "grace@example.com")

    body = dashboard(client, "2026-10-26")

    assert body["needs_attention"] == [] and body["top_tasks"] == [] and body["application_counts"] == {}


# --- insights ------------------------------------------------------------------------


def test_no_records_means_no_insights_and_says_what_is_needed(ada: TestClient) -> None:
    body = insights(ada)

    assert body["insights"] == []
    assert body["minimum_observations"] == 3
    assert any("Analyse at least 3 applications" in note for note in body["data_notes"])


def test_recurring_skill_is_not_a_pattern_until_three_observations(ada: TestClient) -> None:
    cv = upload_cv(ada)
    analysed_app(ada, cv["id"], "PayFlow")
    analysed_app(ada, cv["id"], "Globex")

    two = next(i for i in insights(ada)["insights"] if i["key"] == "recurring_skill:postgresql")
    assert (two["observation_count"], two["sufficient_data"]) == (2, False)
    assert two["statement"].startswith("Not enough data yet (2 observations")

    analysed_app(ada, cv["id"], "Initech")
    three = next(i for i in insights(ada)["insights"] if i["key"] == "recurring_skill:postgresql")
    assert (three["observation_count"], three["sufficient_data"]) == (3, True)
    assert three["statement"] == "PostgreSQL appears in the required or preferred lines of 3 of your 3 analysed applications."
    assert {s["label"].split(", ")[1] for s in three["sources"]} == {"PayFlow", "Globex", "Initech"}
    assert three["basis"] == "job_descriptions"


def test_cv_evidence_insight_is_about_the_cv_not_ability(ada: TestClient) -> None:
    cv = upload_cv(ada)
    for company in ["PayFlow", "Globex", "Initech"]:
        analysed_app(ada, cv["id"], company)

    docker = next(i for i in insights(ada)["insights"] if i["key"] == "cv_evidence:docker")

    assert docker["sufficient_data"] is True
    assert docker["basis"] == "cv_analysis"
    assert "not about your ability" in docker["caveat"]
    assert all(s["kind"] == "requirement" and s["application_id"] for s in docker["sources"])


def test_difficulty_topics_come_from_your_recorded_outcomes(ada: TestClient) -> None:
    app = application(ada)
    for i in range(3):
        ada.post("/api/v1/questions", json={"text": f"SQL question {i}", "topic": "SQL", "response_quality": "could_not_answer",
                                            "application_id": app["id"]})
    ada.post("/api/v1/questions", json={"text": "SQL easy one", "topic": "sql", "response_quality": "confident"})

    sql = next(i for i in insights(ada)["insights"] if i["key"] == "difficulty_topic:sql")

    assert sql["sufficient_data"] is True
    assert sql["statement"] == "You recorded 3 of 4 questions on SQL as partly answered or not answered."
    assert sql["basis"] == "recorded_outcomes"
    assert len(sql["sources"]) == 3


def test_single_session_improvement_is_flagged_as_weak(ada: TestClient) -> None:
    gap = ada.post("/api/v1/skill-gaps", json={"skill_name": "SQL", "reason": "x"}).json()
    task = ada.post("/api/v1/tasks", json={"title": "Practise", "skill_gap_id": gap["id"]}).json()
    attempt = ada.post(f"/api/v1/tasks/{task['id']}/attempts", json={"outcome": "solid"}).json()["attempts"][0]["id"]
    ada.patch(f"/api/v1/tasks/{task['id']}", json={"status": "completed"})
    ada.post(f"/api/v1/skill-gaps/{gap['id']}/reassessments",
             json={"new_status": "improving", "confidence": "medium", "summary": "Solved it", "task_attempt_id": attempt})

    items = {i["category"]: i for i in insights(ada)["insights"]}

    improvement = items["improvement"]
    assert improvement["sufficient_data"] is False
    assert "One session is a weak signal" in improvement["caveat"]
    assert "cited a practice record" in improvement["statement"]
    together = items["preparation_before_improvement"]
    assert "doesn't show the tasks caused the improvement" in together["caveat"]


def test_every_insight_has_sources_and_a_caveat(ada: TestClient) -> None:
    cv = upload_cv(ada)
    for company in ["PayFlow", "Globex", "Initech"]:
        analysed_app(ada, cv["id"], company)

    for item in insights(ada)["insights"]:
        assert item["sources"], item["key"]
        assert item["caveat"], item["key"]
        assert item["observation_count"] >= 1


def test_insights_only_use_your_own_records(client: TestClient) -> None:
    sign_up(client, "ada@example.com")
    cv = upload_cv(client)
    for company in ["PayFlow", "Globex", "Initech"]:
        analysed_app(client, cv["id"], company)
    ada_token = client.cookies.get("careerlens_session")
    sign_up(client, "grace@example.com")

    assert insights(client)["insights"] == []

    act_as(client, ada_token)
    assert insights(client)["insights"]
