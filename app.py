
import os
import re
import sqlite3


from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort
)

from flask_wtf.csrf import CSRFProtect

from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user
)

from werkzeug.security import (
    check_password_hash,
    generate_password_hash
)


# ==========================================
# 1. APPLICATION CONFIGURATION
# ==========================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "local-development-only-change-before-deployment"
)

CSRFProtect(app)

# Flask-Login configuration
login_manager = LoginManager(app)

login_manager.login_view = "login"
login_manager.login_message = "Please log in to continue."

# Database configuration
BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "ac_techdesk.db"


# ==========================================
# 2. TICKET OPTIONS
# ==========================================

PRIORITIES = [
    "Low",
    "Medium",
    "High",
    "Critical"
]

STATUSES = [
    "Open",
    "In Progress",
    "Resolved",
    "Closed"
]

TECHNICIANS = [
    "Unassigned",
    "Harry Smith",
    "Jessica Johnson",
    "Michael Brown",
    "Emily Davis",
]

CATEGORIES = [
    "Hardware",
    "Software",
    "Network",
    "Email",
    "Account Access",
    "Other"
]

DEPARTMENTS = [
    "IT",
    "Human Resources",
    "Finance",
    "Sales",
    "Operations",
    "Other"
]



def get_db():

    # Check whether cloud database settings are available
    turso_url = os.environ.get("TURSO_DATABASE_URL", "").strip()
    turso_token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()

    # Use Turso when cloud credentials are configured
    if turso_url or turso_token:

        if not turso_url or not turso_token:
            raise RuntimeError(
                "Both TURSO_DATABASE_URL and "
                "TURSO_AUTH_TOKEN are required."
            )

        import libsql
        from turso_adapter import TursoConnection

        connection = libsql.connect(
            database=turso_url,
            auth_token=turso_token
        )

        return TursoConnection(connection)

    # Otherwise, use the local SQLite database
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row

    return db


# ==========================================
# 4. USER MODEL
# ==========================================

class User(UserMixin):

    def __init__(self, row):

        self.id = row["id"]
        self.name = row["name"]
        self.email = row["email"]
        self.role = row["role"]
        self._active = bool(row["is_active"])

    @property
    def is_active(self):
        return self._active


# ==========================================
# 5. LOAD LOGGED-IN USER
# ==========================================


@login_manager.user_loader
def load_user(user_id):

    if not str(user_id).isdigit():
        return None

    with closing(get_db()) as db:

        row = db.execute("""
            SELECT *
            FROM users
            WHERE id = ?
              AND is_active = 1
        """, (int(user_id),)).fetchone()

    if row is None:
        return None

    return User(row)



# ==========================================
# ROLE-BASED ACCESS CONTROL
# ==========================================

def role_required(*allowed_roles):

    def decorator(view_function):

        @wraps(view_function)
        @login_required
        def wrapped_function(*args, **kwargs):

            if current_user.role not in allowed_roles:
                abort(403)

            return view_function(*args, **kwargs)

        return wrapped_function

    return decorator



# ==========================================
# 6. DATABASE INITIALIZATION
# ==========================================

def initialize_database():

    with closing(get_db()) as db:

        with db:

            # CREATE TICKETS TABLE

            db.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee TEXT NOT NULL,
                    email TEXT NOT NULL,
                    department TEXT NOT NULL,
                    category TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    description TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Open',
                    assigned_to TEXT NOT NULL DEFAULT 'Unassigned',
                    resolution_notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # CHECK EXISTING TICKET COLUMNS

            columns = [
                row["name"]
                for row in db.execute(
                    "PRAGMA table_info(tickets)"
                ).fetchall()
            ]

            # ADD TECHNICIAN COLUMN TO OLD DATABASES

            if "assigned_to" not in columns:

                db.execute("""
                    ALTER TABLE tickets
                    ADD COLUMN assigned_to TEXT
                    NOT NULL DEFAULT 'Unassigned'
                """)

            # CREATE ACTIVITY HISTORY TABLE

            db.execute("""
                CREATE TABLE IF NOT EXISTS ticket_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (ticket_id)
                        REFERENCES tickets(id)
                )
            """)

            # CREATE USER ACCOUNTS TABLE

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
            # Link tickets to real user accounts

            columns = [
                row["name"]
                for row in db.execute(
                    "PRAGMA table_info(tickets)"
                ).fetchall()
            ]

            if "assigned_user_id" not in columns:
                db.execute("""
                    ALTER TABLE tickets
                    ADD COLUMN assigned_user_id
                    INTEGER REFERENCES users(id)
                """)

            if "created_by_user_id" not in columns:
                db.execute("""
                    ALTER TABLE tickets
                    ADD COLUMN created_by_user_id
                    INTEGER REFERENCES users(id)
                """)



