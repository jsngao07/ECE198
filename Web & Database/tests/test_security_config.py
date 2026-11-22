"""CSRF protection, response headers, and deployment configuration checks."""
import pytest

import app as motion
from conftest import PASSWORD, login


def test_post_without_csrf_token_is_refused(app, make, people):
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()
    r = client.post("/login", data={"user_id": "insA", "password": PASSWORD})
    assert r.status_code == 303                    # handled by the CSRFError handler
    assert client.get("/dashboard").status_code == 302  # login did not happen


def test_device_api_also_requires_csrf_token(app, make, people):
    app.config["WTF_CSRF_ENABLED"] = True
    plan = make.plan(people["pat_a"], people["ins_a"])
    client = app.test_client()
    with client.session_transaction() as s:
        s["user_id"] = people["pat_a"]
    r = client.post("/api/device/progress", json={
        "plan_id": plan, "exercise_name": "Arm Curl", "actual_reps": 5, "actual_seconds": 10})
    assert r.status_code == 303
    assert make.count(motion.ProgressLog) == 0


def test_pages_are_not_cached(client, people):
    login(client, "insA")
    assert "no-store" in client.get("/dashboard").headers["Cache-Control"]


def test_session_cookie_is_httponly(client, people):
    r = login(client, "insA")
    cookie = r.headers["Set-Cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


def test_deployed_config_requires_secret_key(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'x.db'}")
    monkeypatch.delenv("MOTION_SECRET_KEY")
    with pytest.raises(RuntimeError, match="MOTION_SECRET_KEY"):
        motion.create_app()


def test_deployed_config_requires_admin_password(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'x.db'}")
    monkeypatch.delenv("MOTION_ADMIN_PASSWORD")
    with pytest.raises(RuntimeError, match="MOTION_ADMIN_PASSWORD"):
        motion.create_app()


def test_short_admin_password_is_refused(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'x.db'}")
    monkeypatch.setenv("MOTION_ADMIN_PASSWORD", "short")
    with pytest.raises(RuntimeError, match="at least 12"):
        motion.create_app()


def test_deployed_config_uses_secure_cookies(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'x.db'}")
    assert motion.create_app().config["SESSION_COOKIE_SECURE"] is True


def test_admin_password_is_not_reset_on_restart(app, monkeypatch, client):
    monkeypatch.setenv("MOTION_ADMIN_PASSWORD", "a-different-password")
    motion.create_app()  # restart with a changed env var
    assert login(client, "admin", "admin-password-123").status_code == 302
