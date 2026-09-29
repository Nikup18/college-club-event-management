import streamlit as st
import database as db

BADGE_CLASS = {"Approved": "badge-approved", "Pending": "badge-pending", "Rejected": "badge-rejected"}


def render():
    user = st.session_state.user
    st.markdown("## 🎓 My Clubs")
    st.caption("Clubs you've joined or requested to join.")

    memberships = db.get_user_memberships(user["id"])
    if not memberships:
        st.info("You haven't joined any clubs yet. Head to the **Clubs** page to get started!")
        return

    for m in memberships:
        badge = BADGE_CLASS.get(m["status"], "badge-pending")
        st.markdown(f"""
        <div class="cc-card">
            <h3>{m['club_name']} <span class="cc-badge {badge}">{m['status']}</span></h3>
            <div class="cc-meta">📂 {m['category'] or 'General'}</div>
            <div class="cc-meta">👨‍🏫 {m['faculty_coordinator'] or 'TBA'}</div>
            <div class="cc-meta">📝 Requested on {m['joined_at'][:10]}</div>
        </div>
        """, unsafe_allow_html=True)
