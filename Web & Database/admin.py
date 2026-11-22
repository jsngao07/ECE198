"""Create an administrator from deployment environment variables, never hard-coded credentials."""
import os

from werkzeug.security import generate_password_hash

ADMIN_USER_ID = "admin"


def ensure_admin_account(db, user_model):
    """Create the initial admin once; do not reset existing passwords on restart."""
    existing = user_model.query.filter_by(user_id=ADMIN_USER_ID).first()
    if existing:
        if existing.role != "admin":
            raise RuntimeError("The reserved user ID 'admin' belongs to a non-admin account.")
        return

    password = os.environ.get("MOTION_ADMIN_PASSWORD")
    if not password:
        if os.environ.get("DATABASE_URL"):
            raise RuntimeError("Set MOTION_ADMIN_PASSWORD before deploying this app.")
        # Local development can create an admin via environment variables.
        return
    if len(password) < 12:
        raise RuntimeError("MOTION_ADMIN_PASSWORD must have at least 12 characters.")

    db.session.add(user_model(
        user_id=ADMIN_USER_ID,
        name="Administrator",
        password_hash=generate_password_hash(password),
        role="admin",
        approved=True,
    ))
    db.session.commit()
