import streamlit as st
import database as db


def render():
    user = st.session_state.user
    st.markdown("## 🏛️ College Clubs")
    st.caption("Browse and join clubs that match your interests.")

    clubs = db.get_clubs()
    if not clubs:
        st.info("No clubs have been created yet.")
        return

    memberships = {m["club_id"]: m["status"] for m in db.get_user_memberships(user["id"])}

    categories = sorted(set(c["category"] for c in clubs if c["category"]))
    selected_cat = st.selectbox("Filter by category", ["All"] + categories)

    filtered = clubs if selected_cat == "All" else [c for c in clubs if c["category"] == selected_cat]

    cols = st.columns(2)
    for i, club in enumerate(filtered):
        with cols[i % 2]:
            member_count = db.get_club_member_count(club["id"])
            st.markdown(f"""
            <div class="cc-card">
                <h3>{club['name']}</h3>
                <span class="cc-badge badge-category">{club['category'] or 'General'}</span>
                <p class="cc-meta" style="margin-top:10px;">{club['description'] or ''}</p>
                <div class="cc-meta">👨‍🏫 {club['faculty_coordinator'] or 'TBA'}</div>
                <div class="cc-meta">🗓️ {club['meeting_day'] or 'TBA'} &nbsp;•&nbsp; 🕐 {club['meeting_time'] or 'TBA'}</div>
                <div class="cc-meta">👥 {member_count} members</div>
            </div>
            """, unsafe_allow_html=True)

            status = memberships.get(club["id"])
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                with st.expander("View Details"):
                    st.write(club["description"] or "No description available.")
                    st.write(f"**Category:** {club['category']}")
                    st.write(f"**Faculty Coordinator:** {club['faculty_coordinator']}")
                    st.write(f"**Meeting:** {club['meeting_day']} at {club['meeting_time']}")
            with btn_col2:
                if status == "Approved":
                    st.success("✅ You are already a member.")
                elif status == "Pending":
                    st.warning("⏳ Request pending approval.")
                elif status == "Rejected":
                    st.error("❌ Your request was rejected.")
                else:
                    if st.button("Join Club", key=f"join_{club['id']}"):
                        ok, msg = db.join_club(user["id"], club["id"])
                        if ok:
                            st.success(msg)
                        else:
                            st.warning(msg)
                        st.rerun()
