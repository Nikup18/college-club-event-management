"""
app.py
-------
Entry point for the College Club & Event Management System.
Run with:  streamlit run app.py
"""

import os
import logging
import sqlite3
import streamlit as st

import database as db
import auth

from app_pages import (
    student_dashboard,
    clubs,
    events,
    my_clubs,
    my_events,
    announcements,
    profile,
    admin_dashboard,
    manage_clubs,
    manage_events,
    members,
    registrations,
    admin_announcements,
    users,
    analytics,
)

st.set_page_config(
    page_title="College Club & Event Management",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


def load_css():
    css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "style.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Bootstrap
# ----------------------------------------------------------------------
try:
    db.init_db()
except (OSError, sqlite3.Error, RuntimeError, ValueError):
    logging.getLogger(__name__).exception("Database initialization failed")
    st.error(
        "Database setup could not be completed. Ask the project owner to check "
        "the server logs and follow the database troubleshooting steps in README.md."
    )
    st.stop()
auth.init_session_state()
load_css()


# ----------------------------------------------------------------------
# LOGIN / REGISTER SCREEN
# ----------------------------------------------------------------------
def login_screen():
    st.markdown("""
    <div class="cc-login-hero">
        <h1>🎓 College Club &amp; Event Management</h1>
        <p>Connect • Participate • Lead</p>
    </div>
    """, unsafe_allow_html=True)

    _, center, _ = st.columns([1, 1.4, 1])
    with center:
        if not db.has_admin():
            st.info(
                "Administrator setup is pending. The project owner should follow "
                "the administrator setup steps in README.md."
            )
        tab_login, tab_register = st.tabs(["🔐 Login", "📝 Create Student Account"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", use_container_width=True)

                if submitted:
                    if not email or not password:
                        st.error("Please enter both email and password.")
                    else:
                        ok, msg = auth.login(email.strip().lower(), password)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        with tab_register:
            with st.form("register_form"):
                name = st.text_input("Full Name")
                reg_email = st.text_input("Email", key="reg_email")
                reg_password = st.text_input("Password", type="password", key="reg_password",
                                             help="Use at least 8 characters.")
                confirm_password = st.text_input("Confirm Password", type="password")
                col1, col2 = st.columns(2)
                with col1:
                    course = st.text_input("Course (e.g. B.Tech CSE)")
                with col2:
                    year = st.selectbox("Year", ["1", "2", "3", "4"])

                reg_submitted = st.form_submit_button("Create Account", use_container_width=True)

                if reg_submitted:
                    ok, msg = auth.register_student(name, reg_email, reg_password, confirm_password, course, year)
                    if ok:
                        st.success(f"{msg} Please login from the Login tab.")
                    else:
                        st.error(msg)


# ----------------------------------------------------------------------
# SIDEBAR NAVIGATION
# ----------------------------------------------------------------------
STUDENT_NAV = {
    "Dashboard": "🏠",
    "Clubs": "🏛️",
    "Events": "📅",
    "My Clubs": "🎓",
    "My Events": "🎟️",
    "Announcements": "📢",
    "Profile": "👤",
}

ADMIN_NAV = {
    "Dashboard": "🏠",
    "Manage Clubs": "🏛️",
    "Manage Events": "📅",
    "Club Members": "👥",
    "Event Registrations": "🎟️",
    "Announcements": "📢",
    "Users": "👨‍🎓",
    "Analytics": "📊",
}


def sidebar_nav():
    user = st.session_state.user
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align:center; padding: 10px 0 18px 0;">
            <div style="font-size:2rem;">🎓</div>
            <div style="font-weight:700; font-size:1.05rem;">{user['name']}</div>
            <div style="color:#9BA1C9; font-size:0.85rem; text-transform:uppercase; letter-spacing:0.05em;">{user['role']}</div>
        </div>
        """, unsafe_allow_html=True)

        nav_map = ADMIN_NAV if auth.is_admin() else STUDENT_NAV

        for label, icon in nav_map.items():
            btn_type = "primary" if st.session_state.page == label else "secondary"
            if st.button(f"{icon}  {label}", key=f"nav_{label}", use_container_width=True, type=btn_type):
                st.session_state.page = label
                st.rerun()

        st.markdown("---")
        if st.button("🚪  Logout", use_container_width=True):
            auth.logout()
            st.rerun()


# ----------------------------------------------------------------------
# ROUTING
# ----------------------------------------------------------------------
STUDENT_ROUTES = {
    "Dashboard": student_dashboard.render,
    "Clubs": clubs.render,
    "Events": events.render,
    "My Clubs": my_clubs.render,
    "My Events": my_events.render,
    "Announcements": announcements.render,
    "Profile": profile.render,
}

ADMIN_ROUTES = {
    "Dashboard": admin_dashboard.render,
    "Manage Clubs": manage_clubs.render,
    "Manage Events": manage_events.render,
    "Club Members": members.render,
    "Event Registrations": registrations.render,
    "Announcements": admin_announcements.render,
    "Users": users.render,
    "Analytics": analytics.render,
}


def main():
    if not auth.is_logged_in():
        login_screen()
        return

    sidebar_nav()
    routes = ADMIN_ROUTES if auth.is_admin() else STUDENT_ROUTES
    page = st.session_state.page
    render_fn = routes.get(page, routes["Dashboard"])
    render_fn()


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        st.error(str(exc))
    except (sqlite3.Error, OSError):
        logging.getLogger(__name__).exception("Database operation failed")
        st.error(
            "The database is temporarily unavailable. Please try again shortly. "
            "If this continues, ask the project owner to check the server logs."
        )
