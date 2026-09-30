"""Streamlit integration checks against disposable database files.

Install requirements.txt to run these tests. The database-only suite can still
run with Python's standard library; this class is skipped without Streamlit.
"""

from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import database as db

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
PASSWORD = "Example test password 123!"


@unittest.skipIf(AppTest is None, "Install requirements.txt to run Streamlit integration tests")
class StreamlitAppTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db_path = Path(temporary.name) / "test-app.sqlite3"
        database_path = patch.object(db, "DB_NAME", str(self.db_path))
        database_path.start()
        self.addCleanup(database_path.stop)

    def app(self):
        return AppTest.from_file(str(APP_PATH), default_timeout=30).run()

    def assert_page_works(self, app):
        self.assertEqual([], [error.message for error in app.exception])
        self.assertEqual([], [error.value for error in app.error])

    def input(self, app, label):
        return next(widget for widget in app.text_input if widget.label == label)

    def submit(self, app, label):
        next(button for button in app.button if button.label == label).click().run()
        return app

    def account(self, email, role="student"):
        ok, message = db.create_user("Test " + role, email, PASSWORD, role=role,
                                     course="Computer Science", year="2")
        self.assertTrue(ok, message)
        return db.authenticate_user(email, PASSWORD)["id"]

    def login(self, app, email):
        self.input(app, "Email").set_value(email)
        self.input(app, "Password").set_value(PASSWORD)
        self.submit(app, "Login")
        self.assert_page_works(app)
        self.assertTrue(app.session_state["logged_in"])
        return app

    def test_fresh_start_has_empty_database_and_administrator_setup_notice(self):
        app = self.app()
        self.assert_page_works(app)
        self.assertTrue(self.db_path.is_file())
        self.assertEqual([], db.get_all_users())
        self.assertEqual(0, db.get_stats()["total_clubs"])
        self.assertTrue(any("Administrator setup is pending" in item.value for item in app.info))
        self.assertEqual(2, len(app.tabs))
        rendered = "\n".join(item.value for item in app.markdown)
        self.assertNotIn("admin123", rendered)
        self.assertNotIn("admin@college.com", rendered)
        self.assertNotIn("Demo Admin Credentials", rendered)

    def test_student_registration_validates_password_and_normalizes_email(self):
        app = self.app()
        self.input(app, "Full Name").set_value("  Sample Student  ")
        app.text_input(key="reg_email").set_value("  Student@College.EDU  ")
        app.text_input(key="reg_password").set_value("short")
        self.input(app, "Confirm Password").set_value("short")
        self.input(app, "Course (e.g. B.Tech CSE)").set_value("B.Tech CSE")
        self.submit(app, "Create Account")
        self.assertFalse(app.exception)
        self.assertTrue(any("at least 8" in item.value for item in app.error))
        self.assertEqual([], db.get_all_users())

        app.text_input(key="reg_password").set_value(PASSWORD)
        self.input(app, "Confirm Password").set_value(PASSWORD)
        self.submit(app, "Create Account")
        self.assert_page_works(app)
        self.assertTrue(app.success)
        users = db.get_all_users()
        self.assertEqual(1, len(users))
        self.assertEqual("student@college.edu", users[0]["email"])
        self.assertEqual("Sample Student", users[0]["name"])
        self.login(app, "STUDENT@COLLEGE.EDU")
        self.assertEqual("student", app.session_state["user"]["role"])
        self.assertNotIn("password", app.session_state["user"])

    def test_seeded_data_renders_all_administrator_and_student_pages(self):
        db.init_db()
        db.seed_demo_data()
        self.account("admin@example.edu", "admin")
        student_id = self.account("student@example.edu")
        club_id = db.get_clubs()[0]["id"]
        event_id = db.get_events()[0]["id"]
        self.assertTrue(db.join_club(student_id, club_id)[0])
        membership_id = db.get_user_memberships(student_id)[0]["id"]
        db.update_membership_status(membership_id, "Approved")
        self.assertTrue(db.register_event(student_id, event_id)[0])

        app = self.login(self.app(), "admin@example.edu")
        self.assertEqual("admin", app.session_state["user"]["role"])
        for page in ("Dashboard", "Manage Clubs", "Manage Events", "Club Members",
                     "Event Registrations", "Announcements", "Users", "Analytics"):
            with self.subTest(role="admin", page=page):
                app.button(key="nav_" + page).click().run()
                self.assert_page_works(app)
                self.assertEqual(page, app.session_state["page"])

        self.submit(app, "🚪  Logout")
        self.login(app, "student@example.edu")
        for page in ("Dashboard", "Clubs", "Events", "My Clubs", "My Events", "Announcements", "Profile"):
            with self.subTest(role="student", page=page):
                app.button(key="nav_" + page).click().run()
                self.assert_page_works(app)
                self.assertEqual(page, app.session_state["page"])
        self.assertFalse(any(button.key == "nav_Manage Events" for button in app.button))

    def test_rejected_migration_shows_error_and_preserves_existing_data(self):
        with closing(sqlite3.connect(str(self.db_path))) as conn:
            conn.execute("CREATE TABLE existing_records (value TEXT)")
            conn.execute("INSERT INTO existing_records VALUES ('keep this record')")
            conn.commit()

        with self.assertLogs(level="ERROR"):
            app = self.app()
        self.assertFalse(app.exception)
        self.assertTrue(any("Database setup could not be completed" in item.value for item in app.error))
        self.assertEqual(0, len(app.text_input))
        with closing(sqlite3.connect(str(self.db_path))) as conn:
            self.assertEqual("keep this record", conn.execute("SELECT value FROM existing_records").fetchone()[0])
            self.assertEqual(0, conn.execute("PRAGMA user_version").fetchone()[0])
        self.assertEqual(1, len(list(self.db_path.parent.glob("*.pre-v1.*.bak"))))

    def test_event_edits_preserve_zero_capacity_and_protect_registered_students(self):
        db.init_db()
        self.account("admin@example.edu", "admin")
        student_id = self.account("student@example.edu")
        club_id = db.create_club("Test Club", "", "Technology", "", "Monday", "")
        event_id = db.create_event("Closed Event", "", club_id,
                                   (date.today() + timedelta(days=7)).isoformat(), "", "", 0)
        app = self.login(self.app(), "admin@example.edu")
        app.button(key="nav_Manage Events").click().run()
        app.button(key=f"edit_ev_btn_{event_id}").click().run()
        capacity = next(item for item in app.number_input if item.label == "Capacity")
        self.assertEqual(0, capacity.value)
        self.submit(app, "💾 Save Changes")
        self.assert_page_works(app)
        self.assertEqual(0, db.get_event(event_id)["capacity"])

        app.button(key=f"edit_ev_btn_{event_id}").click().run()
        next(item for item in app.number_input if item.label == "Capacity").set_value(2)
        self.submit(app, "💾 Save Changes")
        self.assert_page_works(app)
        self.assertTrue(db.register_event(student_id, event_id)[0])

        app.button(key=f"edit_ev_btn_{event_id}").click().run()
        next(item for item in app.number_input if item.label == "Capacity").set_value(0)
        self.submit(app, "💾 Save Changes")
        self.assertFalse(app.exception)
        self.assertTrue(any("Capacity" in item.value for item in app.error))
        self.assertEqual(2, db.get_event(event_id)["capacity"])
        self.assertEqual(1, db.get_event_registration_count(event_id))


if __name__ == "__main__":
    unittest.main()
