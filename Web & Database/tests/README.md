# Flask app tests

Automated tests for the Motion web app (`app.py`). Each test builds the app
against a fresh temporary SQLite database, so your local
`instance/database.db` and the Render Postgres database are never touched.

## Run

From the `Web & Database` folder, inside your virtual environment:

    python -m pip install -r requirements-dev.txt
    python -m pytest

Useful options:

    python -m pytest tests/test_device_api.py   # one file
    python -m pytest -k csrf                     # tests whose name contains "csrf"
    python -m pytest -x                          # stop at the first failure

## What is covered

| File | Covers |
| --- | --- |
| `test_auth.py` | Login, logout, approval gate, registration validation (12-character password boundary, user ID format, duplicates) |
| `test_access.py` | Role restrictions (patient / instructor / admin), instructors limited to their own patients, admin account management and cascading deletes |
| `test_plans_progress.py` | Seeded Arduino exercise names, exercise library, plan validation, manual progress logging |
| `test_device_api.py` | `/api/device/progress`: valid records, seconds→minutes rounding, range limits, wrong types, missing fields, wrong plan or exercise, other patients' plans, signed-out and instructor access |
| `test_appointments.py` | Requesting, approving, countering, declining, and cancelling appointments |
| `test_security_config.py` | CSRF enforcement (forms and the device API), no-store caching, cookie flags, required deployment environment variables |

Not covered: the Arduino firmware, `static/arduino-sync.js` (runs in the
browser), and Postgres-specific behaviour.
