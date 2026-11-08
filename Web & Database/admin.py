"""Bootstrap the built-in local administrator account."""
from werkzeug.security import generate_password_hash

ADMIN_USER_ID = "admin"
ADMIN_PASSWORD = "admin"


def ensure_admin_account(db, user_model):
    """Create the default administrator once; never overwrite an existing account."""
    existing = user_model.query.filter_by(user_id=ADMIN_USER_ID).first()
    if existing:
        if existing.role != "admin":
            raise RuntimeError("The reserved user ID 'admin' is already assigned to a non-admin account.")
        return
    db.session.add(user_model(
        user_id=ADMIN_USER_ID,
        name="Administrator",
        password_hash=generate_password_hash(ADMIN_PASSWORD),
        role="admin",
        approved=True,
    ))
    db.session.commit()
