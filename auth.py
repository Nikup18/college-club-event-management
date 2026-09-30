"""
auth.py
--------
Session-state based authentication helpers for the Streamlit app.
"""

import re
import streamlit as st
import database as db


def init_session_state():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "user" not in st.session_state:
        st.session_state.user = None
    if "page" not in st.session_state:
        st.session_state.page = "Dashboard"


def is_logged_in():
    return st.session_state.get("logged_in", False)


def is_admin():
    user = st.session_state.get("user")
    return bool(user) and user.get("role") == "admin"


def current_user():
    return st.session_state.get("user")


def login(email, password):
    user = db.authenticate_user(email, password)
    if user:
        st.session_state.logged_in = True
        st.session_state.user = user
        st.session_state.page = "Dashboard"
        return True, "Login successful!"
    return False, "Invalid email or password."


def logout():
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.page = "Dashboard"


def valid_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(pattern, email) is not None


def register_student(name, email, password, confirm_password, course, year):
    email = email.strip().lower()
    if not name.strip():
        return False, "Please enter your full name."
    if not valid_email(email):
        return False, "Please enter a valid email address."
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if password != confirm_password:
        return False, "Passwords do not match."
    if not course.strip():
        return False, "Please enter your course."
    if not year.strip():
        return False, "Please select your year."
    ok, msg = db.create_user(name.strip(), email, password, role="student",
                              course=course.strip(), year=year.strip())
    return ok, msg
