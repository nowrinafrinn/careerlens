from fastapi.testclient import TestClient

from tests.conftest import act_as, sign_up
from tests.test_analyses import ready_application, run


def recs(client: TestClient, analysis_id: str) -> list[dict]:
    response = client.get(f"/api/v1/analyses/{analysis_id}/recommendations")
    assert response.status_code == 200, response.text
    return response.json()


def one(items: list[dict], title: str) -> dict:
    matches = [r for r in items if r["title"] == title]
    assert len(matches) == 1, [r["title"] for r in items]
    return matches[0]


def requirement(analysis: dict, fragment: str) -> dict:
    return next(r for r in analysis["requirements"] if fragment in r["text"])


def test_running_an_analysis_creates_recommendations(ada: TestClient) -> None:
    analysis = run(ada, ready_application(ada)["id"]).json()

    items = recs(ada, analysis["id"])

    titles = {r["title"] for r in items}
    assert "Back up Docker with an example" in titles
    assert "Do you have Kubernetes?" in titles
    assert "Say what this work was for and what came of it" in titles
    assert all(r["status"] == "proposed" and r["number_warnings"] == [] for r in items)
    docker = one(items, "Back up Docker with an example")
    assert (docker["kind"], docker["change_type"]) == ("unverified_claim", "add_bullet")
    assert docker["requirement_text"] == "Familiarity with Docker"
    assert docker["original_text"] == "Tools: Docker, Git, PostgreSQL"


def test_self_report_changes_which_suggestions_apply(ada: TestClient) -> None:
    analysis = run(ada, ready_application(ada)["id"]).json()

    ada.patch(f"/api/v1/requirements/{requirement(analysis, 'Kubernetes')['id']}", json={"self_report": "do_not_have"})
    ada.patch(f"/api/v1/requirements/{requirement(analysis, 'Docker')['id']}", json={"self_report": "do_not_have"})

    items = recs(ada, analysis["id"])
    titles = {r["title"] for r in items}
    assert "Do you have Kubernetes?" not in titles
    gap = one(items, "Kubernetes may be worth learning")
    assert (gap["kind"], gap["change_type"], gap["suggested_text"]) == ("potential_capability_gap", "no_cv_change", None)
    removal = one(items, "Your CV lists Docker, but you said you don't have it")
    assert removal["suggested_text"] == "Tools: Git, PostgreSQL"
    assert "Back up Docker with an example" not in titles


def test_accept_edit_reject_and_undo(ada: TestClient) -> None:
    analysis = run(ada, ready_application(ada)["id"]).json()
    rec = one(recs(ada, analysis["id"]), "Say what this work was for and what came of it")
    url = f"/api/v1/recommendations/{rec['id']}"

    accepted = ada.patch(url, json={"status": "accepted"}).json()
    assert accepted["final_text"] == rec["suggested_text"]
    assert accepted["decided_at"] is not None

    missing = ada.patch(url, json={"status": "edited"})
    assert (missing.status_code, missing.json()["error"]["code"]) == (422, "final_text_required")

    edited = ada.patch(
        url, json={"status": "edited", "final_text": "Designed a PostgreSQL schema for a 30-table reporting app."}
    ).json()
    assert edited["status"] == "edited"
    assert edited["number_warnings"] == ["30"]  # a figure that wasn't in the original: check it

    rejected = ada.patch(url, json={"status": "rejected"}).json()
    assert (rejected["status"], rejected["final_text"]) == ("rejected", None)

    undone = ada.patch(url, json={"status": "proposed"}).json()
    assert (undone["status"], undone["decided_at"]) == ("proposed", None)


def test_accepting_never_modifies_the_cv(ada: TestClient) -> None:
    app = ready_application(ada)
    analysis = run(ada, app["id"]).json()
    cv_before = ada.get(f"/api/v1/cv-versions/{analysis['cv_version']['id']}").json()
    original_file = ada.get(f"/api/v1/cv-versions/{analysis['cv_version']['id']}/file").content

    for rec in recs(ada, analysis["id"]):
        ada.patch(f"/api/v1/recommendations/{rec['id']}", json={"status": "accepted"})

    cv_after = ada.get(f"/api/v1/cv-versions/{analysis['cv_version']['id']}").json()
    assert cv_after["raw_text"] == cv_before["raw_text"]
    assert cv_after["sections"] == cv_before["sections"]
    assert ada.get(f"/api/v1/cv-versions/{analysis['cv_version']['id']}/file").content == original_file


def test_decisions_survive_self_report_changes_and_reruns(ada: TestClient) -> None:
    app = ready_application(ada)
    first = run(ada, app["id"]).json()
    docker_rec = one(recs(ada, first["id"]), "Back up Docker with an example")
    ada.patch(f"/api/v1/recommendations/{docker_rec['id']}", json={"status": "rejected"})

    # A decided suggestion stays even if the self-report would now produce a different one.
    ada.patch(f"/api/v1/requirements/{requirement(first, 'Docker')['id']}", json={"self_report": "do_not_have"})
    still = one(recs(ada, first["id"]), "Back up Docker with an example")
    assert still["status"] == "rejected"

    second = run(ada, app["id"]).json()
    carried = [r for r in recs(ada, second["id"]) if r["title"] == "Say what this work was for and what came of it"]
    assert carried and all(r["status"] == "proposed" for r in carried)
    ada.patch(f"/api/v1/recommendations/{carried[0]['id']}", json={"status": "accepted"})
    third = run(ada, app["id"]).json()
    assert one(recs(ada, third["id"]), "Say what this work was for and what came of it")["status"] == "accepted"


def test_dismissing_a_requirement_drops_its_open_suggestions(ada: TestClient) -> None:
    analysis = run(ada, ready_application(ada)["id"]).json()

    ada.patch(f"/api/v1/requirements/{requirement(analysis, 'Kubernetes')['id']}", json={"dismissed": True})

    assert "Do you have Kubernetes?" not in {r["title"] for r in recs(ada, analysis["id"])}


def test_other_users_cannot_see_or_decide_recommendations(client: TestClient) -> None:
    ada_token = sign_up(client, "ada@example.com")
    analysis = run(client, ready_application(client)["id"]).json()
    rec_id = recs(client, analysis["id"])[0]["id"]
    sign_up(client, "grace@example.com")

    assert client.get(f"/api/v1/analyses/{analysis['id']}/recommendations").status_code == 404
    assert client.patch(f"/api/v1/recommendations/{rec_id}", json={"status": "accepted"}).status_code == 404

    act_as(client, ada_token)
    assert recs(client, analysis["id"])[0]["status"] == "proposed"
