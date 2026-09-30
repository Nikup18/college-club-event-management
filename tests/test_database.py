"""Integration tests run entirely against temporary SQLite databases.

Run with ``python -m unittest discover -s tests -v`` from the project root.
No application database, external services, or third-party test packages are used.
"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import date, timedelta
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

import database as db
from db_schema import DatabaseMigrationError, SCHEMA_VERSION


# The original application's unversioned schema is intentionally kept here.
# Migration tests must exercise an actual old database, not the new schema.
LEGACY_SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'student', course TEXT, year TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE clubs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, description TEXT, category TEXT,
    faculty_coordinator TEXT, meeting_day TEXT, meeting_time TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE club_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL, club_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending', joined_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE CASCADE
);
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL, description TEXT, club_id INTEGER NOT NULL,
    date TEXT NOT NULL, time TEXT, venue TEXT,
    capacity INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
    FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE CASCADE
);
CREATE TABLE event_registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
    registered_at TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL, content TEXT, created_at TEXT NOT NULL
);
"""

TABLES = (
    "users", "clubs", "club_members", "events",
    "event_registrations", "announcements",
)
PASSWORD = "Student-test-password-49!"
LEGACY_SALT = "00112233445566778899aabbccddeeff"
LEGACY_HASH = LEGACY_SALT + "$" + hashlib.pbkdf2_hmac(
    "sha256", PASSWORD.encode(), bytes.fromhex(LEGACY_SALT), 100_000
).hex()


class TemporaryDatabase(unittest.TestCase):
    initialize = True

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db_path = Path(temporary.name) / "test.sqlite3"
        self.path_patch = patch.object(db, "DB_NAME", str(self.db_path))
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        if self.initialize:
            db.init_db()
        self.next_user = 0
        self.next_club = 0
        self.next_event = 0

    def query(self, sql, parameters=(), path=None):
        with closing(sqlite3.connect(path or self.db_path)) as connection:
            return connection.execute(sql, parameters).fetchall()

    def execute(self, sql, parameters=()):
        with closing(db.get_connection()) as connection:
            with connection:
                return connection.execute(sql, parameters).lastrowid

    def user(self):
        self.next_user += 1
        email = f"student{self.next_user}@example.com"
        result = db.create_user(
            f"Student {self.next_user}", email, PASSWORD,
            course="Computer Science", year="2",
        )
        self.assert_result(result, True)
        return db.get_all_users(search=email)[0]["id"]

    def club(self):
        self.next_club += 1
        name = f"Club {self.next_club}"
        db.create_club(name, "A club for students", "Technology", "Dr Rao", "Monday", "17:00")
        return next(club["id"] for club in db.get_clubs() if club["name"] == name)

    def event(self, club_id=None, capacity=3, days=7):
        if club_id is None:
            club_id = self.club()
        self.next_event += 1
        title = f"Workshop {self.next_event}"
        db.create_event(
            title, "Hands-on workshop", club_id,
            (date.today() + timedelta(days=days)).isoformat(),
            "10:00 AM", "Lab 1", capacity,
        )
        return next(event["id"] for event in db.get_events() if event["title"] == title)

    def assert_result(self, result, success):
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIs(result[0], success, result[1])
        self.assertIsInstance(result[1], str)
        self.assertTrue(result[1])

    def assert_fields(self, row, fields):
        self.assertIsInstance(row, dict)
        self.assertTrue(set(fields).issubset(row), row)
        self.assertNotIn("password", row)

    def assert_integrity_error(self, sql, parameters=()):
        with self.assertRaises(sqlite3.IntegrityError):
            self.execute(sql, parameters)


