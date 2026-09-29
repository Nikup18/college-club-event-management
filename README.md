# 🎓 College Club & Event Management System

A complete, presentation-ready web application for managing college clubs, events,
memberships, registrations and announcements — built entirely with **Streamlit** and
**SQLite**.

---

## 📖 Project Description

This system lets students discover and join college clubs, browse and register for
events, and stay updated through announcements. Admins get a full back office to
create/edit/delete clubs and events, approve or reject membership requests, manage
event registrations, post announcements, and view analytics — all from one dashboard.

---

## ✨ Features

### Student
- Register and log in
- Browse clubs and view details
- Join clubs (membership request goes to "Pending" until approved)
- Browse upcoming events and register (duplicate/over-capacity registration blocked)
- View "My Clubs" (with status badges) and "My Events" (with cancel option)
- View announcements
- View and track their own profile, joined clubs and registration history

### Admin
- Dashboard with key metrics and charts
- Create / edit / delete clubs
- Create / edit / delete events (with validation)
- Approve / reject club membership requests
- View and filter event registrations, export to CSV
- Post / delete announcements
- View and search all registered users
- Analytics page with five Plotly charts (members per club, registrations per
  event, events per club, monthly registration trend, club popularity ranking)

---

## 🧰 Technology Stack

- **Python 3**
- **Streamlit** — UI framework
- **SQLite** — embedded database (auto-created on first run)
- **Pandas** — data handling for tables/charts
- **Plotly Express** — interactive charts
- **HTML/CSS** (via `st.markdown`) — custom dark blue/purple theme

No Flask, Django, React, Node.js or external database is used.

---

## 📁 Project Structure

```
college-club-event-management/
│
├── app.py                     # Entry point — login, routing, sidebar nav
├── database.py                # All SQLite schema + CRUD functions
├── auth.py                    # Session-state auth & registration validation
├── requirements.txt
├── README.md
├── college_management.db      # Auto-created on first run (SQLite file)
│
├── app_pages/                 # Page modules (named app_pages, see note below)
│   ├── student_dashboard.py
│   ├── clubs.py
│   ├── events.py
│   ├── my_clubs.py
│   ├── my_events.py
│   ├── announcements.py
│   ├── profile.py
│   ├── admin_dashboard.py
│   ├── manage_clubs.py
│   ├── manage_events.py
│   ├── members.py
│   ├── registrations.py
│   ├── admin_announcements.py
│   ├── users.py
│   └── analytics.py
│
└── assets/
    └── style.css               # Custom dark blue / purple theme
```

> **Note on folder naming:** Streamlit automatically turns any folder literally named
> `pages/` sitting next to the entry script into its own native multi-page navigation
> menu. Since this app uses its own custom sidebar and login-gated routing, the page
> modules live in `app_pages/` instead, to avoid clashing with that automatic feature.

---

## ⚙️ Installation & How to Run

1. Make sure you have **Python 3.9+** installed.
2. Open a terminal in the project folder and install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Run the app:

   ```bash
   streamlit run app.py
   ```

4. Your browser will open automatically at `http://localhost:8501`.

The SQLite database (`college_management.db`) and sample data (5 clubs, 6 events,
3 announcements, one demo admin) are created automatically the first time you run
the app — no manual setup required.

---

## 🔑 Demo Credentials

These are also shown directly on the login page.

| Role  | Email               | Password |
|-------|---------------------|----------|
| Admin | admin@college.com   | admin123 |

Students can create their own account from the **"Create Student Account"** tab on
the login page.

---

## 🗄️ Database Information

SQLite database file: `college_management.db` (auto-created, relative path — works
the same on Windows, macOS and Linux).

**Tables:**
- `users` — id, name, email, password (hashed), role, course, year, created_at
- `clubs` — id, name, description, category, faculty_coordinator, meeting_day, meeting_time, created_at
- `club_members` — id, user_id, club_id, status (Pending/Approved/Rejected), joined_at
- `events` — id, title, description, club_id, date, time, venue, capacity, created_at
- `event_registrations` — id, event_id, user_id, registered_at
- `announcements` — id, title, content, created_at

Passwords are hashed with **PBKDF2-HMAC-SHA256** (100,000 iterations, random salt per
user) using Python's built-in `hashlib` — no compiled third-party crypto dependency,
so installation stays simple and reliable on Windows. All queries use parameterized
statements (`?` placeholders) — no raw string concatenation of user input.

---

## 🚀 Future Enhancements

- Email notifications for approvals/rejections and event reminders
- Event check-in via QR codes
- File uploads for club/event banner images
- Multi-admin roles with permission levels
- Waitlists for full events
- Calendar (.ics) export for registered events

---

## ✅ Verified Working

The following have been implemented and tested end-to-end against the SQLite layer:
account creation, admin & student login (including wrong-password rejection),
duplicate-account prevention, club creation/edit/delete, joining a club and
duplicate-request prevention, membership approval, event creation, event
registration with duplicate- and capacity-blocking, registration cancellation,
announcements, and dashboard statistics.

---

## ▶️ Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```