# ==========================================
# 7. LOGIN
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    # Already logged-in users go to dashboard

    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get(
            "password", ""
        )

        # Look up the user

        with closing(get_db()) as db:

            row = db.execute("""
                SELECT *
                FROM users
                WHERE email = ?
            """, (email,)).fetchone()

        # Check account and password

        if (
            row is None
            or not bool(row["is_active"])
            or not check_password_hash(
                row["password_hash"],
                password
            )
        ):

            flash("Invalid email or password.")

        else:

            user = User(row)

            login_user(user)

            flash("Logged in successfully!")

            return redirect(url_for("home"))

    return render_template("login.html")


# ==========================================
# 8. LOGOUT
# ==========================================

@app.route("/logout", methods=["POST"])
@login_required
def logout():

    logout_user()

    flash("You have been logged out successfully.")

    return redirect(url_for("login"))


# ==========================================
# ADMIN USER MANAGEMENT
# ==========================================

@app.route("/admin/users", methods=["GET", "POST"])
@role_required("Admin")
def admin_users():

    if request.method == "POST":

        name = request.form.get(
            "name", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get(
            "password", ""
        )

        role = request.form.get(
            "role", ""
        )

        # Validate submitted information

        if (
            not name
            or len(name) > 100
            or len(email) > 150
            or not re.fullmatch(
                r"[^@\s]+@[^@\s]+\.[^@\s]+",
                email
            )
            or len(password) < 12
            or role not in ["Technician", "Employee"]
        ):

            flash(
                "Enter valid account information. "
                "Passwords must have at least 12 characters."
            )

            return redirect(url_for("admin_users"))

        # Securely hash the password

        password_hash = generate_password_hash(
            password
        )

        now = datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d %H:%M UTC")

        # Save the new account

        with closing(get_db()) as db:

            try:

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
                        role,
                        1,
                        now
                    ))

            except sqlite3.IntegrityError:

                flash(
                    "An account with this email already exists."
                )

                return redirect(url_for("admin_users"))

        flash("User account created successfully!")

        return redirect(url_for("admin_users"))

    # Display existing users

    with closing(get_db()) as db:

        users = db.execute("""
            SELECT
                id,
                name,
                email,
                role,
                is_active,
                created_at
            FROM users
            ORDER BY id DESC
        """).fetchall()

    return render_template(
        "admin_users.html",
        users=users
    )

# ==========================================
# ACTIVATE / DEACTIVATE USER ACCOUNTS
# ==========================================

@app.route(
    "/admin/users/<int:user_id>/toggle-active",
    methods=["POST"]
)
@role_required("Admin")
def toggle_user_active(user_id):

    # Prevent Admin from changing their own account
    if user_id == int(current_user.id):
        flash("You cannot deactivate your own account.")
        return redirect(url_for("admin_users"))

    with closing(get_db()) as db:

        with db:

            user = db.execute("""
                SELECT id, name, role, is_active
                FROM users
                WHERE id = ?
            """, (user_id,)).fetchone()

            if user is None:
                abort(404)

            # Protect all Admin accounts
            if user["role"] == "Admin":
                abort(403)

            if user["role"] not in ("Technician", "Employee"):
                abort(403)

            # Switch account status
            new_status = 0 if user["is_active"] else 1

            db.execute("""
                UPDATE users
                SET is_active = ?
                WHERE id = ?
                  AND role IN ('Technician', 'Employee')
            """, (
                new_status,
                user_id
            ))

    if new_status == 1:
        flash("User account activated successfully!")
    else:
        flash("User account deactivated successfully!")

    return redirect(url_for("admin_users"))


# ==========================================
# DASHBOARD - ROLE BASED TICKET ACCESS
# ==========================================

