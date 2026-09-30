"""Versioned SQLite schema creation and lossless legacy database upgrades.

The SQL files in ``migrations/`` are the schema source of truth. Every migration
runs in one explicit transaction; ``executescript`` is deliberately avoided
because it can implicitly commit a transaction before running the script.
"""

import os
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


SCHEMA_VERSION = 1
BUSY_TIMEOUT_MS = 30_000
MIGRATIONS_DIRECTORY = Path(__file__).resolve().parent / "migrations"

# Explicit column lists prevent accidental loss when someone has customized an
# old database. All six original tables and their public columns are retained.
LEGACY_COLUMNS = {
    "users": ("id", "name", "email", "password", "role", "course", "year", "created_at"),
    "clubs": (
        "id", "name", "description", "category", "faculty_coordinator",
        "meeting_day", "meeting_time", "created_at",
    ),
    "club_members": ("id", "user_id", "club_id", "status", "joined_at"),
    "events": (
        "id", "title", "description", "club_id", "date", "time", "venue",
        "capacity", "created_at",
    ),
    "event_registrations": ("id", "event_id", "user_id", "registered_at"),
    "announcements": ("id", "title", "content", "created_at"),
}


class DatabaseMigrationError(RuntimeError):
    """The stored database cannot be safely migrated by this app version."""


def _enable_wal(conn):
    """Handle simultaneous first starts racing to change the journal mode.

    SQLite can return SQLITE_BUSY immediately for this pragma, even when a busy
    timeout is configured. Retry only lock errors, within the same timeout.
    """
    deadline = time.monotonic() + BUSY_TIMEOUT_MS / 1000
    while True:
        try:
            if conn.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
                conn.execute("PRAGMA journal_mode = WAL")
            return
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                raise
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise
            time.sleep(min(0.05, remaining))


def _execute_sql_file(conn, filename):
    """Execute complete statements, including trigger bodies, without commits."""
    statement = ""
    for line in (MIGRATIONS_DIRECTORY / filename).read_text(encoding="utf-8").splitlines(True):
        statement += line
        if sqlite3.complete_statement(statement):
            conn.execute(statement)
            statement = ""
    if statement.strip():
        raise DatabaseMigrationError(f"Incomplete SQL statement in migration {filename}.")