class InitializationTests(TemporaryDatabase):
    def test_fresh_database_has_schema_but_no_default_accounts_or_demo_content(self):
        for table in TABLES:
            with self.subTest(table=table):
                self.assertEqual(self.query(f"SELECT COUNT(*) FROM {table}"), [(0,)])
        self.assertIsNone(db.authenticate_user("admin@college.com", "admin123"))
        self.assertEqual(self.query("PRAGMA user_version"), [(SCHEMA_VERSION,)])
        self.assertEqual(self.query("PRAGMA integrity_check"), [("ok",)])
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])
        with closing(db.get_connection()) as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_explicit_demo_seed_is_repeatable_and_contains_no_accounts(self):
        db.seed_demo_data()
        db.seed_demo_data()
        db.init_db()
        self.assertEqual(len(db.get_clubs()), 5)
        self.assertEqual(len(db.get_events(upcoming_only=True)), 6)
        self.assertEqual(len(db.get_announcements()), 3)
        self.assertEqual(db.get_all_users(), [])
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])

    def test_init_and_seed_never_resurrect_deleted_demo_data(self):
        db.seed_demo_data()
        for club in db.get_clubs():
            db.delete_club(club["id"])
        for announcement in db.get_announcements():
            db.delete_announcement(announcement["id"])
        db.init_db()
        db.seed_demo_data()
        db.init_db()
        self.assertEqual(db.get_clubs(), [])
        self.assertEqual(db.get_events(), [])
        self.assertEqual(db.get_announcements(), [])

    def test_repeat_initialization_preserves_real_users_and_club_content(self):
        user_id, club_id = self.user(), self.club()
        event_id = self.event(club_id)
        self.assert_result(db.join_club(user_id, club_id), True)
        self.assert_result(db.register_event(user_id, event_id), True)
        db.create_announcement("Real college notice", "Keep this announcement.")
        before = {table: self.query(f"SELECT * FROM {table} ORDER BY id") for table in TABLES}
        db.init_db()
        db.init_db()
        after = {table: self.query(f"SELECT * FROM {table} ORDER BY id") for table in TABLES}
        self.assertEqual(after, before)
        self.assertEqual(list(self.db_path.parent.glob("*.bak")), [])

    def test_demo_seed_refuses_existing_content_without_partial_inserts(self):
        self.club()
        with self.assertRaises(ValueError):
            db.seed_demo_data()
        self.assertEqual(len(db.get_clubs()), 1)
        self.assertEqual(db.get_events(), [])
        self.assertEqual(db.get_announcements(), [])
        self.assertEqual(db.get_all_users(), [])


