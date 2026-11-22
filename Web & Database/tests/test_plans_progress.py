"""Exercise library, exercise plans, and manual progress logging."""
import pytest

import app as motion
from conftest import login


@pytest.mark.parametrize("name", ["Arm Curl", "Leg Raise", "Sit to Stand",
                                  "Front Arm Raise", "Lateral Arm Raise"])
def test_arduino_exercises_are_seeded(make, name):
    """The web library must contain every exercise name the firmware can send."""
    assert make.count(motion.Exercise, name=name) == 1


def test_restarting_app_does_not_duplicate_seed_exercises(app, make):
    motion.create_app()  # simulates a server restart on the same database
    assert make.count(motion.Exercise, name="Arm Curl") == 1


# --- Exercise library -------------------------------------------------------

def test_instructor_adds_exercise(client, make, people):
    login(client, "insA")
    client.post("/exercises/new", data={"name": "Wall Sit", "category": "Strength"})
    assert make.count(motion.Exercise, name="Wall Sit") == 1


def test_duplicate_exercise_name_is_rejected_case_insensitively(client, make, people):
    login(client, "insA")
    r = client.post("/exercises/new", data={"name": "arm curl"})
    assert b"already exists" in r.data
    assert make.count(motion.Exercise, name="arm curl") == 0


def test_exercise_in_use_cannot_be_deleted(client, make, people):
    make.plan(people["pat_a"], people["ins_a"], "Arm Curl")
    login(client, "insA")
    client.post(f"/exercises/{make.exercise_id('Arm Curl')}/delete")
    assert make.count(motion.Exercise, name="Arm Curl") == 1


def test_unused_exercise_can_be_deleted(client, make, people):
    login(client, "insA")
    client.post(f"/exercises/{make.exercise_id('Plank')}/delete")
    assert make.count(motion.Exercise, name="Plank") == 0


# --- Plans ------------------------------------------------------------------

def plan_form(make, **overrides):
    form = {"exercise_id": str(make.exercise_id("Arm Curl")), "sets": "3",
            "reps": "10", "frequency": "3", "duration": ""}
    form.update(overrides)
    return form


def test_instructor_assigns_plan(client, make, people):
    login(client, "insA")
    r = client.post(f"/plans/new/{people['pat_a']}", data=plan_form(make))
    assert r.status_code == 302
    assert make.count(motion.ExercisePlan, patient_id=people["pat_a"]) == 1


@pytest.mark.parametrize("field, value", [
    ("sets", "0"), ("reps", "-1"), ("frequency", "0"), ("frequency", "8"),
    ("duration", "0"), ("sets", "abc"), ("exercise_id", ""),
])
def test_invalid_plan_values_are_rejected(client, make, people, field, value):
    login(client, "insA")
    r = client.post(f"/plans/new/{people['pat_a']}", data=plan_form(make, **{field: value}))
    assert r.status_code == 200
    assert make.count(motion.ExercisePlan, patient_id=people["pat_a"]) == 0


def test_plan_toggle_flips_active(client, make, people):
    plan = make.plan(people["pat_a"], people["ins_a"])
    login(client, "insA")
    client.post(f"/plans/{plan}/toggle")
    assert make.get(motion.ExercisePlan, plan).active is False
    client.post(f"/plans/{plan}/toggle")
    assert make.get(motion.ExercisePlan, plan).active is True


# --- Manual progress logging ------------------------------------------------

def test_patient_logs_progress(client, make, people):
    plan = make.plan(people["pat_a"], people["ins_a"])
    login(client, "patA")
    r = client.post(f"/progress/log/{plan}", data={"sets": "3", "reps": "12", "duration": "15"})
    assert r.status_code == 302
    with make.app.app_context():
        log = motion.ProgressLog.query.filter_by(plan_id=plan).one()
        assert (log.sets_completed, log.reps_completed, log.duration_minutes) == (3, 12, 15)


@pytest.mark.parametrize("form", [
    {"sets": "0", "reps": "10"},
    {"sets": "3", "reps": "0"},
    {"sets": "3", "reps": "10", "duration": "0"},
    {"sets": "x", "reps": "10"},
])
def test_invalid_progress_is_rejected(client, make, people, form):
    plan = make.plan(people["pat_a"], people["ins_a"])
    login(client, "patA")
    client.post(f"/progress/log/{plan}", data=form)
    assert make.count(motion.ProgressLog, plan_id=plan) == 0


def test_cannot_log_progress_on_inactive_plan(client, make, people):
    plan = make.plan(people["pat_a"], people["ins_a"], active=False)
    login(client, "patA")
    assert client.get(f"/progress/log/{plan}").status_code == 404


def test_logged_progress_shows_on_instructor_patient_page(client, make, people):
    plan = make.plan(people["pat_a"], people["ins_a"])
    login(client, "patA")
    client.post(f"/progress/log/{plan}", data={"sets": "2", "reps": "17"})
    client.post("/logout")
    login(client, "insA")
    r = client.get(f"/patients/{people['pat_a']}")
    assert r.status_code == 200
    assert b"17" in r.data
