"""SQLite persistence for the Streamlit app; schema lives in migrations/.

Each operation owns and closes its connection. Multi-step writes take a reserved
write lock before reading, so independent Streamlit sessions cannot overbook.
"""

from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
import hashlib
import hmac
import os
import re
import sqlite3

from db_schema import initialize_database

ROOT = Path(__file__).resolve().parent
_configured_path = Path(os.environ.get("COLLEGE_DB_PATH") or "college_management.db").expanduser()
DB_NAME = str(_configured_path if _configured_path.is_absolute() else ROOT / _configured_path)
PASSWORD_ITERATIONS = 600_000
USER_COLUMNS = "id, name, email, role, course, year, created_at"


def get_connection():
    """Return a connection owned by the caller (which must close it)."""
    conn = sqlite3.connect(DB_NAME, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


@contextmanager
def _session(write=False):
    conn = get_connection()
    try:
        with conn:
            if write:
                conn.execute("BEGIN IMMEDIATE")
            yield conn
    finally:
        conn.close()


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _all(query, params=()):
    with _session() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def _one(query, params=()):
    with _session() as conn:
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None


def _execute(query, params=()):
    try:
        with _session(write=True) as conn:
            return conn.execute(query, params).lastrowid
    except sqlite3.IntegrityError as exc:
        if "capacity" in str(exc).lower():
            raise ValueError("Capacity cannot be lower than the number of registrations.") from exc
        raise ValueError("Invalid data or a related record no longer exists. Refresh and try again.") from exc


def _required(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} cannot be empty.")
    return value.strip()


def hash_password(password: str, salt: str = None) -> str:
    """Versioned PBKDF2 hash with a random 128-bit salt."""
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 bytes.fromhex(salt), PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Accept both versioned hashes and the original 100k-iteration format."""
    try:
        parts = stored_hash.split("$")
        if len(parts) == 2:
            salt, expected = parts
            iterations = 100_000
        elif len(parts) == 4 and parts[0] == "pbkdf2_sha256":
            _, iteration_text, salt, expected = parts
            iterations = int(iteration_text)
            if not 100_000 <= iterations <= 2_000_000:
                return False
        else:
            return False
        if len(salt) != 32 or len(expected) != 64:
            return False
        expected_bytes = bytes.fromhex(expected)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                     bytes.fromhex(salt), iterations)
        return hmac.compare_digest(actual, expected_bytes)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return False


def init_db():
    """Create or migrate the schema without inventing accounts or demo content."""
    initialize_database(DB_NAME)


def has_admin():
    return _one("SELECT id FROM users WHERE role='admin' LIMIT 1") is not None


def seed_demo_data():
    """Explicit, transactional, one-time sample content; never creates accounts."""
    with _session(write=True) as conn:
        if conn.execute("SELECT 1 FROM app_metadata WHERE key='demo_seeded'").fetchone():
            return False
        for table in ("clubs", "events", "announcements"):
            if conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
                raise ValueError("Sample content can only be added to an empty database.")
        now = _now()
        clubs = [
            ("Coding Club", "Programming, hackathons and open source.", "Technology", "Dr. Ananya Rao", "Monday", "5:00 PM"),
            ("Robotics Club", "Design, build and program robots.", "Technology", "Prof. Vikram Shah", "Wednesday", "4:30 PM"),
            ("AI & ML Club", "Artificial intelligence projects and talks.", "Technology", "Dr. Priya Menon", "Tuesday", "6:00 PM"),
            ("Cultural Club", "Music, dance, drama and the arts.", "Arts & Culture", "Prof. Kavita Iyer", "Thursday", "5:30 PM"),
            ("Sports Club", "Tournaments and fitness activities.", "Sports", "Coach Rakesh Verma", "Friday", "6:30 PM"),
        ]
        club_ids = []
        for club in clubs:
            cursor = conn.execute("""
                INSERT INTO clubs (name, description, category, faculty_coordinator, meeting_day, meeting_time, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (*club, now))
            club_ids.append(cursor.lastrowid)
        events = [
            ("Campus Hackathon", "24-hour coding marathon.", club_ids[0], 10, "09:00 AM", "Main Auditorium", 60),
            ("Intro to Python Workshop", "Hands-on workshop for beginners.", club_ids[0], 4, "03:00 PM", "Lab 204", 40),
            ("RoboWars", "Robot battle competition.", club_ids[1], 15, "11:00 AM", "Sports Complex", 50),
            ("AI Talk: Future of LLMs", "Guest lecture on language models.", club_ids[2], 7, "05:00 PM", "Seminar Hall 1", 100),
            ("Cultural Night", "Music, dance and drama performances.", club_ids[3], 20, "06:00 PM", "Open Air Theatre", 200),
            ("Inter-College Football Match", "Friendly football match.", club_ids[4], 12, "04:00 PM", "College Ground", 300),
        ]
        for title, description, club_id, days, event_time, venue, capacity in events:
            conn.execute("""
                INSERT INTO events (title, description, club_id, date, time, venue, capacity, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (title, description, club_id, (date.today() + timedelta(days=days)).isoformat(),
                  event_time, venue, capacity, now))
        announcements = [
            ("Welcome to the New Semester!", "Check the Events page for club activities."),
            ("Club Registrations Now Open", "Visit Clubs to request membership."),
            ("Annual Fest Dates Announced", "Our annual fest will be held next month. Watch for the schedule."),
        ]
        conn.executemany("INSERT INTO announcements (title, content, created_at) VALUES (?, ?, ?)",
                         [(title, content, now) for title, content in announcements])
        conn.execute("INSERT INTO app_metadata (key, value) VALUES ('demo_seeded', ?)", (now,))
        return True


def create_user(name, email, password, role="student", course="", year=""):
    try:
        name = _required(name, "Name")
        email = _required(email, "Email").lower()
        if not re.fullmatch(r"[a-z0-9_.+\-]+@[a-z0-9\-]+(?:\.[a-z0-9\-]+)+", email):
            return False, "Please enter a valid email address."
        if role not in ("student", "admin"):
            return False, "Invalid account role."
        if not isinstance(password, str) or len(password) < 8:
            return False, "Password must be at least 8 characters long."
        password_hash = hash_password(password)
        with _session(write=True) as conn:
            conn.execute("""
                INSERT INTO users (name, email, password, role, course, year, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, email, password_hash, role, course, year, _now()))
    except ValueError as exc:
        return False, str(exc)
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists."
    return True, "Account created successfully."


def authenticate_user(email, password):
    row = _one("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email.strip().lower(),))
    if row is None or not verify_password(password, row["password"]):
        return None
    stored_hash = row.pop("password")
    if not stored_hash.startswith(f"pbkdf2_sha256${PASSWORD_ITERATIONS}$"):
        # Compare the old hash as well: a simultaneous password change must win.
        _execute("UPDATE users SET password=? WHERE id=? AND password=?",
                 (hash_password(password), row["id"], stored_hash))
    return row


def get_user(user_id):
    return _one(f"SELECT {USER_COLUMNS} FROM users WHERE id=?", (user_id,))


def get_all_users(role=None, search=None):
    query = f"SELECT {USER_COLUMNS} FROM users WHERE 1=1"
    params = []
    if role:
        query += " AND role=?"
        params.append(role)
    if search:
        query += " AND (name LIKE ? OR email LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    return _all(query + " ORDER BY created_at DESC, id DESC", params)


def create_club(name, description, category, faculty_coordinator, meeting_day, meeting_time):
    return _execute("""
        INSERT INTO clubs (name, description, category, faculty_coordinator, meeting_day, meeting_time, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (_required(name, "Club name"), description, category, faculty_coordinator, meeting_day, meeting_time, _now()))


def get_clubs():
    return _all("SELECT * FROM clubs ORDER BY name ASC, id ASC")


def get_club(club_id):
    return _one("SELECT * FROM clubs WHERE id=?", (club_id,))


def update_club(club_id, name, description, category, faculty_coordinator, meeting_day, meeting_time):
    _execute("""UPDATE clubs SET name=?, description=?, category=?, faculty_coordinator=?, meeting_day=?, meeting_time=?
                WHERE id=?""",
             (_required(name, "Club name"), description, category, faculty_coordinator, meeting_day, meeting_time, club_id))


def delete_club(club_id):
    _execute("DELETE FROM clubs WHERE id=?", (club_id,))


def join_club(user_id, club_id):
    with _session(write=True) as conn:
        existing = conn.execute("SELECT status FROM club_members WHERE user_id=? AND club_id=?", (user_id, club_id)).fetchone()
        if existing:
            messages = {"Approved": "You are already a member.",
                        "Pending": "Your membership request is already pending approval.",
                        "Rejected": "Your previous request for this club was rejected."}
            return False, messages[existing["status"]]
        if not conn.execute("SELECT id FROM users WHERE id=? AND role='student'", (user_id,)).fetchone():
            return False, "Student account not found."
        if not conn.execute("SELECT id FROM clubs WHERE id=?", (club_id,)).fetchone():
            return False, "Club not found."
        conn.execute("INSERT INTO club_members (user_id, club_id, status, joined_at) VALUES (?, ?, 'Pending', ?)",
                     (user_id, club_id, _now()))
    return True, "Membership request submitted! Awaiting admin approval."


def get_user_memberships(user_id):
    return _all("""
        SELECT cm.*, c.name AS club_name, c.category, c.faculty_coordinator
        FROM club_members cm JOIN clubs c ON cm.club_id=c.id
        WHERE cm.user_id=? ORDER BY cm.joined_at DESC, cm.id DESC
    """, (user_id,))


def get_all_memberships():
    return _all("""
        SELECT cm.*, u.name AS student_name, u.email, u.course, u.year, c.name AS club_name
        FROM club_members cm JOIN users u ON cm.user_id=u.id JOIN clubs c ON cm.club_id=c.id
        ORDER BY cm.joined_at DESC, cm.id DESC
    """)


def update_membership_status(membership_id, status):
    if status not in ("Pending", "Approved", "Rejected"):
        raise ValueError("Invalid membership status.")
    _execute("UPDATE club_members SET status=? WHERE id=?", (status, membership_id))


def get_club_member_count(club_id):
    return _one("SELECT COUNT(*) AS cnt FROM club_members WHERE club_id=? AND status='Approved'", (club_id,))["cnt"]


def _validate_event(title, event_date, capacity):
    title = _required(title, "Event title")
    try:
        if date.fromisoformat(event_date).isoformat() != event_date:
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError("Event date must be a valid date in YYYY-MM-DD format.") from None
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 0:
        raise ValueError("Capacity must be a nonnegative whole number (zero closes registration).")
    return title


def create_event(title, description, club_id, event_date, event_time, venue, capacity):
    title = _validate_event(title, event_date, capacity)
    return _execute("""
        INSERT INTO events (title, description, club_id, date, time, venue, capacity, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (title, description, club_id, event_date, event_time, venue, capacity, _now()))


def get_events(upcoming_only=False):
    query = "SELECT e.*, c.name AS club_name FROM events e JOIN clubs c ON e.club_id=c.id"
    return _all(query + (" WHERE e.date>=?" if upcoming_only else "") + " ORDER BY e.date ASC, e.id ASC",
                (date.today().isoformat(),) if upcoming_only else ())


def get_event(event_id):
    return _one("SELECT e.*, c.name AS club_name FROM events e JOIN clubs c ON e.club_id=c.id WHERE e.id=?", (event_id,))


def update_event(event_id, title, description, club_id, event_date, event_time, venue, capacity):
    title = _validate_event(title, event_date, capacity)
    _execute("""UPDATE events SET title=?, description=?, club_id=?, date=?, time=?, venue=?, capacity=? WHERE id=?""",
             (title, description, club_id, event_date, event_time, venue, capacity, event_id))


def delete_event(event_id):
    _execute("DELETE FROM events WHERE id=?", (event_id,))


def get_event_registration_count(event_id):
    return _one("SELECT COUNT(*) AS cnt FROM event_registrations WHERE event_id=?", (event_id,))["cnt"]


def register_event(user_id, event_id):
    with _session(write=True) as conn:
        if conn.execute("SELECT id FROM event_registrations WHERE user_id=? AND event_id=?", (user_id, event_id)).fetchone():
            return False, "You are already registered for this event."
        event = conn.execute("SELECT capacity, date FROM events WHERE id=?", (event_id,)).fetchone()
        if event is None:
            return False, "Event not found."
        if event["date"] < date.today().isoformat():
            return False, "Registration is closed for past events."
        if not conn.execute("SELECT id FROM users WHERE id=? AND role='student'", (user_id,)).fetchone():
            return False, "Student account not found."
        current = conn.execute("SELECT COUNT(*) FROM event_registrations WHERE event_id=?", (event_id,)).fetchone()[0]
        if current >= event["capacity"]:
            return False, "Sorry, this event is already full."
        conn.execute("INSERT INTO event_registrations (event_id, user_id, registered_at) VALUES (?, ?, ?)",
                     (event_id, user_id, _now()))
    return True, "Successfully registered for the event!"


def cancel_event_registration(user_id, event_id):
    _execute("DELETE FROM event_registrations WHERE user_id=? AND event_id=?", (user_id, event_id))
    return True, "Registration cancelled."


def get_user_registrations(user_id):
    return _all("""
        SELECT er.*, e.title, e.date, e.time, e.venue, c.name AS club_name
        FROM event_registrations er JOIN events e ON er.event_id=e.id JOIN clubs c ON e.club_id=c.id
        WHERE er.user_id=? ORDER BY e.date ASC, er.id ASC
    """, (user_id,))


def get_all_registrations():
    return _all("""
        SELECT er.*, u.name AS student_name, u.email, e.title AS event_title, e.date AS event_date, c.name AS club_name
        FROM event_registrations er JOIN users u ON er.user_id=u.id
        JOIN events e ON er.event_id=e.id JOIN clubs c ON e.club_id=c.id
        ORDER BY er.registered_at DESC, er.id DESC
    """)


def create_announcement(title, content):
    return _execute("INSERT INTO announcements (title, content, created_at) VALUES (?, ?, ?)",
                    (_required(title, "Announcement title"), content, _now()))


def get_announcements():
    return _all("SELECT * FROM announcements ORDER BY created_at DESC, id DESC")


def delete_announcement(announcement_id):
    _execute("DELETE FROM announcements WHERE id=?", (announcement_id,))


def get_stats():
    # One statement gives all dashboard counters the same read snapshot.
    return _one("""
        SELECT (SELECT COUNT(*) FROM users WHERE role='student') AS total_students,
               (SELECT COUNT(*) FROM clubs) AS total_clubs,
               (SELECT COUNT(*) FROM events) AS total_events,
               (SELECT COUNT(*) FROM event_registrations) AS total_registrations
    """)
