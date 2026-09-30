"""Exercise administration commands against disposable databases only."""

from contextlib import closing, redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import database as db
import manage_db


class AdministrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.path = self.directory / "application.db"
        path_patch = patch.object(db, "DB_NAME", str(self.path))
        path_patch.start()
        self.addCleanup(path_patch.stop)

    def command(self, *args, passwords=()):
        output, error = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(error), patch.object(manage_db, "getpass", side_effect=passwords):
            status = manage_db.main(list(args))
        return status, output.getvalue() + error.getvalue()

    def test_create_admin_and_rotate_password_without_printing_credentials(self):
        first, second = "Initial-strong-password!", "Replacement-strong-password!"
        result, output = self.command("create-admin", "--email", " ADMIN@Example.com ", passwords=(first, first))
        self.assertEqual(result, 0, output)
        self.assertNotIn(first, output)
        self.assertTrue(db.has_admin())
        self.assertEqual(db.authenticate_user("admin@example.com", first)["role"], "admin")
        result, output = self.command("reset-password", "--email", "admin@example.com", passwords=(second, second))
        self.assertEqual(result, 0, output)
        self.assertNotIn(second, output)
        self.assertIsNone(db.authenticate_user("admin@example.com", first))
        self.assertIsNotNone(db.authenticate_user("admin@example.com", second))

    def test_invalid_prompts_and_duplicate_admin_never_replace_accounts(self):
        self.assertEqual(self.command("create-admin", "--email", "admin@example.com", passwords=("short",))[0], 1)
        self.assertFalse(db.has_admin())
        self.assertEqual(self.command("create-admin", "--email", "admin@example.com", passwords=("Long-password-one", "Long-password-two"))[0], 1)
        self.assertFalse(db.has_admin())
        secret = "Original-password!"
        self.assertTrue(db.create_user("Admin", "admin@example.com", secret, role="admin")[0])
        self.assertEqual(self.command("create-admin", "--email", "ADMIN@example.com", passwords=("New-password-value!",) * 2)[0], 1)
        self.assertIsNotNone(db.authenticate_user("admin@example.com", secret))
        self.assertEqual(len(db.get_all_users()), 1)

    def test_backup_contains_live_wal_data_and_never_overwrites(self):
        db.init_db()
        # Keep an active connection so committed content may still be in the WAL.
        with closing(db.get_connection()) as connection:
            with connection:
                connection.execute("INSERT INTO announcements(title,content,created_at) VALUES('Keep this','Content','2026-09-30')")
            destination = self.directory / "backup.db"
            status, output = self.command("backup", str(destination))
            self.assertEqual(status, 0, output)
            with closing(sqlite3.connect(destination)) as backup:
                self.assertEqual(backup.execute("SELECT title FROM announcements").fetchall(), [("Keep this",)])
                self.assertEqual(backup.execute("PRAGMA integrity_check").fetchone(), ("ok",))
            original_backup = destination.read_bytes()
            self.assertEqual(self.command("backup", str(destination))[0], 1)
            self.assertEqual(destination.read_bytes(), original_backup)
            self.assertEqual(self.command("backup", str(self.path))[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM announcements").fetchone()[0], 1)

    def test_check_and_backup_never_create_missing_source_database(self):
        self.assertEqual(self.command("check")[0], 1)
        self.assertEqual(self.command("backup", str(self.directory / "backup.db"))[0], 1)
        self.assertFalse(self.path.exists())
        self.assertFalse((self.directory / "backup.db").exists())

    def test_check_detects_broken_references_and_outdated_schema(self):
        self.assertEqual(self.command("init")[0], 0)
        self.assertEqual(self.command("check")[0], 0)
        with closing(sqlite3.connect(self.path)) as connection:
            with connection:
                connection.execute("INSERT INTO club_members(user_id,club_id,joined_at) VALUES(999,999,'2026-09-30')")
        self.assertEqual(self.command("check")[0], 1)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("PRAGMA user_version=0")
        self.assertEqual(self.command("check")[0], 1)
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 0)

    def test_env_path_is_independent_of_working_directory(self):
        # This subprocess also verifies import/bootstrap from the documented CLI.
        target = self.directory / "persistent" / "college.db"
        environment = dict(os.environ, COLLEGE_DB_PATH=str(target))
        result = subprocess.run(
            [sys.executable, str(Path(manage_db.__file__).resolve()), "init"],
            cwd=self.directory, env=environment, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(target.is_file())
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
