from datetime import date

import pytest
from fastapi.testclient import TestClient

from tests.conftest import act_as, sign_up

API = "/api/v1/applications"


def create(client: TestClient, **fields) -> dict:
    payload = {"company_name": "Acme", "position_title": "Backend Engineer", **fields}
    response = client.post(API, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def timeline(client: TestClient, application_id: str) -> list[dict]:
    response = client.get(f"{API}/{application_id}/timeline")
    assert response.status_code == 200, response.text
    return response.json()


# --- create / read ------------------------------------------------------------


def test_create_application_with_defaults(ada: TestClient) -> None:
    app = create(ada, job_url="https://jobs.example.com/123", deadline="2026-11-30")

    assert app["status"] == "interested"
    assert app["applied_on"] is None
    assert app["deadline"] == "2026-11-30"
    assert app["job_url"] == "https://jobs.example.com/123"
    assert app["rounds"] == []

    events = timeline(ada, app["id"])
    assert [e["event_type"] for e in events] == ["application_created"]
    assert events[0]["new_value"]["company_name"] == "Acme"


def test_creating_as_applied_sets_applied_on_to_today(ada: TestClient) -> None:
    app = create(ada, status="applied")

    assert app["applied_on"] == date.today().isoformat()


def test_get_application_returns_detail(ada: TestClient) -> None:
    created = create(ada, job_description="Build APIs in Python.", notes="Referral from Sam")

    response = ada.get(f"{API}/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["job_description"] == "Build APIs in Python."
    assert body["notes"] == "Referral from Sam"


@pytest.mark.parametrize(
    "payload",
    [
        {"company_name": "   ", "position_title": "Engineer"},
        {"company_name": "Acme"},
        {"company_name": "Acme", "position_title": "Engineer", "status": "hired"},
        {"company_name": "Acme", "position_title": "Engineer", "job_url": "not a url"},
        {"company_name": "Acme", "position_title": "Engineer", "job_url": "javascript:alert(1)"},
        {"company_name": "Acme", "position_title": "Engineer", "unknown_field": 1},
    ],
)
def test_invalid_applications_are_rejected(ada: TestClient, payload: dict) -> None:
    response = ada.post(API, json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_requires_sign_in(client: TestClient) -> None:
    assert client.get(API).status_code == 401
    assert client.post(API, json={"company_name": "Acme", "position_title": "Engineer"}).status_code == 401


# --- list / search ----------------------------------------------------------


def test_list_filters_and_searches(ada: TestClient) -> None:
    create(ada, company_name="Acme", position_title="Backend Engineer")
    create(ada, company_name="Globex", position_title="Data Analyst", status="applied")
    create(ada, company_name="Initech", position_title="QA Engineer")

    everything = ada.get(API).json()
    assert everything["total"] == 3

    applied = ada.get(API, params={"status": "applied"}).json()
    assert [a["company_name"] for a in applied["items"]] == ["Globex"]

    engineers = ada.get(API, params={"q": "engineer"}).json()
    assert {a["company_name"] for a in engineers["items"]} == {"Acme", "Initech"}

    by_company = ada.get(API, params={"q": "GLOB"}).json()
    assert by_company["total"] == 1


def test_search_treats_wildcards_literally(ada: TestClient) -> None:
    create(ada, company_name="Acme")

    assert ada.get(API, params={"q": "%"}).json()["total"] == 0
    assert ada.get(API, params={"q": "_"}).json()["total"] == 0


def test_list_paginates(ada: TestClient) -> None:
    for i in range(5):
        create(ada, company_name=f"Company {i}")

    page = ada.get(API, params={"limit": 2, "offset": 2}).json()

    assert page["total"] == 5
    assert len(page["items"]) == 2
    assert (page["limit"], page["offset"]) == (2, 2)


# --- updates and history ----------------------------------------------------------


def test_status_change_is_recorded_with_old_and_new_values(ada: TestClient) -> None:
    app = create(ada)

    response = ada.patch(f"{API}/{app['id']}", json={"status": "preparing", "change_reason": "Tailoring CV"})

    assert response.status_code == 200
    assert response.json()["status"] == "preparing"
    event = timeline(ada, app["id"])[-1]
    assert event["event_type"] == "application_status_changed"
    assert event["old_value"] == {"status": "interested"}
    assert event["new_value"] == {"status": "preparing"}
    assert event["reason"] == "Tailoring CV"


def test_moving_to_applied_records_applied_date(ada: TestClient) -> None:
    app = create(ada)

    body = ada.patch(f"{API}/{app['id']}", json={"status": "applied"}).json()

    assert body["applied_on"] == date.today().isoformat()
    types = [e["event_type"] for e in timeline(ada, app["id"])]
    assert types == ["application_created", "application_status_changed", "application_date_changed"]


def test_explicit_applied_date_is_kept(ada: TestClient) -> None:
    app = create(ada)

    body = ada.patch(f"{API}/{app['id']}", json={"status": "applied", "applied_on": "2026-10-01"}).json()

    assert body["applied_on"] == "2026-10-01"


def test_deadline_change_keeps_the_original_deadline(ada: TestClient) -> None:
    app = create(ada, deadline="2026-11-01")

    ada.patch(f"{API}/{app['id']}", json={"deadline": "2026-11-15"})

    event = timeline(ada, app["id"])[-1]
    assert event["event_type"] == "application_date_changed"
    assert event["old_value"] == {"deadline": "2026-11-01"}
    assert event["new_value"] == {"deadline": "2026-11-15"}


def test_unchanged_values_and_text_edits_add_no_history(ada: TestClient) -> None:
    app = create(ada)

    ada.patch(f"{API}/{app['id']}", json={"status": "interested", "notes": "Looks interesting"})

    assert [e["event_type"] for e in timeline(ada, app["id"])] == ["application_created"]


def test_patch_can_clear_optional_fields_but_not_required_ones(ada: TestClient) -> None:
    app = create(ada, source="LinkedIn")

    cleared = ada.patch(f"{API}/{app['id']}", json={"source": None})
    assert cleared.status_code == 200
    assert cleared.json()["source"] is None

    rejected = ada.patch(f"{API}/{app['id']}", json={"company_name": None})
    assert rejected.status_code == 422


def test_archive_hides_from_list_and_restore_brings_back(ada: TestClient) -> None:
    app = create(ada)

    archived = ada.post(f"{API}/{app['id']}/archive").json()
    assert archived["archived_at"] is not None
    assert ada.get(API).json()["total"] == 0
    assert ada.get(API, params={"include_archived": True}).json()["total"] == 1
    assert ada.get(f"{API}/{app['id']}").status_code == 200  # still readable

    ada.post(f"{API}/{app['id']}/archive")  # archiving twice records nothing extra
    ada.post(f"{API}/{app['id']}/restore")

    assert ada.get(API).json()["total"] == 1
    types = [e["event_type"] for e in timeline(ada, app["id"])]
    assert types == ["application_created", "application_archived", "application_restored"]


# --- isolation ----------------------------------------------------------------


def test_other_users_cannot_see_or_change_an_application(client: TestClient) -> None:
    ada_token = sign_up(client, "ada@example.com")
    app = create(client)
    sign_up(client, "grace@example.com")

    app_url = f"{API}/{app['id']}"
    assert client.get(API).json()["total"] == 0
    assert client.get(app_url).status_code == 404  # 404, not 403: existence isn't revealed
    assert client.patch(app_url, json={"status": "rejected"}).status_code == 404
    assert client.post(f"{app_url}/archive").status_code == 404
    assert client.get(f"{app_url}/timeline").status_code == 404
    assert client.get(f"{app_url}/rounds").status_code == 404
    assert client.post(f"{app_url}/rounds", json={"name": "HR", "round_type": "hr_interview"}).status_code == 404

    act_as(client, ada_token)
    assert client.get(app_url).json()["status"] == "interested"  # untouched


def test_unknown_application_is_404(ada: TestClient) -> None:
    response = ada.get(f"{API}/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
