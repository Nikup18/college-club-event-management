import streamlit as st
import database as db


def render():
    user = st.session_state.user
    st.markdown("## 📅 Upcoming Events")
    st.caption("Register for events happening across campus.")

    events = db.get_events(upcoming_only=True)
    if not events:
        st.info("No upcoming events right now. Check back later!")
        return

    my_registrations = {r["event_id"] for r in db.get_user_registrations(user["id"])}

    club_names = sorted(set(e["club_name"] for e in events))
    selected_club = st.selectbox("Filter by club", ["All"] + club_names)
    filtered = events if selected_club == "All" else [e for e in events if e["club_name"] == selected_club]

    for e in filtered:
        registered_count = db.get_event_registration_count(e["id"])
        seats_left = max(e["capacity"] - registered_count, 0)
        is_full = seats_left <= 0
        already_registered = e["id"] in my_registrations

        st.markdown(f"""
        <div class="cc-card">
            <h3>{e['title']}</h3>
            <span class="cc-badge badge-category">{e['club_name']}</span>
            <p class="cc-meta" style="margin-top:10px;">{e['description'] or ''}</p>
            <div class="cc-meta">📅 {e['date']} &nbsp;|&nbsp; 🕐 {e.get('time') or 'TBA'} &nbsp;|&nbsp; 📍 {e.get('venue') or 'TBA'}</div>
            <div class="cc-meta">🪑 {seats_left} / {e['capacity']} seats available</div>
        </div>
        """, unsafe_allow_html=True)

        progress = min(registered_count / e["capacity"], 1.0) if e["capacity"] else 0
        st.progress(progress)

        if already_registered:
            st.success("✅ You are registered for this event.")
        elif is_full:
            st.error("🚫 This event is full.")
        else:
            if st.button("Register", key=f"reg_{e['id']}"):
                ok, msg = db.register_event(user["id"], e["id"])
                if ok:
                    st.success(msg)
                else:
                    st.warning(msg)
                st.rerun()

        st.markdown("")