class AuthenticationTests(TemporaryDatabase):
    def test_account_email_normalization_duplicates_and_sanitized_reads(self):
        self.assert_result(db.create_user("Alice", "\t ALICE@Example.Com \r\n", PASSWORD), True)
        self.assert_result(db.create_user("Other Alice", "alice@example.com", PASSWORD), False)
        user = db.authenticate_user(" ALICE@EXAMPLE.COM ", PASSWORD)
        self.assert_fields(user, ("id", "name", "email", "role", "course", "year", "created_at"))
        self.assertEqual(user["email"], "alice@example.com")
        self.assertEqual(user["role"], "student")
        self.assert_fields(db.get_user(user["id"]), ("id", "email"))
        self.assert_fields(db.get_all_users()[0], ("id", "email"))
        self.assertIsNone(db.authenticate_user("alice@example.com", "incorrect-password"))
        self.assertIsNone(db.authenticate_user("missing@example.com", PASSWORD))
        self.assertIsNone(db.get_user(999999))

    def test_password_hashes_are_salted_versioned_and_verified(self):
        first = db.hash_password(PASSWORD)
        second = db.hash_password(PASSWORD)
        self.assertNotEqual(first, second)
        self.assertIn("600000", first.split("$"))
        self.assertTrue(db.verify_password(PASSWORD, first))
        self.assertFalse(db.verify_password("wrong-password", first))
        self.assertNotIn(PASSWORD, first)

    def test_malformed_hashes_are_rejected_without_crashing(self):
        malformed = (
            None, "", "not-a-hash", "not-hex$1234", "$",
            LEGACY_SALT + "$00", "pbkdf2_sha256$invalid$salt$hash",
            "pbkdf2_sha256$-1$" + LEGACY_SALT + "$00",
            "pbkdf2_sha256$999999999999$" + LEGACY_SALT + "$00",
        )
        for stored in malformed:
            with self.subTest(stored=stored):
                self.assertFalse(db.verify_password(PASSWORD, stored))

    def test_legacy_password_is_upgraded_only_after_successful_login(self):
        user_id = self.execute(
            "INSERT INTO users(name,email,password,role,created_at) VALUES(?,?,?,?,?)",
            ("Legacy Student", "legacy@example.com", LEGACY_HASH, "student", "2025-01-01T12:00:00"),
        )
        self.assertTrue(db.verify_password(PASSWORD, LEGACY_HASH))
        self.assertIsNone(db.authenticate_user("legacy@example.com", "wrong-password"))
        self.assertEqual(self.query("SELECT password FROM users WHERE id=?", (user_id,))[0][0], LEGACY_HASH)
        user = db.authenticate_user("legacy@example.com", PASSWORD)
        self.assert_fields(user, ("id", "email"))
        upgraded = self.query("SELECT password FROM users WHERE id=?", (user_id,))[0][0]
        self.assertNotEqual(upgraded, LEGACY_HASH)
        self.assertIn("600000", upgraded.split("$"))
        self.assertTrue(db.verify_password(PASSWORD, upgraded))

    def test_invalid_account_inputs_do_not_create_accounts(self):
        cases = (
            ("", "student@example.com", PASSWORD, "student"),
            ("Student", "invalid-email", PASSWORD, "student"),
            ("Student", "student@example.com", "", "student"),
            ("Student", "student@example.com", PASSWORD, "superadmin"),
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                self.assert_result(db.create_user(*arguments), False)
        self.assertEqual(db.get_all_users(), [])


class WorkflowTests(TemporaryDatabase):
    def test_club_membership_approval_and_rejection_keep_page_fields(self):
        user_id = self.user()
        club_id = self.club()
        self.assert_fields(db.get_club(club_id), ("name", "description", "category", "faculty_coordinator", "meeting_day", "meeting_time"))
        self.assert_result(db.join_club(user_id, club_id), True)
        self.assert_result(db.join_club(user_id, club_id), False)
        memberships = db.get_user_memberships(user_id)
        self.assertEqual(len(memberships), 1)
        self.assert_fields(memberships[0], ("id", "user_id", "club_id", "status", "joined_at", "club_name", "category", "faculty_coordinator"))
        self.assertEqual(memberships[0]["status"], "Pending")
        self.assertEqual(db.get_club_member_count(club_id), 0)
        membership_id = memberships[0]["id"]
        db.update_membership_status(membership_id, "Approved")
        self.assertEqual(db.get_club_member_count(club_id), 1)
        self.assert_result(db.join_club(user_id, club_id), False)
        self.assert_fields(db.get_all_memberships()[0], ("student_name", "email", "course", "year", "club_name"))
        db.update_membership_status(membership_id, "Rejected")
        self.assertEqual(db.get_club_member_count(club_id), 0)
        self.assert_result(db.join_club(user_id, club_id), False)
        db.update_club(club_id, "Updated Club", "Updated", "Arts", "Dr Sen", "Tuesday", "18:00")
        self.assertEqual(db.get_club(club_id)["name"], "Updated Club")

    def test_event_registration_cancel_and_update_keep_page_fields(self):
        user_id = self.user()
        club_id = self.club()
        event_id = self.event(club_id=club_id)
        self.assert_fields(db.get_event(event_id), ("title", "description", "club_id", "date", "time", "venue", "capacity", "club_name"))
        self.assert_result(db.register_event(user_id, event_id), True)
        self.assert_result(db.register_event(user_id, event_id), False)
        self.assertEqual(db.get_event_registration_count(event_id), 1)
        registrations = db.get_user_registrations(user_id)
        self.assert_fields(registrations[0], ("id", "event_id", "user_id", "registered_at", "title", "date", "time", "venue", "club_name"))
        self.assert_fields(db.get_all_registrations()[0], ("student_name", "email", "event_title", "event_date", "club_name"))
        new_date = (date.today() + timedelta(days=10)).isoformat()
        db.update_event(event_id, "Updated Workshop", "New description", club_id, new_date, "11:00", "Lab 2", 5)
        event = db.get_event(event_id)
        self.assertEqual((event["title"], event["date"], event["venue"], event["capacity"]), ("Updated Workshop", new_date, "Lab 2", 5))
        self.assert_result(db.cancel_event_registration(user_id, event_id), True)
        self.assertEqual(db.get_user_registrations(user_id), [])
        self.assertEqual(db.get_event_registration_count(event_id), 0)
        self.assert_result(db.register_event(user_id, event_id), True)
        db.delete_event(event_id)
        self.assertIsNone(db.get_event(event_id))
        self.assertEqual(db.get_all_registrations(), [])

    def test_announcements_user_filters_and_dashboard_stats(self):
        user_id = self.user()
        self.assert_result(db.create_user("Administrator", "admin@example.com", PASSWORD, role="admin"), True)
        self.assertEqual(len(db.get_all_users(role="student")), 1)
        self.assertEqual(len(db.get_all_users(role="admin")), 1)
        self.assertEqual(len(db.get_all_users(search="Administrator")), 1)
        self.assertEqual(db.get_all_users(search="' OR 1=1 --"), [])
        club_id = self.club()
        event_id = self.event(club_id)
        self.assert_result(db.register_event(user_id, event_id), True)
        self.assertEqual(db.get_stats(), {"total_students": 1, "total_clubs": 1, "total_events": 1, "total_registrations": 1})
        db.create_announcement("Semester update", "New workshops are available.")
        announcement = db.get_announcements()[0]
        self.assert_fields(announcement, ("id", "title", "content", "created_at"))
        db.delete_announcement(announcement["id"])
        self.assertEqual(db.get_announcements(), [])

    def test_missing_membership_and_registration_references_are_friendly_failures(self):
        user_id, club_id = self.user(), self.club()
        event_id = self.event(club_id)
        for result in (
            db.join_club(999999, club_id), db.join_club(user_id, 999999),
            db.register_event(999999, event_id), db.register_event(user_id, 999999),
        ):
            self.assert_result(result, False)
        self.assertEqual(db.get_all_memberships(), [])
        self.assertEqual(db.get_all_registrations(), [])

    def test_past_and_zero_capacity_events_reject_registration(self):
        user_id, club_id = self.user(), self.club()
        expired = self.event(club_id, days=-1)
        closed = self.event(club_id, capacity=0)
        upcoming = self.event(club_id)
        self.assert_result(db.register_event(user_id, expired), False)
        self.assert_result(db.register_event(user_id, closed), False)
        self.assertEqual({event["id"] for event in db.get_events(upcoming_only=True)}, {closed, upcoming})
        self.assertEqual(db.get_all_registrations(), [])

    def test_lowering_capacity_cannot_displace_existing_registrations(self):
        club_id = self.club()
        event_id = self.event(club_id, capacity=2)
        self.assert_result(db.register_event(self.user(), event_id), True)
        self.assert_result(db.register_event(self.user(), event_id), True)
        event = db.get_event(event_id)
        with self.assertRaises(ValueError):
            db.update_event(event_id, "Attempted edit", "", club_id, event["date"], event["time"], event["venue"], 1)
        self.assertEqual(db.get_event(event_id)["title"], event["title"])
        self.assertEqual(db.get_event(event_id)["capacity"], 2)
        self.assertEqual(db.get_event_registration_count(event_id), 2)

    def test_invalid_crud_inputs_raise_value_error_without_partial_writes(self):
        club_id = self.club()
        event_id = self.event(club_id)
        future = (date.today() + timedelta(days=7)).isoformat()
        cases = (
            lambda: db.create_club(" ", "", "", "", "", ""),
            lambda: db.update_club(club_id, " ", "", "", "", "", ""),
            lambda: db.create_announcement(" ", "content"),
            lambda: db.create_event("", "", club_id, future, "", "", 1),
            lambda: db.create_event("Invalid capacity", "", club_id, future, "", "", -1),
            lambda: db.create_event("Invalid capacity", "", club_id, future, "", "", 1.5),
            lambda: db.create_event("Invalid date", "", club_id, "2026-02-30", "", "", 1),
            lambda: db.create_event("Missing club", "", 999999, future, "", "", 1),
            lambda: db.update_event(event_id, "", "", club_id, future, "", "", 1),
            lambda: db.update_membership_status(1, "Owner"),
        )
        for operation in cases:
            with self.subTest(operation=operation):
                with self.assertRaises(ValueError):
                    operation()
        self.assertEqual(len(db.get_clubs()), 1)
        self.assertEqual(len(db.get_events()), 1)
        self.assertEqual(db.get_announcements(), [])


class ConstraintTests(TemporaryDatabase):
    def test_database_rejects_invalid_roles_statuses_foreign_keys_and_capacities(self):
        user_id, club_id = self.user(), self.club()
        event_id = self.event(club_id)
        self.assert_integrity_error("UPDATE users SET role='owner' WHERE id=?", (user_id,))
        self.assert_integrity_error("UPDATE events SET capacity=-1 WHERE id=?", (event_id,))
        self.assert_integrity_error("UPDATE events SET capacity=1.5 WHERE id=?", (event_id,))
        self.assert_integrity_error("UPDATE events SET club_id=999999 WHERE id=?", (event_id,))
        self.assert_integrity_error(
            "INSERT INTO club_members(user_id,club_id,status,joined_at) VALUES(?,?,?,?)",
            (user_id, club_id, "Owner", "2026-01-01"),
        )
        self.assert_integrity_error(
            "INSERT INTO club_members(user_id,club_id,status,joined_at) VALUES(?,?,?,?)",
            (999999, club_id, "Pending", "2026-01-01"),
        )
        self.assert_integrity_error(
            "INSERT INTO event_registrations(event_id,user_id,registered_at) VALUES(?,?,?)",
            (event_id, 999999, "2026-01-01"),
        )
        self.assert_integrity_error(
            "INSERT INTO users(name,email,password,created_at) VALUES(?,?,?,?)",
            ("Duplicate", "STUDENT1@EXAMPLE.COM", LEGACY_HASH, "2026-01-01"),
        )
        self.assert_integrity_error(
            "INSERT INTO users(name,email,password,created_at) VALUES(?,?,?,?)",
            ("Whitespace", "\tother@example.com\r\n", LEGACY_HASH, "2026-01-01"),
        )

    def test_database_enforces_membership_and_registration_uniqueness(self):
        user_id, club_id = self.user(), self.club()
        event_id = self.event(club_id)
        self.assert_result(db.join_club(user_id, club_id), True)
        self.assert_result(db.register_event(user_id, event_id), True)
        self.assert_integrity_error(
            "INSERT INTO club_members(user_id,club_id,status,joined_at) VALUES(?,?,'Pending',?)",
            (user_id, club_id, "2026-01-01"),
        )
        self.assert_integrity_error(
            "INSERT INTO event_registrations(event_id,user_id,registered_at) VALUES(?,?,?)",
            (event_id, user_id, "2026-01-01"),
        )

    def test_capacity_triggers_protect_direct_inserts_updates_and_event_edits(self):
        club_id = self.club()
        full = self.event(club_id, capacity=1)
        other = self.event(club_id, capacity=2)
        first, second = self.user(), self.user()
        self.assert_result(db.register_event(first, full), True)
        self.assert_result(db.register_event(second, other), True)
        self.assert_integrity_error(
            "INSERT INTO event_registrations(event_id,user_id,registered_at) VALUES(?,?,?)",
            (full, second, "2026-01-01"),
        )
        self.assert_integrity_error(
            "UPDATE event_registrations SET event_id=? WHERE event_id=? AND user_id=?",
            (full, other, second),
        )
        self.assert_integrity_error("UPDATE events SET capacity=0 WHERE id=?", (full,))
        self.assertEqual(db.get_event_registration_count(full), 1)
        self.assertEqual(db.get_event_registration_count(other), 1)

    def test_club_delete_cascades_memberships_events_and_registrations(self):
        user_id, club_id = self.user(), self.club()
        event_id = self.event(club_id)
        self.assert_result(db.join_club(user_id, club_id), True)
        self.assert_result(db.register_event(user_id, event_id), True)
        db.delete_club(club_id)
        self.assertIsNone(db.get_club(club_id))
        self.assertEqual(db.get_events(), [])
        self.assertEqual(db.get_all_memberships(), [])
        self.assertEqual(db.get_all_registrations(), [])
        self.assertIsNotNone(db.get_user(user_id))
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])

    def test_user_delete_cascades_memberships_and_registrations(self):
        user_id, club_id = self.user(), self.club()
        event_id = self.event(club_id)
        self.assert_result(db.join_club(user_id, club_id), True)
        self.assert_result(db.register_event(user_id, event_id), True)
        self.execute("DELETE FROM users WHERE id=?", (user_id,))
        self.assertEqual(db.get_all_memberships(), [])
        self.assertEqual(db.get_all_registrations(), [])
        self.assertIsNotNone(db.get_club(club_id))
        self.assertIsNotNone(db.get_event(event_id))
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])


