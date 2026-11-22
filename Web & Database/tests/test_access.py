"""Role restrictions and data isolation between instructors and patients."""
import pytest

import app as motion
from conftest import ADMIN_PASSWORD, PASSWORD, login


@pytest.mark.parametrize("path", ["/patients", "/patients/new", "/exercises/new", "/admin"])
def test_patient_is_forbidden_from_staff_pages(client, people, path):
    login(client, "patA")
    assert client.get(path).status_code == 403


def test_instructor_is_forbidden_from_admin(client, people):
    login(client, "insA")
    assert client.get("/admin").status_code == 403


def test_instructor_cannot_log_progress_as_patient(client, make, people):
    plan = make.plan(people["pat_a"], people["ins_a"])
    login(client, "insA")
    assert client.get(f"/progress/log/{plan}").status_code == 403


def test_instructor_sees_only_own_patients(client, people):
    login(client, "insA")
    page = client.get("/patients").data
    assert b"Pata" in page        # their own patient (name is user_id.title())
    assert b"Patb" not in page    # the other instructor's patient


@pytest.mark.parametrize("method, path", [
    ("get", "/patients/{pid}"),
    ("post", "/patients/{pid}/notes"),
    ("post", "/patients/{pid}/approve"),
    ("post", "/patients/{pid}/delete"),
    ("get", "/plans/new/{pid}"),
])
def test_instructor_cannot_touch_another_instructors_patient(client, make, people, method, path):
    login(client, "insA")
    r = getattr(client, method)(path.format(pid=people["pat_b"]))
    assert r.status_code == 404
    assert make.get(motion.User, people["pat_b"]) is not None  # not deleted


def test_instructor_cannot_toggle_another_instructors_plan(client, make, people):
    plan = make.plan(people["pat_b"], people["ins_b"])
    login(client, "insA")
    assert client.post(f"/plans/{plan}/toggle").status_code == 404
    assert make.get(motion.ExercisePlan, plan).active is True


def test_patient_cannot_log_progress_on_someone_elses_plan(client, make, people):
    plan = make.plan(people["pat_b"], people["ins_b"])
    login(client, "patA")
    assert client.get(f"/progress/log/{plan}").status_code == 404


# --- Instructor patient management -----------------------------------------

def test_instructor_approves_pending_patient(client, make, people):
    login(client, "insA")
    client.post(f"/patients/{people['pending']}/approve")
    assert make.get(motion.User, people["pending"]).approved is True


def test_instructor_creates_patient_directly(client, make, people):
    login(client, "insA")
    client.post("/patients/new", data={"user_id": "walkin", "name": "Walk In", "password": PASSWORD})
    with make.app.app_context():
        p = motion.User.query.filter_by(user_id="walkin").one()
        assert (p.role, p.approved, p.instructor_id) == ("patient", True, people["ins_a"])


def test_instructor_deletes_own_patient_and_their_records(client, make, people):
    plan = make.plan(people["pat_a"], people["ins_a"])
    login(client, "patA")
    client.post(f"/progress/log/{plan}", data={"sets": "3", "reps": "10"})
    client.post("/logout")

    login(client, "insA")
    client.post(f"/patients/{people['pat_a']}/delete")
    assert make.get(motion.User, people["pat_a"]) is None
    assert make.count(motion.ExercisePlan, patient_id=people["pat_a"]) == 0
    assert make.count(motion.ProgressLog, patient_id=people["pat_a"]) == 0


def test_instructor_notes_are_saved(client, make, people):
    login(client, "insA")
    client.post(f"/patients/{people['pat_a']}/notes", data={"notes": "Knee pain on left"})
    assert make.get(motion.User, people["pat_a"]).instructor_notes == "Knee pain on left"


# --- Admin ------------------------------------------------------------------

def test_admin_creates_instructor(client, make):
    login(client, "admin", ADMIN_PASSWORD)
    client.post("/admin/instructors/new", data={"user_id": "coach", "name": "Coach", "password": PASSWORD})
    with make.app.app_context():
        assert motion.User.query.filter_by(user_id="coach").one().role == "instructor"


def test_admin_rejects_short_instructor_password(client, make):
    login(client, "admin", ADMIN_PASSWORD)
    client.post("/admin/instructors/new", data={"user_id": "coach", "name": "Coach", "password": "short"})
    assert make.count(motion.User, user_id="coach") == 0


def test_admin_password_reset_lets_user_log_in_with_new_password(client, people):
    login(client, "admin", ADMIN_PASSWORD)
    client.post(f"/admin/users/{people['ins_a']}/edit",
                data={"user_id": "insA", "name": "Ins A", "password": "brand-new-pass-1"})
    client.post("/logout")
    assert login(client, "insA").status_code == 200            # old password fails
    assert login(client, "insA", "brand-new-pass-1").status_code == 302


def test_admin_cannot_edit_the_admin_account(client, make):
    login(client, "admin", ADMIN_PASSWORD)
    with make.app.app_context():
        admin_id = motion.User.query.filter_by(user_id="admin").one().id
    r = client.post(f"/admin/users/{admin_id}/edit", data={"user_id": "hacked", "name": "x"})
    assert r.status_code == 404


def test_deleting_instructor_removes_their_patients_and_data(client, make, people):
    plan = make.plan(people["pat_a"], people["ins_a"])
    login(client, "admin", ADMIN_PASSWORD)
    client.post(f"/admin/instructors/{people['ins_a']}/delete")
    assert make.get(motion.User, people["ins_a"]) is None
    assert make.get(motion.User, people["pat_a"]) is None
    assert make.get(motion.User, people["pending"]) is None
    assert make.get(motion.ExercisePlan, plan) is None
    # The other instructor's side is untouched.
    assert make.get(motion.User, people["pat_b"]) is not None


def test_admin_delete_route_refuses_non_instructors(client, make, people):
    login(client, "admin", ADMIN_PASSWORD)
    assert client.post(f"/admin/instructors/{people['pat_a']}/delete").status_code == 404
    assert make.get(motion.User, people["pat_a"]) is not None