@app.route("/")
@login_required
def home():

    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "")

    if status_filter not in STATUSES:
        status_filter = ""

    # Restrict which tickets the user can see

    scope = " WHERE 1=1"
    scope_parameters = []

    if current_user.role == "Technician":

        scope += " AND assigned_user_id = ?"
        scope_parameters.append(int(current_user.id))

    elif current_user.role == "Employee":

        scope += " AND created_by_user_id = ?"
        scope_parameters.append(int(current_user.id))

    elif current_user.role != "Admin":
        abort(403)

    with closing(get_db()) as db:

        query = "SELECT * FROM tickets" + scope
        parameters = list(scope_parameters)

        # Search within permitted tickets

        if search:

            query += """
                AND (
                    subject LIKE ?
                    OR employee LIKE ?
                    OR email LIKE ?
                    OR category LIKE ?
                )
            """

            term = f"%{search}%"
            parameters.extend([term] * 4)

        if status_filter:

            query += " AND status = ?"
            parameters.append(status_filter)

        query += " ORDER BY id DESC"

        tickets = db.execute(
            query, parameters
        ).fetchall()

        # Count only tickets accessible to this user

        stats = db.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM tickets
            """
            + scope +
            " GROUP BY status",
            scope_parameters
        ).fetchall()

    counts = {
        row["status"]: row["count"]
        for row in stats
    }

    return render_template(
        "dashboard.html",
        tickets=tickets,
        total=sum(counts.values()),
        open_count=counts.get("Open", 0),
        progress_count=counts.get("In Progress", 0),
        resolved_count=(
            counts.get("Resolved", 0)
            + counts.get("Closed", 0)
        ),
        statuses=STATUSES,
        search=search,
        status_filter=status_filter
    )



# ==========================================
# 10. CREATE SUPPORT TICKET
# ==========================================

@app.route("/create", methods=["GET", "POST"])
@login_required
def create_ticket():

    if request.method == "POST":

        employee = request.form.get(
            "employee", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip()

        department = request.form.get(
            "department", ""
        )

        category = request.form.get(
            "category", ""
        )

        subject = request.form.get(
            "subject", ""
        ).strip()

        description = request.form.get(
            "description", ""
        ).strip()

        priority = request.form.get(
            "priority", ""
        )
        # Employees must submit tickets under their own account
        if current_user.role == "Employee":
            employee = current_user.name
            email = current_user.email
        # VALIDATE EMAIL

        valid_email = re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+",
            email
        )

        # CHECK REQUIRED FIELDS

        if not all([
            employee,
            email,
            department,
            category,
            subject,
            description,
            priority
        ]):

            flash("Please complete all fields.")

            return redirect(
                url_for("create_ticket")
            )

        # VALIDATE TICKET INFORMATION

        if (
            len(employee) > 100
            or len(email) > 150
            or len(subject) > 150
            or len(description) > 3000
            or not valid_email
            or department not in DEPARTMENTS
            or category not in CATEGORIES
            or priority not in PRIORITIES
        ):

            flash("Please enter valid ticket information.")

            return redirect(
                url_for("create_ticket")
            )

        # CREATION TIMESTAMP

        now = datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d %H:%M UTC")

        # SAVE TICKET AND ACTIVITY

        with closing(get_db()) as db:

            with db:

                cursor = db.execute("""
                    INSERT INTO tickets (
                        employee,
                        email,
                        department,
                        category,
                        subject,
                        description,
                        priority,
                        status,
                        assigned_to,
                        resolution_notes,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    employee,
                    email,
                    department,
                    category,
                    subject,
                    description,
                    priority,
                    "Open",
                    "Unassigned",
                    "",
                    now,
                    now
                ))

                # GET THE NEW TICKET ID

                ticket_id = cursor.lastrowid

                # Save the account that created this ticket

                db.execute("""
                    UPDATE tickets
                    SET created_by_user_id = ?
                    WHERE id = ?
                """, (
                    int(current_user.id),
                    ticket_id
                ))


                # RECORD TICKET CREATION

                db.execute("""
                    INSERT INTO ticket_activity (
                        ticket_id,
                        action,
                        created_at
                    )
                    VALUES (?, ?, ?)
                """, (
                    ticket_id,
                    "Ticket created",
                    now
                ))

        flash("Support ticket created successfully!")

        return redirect(url_for("home"))

    return render_template(
        "create_ticket.html",
        departments=DEPARTMENTS,
        categories=CATEGORIES,
        priorities=PRIORITIES
    )