class ConcurrencyTests(TemporaryDatabase):
    def test_simultaneous_signups_share_one_normalized_email_identity(self):
        emails = (" Shared.Student@Example.COM ", "shared.student@example.com")
        barrier = threading.Barrier(len(emails))

        def signup(email):
            barrier.wait(timeout=10)
            return db.create_user("Shared Student", email, PASSWORD)

        with ThreadPoolExecutor(max_workers=len(emails)) as executor:
            results = list(executor.map(signup, emails, timeout=30))
        self.assertEqual(sum(result[0] for result in results), 1, results)
        for result in results:
            self.assert_result(result, result[0])
        users = db.get_all_users()
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]["email"], "shared.student@example.com")
        self.assertIsNotNone(db.authenticate_user("SHARED.STUDENT@EXAMPLE.COM", PASSWORD))

    def test_only_one_student_can_claim_the_last_seat(self):
        event_id = self.event(capacity=1)
        users = [self.user(), self.user()]
        barrier = threading.Barrier(len(users))

        def register(user_id):
            barrier.wait(timeout=10)
            return db.register_event(user_id, event_id)

        with ThreadPoolExecutor(max_workers=len(users)) as executor:
            results = list(executor.map(register, users, timeout=30))
        self.assertEqual(sum(result[0] for result in results), 1, results)
        for result in results:
            self.assert_result(result, result[0])
        self.assertEqual(db.get_event_registration_count(event_id), 1)

    def test_simultaneous_duplicate_membership_requests_insert_one_row(self):
        user_id, club_id = self.user(), self.club()
        barrier = threading.Barrier(4)

        def join(_):
            barrier.wait(timeout=10)
            return db.join_club(user_id, club_id)

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(join, range(4), timeout=30))
        self.assertEqual(sum(result[0] for result in results), 1, results)
        self.assertEqual(len(db.get_user_memberships(user_id)), 1)


