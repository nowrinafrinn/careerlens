"""API tests for requirement analysis: running, reading, staleness, user input, isolation."""

from fastapi.testclient import TestClient

from tests.conftest import act_as, sign_up
from tests.cv_files import SAMPLE_CV_LINES, make_pdf
from tests.test_requirement_analysis import SAMPLE_JD

APPS = "/api/v1/applications"


def upload_cv(client: TestClient, lines: list[str] = SAMPLE_CV_LINES, name: str = "cv.pdf") -> dict:
    response = client.post("/api/v1/cv-versions", files={"file": (name, make_pdf(lines), "application/pdf")})
    assert response.status_code == 201, response.text
    return response.json()


def ready_application(client: TestClient, job_description: str = SAMPLE_JD) -> dict:
    cv = upload_cv(client)
    response = client.post(
        APPS,
        json={"company_name": "PayFlow", "position_title": "Backend Engineer", "job_description": job_description,
              "cv_version_id": cv["id"]},
    )
    assert response.status_code == 201, response.text
    return response.json()


def run(client: TestClient, application_id: str):
    return client.post(f"{APPS}/{application_id}/analyses")


def find(analysis: dict, fragment: str) -> dict:
    return next(r for r in analysis["requirements"] if fragment in r["text"])


# --- running and reading -------------------------------------------------------------------


def test_analysis_extracts_requirements_and_links_cv_passages(ada: TestClient) -> None:
    app = ready_application(ada)

    response = run(ada, app["id"])

    assert response.status_code == 201, response.text
    analysis = response.json()
    assert analysis["method"] == "rule_engine"
    assert analysis["is_stale"] is False
    assert len(analysis["requirements"]) == 10

    postgres = find(analysis, "PostgreSQL")
    assert postgres["evidence_status"] == "demonstrated"
    evidence = postgres["evidence"][0]
    assert evidence["section_type"] == "projects"
    assert evidence["passage_text"] == "Designed a PostgreSQL schema with Alembic migrations."

    # Evidence offsets point at the exact text of the CV version used.
    cv = ada.get(f"/api/v1/cv-versions/{analysis['cv_version']['id']}").json()
    for requirement in analysis["requirements"]:
        for link in requirement["evidence"]:
            assert cv["raw_text"][link["char_start"] : link["char_end"]] == link["passage_text"]
    # And requirement offsets point at the exact job description text.
    for requirement in analysis["requirements"]:
        assert SAMPLE_JD[requirement["jd_char_start"] : requirement["jd_char_end"]] == requirement["text"]


def test_coverage_counts_required_lines_only_and_explains_itself(ada: TestClient) -> None:
    analysis = run(ada, ready_application(ada)["id"]).json()

    coverage = analysis["coverage"]
    # Required: degree, years, FastAPI/Django, PostgreSQL, Docker, communication.
    assert coverage["required_total"] == 6
    assert coverage["demonstrated"] == 3  # degree, FastAPI/Django, PostgreSQL
    assert coverage["partially_demonstrated"] == 2  # years of Python, Docker (skills list only)
    assert coverage["needs_verification"] == 1  # communication
    assert coverage["percent"] == 50
    assert "does not predict whether you'll be hired" in coverage["explanation"]


def test_reopening_returns_the_stored_analysis_without_rerunning(ada: TestClient) -> None:
    app = ready_application(ada)
    created = run(ada, app["id"]).json()

    latest = ada.get(f"{APPS}/{app['id']}/analyses/latest").json()

    assert latest["id"] == created["id"]
    assert len(ada.get(f"{APPS}/{app['id']}/analyses").json()) == 1


def test_missing_job_description_or_cv_is_explained(ada: TestClient) -> None:
    no_jd = ada.post(APPS, json={"company_name": "A", "position_title": "B"}).json()
    response = run(ada, no_jd["id"])
    assert (response.status_code, response.json()["error"]["code"]) == (422, "missing_job_description")

    no_cv = ada.post(APPS, json={"company_name": "A", "position_title": "B", "job_description": SAMPLE_JD}).json()
    response = run(ada, no_cv["id"])
    assert (response.status_code, response.json()["error"]["code"]) == (422, "missing_cv")


def test_no_analysis_yet_is_a_clear_404(ada: TestClient) -> None:
    app = ready_application(ada)

    response = ada.get(f"{APPS}/{app['id']}/analyses/latest")

    assert (response.status_code, response.json()["error"]["code"]) == (404, "no_analysis")


# --- staleness ---------------------------------------------------------------------------


def test_changed_job_description_makes_analysis_stale(ada: TestClient) -> None:
    app = ready_application(ada)
    run(ada, app["id"])

    ada.patch(f"{APPS}/{app['id']}", json={"job_description": SAMPLE_JD + "\n- Experience with Kafka"})
    latest = ada.get(f"{APPS}/{app['id']}/analyses/latest").json()

    assert latest["is_stale"] is True
    assert latest["stale_reasons"] == ["The job description has changed since this analysis."]


