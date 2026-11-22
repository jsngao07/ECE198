"""POST /api/device/progress — the endpoint the browser calls after reading
an exercise record from the Arduino over Web Serial."""
import pytest

import app as motion
from conftest import login

URL = "/api/device/progress"


@pytest.fixture
def plan(make, people):
    return make.plan(people["pat_a"], people["ins_a"], "Arm Curl")


@pytest.fixture
def patient(client, people):
    login(client, "patA")
    return client


def record(pid, **overrides):
    body = {"plan_id": pid, "exercise_name": "Arm Curl",
            "actual_reps": 12, "actual_seconds": 45}
    body.update(overrides)
    return body


def test_valid_record_is_saved(patient, make, plan):
    r = patient.post(URL, json=record(plan))
    assert r.status_code == 200
    assert r.json["ok"] is True
    log = make.get(motion.ProgressLog, r.json["log_id"])
    assert log.plan_id == plan
    assert log.reps_completed == 12
    assert log.sets_completed == 1
    assert "45 seconds" in log.notes


@pytest.mark.parametrize("seconds, minutes", [
    (0, None), (1, 1), (59, 1), (60, 1), (61, 2), (3600, 60),
])
def test_seconds_are_rounded_up_to_minutes(patient, make, plan, seconds, minutes):
    r = patient.post(URL, json=record(plan, actual_seconds=seconds))
    assert make.get(motion.ProgressLog, r.json["log_id"]).duration_minutes == minutes


@pytest.mark.parametrize("name", ["arm curl", "ARM CURL", "  Arm Curl  "])
def test_exercise_name_match_ignores_case_and_spaces(patient, plan, name):
    assert patient.post(URL, json=record(plan, exercise_name=name)).status_code == 200


@pytest.mark.parametrize("reps, seconds", [(0, 0), (10000, 36000)])
def test_range_limits_are_inclusive(patient, plan, reps, seconds):
    r = patient.post(URL, json=record(plan, actual_reps=reps, actual_seconds=seconds))
    assert r.status_code == 200


@pytest.mark.parametrize("overrides", [
    {"actual_reps": -1},
    {"actual_reps": 10001},
    {"actual_seconds": -1},
    {"actual_seconds": 36001},
])
def test_out_of_range_values_are_rejected(patient, make, plan, overrides):
    r = patient.post(URL, json=record(plan, **overrides))
    assert r.status_code == 400
    assert make.count(motion.ProgressLog) == 0


@pytest.mark.parametrize("overrides", [
    {"actual_reps": "12"},       # string instead of int
    {"actual_reps": 12.0},       # float
    {"actual_reps": True},       # bool is an int subclass in Python
    {"actual_seconds": None},
    {"plan_id": "1"},
    {"exercise_name": 5},
])
def test_wrong_types_are_rejected(patient, make, plan, overrides):
    r = patient.post(URL, json=record(plan, **overrides))
    assert r.status_code == 400
    assert make.count(motion.ProgressLog) == 0


@pytest.mark.parametrize("missing", ["plan_id", "exercise_name", "actual_reps", "actual_seconds"])
def test_missing_fields_are_rejected(patient, plan, missing):
    body = record(plan)
    del body[missing]
    assert patient.post(URL, json=body).status_code == 400


@pytest.mark.parametrize("payload", [[1, 2, 3], "text", 42])
def test_non_object_json_is_rejected(patient, plan, payload):
    assert patient.post(URL, json=payload).status_code == 400


def test_non_json_body_is_rejected(patient, plan):
    r = patient.post(URL, data="not json", content_type="text/plain")
    assert r.status_code == 400


def test_mismatched_exercise_is_rejected(patient, make, plan):
    r = patient.post(URL, json=record(plan, exercise_name="Leg Raise"))
    assert r.status_code == 400
    assert make.count(motion.ProgressLog) == 0


def test_unknown_plan_returns_404(patient, plan):
    assert patient.post(URL, json=record(plan + 999)).status_code == 404


def test_inactive_plan_returns_404(patient, make, people):
    inactive = make.plan(people["pat_a"], people["ins_a"], active=False)
    assert patient.post(URL, json=record(inactive)).status_code == 404


def test_patient_cannot_save_to_another_patients_plan(patient, make, people):
    other = make.plan(people["pat_b"], people["ins_b"], "Arm Curl")
    r = patient.post(URL, json=record(other))
    assert r.status_code == 404
    assert make.count(motion.ProgressLog) == 0


def test_signed_out_request_is_redirected_and_not_saved(client, make, plan):
    r = client.post(URL, json=record(plan))
    assert r.status_code == 302
    assert make.count(motion.ProgressLog) == 0


def test_instructor_cannot_use_device_endpoint(client, make, people, plan):
    login(client, "insA")
    assert client.post(URL, json=record(plan)).status_code == 403


def test_saved_device_record_appears_on_patient_dashboard(patient, plan):
    patient.post(URL, json=record(plan, actual_reps=37))
    page = patient.get("/dashboard")
    assert page.status_code == 200
    assert b"37" in page.data