#
# ==========================================
# TICKET DETAILS - ROLE BASED ACCESS
# ==========================================

@app.route(
    "/ticket/<int:ticket_id>",
    methods=["GET", "POST"]
)
@login_required
def ticket_detail(ticket_id):

    with closing(get_db()) as db:

        ticket = db.execute(
            "SELECT * FROM tickets WHERE id = ?",
            (ticket_id,)
        ).fetchone()

        if ticket is None:
            abort(404)

        # Check permission before displaying ticket details

        if current_user.role == "Admin":
            pass

        elif current_user.role == "Technician":

            if ticket["assigned_user_id"] != int(current_user.id):
                abort(404)

        elif current_user.role == "Employee":

            if ticket["created_by_user_id"] != int(current_user.id):
                abort(404)

        else:
            abort(403)

        # Admins can choose registered technicians

        technicians = []

        if current_user.role == "Admin":

            technicians = db.execute("""
                SELECT id, name
                FROM users
                WHERE role = 'Technician'
                  AND is_active = 1
                ORDER BY name
            """).fetchall()

        if request.method == "POST":

            # Employees cannot change ticket details

            if current_user.role not in ("Admin", "Technician"):
                abort(403)

            status = request.form.get("status", "")
            notes = request.form.get(
                "resolution_notes", ""
            ).strip()

            if status not in STATUSES or len(notes) > 3000:
                flash("Invalid ticket update.")
                return redirect(
                    url_for("ticket_detail", ticket_id=ticket_id)
                )

            if status in ("Resolved", "Closed") and not notes:
                flash("Resolution notes are required.")
                return redirect(
                    url_for("ticket_detail", ticket_id=ticket_id)
                )

            # Preserve current technician assignment
            assigned_user_id = ticket["assigned_user_id"]
            assigned_name = ticket["assigned_to"]

            # Only Admin can change the assigned technician
            if current_user.role == "Admin":

                selected_id = request.form.get(
                    "assigned_user_id", ""
                ).strip()

                if selected_id:

                    if not selected_id.isdigit():
                        abort(400)

                    technician = db.execute("""
                        SELECT id, name
                        FROM users
                        WHERE id = ?
                          AND role = 'Technician'
                          AND is_active = 1
                    """, (int(selected_id),)).fetchone()

                    if technician is None:
                        abort(400)

                    assigned_user_id = technician["id"]
                    assigned_name = technician["name"]

                else:
                    assigned_user_id = None
                    assigned_name = "Unassigned"

            # Record changes

            changes = []

            if status != ticket["status"]:
                changes.append(
                    f"Status changed: {ticket['status']} → {status}"
                )

            if assigned_user_id != ticket["assigned_user_id"]:
                changes.append(
                    f"Technician changed: "
                    f"{ticket['assigned_to']} → {assigned_name}"
                )

            if notes != ticket["resolution_notes"]:
                changes.append("Resolution notes updated")

            now = datetime.now(timezone.utc).strftime(
                "%Y-%m-%d %H:%M UTC"
            )

            # Save ticket and activity history together

            with db:

                db.execute("""
                    UPDATE tickets
                    SET status = ?,
                        assigned_user_id = ?,
                        assigned_to = ?,
                        resolution_notes = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    status,
                    assigned_user_id,
                    assigned_name,
                    notes,
                    now,
                    ticket_id
                ))

                for change in changes:

                    db.execute("""
                        INSERT INTO ticket_activity (
                            ticket_id,
                            action,
                            created_at
                        )
                        VALUES (?, ?, ?)
                    """, (
                        ticket_id,
                        change,
                        now
                    ))

            flash("Ticket updated successfully!")

            return redirect(
                url_for("ticket_detail", ticket_id=ticket_id)
            )

        activity = db.execute("""
            SELECT id, action, created_at
            FROM ticket_activity
            WHERE ticket_id = ?
            ORDER BY id DESC
        """, (ticket_id,)).fetchall()

    return render_template(
        "ticket_detail.html",
        ticket=ticket,
        statuses=STATUSES,
        technicians=technicians,
        activity=activity
    )

# ==========================================
# 12. KNOWLEDGE BASE
# ==========================================

@app.route("/knowledge-base")
@login_required
def knowledge_base():

    articles = [

        {
            "title": "Wi-Fi Troubleshooting",
            "category": "Networking",
            "steps": [
                "Check that Wi-Fi is enabled.",
                "Verify the correct network is selected.",
                "Run ipconfig in Command Prompt.",
                "Check the computer's IP configuration.",
                "Test network connectivity.",
                "Investigate DNS issues if necessary."
            ]
        },

        {
            "title": "Outlook Email Problems",
            "category": "Microsoft 365",
            "steps": [
                "Check the internet connection.",
                "Verify Outlook is not in offline mode.",
                "Restart Outlook.",
                "Check email account configuration.",
                "Check Microsoft 365 service health.",
                "Escalate unresolved problems."
            ]
        },

        {
            "title": "Printer Troubleshooting",
            "category": "Hardware",
            "steps": [
                "Check printer power and connections.",
                "Check paper and toner levels.",
                "Confirm the correct printer is selected.",
                "Inspect the print queue.",
                "Check printer network connectivity.",
                "Print a test page."
            ]
        },

        {
            "title": "Slow Windows Computer",
            "category": "Windows",
            "steps": [
                "Open Windows Task Manager.",
                "Check CPU and memory usage.",
                "Check available disk space.",
                "Review startup applications.",
                "Check Windows updates.",
                "Review security alerts."
            ]
        },

        {
            "title": "Windows Login Problems",
            "category": "Account Access",
            "steps": [
                "Confirm the correct username.",
                "Check Caps Lock and keyboard layout.",
                "Check network connectivity.",
                "Verify account status with an administrator.",
                "Follow approved password reset procedures."
            ]
        }

    ]

    return render_template(
        "knowledge_base.html",
        articles=articles
    )


# ==========================================
# ADMIN REPORTS AND ANALYTICS
# ==========================================

@app.route("/admin/reports")
@role_required("Admin")
def admin_reports():

    with closing(get_db()) as db:

        # Overall ticket statistics
        stats = db.execute("""
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(
                    CASE WHEN status = 'Open'
                    THEN 1 ELSE 0 END
                ), 0) AS open_count,
                COALESCE(SUM(
                    CASE WHEN status = 'In Progress'
                    THEN 1 ELSE 0 END
                ), 0) AS progress_count,
                COALESCE(SUM(
                    CASE WHEN status = 'Resolved'
                    THEN 1 ELSE 0 END
                ), 0) AS resolved_count,
                COALESCE(SUM(
                    CASE WHEN status = 'Closed'
                    THEN 1 ELSE 0 END
                ), 0) AS closed_count
            FROM tickets
        """).fetchone()

        # Tickets grouped by status
        status_report = db.execute("""
            SELECT status, COUNT(*) AS ticket_count
            FROM tickets
            GROUP BY status
            ORDER BY ticket_count DESC
        """).fetchall()

        # Tickets grouped by priority
        priority_report = db.execute("""
            SELECT priority, COUNT(*) AS ticket_count
            FROM tickets
            GROUP BY priority
            ORDER BY
                CASE priority
                    WHEN 'Critical' THEN 1
                    WHEN 'High' THEN 2
                    WHEN 'Medium' THEN 3
                    WHEN 'Low' THEN 4
                    ELSE 5
                END
        """).fetchall()

        # Tickets grouped by category
        category_report = db.execute("""
            SELECT category, COUNT(*) AS ticket_count
            FROM tickets
            GROUP BY category
            ORDER BY ticket_count DESC
        """).fetchall()

        # Ticket workload by assigned technician
        technician_report = db.execute("""
            SELECT
                CASE
                    WHEN u.id IS NOT NULL
                        THEN u.name
                    WHEN t.assigned_to = 'Unassigned'
                        THEN 'Unassigned'
                    ELSE 'Legacy: ' || t.assigned_to
                END AS technician,
                COUNT(*) AS ticket_count
            FROM tickets AS t
            LEFT JOIN users AS u
                ON t.assigned_user_id = u.id
            GROUP BY technician
            ORDER BY ticket_count DESC
        """).fetchall()

    return render_template(
        "reports.html",
        stats=stats,
        status_report=status_report,
        priority_report=priority_report,
        category_report=category_report,
        technician_report=technician_report
    )

# ==========================================
# 13. START APPLICATION
# ==========================================

if __name__ == "__main__":

    initialize_database()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