def test_switching_cv_version_makes_analysis_stale(ada: TestClient) -> None:
    app = ready_application(ada)
    run(ada, app["id"])
    other = upload_cv(ada, [*SAMPLE_CV_LINES, "Certifications", "AWS Cloud Practitioner"], "v2.pdf")

    ada.patch(f"{APPS}/{app['id']}", json={"cv_version_id": other["id"]})

    latest = ada.get(f"{APPS}/{app['id']}/analyses/latest").json()
    assert latest["stale_reasons"] == ["The application now uses a different CV version."]


def test_correcting_a_cv_section_makes_analysis_stale(ada: TestClient) -> None:
    app = ready_application(ada)
    analysis = run(ada, app["id"]).json()
    cv = ada.get(f"/api/v1/cv-versions/{analysis['cv_version']['id']}").json()
    experience = next(s for s in cv["sections"] if s["section_type"] == "experience")

    ada.patch(f"/api/v1/cv-versions/{cv['id']}/sections/{experience['id']}", json={"section_type": "internship"})

    latest = ada.get(f"{APPS}/{app['id']}/analyses/latest").json()
    assert latest["stale_reasons"] == ["Section types in the CV were corrected since this analysis."]


# --- the candidate's own assessment --------------------------------------------------------


def test_not_found_in_cv_is_not_a_verified_lack_of_skill(ada: TestClient) -> None:
    analysis = run(ada, ready_application(ada)["id"]).json()

    kubernetes = find(analysis, "Kubernetes")

    # The CV verdict and the candidate's own answer are separate fields.
    assert kubernetes["evidence_status"] == "not_found_in_cv"
    assert kubernetes["self_report"] == "unknown"
    assert "doesn't mean you lack it" in kubernetes["missing_details"]


def test_self_report_is_stored_beside_the_verdict_not_instead_of_it(ada: TestClient) -> None:
    analysis = run(ada, ready_application(ada)["id"]).json()
    kubernetes = find(analysis, "Kubernetes")

    response = ada.patch(f"/api/v1/requirements/{kubernetes['id']}", json={"self_report": "have_not_on_cv"})

    assert response.status_code == 200
    body = response.json()
    assert body["self_report"] == "have_not_on_cv"
    assert body["evidence_status"] == "not_found_in_cv"  # the CV still doesn't show it


def test_user_input_carries_over_to_a_rerun(ada: TestClient) -> None:
    app = ready_application(ada)
    first = run(ada, app["id"]).json()
    ada.patch(f"/api/v1/requirements/{find(first, 'Kubernetes')['id']}", json={"self_report": "learning"})
    ada.patch(f"/api/v1/requirements/{find(first, 'AWS')['id']}", json={"importance": "required"})
    ada.patch(f"/api/v1/requirements/{find(first, 'Collaborate')['id']}", json={"dismissed": True})

    second = run(ada, app["id"]).json()

    assert second["id"] != first["id"]
    assert find(second, "Kubernetes")["self_report"] == "learning"
    assert find(second, "AWS")["importance"] == "required"
    assert find(second, "AWS")["user_edited"] is True
    assert find(second, "Collaborate")["dismissed"] is True
    assert len(ada.get(f"{APPS}/{app['id']}/analyses").json()) == 2  # the first one is kept


def test_dismissed_and_reprioritised_lines_change_coverage(ada: TestClient) -> None:
    analysis = run(ada, ready_application(ada)["id"]).json()
    communication = find(analysis, "communication")

    ada.patch(f"/api/v1/requirements/{communication['id']}", json={"dismissed": True})

    coverage = ada.get(f"/api/v1/analyses/{analysis['id']}").json()["coverage"]
    assert coverage["required_total"] == 5
    assert coverage["percent"] == 60


def test_changing_category_reassesses_against_the_same_cv(ada: TestClient) -> None:
    analysis = run(ada, ready_application(ada)["id"]).json()
    degree = find(analysis, "Bachelor's degree")
    assert degree["evidence_status"] == "demonstrated"

    body = ada.patch(f"/api/v1/requirements/{degree['id']}", json={"category": "other"}).json()

    assert body["category"] == "other"
    assert body["evidence_status"] == "needs_verification"
    assert body["user_edited"] is True


# --- isolation -------------------------------------------------------------------------


def test_other_users_cannot_run_read_or_change_an_analysis(client: TestClient) -> None:
    ada_token = sign_up(client, "ada@example.com")
    app = ready_application(client)
    analysis = run(client, app["id"]).json()
    requirement_id = analysis["requirements"][0]["id"]
    sign_up(client, "grace@example.com")

    assert run(client, app["id"]).status_code == 404
    assert client.get(f"{APPS}/{app['id']}/analyses").status_code == 404
    assert client.get(f"{APPS}/{app['id']}/analyses/latest").status_code == 404
    assert client.get(f"/api/v1/analyses/{analysis['id']}").status_code == 404
    assert client.patch(f"/api/v1/requirements/{requirement_id}", json={"self_report": "do_not_have"}).status_code == 404

    act_as(client, ada_token)
    assert client.get(f"/api/v1/analyses/{analysis['id']}").json()["requirements"][0]["self_report"] == "unknown"
