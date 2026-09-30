# College Club & Event Management

A Streamlit application for college clubs, membership approvals, event registrations,
announcements and activity reports. Its SQLite database persists data on disk and
enforces relationships, unique memberships and registrations, and event capacity.

Students can create an account, request club membership, register for events, cancel
registrations and view their profile. Administrators manage clubs, events,
memberships and announcements, export registrations to CSV, and view analytics.

## Run locally

Install Python 3.9 or newer and Git, then clone the project:

```sh
git clone https://github.com/Nikup18/college-club-event-management.git
cd college-club-event-management
```

Create and activate a virtual environment. On Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies and initialize the database:

```sh
python -m pip install -r requirements.txt
python manage_db.py init
```

Create your administrator account:

```sh
python manage_db.py create-admin --email admin@college.edu --name "College Admin"
```

The command prompts for a password and confirmation without displaying them. Use
at least 12 characters. There is no default administrator or shared password.
Students register through the app and must choose a password of at least 8 characters.

Start the app and open [localhost:8501](http://localhost:8501):

```sh
python -m streamlit run app.py
```

If PowerShell blocks virtual environment activation, use
`.\.venv\Scripts\python.exe` in place of `python` in the commands above.

## Database setup

The default database is `college_management.db` in the project directory. App
startup creates an **empty** database automatically if needed; it does not create
accounts or insert demo records. Database files and backups are local runtime data
and are excluded from Git. A fresh clone gets its database from the versioned schema.

To use another location, set `COLLEGE_DB_PATH` **before** running any app or database
command. Relative paths resolve against the project directory; absolute paths work
too. For example, in PowerShell:

```powershell
$env:COLLEGE_DB_PATH = "data/college.db"
```

Or in a macOS/Linux shell:

```sh
export COLLEGE_DB_PATH="data/college.db"
```

The [.env.example](.env.example) file documents this setting; `.env` files are not
loaded automatically. Set the variable in your shell or hosting service.

For an optional demonstration with 5 clubs, 6 upcoming events and 3 announcements:

```sh
python manage_db.py seed-demo
```

Demo seeding creates no accounts. It requires empty clubs, events and announcements
and records completion so rerunning it does not duplicate data. Deleting records
does not cause the app to reseed them.

## Maintenance and upgrades

Check the database and create a consistent backup:

```sh
python manage_db.py check
python manage_db.py backup backups/college-backup.sqlite3
```

Choose a new filename for each backup. The backup command uses SQLite's backup API
and refuses to overwrite an existing file. Keep backup copies outside the hosting
machine as well; they contain account and student information.

Before updating an older checkout, stop the app and make a consistent SQLite
backup **outside the checkout**. Older versions tracked the database file in Git;
this release removes it from version control. After updating, set `COLLEGE_DB_PATH`
to your preserved database before running initialization.

Existing databases from the original project are migrated on startup or with
`python manage_db.py init`. Before a legacy migration, the app creates a uniquely
named `.pre-v1.*.bak` backup beside the original database. Valid records and IDs
are preserved. Invalid records, duplicate relationships, colliding email addresses
or overbooked events stop the migration instead of silently discarding data.

If upgrading an existing installation, rotate its old demo administrator password
before making the app accessible to others:

```sh
python manage_db.py reset-password --email admin@college.com
```

The prompt requires a new password of at least 12 characters. Existing accounts
are preserved by migration; updating the code does not change their passwords.

If setup fails, inspect the terminal/server log, back up the original database,
and follow [database troubleshooting and recovery](docs/database.md#recovery-and-troubleshooting).
Do not delete the database to resolve an upgrade error.

## Deployment

SQLite is a good fit for this app on **one host with persistent local storage**.
Store the database on a disk that survives restarts and redeployments, configure
`COLLEGE_DB_PATH`, and arrange regular backups. Write-ahead logging, foreign keys,
busy timeouts and transactional registration protect normal concurrent requests.
SQLite still serializes writers.

Ephemeral hosting storage will lose local data. For several app instances on
different machines or sustained heavy writes, use a managed PostgreSQL database
and adapt the database access layer and migrations; setting a PostgreSQL URL in
`COLLEGE_DB_PATH` does not perform that conversion. Do not share a SQLite file
between machines over a network filesystem.

## Project layout and development

```text
app.py                  Streamlit login, navigation and routing
auth.py                 Session authentication and registration validation
database.py             Database queries, transactions and password hashing
db_schema.py            Schema initialization and legacy migration
migrations/             Versioned SQL schema, constraints and indexes
manage_db.py            Setup, admin creation, password reset, demo seed, backup and checks
app_pages/              Student and administrator pages
assets/style.css        Application theme
docs/database.md        Data model, constraints, migration and recovery
tests/                  Automated regression tests
.github/workflows/      Continuous integration
```

Page modules use `app_pages/` because Streamlit treats `pages/` as automatic
navigation, which would conflict with this app's login-gated navigation.

Run the regression suite after installing dependencies:

```sh
python -m unittest discover -s tests -v
python -m compileall -q app.py auth.py database.py db_schema.py manage_db.py app_pages tests
```

GitHub Actions runs these checks on Python 3.9 and 3.13. See the workflow run for
its status. [Database documentation](docs/database.md) explains the schema and
operational limits.
