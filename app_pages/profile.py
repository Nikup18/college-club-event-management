import streamlit as st
import database as db


def render():
    user = st.session_state.user
    st.markdown("## 👤 My Profile")

    memberships = db.get_user_memberships(user["id"])
    registrations = db.get_user_registrations(user["id"])
    joined = [m for m in memberships if m["status"] == "Approved"]

    col1, col2 = st.columns([1, 1.4])

    with col1:
        st.markdown(f"""
        <div class="cc-card">
            <h3>{user['name']}</h3>
            <div class="cc-meta">✉️ {user['email']}</div>
            <div class="cc-meta">🎓 {user.get('course') or '-'}</div>
            <div class="cc-meta">📚 Year {user.get('year') or '-'}</div>
            <div class="cc-meta">🗓️ Joined {user['created_at'][:10]}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        m1, m2 = st.columns(2)
        m1.metric("Clubs Joined", len(joined))
        m2.metric("Events Registered", len(registrations))

    st.markdown("---")
    st.markdown("### 🏛️ Joined Clubs")
    if joined:
        for m in joined:
            st.markdown(f"- **{m['club_name']}** ({m['category']})")
    else:
        st.info("No approved club memberships yet.")

    st.markdown("### 🎟️ Event Registration History")
    if registrations:
        for r in registrations:
            st.markdown(f"- **{r['title']}** — {r['club_name']} on {r['date']}")
    else:
        st.info("No event registrations yet.")
