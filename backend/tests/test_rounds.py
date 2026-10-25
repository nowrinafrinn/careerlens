from fastapi.testclient import TestClient

from tests.conftest import act_as, sign_up

APPS = "/api/v1/applications"
ROUNDS = "/api/v1/rounds"


def new_application(client: TestClient, status: str = "applied") -> dict:
    response = client.post(APPS, json={"company_name": "Acme", "position_title": "Engineer", "status": status})
    assert response.status_code == 201, response.text
    return response.json()


def add_round(client: TestClient, application_id: str, **fields) -> dict:
    payload = {"name": "Technical interview", "round_type": "technical_interview", **fields}
    response = client.post(f"{APPS}/{application_id}/rounds", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def events(client: TestClient, application_id: str) -> list[dict]:
    return client.get(f"{APPS}/{application_id}/timeline").json()


# --- creation ----------------------------------------------------------------


def test_round_without_date_is_not_scheduled(ada: TestClient) -> None:
    app = new_application(ada)

    rnd = add_round(ada, app["id"])

    assert rnd["status"] == "not_scheduled"
    assert rnd["result"] == "unknown"
    assert rnd["position"] == 0


def test_round_with_date_is_upcoming_and_positions_increase(ada: TestClient) -> None:
    app = new_application(ada)

    first = add_round(ada, app["id"], name="Online assessment", round_type="online_assessment")
    second = add_round(ada, app["id"], scheduled_at="2026-11-10T10:00:00+06:00")

    assert second["status"] == "upcoming"
    assert (first["position"], second["position"]) == (0, 1)
    detail = ada.get(f"{APPS}/{app['id']}").json()
    assert [r["name"] for r in detail["rounds"]] == ["Online assessment", "Technical interview"]


def test_round_creation_is_recorded(ada: TestClient) -> None:
    app = new_application(ada)
    rnd = add_round(ada, app["id"])

    event = events(ada, app["id"])[-1]
    assert event["event_type"] == "round_created"
    assert event["round_id"] == rnd["id"]
    assert event["new_value"]["round_name"] == "Technical interview"


def test_scheduled_time_requires_a_timezone(ada: TestClient) -> None:
    app = new_application(ada)

    response = ada.post(
        f"{APPS}/{app['id']}/rounds",
        json={"name": "HR", "round_type": "hr_interview", "scheduled_at": "2026-11-10T10:00:00"},
    )

    assert response.status_code == 422


def test_round_links_must_be_http_urls(ada: TestClient) -> None:
    app = new_application(ada)

    ok = add_round(ada, app["id"], links=[{"label": "Invite", "url": "https://meet.example.com/abc"}])
    bad = ada.post(
        f"{APPS}/{app['id']}/rounds",
        json={"name": "HR", "round_type": "hr_interview", "links": [{"label": "x", "url": "file:///etc/passwd"}]},
    )

    assert ok["links"] == [{"label": "Invite", "url": "https://meet.example.com/abc"}]
    assert bad.status_code == 422


# --- rescheduling keeps history -------------------------------------------------------


def test_rescheduling_preserves_the_original_date(ada: TestClient) -> None:
    app = new_application(ada)
    rnd = add_round(ada, app["id"], scheduled_at="2026-11-10T10:00:00+00:00")

    response = ada.patch(
        f"{ROUNDS}/{rnd['id']}",
        json={"scheduled_at": "2026-11-12T14:30:00+00:00", "change_reason": "Interviewer unavailable"},
    )

    assert response.status_code == 200
    assert response.json()["scheduled_at"].startswith("2026-11-12T14:30:00")
    event = events(ada, app["id"])[-1]
    assert event["event_type"] == "round_rescheduled"
    assert event["old_value"]["scheduled_at"].startswith("2026-11-10T10:00:00")
    assert event["new_value"]["scheduled_at"].startswith("2026-11-12T14:30:00")
    assert event["reason"] == "Interviewer unavailable"


def test_two_reschedules_keep_every_date(ada: TestClient) -> None:
    app = new_application(ada)
    rnd = add_round(ada, app["id"], scheduled_at="2026-11-10T10:00:00+00:00")

    ada.patch(f"{ROUNDS}/{rnd['id']}", json={"scheduled_at": "2026-11-12T10:00:00+00:00"})
    ada.patch(f"{ROUNDS}/{rnd['id']}", json={"scheduled_at": "2026-11-15T10:00:00+00:00"})

    moves = [e for e in events(ada, app["id"]) if e["event_type"] == "round_rescheduled"]
    assert [(m["old_value"]["scheduled_at"][:10], m["new_value"]["scheduled_at"][:10]) for m in moves] == [
        ("2026-11-10", "2026-11-12"),
        ("2026-11-12", "2026-11-15"),
    ]


def test_first_date_counts_as_scheduling_and_makes_round_upcoming(ada: TestClient) -> None:
    app = new_application(ada)
    rnd = add_round(ada, app["id"])

    body = ada.patch(f"{ROUNDS}/{rnd['id']}", json={"scheduled_at": "2026-11-10T10:00:00+00:00"}).json()

    assert body["status"] == "upcoming"
    types = [e["event_type"] for e in events(ada, app["id"])]
    assert types[-2:] == ["round_scheduled", "round_status_changed"]


def test_history_stores_times_in_utc_whatever_timezone_was_sent(ada: TestClient) -> None:
    app = new_application(ada)
    rnd = add_round(ada, app["id"], scheduled_at="2026-11-05T15:00:00+06:00")

    ada.patch(f"{ROUNDS}/{rnd['id']}", json={"scheduled_at": "2026-11-07T15:00:00+06:00"})

    created, moved = [e for e in events(ada, app["id"]) if e["round_id"] == rnd["id"]]
    assert created["new_value"]["scheduled_at"] == "2026-11-05T09:00:00Z"
    assert moved["old_value"]["scheduled_at"] == "2026-11-05T09:00:00Z"
    assert moved["new_value"]["scheduled_at"] == "2026-11-07T09:00:00Z"


def test_same_instant_in_another_timezone_is_not_a_reschedule(ada: TestClient) -> None:
    app = new_application(ada)
    rnd = add_round(ada, app["id"], scheduled_at="2026-11-10T10:00:00+00:00")

    ada.patch(f"{ROUNDS}/{rnd['id']}", json={"scheduled_at": "2026-11-10T16:00:00+06:00"})

    assert "round_rescheduled" not in [e["event_type"] for e in events(ada, app["id"])]


# --- completion vs passing ------------------------------------------------------------


def test_completing_a_round_does_not_mean_passing_it(ada: TestClient) -> None:
    app = new_application(ada, status="in_progress")
    rnd = add_round(ada, app["id"], scheduled_at="2026-11-10T10:00:00+00:00")

    body = ada.patch(f"{ROUNDS}/{rnd['id']}", json={"status": "completed"}).json()

    assert body["status"] == "completed"
    assert body["result"] == "unknown"
    assert body["completed_at"] is not None
    # And the application's own status is untouched.
    assert ada.get(f"{APPS}/{app['id']}").json()["status"] == "in_progress"


def test_passing_the_final_round_does_not_change_application_status(ada: TestClient) -> None:
    app = new_application(ada, status="in_progress")
    rnd = add_round(ada, app["id"], name="Final", round_type="final_decision")

    ada.patch(f"{ROUNDS}/{rnd['id']}", json={"status": "completed", "result": "passed"})

    assert ada.get(f"{APPS}/{app['id']}").json()["status"] == "in_progress"


def test_result_is_recorded_separately_from_status(ada: TestClient) -> None:
    app = new_application(ada)
    rnd = add_round(ada, app["id"], scheduled_at="2026-11-10T10:00:00+00:00")

    ada.patch(f"{ROUNDS}/{rnd['id']}", json={"status": "awaiting_result"})
    ada.patch(f"{ROUNDS}/{rnd['id']}", json={"result": "failed", "change_reason": "Email from recruiter"})

    round_events = [e for e in events(ada, app["id"]) if e["round_id"] == rnd["id"]]
    assert [e["event_type"] for e in round_events][-2:] == ["round_status_changed", "round_result_recorded"]
    assert round_events[-1]["old_value"]["result"] == "unknown"
    assert round_events[-1]["new_value"]["result"] == "failed"


def test_follow_up_date_change_is_recorded(ada: TestClient) -> None:
    app = new_application(ada)
    rnd = add_round(ada, app["id"], follow_up_date="2026-11-20")

    ada.patch(f"{ROUNDS}/{rnd['id']}", json={"follow_up_date": "2026-11-25"})

    event = events(ada, app["id"])[-1]
    assert event["event_type"] == "round_date_changed"
    assert event["old_value"]["follow_up_date"] == "2026-11-20"
    assert event["new_value"]["follow_up_date"] == "2026-11-25"


def test_round_required_fields_cannot_be_cleared(ada: TestClient) -> None:
    app = new_application(ada)
    rnd = add_round(ada, app["id"])

    assert ada.patch(f"{ROUNDS}/{rnd['id']}", json={"status": None}).status_code == 422
    assert ada.patch(f"{ROUNDS}/{rnd['id']}", json={"name": None}).status_code == 422


# --- deletion keeps history ---------------------------------------------------------


def test_deleting_a_round_keeps_its_history(ada: TestClient) -> None:
    app = new_application(ada)
    rnd = add_round(ada, app["id"], name="Duplicate HR", round_type="hr_interview")

    response = ada.delete(f"{ROUNDS}/{rnd['id']}", params={"reason": "Created twice"})

    assert response.status_code == 204
    assert ada.get(f"{ROUNDS}/{rnd['id']}").status_code == 404
    assert ada.get(f"{APPS}/{app['id']}").json()["rounds"] == []
    history = events(ada, app["id"])
    assert [e["event_type"] for e in history][-2:] == ["round_created", "round_deleted"]
    deleted = history[-1]
    assert deleted["old_value"]["round_name"] == "Duplicate HR"
    assert deleted["reason"] == "Created twice"


# --- isolation ---------------------------------------------------------------------


def test_other_users_cannot_read_change_or_delete_a_round(client: TestClient) -> None:
    ada_token = sign_up(client, "ada@example.com")
    app = new_application(client)
    rnd = add_round(client, app["id"])
    sign_up(client, "grace@example.com")

    url = f"{ROUNDS}/{rnd['id']}"
    assert client.get(url).status_code == 404
    assert client.patch(url, json={"result": "failed"}).status_code == 404
    assert client.delete(url).status_code == 404

    act_as(client, ada_token)
    assert client.get(url).json()["result"] == "unknown"
