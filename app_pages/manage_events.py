import streamlit as st
from datetime import date
import database as db


def render():
    st.markdown("## 📅 Manage Events")

    clubs = db.get_clubs()
    if not clubs:
        st.warning("You need to create at least one club before adding events.")
        return

    club_options = {c["name"]: c["id"] for c in clubs}

    tab1, tab2 = st.tabs(["➕ Create Event", "📋 All Events"])

    with tab1:
        with st.form("create_event_form", clear_on_submit=True):
            title = st.text_input("Event Title *")
            description = st.text_area("Description")
            club_name = st.selectbox("Club *", list(club_options.keys()))
            col1, col2 = st.columns(2)
            with col1:
                event_date = st.date_input("Date *", min_value=date.today())
            with col2:
                event_time = st.text_input("Time (e.g. 10:00 AM)")
            venue = st.text_input("Venue")
            capacity = st.number_input("Capacity *", min_value=0, value=50, step=1,
                                       help="Set to 0 to close registration.")

            submitted = st.form_submit_button("Create Event")
            if submitted:
                errors = []
                if not title.strip():
                    errors.append("Event title cannot be empty.")
                if not club_name:
                    errors.append("Please select a club.")
                if capacity < 0:
                    errors.append("Capacity cannot be negative.")
                if errors:
                    for err in errors:
                        st.error(err)
                else:
                    try:
                        db.create_event(title.strip(), description.strip(), club_options[club_name],
                                         event_date.isoformat(), event_time.strip(), venue.strip(), int(capacity))
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.success(f"Event '{title}' created successfully!")
                        st.rerun()

    with tab2:
        events = db.get_events()
        if not events:
            st.info("No events created yet.")
            return

        for e in events:
            reg_count = db.get_event_registration_count(e["id"])
            with st.expander(f"📅 {e['title']}  ·  {e['club_name']}  ·  {e['date']}"):
                edit_key = f"edit_ev_mode_{e['id']}"
                if edit_key not in st.session_state:
                    st.session_state[edit_key] = False

                if not st.session_state[edit_key]:
                    st.write(e["description"] or "No description.")
                    st.write(f"**Venue:** {e.get('venue') or 'TBA'}")
                    st.write(f"**Time:** {e.get('time') or 'TBA'}")
                    st.write(f"**Registrations:** {reg_count} / {e['capacity']}")

                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✏️ Edit", key=f"edit_ev_btn_{e['id']}"):
                            st.session_state[edit_key] = True
                            st.rerun()
                    with c2:
                        confirm_key = f"confirm_del_ev_{e['id']}"
                        if st.session_state.get(confirm_key):
                            st.warning("Are you sure? This will also remove all registrations for this event.")
                            cc1, cc2 = st.columns(2)
                            with cc1:
                                if st.button("✅ Yes, delete", key=f"yes_del_ev_{e['id']}"):
                                    db.delete_event(e["id"])
                                    st.success("Event deleted.")
                                    st.rerun()
                            with cc2:
                                if st.button("Cancel", key=f"no_del_ev_{e['id']}"):
                                    st.session_state[confirm_key] = False
                                    st.rerun()
                        else:
                            if st.button("🗑️ Delete", key=f"del_ev_btn_{e['id']}"):
                                st.session_state[confirm_key] = True
                                st.rerun()
                else:
                    with st.form(f"edit_ev_form_{e['id']}"):
                        new_title = st.text_input("Event Title", value=e["title"])
                        new_desc = st.text_area("Description", value=e["description"] or "")
                        club_names = list(club_options.keys())
                        current_club_name = e["club_name"] if e["club_name"] in club_names else club_names[0]
                        new_club = st.selectbox("Club", club_names, index=club_names.index(current_club_name))
                        try:
                            current_date = date.fromisoformat(e["date"])
                        except Exception:
                            current_date = date.today()
                        new_date = st.date_input("Date", value=current_date)
                        new_time = st.text_input("Time", value=e.get("time") or "")
                        new_venue = st.text_input("Venue", value=e.get("venue") or "")
                        new_capacity = st.number_input("Capacity", min_value=0, value=e["capacity"], step=1,
                                                       help="Set to 0 to close registration if no students are registered.")

                        s1, s2 = st.columns(2)
                        with s1:
                            save = st.form_submit_button("💾 Save Changes")
                        with s2:
                            cancel = st.form_submit_button("Cancel")

                        if save:
                            if not new_title.strip():
                                st.error("Event title cannot be empty.")
                            elif new_capacity < reg_count:
                                st.error(f"Capacity can't be lower than current registrations ({reg_count}).")
                            else:
                                try:
                                    db.update_event(e["id"], new_title.strip(), new_desc.strip(),
                                                     club_options[new_club], new_date.isoformat(),
                                                     new_time.strip(), new_venue.strip(), int(new_capacity))
                                except ValueError as exc:
                                    st.error(str(exc))
                                else:
                                    st.session_state[edit_key] = False
                                    st.success("Event updated successfully!")
                                    st.rerun()
                        if cancel:
                            st.session_state[edit_key] = False
                            st.rerun()
