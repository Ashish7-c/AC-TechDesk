
import os
from contextlib import closing
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash

# Require deployment secrets
if not os.environ.get("SECRET_KEY"):
    raise RuntimeError("SECRET_KEY is required.")

from app import app, get_db, initialize_database

# Initialize database tables
initialize_database()

# Read demo administrator configuration
admin_name = "AC-TechDesk Demo Admin"
admin_email = os.environ.get(
    "DEMO_ADMIN_EMAIL", ""
).strip().lower()
admin_password = os.environ.get(
    "DEMO_ADMIN_PASSWORD", ""
)

if not admin_email or len(admin_password) < 16:
    raise RuntimeError(
        "Configure DEMO_ADMIN_EMAIL and "
        "DEMO_ADMIN_PASSWORD (minimum 16 characters)."
    )

# Create an administrator only when needed
with closing(get_db()) as db:
    existing_admin = db.execute(
        "SELECT id FROM users WHERE email = ?",
        (admin_email,)
    ).fetchone()

    if existing_admin is None:
        with db:
            db.execute(
                """
                INSERT INTO users
                (name, email, password_hash, role,
                 is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    admin_name,
                    admin_email,
                    generate_password_hash(admin_password),
                    "Admin",
                    1,
                    datetime.now(timezone.utc).strftime(
                        "%Y-%m-%d %H:%M UTC"
                    )
                )
            )

        print("Demo administrator initialized.")
