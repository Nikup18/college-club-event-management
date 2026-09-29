import streamlit as st
import database as db


def render():
    user = st.session_state.user
    st.markdown("## 🎟️ My Events")
    st.caption("Events you've registered for.")

    registrations = db.get_user_registrations(user["id"])
    if not registrations:
        st.info("You haven't registered for any events yet. Check out the **Events** page!")
        return

    for r in registrations:
        st.markdown(f"""
        <div class="cc-card">
            <h3>{r['title']}</h3>
            <span class="cc-badge badge-category">{r['club_name']}</span>
            <div class="cc-meta" style="margin-top:10px;">📅 {r['date']} &nbsp;|&nbsp; 🕐 {r.get('time') or 'TBA'} &nbsp;|&nbsp; 📍 {r.get('venue') or 'TBA'}</div>
            <div class="cc-meta">📝 Registered on {r['registered_at'][:10]}</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Cancel Registration", key=f"cancel_{r['event_id']}"):
            db.cancel_event_registration(user["id"], r["event_id"])
            st.success("Registration cancelled.")
            st.rerun()
