
from contextlib import closing
from datetime import datetime, timezone
from getpass import getpass

from werkzeug.security import generate_password_hash

from app import get_db, initialize_database


# ==========================================
# CREATE ADMIN ACCOUNT
# ==========================================

def create_admin():

    # Initialize existing database tables
    initialize_database()

    print("\nAC-TechDesk - Create Administrator\n")

    # ======================================
    # ENSURE USERS TABLE EXISTS
    # ======================================

    with closing(get_db()) as db:

        with db:

            db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'Employee'
                        CHECK (
                            role IN (
                                'Admin',
                                'Technician',
                                'Employee'
                            )
                        ),
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)

    print("Users database table is ready.")

    # ======================================
    # GET ADMIN DETAILS
    # ======================================

    name = input("Full name: ").strip()

    email = input("Email address: ").strip().lower()

    password = getpass(
        "Password (minimum 12 characters): "
    )

    confirm_password = getpass(
        "Confirm password: "
    )

    # ======================================
    # VALIDATE ADMIN DETAILS
    # ======================================

    if not name or not email or "@" not in email:
        print("Please enter a valid name and email.")
        return

    if len(password) < 12:
        print("Password must contain at least 12 characters.")
        return

    if password != confirm_password:
        print("Passwords do not match.")
        return

    # ======================================
    # CHECK EXISTING ADMIN ACCOUNT
    # ======================================

    with closing(get_db()) as db:

        existing_user = db.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing_user:

            print(
                "An account with this email already exists."
            )
            return

        # Hash password securely
        password_hash = generate_password_hash(
            password
        )

        # Record creation time in UTC
        now = datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d %H:%M UTC")

        # ==================================
        # SAVE ADMIN ACCOUNT
        # ==================================

        with db:

            db.execute("""
                INSERT INTO users (
                    name,
                    email,
                    password_hash,
                    role,
                    is_active,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                name,
                email,
                password_hash,
                "Admin",
                1,
                now
            ))

    print(
        "\nAdministrator account created successfully!"
    )


# ==========================================
# RUN ADMIN CREATION
# ==========================================

if __name__ == "__main__":

    create_admin()
