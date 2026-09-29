"""
database.py
------------
All SQLite database logic for the College Club & Event Management System.
Every query uses parameterized statements (no string concatenation of user input).
"""

import sqlite3
import hashlib
import hmac
import os
from datetime import datetime, date

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "college_management.db")


# ----------------------------------------------------------------------
# Connection helper
# ----------------------------------------------------------------------
def get_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ----------------------------------------------------------------------
# Password hashing (PBKDF2-HMAC-SHA256, stdlib only — no compiled deps,
# so the project installs cleanly on any machine, including Windows).
# ----------------------------------------------------------------------
def hash_password(password: str, salt: str = None) -> str:
    if salt is None:
        salt = os.urandom(16).hex()
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100_000)
    return f"{salt}${pwd_hash.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, _ = stored_hash.split("$")
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(password, salt), stored_hash)


# ----------------------------------------------------------------------
# Schema initialization
# ----------------------------------------------------------------------
def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
            course TEXT,
            year TEXT,
            created_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS clubs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            faculty_coordinator TEXT,
            meeting_day TEXT,
            meeting_time TEXT,
            created_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS club_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            club_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            joined_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            club_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time TEXT,
            venue TEXT,
            capacity INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS event_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            registered_at TEXT NOT NULL,
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()

    # Create default admin if it doesn't exist
    c.execute("SELECT id FROM users WHERE email = ?", ("admin@college.com",))
    if c.fetchone() is None:
        c.execute(
            "INSERT INTO users (name, email, password, role, course, year, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("System Admin", "admin@college.com", hash_password("admin123"), "admin", "-", "-",
             datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()

    # Seed sample data only on first run (no clubs yet)
    c.execute("SELECT COUNT(*) AS cnt FROM clubs")
    if c.fetchone()["cnt"] == 0:
        _seed_sample_data(conn)

    conn.close()


def _seed_sample_data(conn):
    c = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")

    clubs = [
        ("Coding Club", "A community for students who love programming, hackathons and open source.",
         "Technology", "Dr. Ananya Rao", "Monday", "5:00 PM"),
        ("Robotics Club", "Design, build and program robots for competitions and fun projects.",
         "Technology", "Prof. Vikram Shah", "Wednesday", "4:30 PM"),
        ("AI & ML Club", "Explore artificial intelligence and machine learning through projects and talks.",
         "Technology", "Dr. Priya Menon", "Tuesday", "6:00 PM"),
        ("Cultural Club", "Celebrating music, dance, drama and the arts across campus.",
         "Arts & Culture", "Prof. Kavita Iyer", "Thursday", "5:30 PM"),
        ("Sports Club", "Organizing tournaments and fitness activities for all students.",
         "Sports", "Coach Rakesh Verma", "Friday", "6:30 PM"),
    ]
    club_ids = []
    for club in clubs:
        c.execute("""
            INSERT INTO clubs (name, description, category, faculty_coordinator, meeting_day, meeting_time, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (*club, now))
        club_ids.append(c.lastrowid)

    def future_date(days):
        from datetime import timedelta
        return (date.today() + timedelta(days=days)).isoformat()

    events = [
        ("Hackathon 2026", "24-hour coding marathon with prizes for the best projects.", club_ids[0],
         future_date(10), "09:00 AM", "Main Auditorium", 60),
        ("Intro to Python Workshop", "Hands-on workshop for beginners in Python programming.", club_ids[0],
         future_date(4), "03:00 PM", "Lab 204", 40),
        ("RoboWars", "Robot battle competition open to all engineering students.", club_ids[1],
         future_date(15), "11:00 AM", "Sports Complex", 50),
        ("AI Talk: Future of LLMs", "Guest lecture on the future of large language models.", club_ids[2],
         future_date(7), "05:00 PM", "Seminar Hall 1", 100),
        ("Cultural Night", "An evening of music, dance and drama performances.", club_ids[3],
         future_date(20), "06:00 PM", "Open Air Theatre", 200),
        ("Inter-College Football Match", "Friendly football match against a neighboring college.", club_ids[4],
         future_date(12), "04:00 PM", "College Ground", 300),
    ]
    for ev in events:
        c.execute("""
            INSERT INTO events (title, description, club_id, date, time, venue, capacity, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (*ev, now))

    announcements = [
        ("Welcome to the New Semester!", "We're excited to kick off a new semester full of club activities and events. Check the Events page regularly!"),
        ("Club Registrations Now Open", "All clubs are now accepting new members. Head to the Clubs page to join one that interests you."),
        ("Annual Fest Dates Announced", "Our annual college fest will be held next month. Stay tuned for the detailed schedule."),
    ]
    for title, content in announcements:
        c.execute("INSERT INTO announcements (title, content, created_at) VALUES (?, ?, ?)", (title, content, now))

    conn.commit()


# ----------------------------------------------------------------------
# USERS
# ----------------------------------------------------------------------
def create_user(name, email, password, role="student", course="", year=""):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE email = ?", (email,))
    if c.fetchone():
        conn.close()
        return False, "An account with this email already exists."
    c.execute("""
        INSERT INTO users (name, email, password, role, course, year, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, email, hash_password(password), role, course, year, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    return True, "Account created successfully."


def authenticate_user(email, password):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()
    if row is None:
        return None
    if verify_password(password, row["password"]):
        return dict(row)
    return None


def get_user(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_users(role=None, search=None):
    conn = get_connection()
    c = conn.cursor()
    query = "SELECT * FROM users WHERE 1=1"
    params = []
    if role:
        query += " AND role = ?"
        params.append(role)
    if search:
        query += " AND (name LIKE ? OR email LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    query += " ORDER BY created_at DESC"
    c.execute(query, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


# ----------------------------------------------------------------------
# CLUBS
# ----------------------------------------------------------------------
def create_club(name, description, category, faculty_coordinator, meeting_day, meeting_time):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO clubs (name, description, category, faculty_coordinator, meeting_day, meeting_time, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, description, category, faculty_coordinator, meeting_day, meeting_time,
          datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()


def get_clubs():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM clubs ORDER BY name ASC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_club(club_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM clubs WHERE id = ?", (club_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_club(club_id, name, description, category, faculty_coordinator, meeting_day, meeting_time):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE clubs SET name=?, description=?, category=?, faculty_coordinator=?, meeting_day=?, meeting_time=?
        WHERE id=?
    """, (name, description, category, faculty_coordinator, meeting_day, meeting_time, club_id))
    conn.commit()
    conn.close()


def delete_club(club_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM clubs WHERE id = ?", (club_id,))
    conn.commit()
    conn.close()


# ----------------------------------------------------------------------
# CLUB MEMBERSHIPS
# ----------------------------------------------------------------------
def join_club(user_id, club_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM club_members WHERE user_id=? AND club_id=?", (user_id, club_id))
    existing = c.fetchone()
    if existing:
        conn.close()
        if existing["status"] == "Approved":
            return False, "You are already a member."
        elif existing["status"] == "Pending":
            return False, "Your membership request is already pending approval."
        else:
            return False, "Your previous request for this club was rejected."
    c.execute("""
        INSERT INTO club_members (user_id, club_id, status, joined_at) VALUES (?, ?, 'Pending', ?)
    """, (user_id, club_id, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    return True, "Membership request submitted! Awaiting admin approval."


def get_user_memberships(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT cm.*, c.name AS club_name, c.category, c.faculty_coordinator
        FROM club_members cm
        JOIN clubs c ON cm.club_id = c.id
        WHERE cm.user_id = ?
        ORDER BY cm.joined_at DESC
    """, (user_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_all_memberships():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT cm.*, u.name AS student_name, u.email, u.course, u.year, c.name AS club_name
        FROM club_members cm
        JOIN users u ON cm.user_id = u.id
        JOIN clubs c ON cm.club_id = c.id
        ORDER BY cm.joined_at DESC
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def update_membership_status(membership_id, status):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE club_members SET status=? WHERE id=?", (status, membership_id))
    conn.commit()
    conn.close()


def get_club_member_count(club_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) AS cnt FROM club_members WHERE club_id=? AND status='Approved'", (club_id,))
    cnt = c.fetchone()["cnt"]
    conn.close()
    return cnt


# ----------------------------------------------------------------------
# EVENTS
# ----------------------------------------------------------------------
def create_event(title, description, club_id, event_date, event_time, venue, capacity):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO events (title, description, club_id, date, time, venue, capacity, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (title, description, club_id, event_date, event_time, venue, capacity,
          datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()


def get_events(upcoming_only=False):
    conn = get_connection()
    c = conn.cursor()
    query = """
        SELECT e.*, c.name AS club_name
        FROM events e
        JOIN clubs c ON e.club_id = c.id
    """
    if upcoming_only:
        query += " WHERE e.date >= ?"
        c.execute(query + " ORDER BY e.date ASC", (date.today().isoformat(),))
    else:
        c.execute(query + " ORDER BY e.date ASC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_event(event_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT e.*, c.name AS club_name FROM events e JOIN clubs c ON e.club_id = c.id WHERE e.id = ?
    """, (event_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_event(event_id, title, description, club_id, event_date, event_time, venue, capacity):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE events SET title=?, description=?, club_id=?, date=?, time=?, venue=?, capacity=?
        WHERE id=?
    """, (title, description, club_id, event_date, event_time, venue, capacity, event_id))
    conn.commit()
    conn.close()


def delete_event(event_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()


def get_event_registration_count(event_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) AS cnt FROM event_registrations WHERE event_id=?", (event_id,))
    cnt = c.fetchone()["cnt"]
    conn.close()
    return cnt


# ----------------------------------------------------------------------
# EVENT REGISTRATIONS
# ----------------------------------------------------------------------
def register_event(user_id, event_id):
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT * FROM event_registrations WHERE user_id=? AND event_id=?", (user_id, event_id))
    if c.fetchone():
        conn.close()
        return False, "You are already registered for this event."

    c.execute("SELECT capacity FROM events WHERE id=?", (event_id,))
    event_row = c.fetchone()
    if event_row is None:
        conn.close()
        return False, "Event not found."
    capacity = event_row["capacity"]

    c.execute("SELECT COUNT(*) AS cnt FROM event_registrations WHERE event_id=?", (event_id,))
    current = c.fetchone()["cnt"]
    if current >= capacity:
        conn.close()
        return False, "Sorry, this event is already full."

    c.execute("""
        INSERT INTO event_registrations (event_id, user_id, registered_at) VALUES (?, ?, ?)
    """, (event_id, user_id, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    return True, "Successfully registered for the event!"


def cancel_event_registration(user_id, event_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM event_registrations WHERE user_id=? AND event_id=?", (user_id, event_id))
    conn.commit()
    conn.close()
    return True, "Registration cancelled."


def get_user_registrations(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT er.*, e.title, e.date, e.time, e.venue, c.name AS club_name
        FROM event_registrations er
        JOIN events e ON er.event_id = e.id
        JOIN clubs c ON e.club_id = c.id
        WHERE er.user_id = ?
        ORDER BY e.date ASC
    """, (user_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_all_registrations():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT er.*, u.name AS student_name, u.email, e.title AS event_title, e.date AS event_date,
               c.name AS club_name
        FROM event_registrations er
        JOIN users u ON er.user_id = u.id
        JOIN events e ON er.event_id = e.id
        JOIN clubs c ON e.club_id = c.id
        ORDER BY er.registered_at DESC
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


# ----------------------------------------------------------------------
# ANNOUNCEMENTS
# ----------------------------------------------------------------------
def create_announcement(title, content):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO announcements (title, content, created_at) VALUES (?, ?, ?)",
              (title, content, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()


def get_announcements():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM announcements ORDER BY created_at DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def delete_announcement(announcement_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM announcements WHERE id = ?", (announcement_id,))
    conn.commit()
    conn.close()


# ----------------------------------------------------------------------
# STATISTICS (used by dashboards & analytics)
# ----------------------------------------------------------------------
def get_stats():
    conn = get_connection()
    c = conn.cursor()
    stats = {}
    stats["total_students"] = c.execute("SELECT COUNT(*) AS cnt FROM users WHERE role='student'").fetchone()["cnt"]
    stats["total_clubs"] = c.execute("SELECT COUNT(*) AS cnt FROM clubs").fetchone()["cnt"]
    stats["total_events"] = c.execute("SELECT COUNT(*) AS cnt FROM events").fetchone()["cnt"]
    stats["total_registrations"] = c.execute("SELECT COUNT(*) AS cnt FROM event_registrations").fetchone()["cnt"]
    conn.close()
    return stats
