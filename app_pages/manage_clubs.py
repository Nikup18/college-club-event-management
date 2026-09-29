import streamlit as st
import database as db

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
CATEGORIES = ["Technology", "Arts & Culture", "Sports", "Literary", "Social Service", "Business", "Other"]


def render():
    st.markdown("## 🏛️ Manage Clubs")

    tab1, tab2 = st.tabs(["➕ Create Club", "📋 All Clubs"])

    with tab1:
        with st.form("create_club_form", clear_on_submit=True):
            name = st.text_input("Club Name *")
            description = st.text_area("Description")
            category = st.selectbox("Category", CATEGORIES)
            coordinator = st.text_input("Faculty Coordinator")
            col1, col2 = st.columns(2)
            with col1:
                meeting_day = st.selectbox("Meeting Day", DAYS)
            with col2:
                meeting_time = st.text_input("Meeting Time (e.g. 5:00 PM)")

            submitted = st.form_submit_button("Create Club")
            if submitted:
                if not name.strip():
                    st.error("Club name is required.")
                else:
                    db.create_club(name.strip(), description.strip(), category, coordinator.strip(),
                                    meeting_day, meeting_time.strip())
                    st.success(f"Club '{name}' created successfully!")
                    st.rerun()

    with tab2:
        clubs = db.get_clubs()
        if not clubs:
            st.info("No clubs created yet.")
            return

        for club in clubs:
            with st.expander(f"🏛️ {club['name']}  ·  {club['category'] or 'General'}"):
                edit_key = f"edit_mode_{club['id']}"
                if edit_key not in st.session_state:
                    st.session_state[edit_key] = False

                if not st.session_state[edit_key]:
                    st.write(club["description"] or "No description.")
                    st.write(f"**Faculty Coordinator:** {club['faculty_coordinator']}")
                    st.write(f"**Meeting:** {club['meeting_day']} at {club['meeting_time']}")
                    st.write(f"**Members:** {db.get_club_member_count(club['id'])}")

                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✏️ Edit", key=f"edit_btn_{club['id']}"):
                            st.session_state[edit_key] = True
                            st.rerun()
                    with c2:
                        confirm_key = f"confirm_del_{club['id']}"
                        if st.session_state.get(confirm_key):
                            st.warning("Are you sure? This will also remove related memberships and events.")
                            cc1, cc2 = st.columns(2)
                            with cc1:
                                if st.button("✅ Yes, delete", key=f"yes_del_{club['id']}"):
                                    db.delete_club(club["id"])
                                    st.success("Club deleted.")
                                    st.rerun()
                            with cc2:
                                if st.button("Cancel", key=f"no_del_{club['id']}"):
                                    st.session_state[confirm_key] = False
                                    st.rerun()
                        else:
                            if st.button("🗑️ Delete", key=f"del_btn_{club['id']}"):
                                st.session_state[confirm_key] = True
                                st.rerun()
                else:
                    with st.form(f"edit_form_{club['id']}"):
                        new_name = st.text_input("Club Name", value=club["name"])
                        new_desc = st.text_area("Description", value=club["description"] or "")
                        new_cat = st.selectbox("Category", CATEGORIES,
                                                index=CATEGORIES.index(club["category"]) if club["category"] in CATEGORIES else 0)
                        new_coord = st.text_input("Faculty Coordinator", value=club["faculty_coordinator"] or "")
                        new_day = st.selectbox("Meeting Day", DAYS,
                                                index=DAYS.index(club["meeting_day"]) if club["meeting_day"] in DAYS else 0)
                        new_time = st.text_input("Meeting Time", value=club["meeting_time"] or "")

                        s1, s2 = st.columns(2)
                        with s1:
                            save = st.form_submit_button("💾 Save Changes")
                        with s2:
                            cancel = st.form_submit_button("Cancel")

                        if save:
                            if not new_name.strip():
                                st.error("Club name is required.")
                            else:
                                db.update_club(club["id"], new_name.strip(), new_desc.strip(), new_cat,
                                                new_coord.strip(), new_day, new_time.strip())
                                st.session_state[edit_key] = False
                                st.success("Club updated successfully!")
                                st.rerun()
                        if cancel:
                            st.session_state[edit_key] = False
                            st.rerun()