class MigrationTests(TemporaryDatabase):
    initialize = False

    def initialize_simultaneously(self):
        barrier = threading.Barrier(8)

        def initialize(_):
            barrier.wait(timeout=10)
            # Each call opens its own SQLite connection to the same file.
            db.init_db()

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(initialize, range(8), timeout=45))

    def make_legacy_database(self):
        future = (date.today() + timedelta(days=30)).isoformat()
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.executescript(LEGACY_SCHEMA)
            with connection:
                connection.execute(
                    "INSERT INTO users VALUES(7,?,?,?,?,?,?,?)",
                    ("Legacy Student", "\t Legacy@Example.COM \r\n", LEGACY_HASH, "student", "Engineering", "3", "2025-01-02T10:00:00"),
                )
                connection.execute(
                    "INSERT INTO clubs VALUES(11,?,?,?,?,?,?,?)",
                    ("Original Club", "Keep this description", "Technology", "Dr Original", "Monday", "17:00", "2025-01-02T10:00:00"),
                )
                connection.execute("INSERT INTO club_members VALUES(13,7,11,'Approved','2025-01-02T10:00:00')")
                connection.execute(
                    "INSERT INTO events VALUES(17,?,?,11,?,?,?,?,?)",
                    ("Original Event", "Keep this event", future, "09:00 AM", "Original Hall", 3, "2025-01-02T10:00:00"),
                )
                connection.execute("INSERT INTO event_registrations VALUES(19,17,7,'2025-01-02T10:00:00')")
                connection.execute("INSERT INTO announcements VALUES(23,'Original notice','Keep this notice','2025-01-02T10:00:00')")
                connection.execute("UPDATE sqlite_sequence SET seq=80 WHERE name='clubs'")

    def snapshot(self, path=None):
        return {table: self.query(f"SELECT * FROM {table} ORDER BY id", path=path) for table in TABLES}

    def backups(self):
        return list(self.db_path.parent.glob(self.db_path.name + ".pre-v1.*.bak"))

    def test_simultaneous_fresh_initialization_creates_one_valid_empty_schema(self):
        self.initialize_simultaneously()
        self.assertEqual(self.query("PRAGMA user_version"), [(SCHEMA_VERSION,)])
        self.assertEqual(self.query("PRAGMA integrity_check"), [("ok",)])
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])
        self.assertEqual(self.snapshot(), {table: [] for table in TABLES})
        self.assertEqual(self.backups(), [])

    def test_simultaneous_legacy_initialization_migrates_once_with_one_backup(self):
        self.make_legacy_database()
        original = self.snapshot()
        self.initialize_simultaneously()
        expected = dict(original)
        row = list(expected["users"][0])
        row[2] = "legacy@example.com"
        expected["users"] = [tuple(row)]
        self.assertEqual(self.snapshot(), expected)
        self.assertEqual(self.query("PRAGMA user_version"), [(SCHEMA_VERSION,)])
        self.assertEqual(self.query("PRAGMA integrity_check"), [("ok",)])
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(self.snapshot(self.backups()[0]), original)

    def test_legacy_migration_preserves_records_ids_passwords_and_sequence(self):
        self.make_legacy_database()
        original = self.snapshot()
        db.init_db()
        migrated = self.snapshot()
        expected = dict(original)
        row = list(expected["users"][0])
        row[2] = "legacy@example.com"
        expected["users"] = [tuple(row)]
        self.assertEqual(migrated, expected)
        self.assertEqual(self.query("PRAGMA user_version"), [(SCHEMA_VERSION,)])
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])
        self.assertEqual(self.query("PRAGMA integrity_check"), [("ok",)])
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(self.snapshot(self.backups()[0]), original)
        db.init_db()
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(self.snapshot(), migrated)
        self.assertGreater(self.club(), 80)

    def test_legacy_email_collision_rolls_back_without_losing_data(self):
        self.make_legacy_database()
        with closing(sqlite3.connect(self.db_path)) as connection:
            with connection:
                connection.execute(
                    "INSERT INTO users(name,email,password,role,created_at) VALUES(?,?,?,?,?)",
                    ("Duplicate Student", "legacy@example.com", LEGACY_HASH, "student", "2025-01-02T10:00:00"),
                )
        original = self.snapshot()
        with self.assertRaises(DatabaseMigrationError):
            db.init_db()
        self.assertEqual(self.snapshot(), original)
        self.assertEqual(self.query("PRAGMA user_version"), [(0,)])
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(self.snapshot(self.backups()[0]), original)

    def test_invalid_legacy_relationships_roll_back_without_losing_data(self):
        self.make_legacy_database()
        with closing(sqlite3.connect(self.db_path)) as connection:
            with connection:
                connection.execute("UPDATE club_members SET user_id=999999 WHERE id=13")
        original = self.snapshot()
        with self.assertRaises(DatabaseMigrationError):
            db.init_db()
        self.assertEqual(self.snapshot(), original)
        self.assertEqual(self.query("PRAGMA user_version"), [(0,)])
        self.assertEqual(len(self.backups()), 1)

    def test_database_from_future_schema_is_rejected_unchanged(self):
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute(f"PRAGMA user_version={SCHEMA_VERSION + 1}")
        with self.assertRaises(DatabaseMigrationError):
            db.init_db()
        self.assertEqual(self.query("PRAGMA user_version"), [(SCHEMA_VERSION + 1,)])
        self.assertEqual(self.query("SELECT name FROM sqlite_master WHERE type='table'"), [])
        self.assertEqual(self.backups(), [])


if __name__ == "__main__":
    unittest.main()
