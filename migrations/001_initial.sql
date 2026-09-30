-- Version 1: the authoritative schema for a fresh or upgraded database.
-- Run through db_schema.initialize_database() to upgrade an existing database.
-- Use PRAGMA foreign_keys = ON for every connection that writes to these tables.

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
        CONSTRAINT users_name_not_blank
        CHECK (length(trim(name, char(9, 10, 11, 12, 13, 32))) > 0),
    email TEXT NOT NULL COLLATE NOCASE UNIQUE
        CONSTRAINT users_email_normalized
        CHECK (
            length(email) > 0
            AND email COLLATE BINARY = lower(trim(email, char(9, 10, 11, 12, 13, 32)))
        ),
    password TEXT NOT NULL
        CONSTRAINT users_password_not_blank CHECK (length(password) > 0),
    role TEXT NOT NULL DEFAULT 'student'
        CONSTRAINT users_valid_role CHECK (role IN ('admin', 'student')),
    course TEXT,
    year TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE clubs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
        CONSTRAINT clubs_name_not_blank
        CHECK (length(trim(name, char(9, 10, 11, 12, 13, 32))) > 0),
    description TEXT,
    category TEXT,
    faculty_coordinator TEXT,
    meeting_day TEXT,
    meeting_time TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE club_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    club_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending'
        CONSTRAINT club_members_valid_status
        CHECK (status IN ('Pending', 'Approved', 'Rejected')),
    joined_at TEXT NOT NULL,
    CONSTRAINT club_members_unique_membership UNIQUE (user_id, club_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE CASCADE
);

CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL
        CONSTRAINT events_title_not_blank
        CHECK (length(trim(title, char(9, 10, 11, 12, 13, 32))) > 0),
    description TEXT,
    club_id INTEGER NOT NULL,
    date TEXT NOT NULL
        CONSTRAINT events_valid_date CHECK (
            length(date) = 10
            AND date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
            AND date >= '0001-01-01'
            AND date(date, '+0 days') IS NOT NULL
            AND date(date, '+0 days') = date
        ),
    time TEXT,
    venue TEXT,
    capacity INTEGER NOT NULL DEFAULT 0
        CONSTRAINT events_valid_capacity
        CHECK (typeof(capacity) = 'integer' AND capacity >= 0),
    created_at TEXT NOT NULL,
    FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE CASCADE
);

CREATE TABLE event_registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    registered_at TEXT NOT NULL,
    CONSTRAINT event_registrations_unique_attendee UNIQUE (event_id, user_id),
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL
        CONSTRAINT announcements_title_not_blank
        CHECK (length(trim(title, char(9, 10, 11, 12, 13, 32))) > 0),
    content TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE app_metadata (
    key TEXT PRIMARY KEY NOT NULL CHECK (length(trim(key)) > 0),
    value TEXT NOT NULL
);

-- Composite unique indexes above also index the first foreign-key column.
CREATE INDEX idx_users_role_created ON users(role, created_at DESC);
CREATE INDEX idx_clubs_name ON clubs(name);
CREATE INDEX idx_club_members_club_status ON club_members(club_id, status);
CREATE INDEX idx_club_members_status_joined ON club_members(status, joined_at DESC);
CREATE INDEX idx_club_members_joined ON club_members(joined_at DESC);
CREATE INDEX idx_events_date ON events(date, time, id);
CREATE INDEX idx_events_club_date ON events(club_id, date);
CREATE INDEX idx_event_registrations_user ON event_registrations(user_id, registered_at DESC);
CREATE INDEX idx_event_registrations_created ON event_registrations(registered_at DESC);
CREATE INDEX idx_announcements_created ON announcements(created_at DESC);

-- These guards run inside SQLite's serialized write transaction, including
-- writes made outside the application. A capacity of zero closes registration.
CREATE TRIGGER event_registrations_capacity_insert
BEFORE INSERT ON event_registrations
FOR EACH ROW
WHEN (SELECT count(*) FROM event_registrations WHERE event_id = NEW.event_id)
     >= (SELECT capacity FROM events WHERE id = NEW.event_id)
BEGIN
    SELECT RAISE(ABORT, 'Event is full.');
END;

CREATE TRIGGER event_registrations_capacity_update
BEFORE UPDATE OF event_id, user_id ON event_registrations
FOR EACH ROW
WHEN (SELECT count(*) FROM event_registrations
      WHERE event_id = NEW.event_id AND id <> OLD.id)
     >= (SELECT capacity FROM events WHERE id = NEW.event_id)
BEGIN
    SELECT RAISE(ABORT, 'Event is full.');
END;

CREATE TRIGGER events_capacity_update
BEFORE UPDATE OF capacity ON events
FOR EACH ROW
WHEN NEW.capacity < (SELECT count(*) FROM event_registrations WHERE event_id = OLD.id)
BEGIN
    SELECT RAISE(ABORT, 'Event capacity cannot be less than the number of registrations.');
END;

PRAGMA user_version = 1;