def _schema_tables(conn):
    return {
        row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def _validate_legacy_layout(conn, tables):
    expected = set(LEGACY_COLUMNS)
    if tables != expected:
        details = []
        if expected - tables:
            details.append("missing tables: " + ", ".join(sorted(expected - tables)))
        if tables - expected:
            details.append("unrecognized tables: " + ", ".join(sorted(tables - expected)))
        raise DatabaseMigrationError("Unrecognized legacy schema (" + "; ".join(details) + ").")
    for table, expected_columns in LEGACY_COLUMNS.items():
        actual_columns = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
        if actual_columns != set(expected_columns):
            raise DatabaseMigrationError(
                f"Legacy table {table} has missing or additional columns; automatic import would lose data."
            )
    custom_objects = conn.execute(
        "SELECT type, name FROM sqlite_master "
        "WHERE type IN ('view', 'trigger') OR (type = 'index' AND sql IS NOT NULL)"
    ).fetchall()
    if custom_objects:
        objects = ", ".join(f"{kind} {name}" for kind, name in custom_objects)
        raise DatabaseMigrationError(
            f"Legacy database has custom schema objects requiring a manual migration: {objects}."
        )


def _backup_legacy_database(db_path):
    """Copy a committed snapshot, including WAL data, without overwriting files.

    The migration connection already holds BEGIN IMMEDIATE, which prevents
    another writer from changing the legacy data while this second connection
    takes its snapshot. SQLite's backup API must use this separate read source:
    backing up the connection holding a write transaction would wait on itself.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = db_path.with_name(f"{db_path.name}.pre-v1.{timestamp}.{uuid4().hex[:8]}.bak")
    descriptor = os.open(str(backup_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        with closing(sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)) as source:
            with closing(sqlite3.connect(str(backup_path))) as target:
                source.backup(target)
    except BaseException:
        # This path was exclusively created above and contains no user data.
        backup_path.unlink(missing_ok=True)
        raise
    return backup_path


def _import_legacy_database(conn):
    # Keep AUTOINCREMENT high-water marks even if the highest ID was deleted.
    sequences = {}
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'sqlite_sequence'").fetchone():
        sequences = dict(conn.execute("SELECT name, seq FROM sqlite_sequence"))
    for table in LEGACY_COLUMNS:
        conn.execute(f'ALTER TABLE "{table}" RENAME TO "__legacy_v0_{table}"')

    _execute_sql_file(conn, "001_initial.sql")
    for table, columns in LEGACY_COLUMNS.items():
        column_sql = ", ".join(f'"{column}"' for column in columns)
        expressions = ", ".join(
            'lower(trim("email", char(9, 10, 11, 12, 13, 32)))'
            if table == "users" and column == "email" else f'"{column}"'
            for column in columns
        )
        conn.execute(
            f'INSERT INTO "{table}" ({column_sql}) '
            f'SELECT {expressions} FROM "__legacy_v0_{table}" ORDER BY id'
        )

    foreign_key_errors = conn.execute("PRAGMA foreign_key_check").fetchmany(5)
    if foreign_key_errors:
        raise DatabaseMigrationError(f"Legacy rows contain broken foreign keys: {foreign_key_errors}.")

    for table in reversed(LEGACY_COLUMNS):
        conn.execute(f'DROP TABLE "__legacy_v0_{table}"')
    for table, sequence in sequences.items():
        if table not in LEGACY_COLUMNS:
            continue
        row = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = ?", (table,)).fetchone()
        if row is None:
            conn.execute("INSERT INTO sqlite_sequence(name, seq) VALUES (?, ?)", (table, sequence))
        elif sequence > row[0]:
            conn.execute("UPDATE sqlite_sequence SET seq = ? WHERE name = ?", (sequence, table))


def initialize_database(path):
    """Create or migrate a file database; preserve all legacy rows and IDs.

    Version-0 databases receive a unique backup beside the original before any
    schema changes. Email whitespace/case is normalized while importing; if
    that reveals duplicates, or another new constraint rejects existing data,
    the complete migration is rolled back. No rows are discarded or merged.
    The caller should surface DatabaseMigrationError and let the owner repair
    the original legacy data before retrying. Repeated startup is a no-op.
    """
    db_path = Path(path).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = None
    with closing(sqlite3.connect(str(db_path), timeout=BUSY_TIMEOUT_MS / 1000, isolation_level=None)) as conn:
        conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise DatabaseMigrationError(
                f"Database schema version {version} is newer than this app supports ({SCHEMA_VERSION}). "
                "Use a compatible newer app; do not reset the database version."
            )
        _enable_wal(conn)
        conn.execute("PRAGMA foreign_keys = ON")
        if version == SCHEMA_VERSION:
            return

        # Table rebuilding requires disabling cascades outside the transaction.
        # The migrated data is explicitly foreign-key checked before commit.
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            conn.execute("BEGIN IMMEDIATE")
            # Another process may have completed initialization while we waited.
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise DatabaseMigrationError(
                    f"Database schema version {version} is newer than this app supports ({SCHEMA_VERSION})."
                )
            if version == 0:
                tables = _schema_tables(conn)
                if tables:
                    backup_path = _backup_legacy_database(db_path)
                    _validate_legacy_layout(conn, tables)
                    _import_legacy_database(conn)
                else:
                    _execute_sql_file(conn, "001_initial.sql")
            elif version != SCHEMA_VERSION:
                raise DatabaseMigrationError(f"No migration is available from schema version {version}.")

            foreign_key_errors = conn.execute("PRAGMA foreign_key_check").fetchmany(5)
            if foreign_key_errors:
                raise DatabaseMigrationError(f"Foreign key validation failed: {foreign_key_errors}.")
            conn.commit()
        except (sqlite3.Error, DatabaseMigrationError, OSError) as exc:
            conn.rollback()
            backup_message = f" Legacy backup: {backup_path}." if backup_path else ""
            raise DatabaseMigrationError(
                f"Database migration failed: {exc} No existing rows were changed.{backup_message} "
                "Correct the reported legacy data/schema issue manually, then restart; "
                "do not delete the database or change PRAGMA user_version to bypass validation."
            ) from exc
        finally:
            conn.execute("PRAGMA foreign_keys = ON")
