"""Database administration without starting Streamlit or exposing passwords."""

import argparse
from contextlib import closing
from getpass import getpass
from pathlib import Path
import sqlite3
import sys

import database as db
from db_schema import DatabaseMigrationError, SCHEMA_VERSION


def _read_password():
    password = getpass("New password (at least 12 characters): ")
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters long.")
    if password != getpass("Confirm password: "):
        raise ValueError("Passwords do not match.")
    return password


def _readonly_connection():
    source = Path(db.DB_NAME).resolve()
    if not source.is_file():
        raise ValueError("Database does not exist. Run: python manage_db.py init")
    return sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=15)


def backup_database(destination):
    """Use SQLite's online backup API; refuse to overwrite any existing file."""
    destination = Path(destination).expanduser().resolve()
    if destination == Path(db.DB_NAME).resolve():
        raise ValueError("Backup destination must differ from the active database.")
    with closing(_readonly_connection()) as source:
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Reserve the name exclusively before opening it with SQLite.
        with destination.open("xb"):
            pass
        try:
            with closing(sqlite3.connect(str(destination))) as target:
                source.backup(target)
                if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Backup integrity check failed.")
        except Exception:
            destination.unlink(missing_ok=True)
            raise
    return destination


def check_database():
    """Read-only health check: never initialize or migrate as a side effect."""
    with closing(_readonly_connection()) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version != SCHEMA_VERSION:
            raise ValueError(f"Schema version is {version}; expected {SCHEMA_VERSION}. Run init to migrate older databases.")
        integrity = [row[0] for row in conn.execute("PRAGMA integrity_check")]
        if integrity != ["ok"]:
            raise ValueError("Database integrity check failed: " + "; ".join(integrity))
        if conn.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Database contains invalid foreign key references.")
        if conn.execute("""
            SELECT 1 FROM events e WHERE e.capacity <
            (SELECT COUNT(*) FROM event_registrations r WHERE r.event_id=e.id) LIMIT 1
        """).fetchone():
            raise ValueError("An event has more registrations than its capacity.")
    return version


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Create or safely upgrade the database")
    admin = commands.add_parser("create-admin", help="Create an administrator with a hidden password prompt")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", default="College Admin")
    reset = commands.add_parser("reset-password", help="Reset an existing user's password with a hidden prompt")
    reset.add_argument("--email", required=True)
    commands.add_parser("seed-demo", help="Add one-time sample content to an empty database; no demo accounts")
    backup = commands.add_parser("backup", help="Create a consistent backup without overwriting a file")
    backup.add_argument("destination")
    commands.add_parser("check", help="Check schema version, integrity, references and event capacity")
    args = parser.parse_args(argv)
    try:
        if args.command == "backup":
            print(f"Backup saved: {backup_database(args.destination)}")
        elif args.command == "check":
            print(f"Database checks passed (schema v{check_database()}).")
        else:
            db.init_db()
            if args.command == "init":
                print(f"Database ready (schema v{SCHEMA_VERSION}): {db.DB_NAME}")
            elif args.command == "create-admin":
                ok, message = db.create_user(args.name, args.email, _read_password(), role="admin")
                if not ok:
                    raise ValueError(message)
                print("Administrator created. You can now sign in.")
            elif args.command == "reset-password":
                email = args.email.strip().lower()
                with closing(db.get_connection()) as conn:
                    row = conn.execute("SELECT id FROM users WHERE email=? COLLATE NOCASE", (email,)).fetchone()
                    if row is None:
                        raise ValueError("Account not found.")
                    password_hash = db.hash_password(_read_password())
                    with conn:
                        conn.execute("UPDATE users SET password=? WHERE id=?", (password_hash, row["id"]))
                print("Password updated. Sign out of existing sessions and sign in again.")
            elif args.command == "seed-demo":
                print("Sample content created." if db.seed_demo_data() else "Sample content was already initialized; nothing changed.")
        return 0
    except (ValueError, OSError, sqlite3.Error, DatabaseMigrationError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled; no password change was saved.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
