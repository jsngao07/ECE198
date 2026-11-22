"""Login, logout, and patient self-registration."""
import pytest

import app as motion
from conftest import ADMIN_PASSWORD, PASSWORD, login


def test_root_redirects_signed_out_user_to_login(client):
    r = client.get("/")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/login")


def test_login_page_renders(client):
    assert client.get("/login").status_code == 200


def test_valid_login_goes_to_dashboard(client, people):
    r = login(client, "insA")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/dashboard")
    assert client.get("/dashboard").status_code == 200


def test_wrong_password_is_rejected(client, people):
    r = login(client, "insA", "wrong-password-123")
    assert r.status_code == 200
    assert b"Invalid ID or password." in r.data
    assert client.get("/dashboard").status_code == 302  # still signed out


def test_unknown_user_is_rejected(client, people):
    r = login(client, "nobody")
    assert b"Invalid ID or password." in r.data


def test_unapproved_patient_cannot_log_in(client, people):
    r = login(client, "patWait")
    assert b"waiting for instructor approval" in r.data
    assert client.get("/dashboard").status_code == 302


def test_admin_account_is_created_from_env_and_can_log_in(client):
    r = login(client, "admin", ADMIN_PASSWORD)
    assert r.headers["Location"].endswith("/dashboard")
    r = client.get("/dashboard")
    assert r.headers["Location"].endswith("/admin")


def test_logout_requires_post_and_clears_session(client, people):
    login(client, "insA")
    assert client.get("/logout").status_code == 405
    client.post("/logout")
    assert client.get("/dashboard").status_code == 302


@pytest.mark.parametrize("path", ["/dashboard", "/patients", "/exercises", "/appointments", "/admin"])
def test_protected_pages_redirect_to_login(client, path):
    r = client.get(path)
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


# --- Registration -----------------------------------------------------------

def register(client, instructor_id, **overrides):
    form = {"user_id": "newpat", "name": "New Patient", "email": "",
            "password": PASSWORD, "instructor_id": str(instructor_id)}
    form.update(overrides)
    return client.post("/register", data=form)


def test_registration_creates_unapproved_patient_under_instructor(client, make, people):
    r = register(client, people["ins_a"])
    assert r.status_code == 302
    with make.app.app_context():
        user = motion.User.query.filter_by(user_id="newpat").one()
        assert user.role == "patient"
        assert user.approved is False
        assert user.instructor_id == people["ins_a"]
        assert user.password_hash != PASSWORD  # stored hashed, not plain text


@pytest.mark.parametrize("password, accepted", [
    ("a" * 11, False),   # one short of the minimum
    ("a" * 12, True),    # exactly the minimum
    ("", False),
])
def test_registration_password_length_boundary(client, make, people, password, accepted):
    register(client, people["ins_a"], password=password)
    assert (make.count(motion.User, user_id="newpat") == 1) is accepted


@pytest.mark.parametrize("user_id", ["1abc", "abc_def", "abcdefghijk", "", "has space"])
def test_registration_rejects_invalid_user_ids(client, make, people, user_id):
    r = register(client, people["ins_a"], user_id=user_id)
    assert r.status_code == 200
    assert make.count(motion.User, user_id=user_id) == 0


def test_registration_rejects_duplicate_user_id(client, make, people):
    r = register(client, people["ins_a"], user_id="patA")
    assert b"already registered" in r.data
    assert make.count(motion.User, user_id="patA") == 1


def test_registration_rejects_duplicate_email(client, make, people):
    register(client, people["ins_a"], user_id="first", email="a@example.com")
    r = register(client, people["ins_a"], user_id="second", email="a@example.com")
    assert b"already registered" in r.data
    assert make.count(motion.User, user_id="second") == 0


def test_registration_rejects_a_patient_posing_as_instructor(client, make, people):
    register(client, people["pat_a"])
    assert make.count(motion.User, user_id="newpat") == 0


def test_registration_rejects_missing_instructor(client, make, people):
    register(client, "")
    assert make.count(motion.User, user_id="newpat") == 0
