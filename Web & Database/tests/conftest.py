"""Shared pytest fixtures for the Motion Flask app.

Every test gets a brand-new SQLite database in a temporary folder, so tests
never touch Web & Database/instance/database.db or the deployed Postgres DB.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

# app.py builds an app at import time (`app = create_app()`), so point that
# first build at a throwaway database *before* importing it.
_IMPORT_DB = Path(tempfile.mkdtemp()) / "import.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_IMPORT_DB}"
os.environ["MOTION_SECRET_KEY"] = "test-secret-key"
os.environ["MOTION_ADMIN_PASSWORD"] = "admin-password-123"

import app as motion  # noqa: E402  (must come after the env setup above)

PASSWORD = "correct-horse-1"  # 15 characters, satisfies the >=12 rule
ADMIN_PASSWORD = os.environ["MOTION_ADMIN_PASSWORD"]


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    flask_app = motion.create_app()
    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,      # CSRF has its own dedicated test
        SESSION_COOKIE_SECURE=False,  # the test client talks plain http
    )
    yield flask_app
    with flask_app.app_context():
        motion.db.session.remove()
        motion.db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


class Factory:
    """Creates database rows directly so tests can focus on one behaviour."""

    def __init__(self, app):
        self.app = app

    def _add(self, obj):
        with self.app.app_context():
            motion.db.session.add(obj)
            motion.db.session.commit()
            return obj.id

    def user(self, user_id, role, *, approved=True, instructor_id=None, password=PASSWORD):
        from werkzeug.security import generate_password_hash
        return self._add(motion.User(
            user_id=user_id, name=user_id.title(), role=role, approved=approved,
            instructor_id=instructor_id, password_hash=generate_password_hash(password)))

    def exercise_id(self, name):
        with self.app.app_context():
            return motion.Exercise.query.filter_by(name=name).one().id

    def plan(self, patient_id, instructor_id, exercise="Arm Curl", *, active=True):
        return self._add(motion.ExercisePlan(
            patient_id=patient_id, instructor_id=instructor_id,
            exercise_id=self.exercise_id(exercise), sets=3, reps=10, active=active))

    def get(self, model, pk):
        with self.app.app_context():
            obj = motion.db.session.get(model, pk)
            if obj is not None:
                motion.db.session.expunge(obj)
            return obj

    def count(self, model, **filters):
        with self.app.app_context():
            return model.query.filter_by(**filters).count()


@pytest.fixture
def make(app):
    return Factory(app)


@pytest.fixture
def people(make):
    """Two instructors, each with one approved patient, plus one pending patient."""
    ins_a = make.user("insA", "instructor")
    ins_b = make.user("insB", "instructor")
    return {
        "ins_a": ins_a,
        "ins_b": ins_b,
        "pat_a": make.user("patA", "patient", instructor_id=ins_a),
        "pat_b": make.user("patB", "patient", instructor_id=ins_b),
        "pending": make.user("patWait", "patient", approved=False, instructor_id=ins_a),
    }


def login(client, user_id, password=PASSWORD):
    return client.post("/login", data={"user_id": user_id, "password": password})
