import streamlit as st
import pandas as pd
import database as db


def render():
    st.markdown("## 👥 Club Membership Requests")

    memberships = db.get_all_memberships()
    if not memberships:
        st.info("No membership requests yet.")
        return

    status_filter = st.selectbox("Filter by status", ["Pending", "Approved", "Rejected", "All"])
    filtered = memberships if status_filter == "All" else [m for m in memberships if m["status"] == status_filter]

    if not filtered:
        st.info(f"No {status_filter.lower()} requests.")
        return

    st.caption(f"Showing {len(filtered)} request(s)")

    for m in filtered:
        col1, col2, col3, col4, col5, col6 = st.columns([2, 2.2, 1.6, 1.2, 0.8, 1.6])
        col1.write(f"**{m['student_name']}**")
        col2.write(m["email"])
        col3.write(m["club_name"])
        col4.write(m["course"] or "-")
        col5.write(m["year"] or "-")

        if m["status"] == "Pending":
            with col6:
                a, r = st.columns(2)
                with a:
                    if st.button("✅", key=f"approve_{m['id']}", help="Approve"):
                        db.update_membership_status(m["id"], "Approved")
                        st.success(f"{m['student_name']} approved for {m['club_name']}.")
                        st.rerun()
                with r:
                    if st.button("❌", key=f"reject_{m['id']}", help="Reject"):
                        db.update_membership_status(m["id"], "Rejected")
                        st.warning(f"{m['student_name']} rejected for {m['club_name']}.")
                        st.rerun()
        else:
            badge_class = "badge-approved" if m["status"] == "Approved" else "badge-rejected"
            col6.markdown(f'<span class="cc-badge {badge_class}">{m["status"]}</span>', unsafe_allow_html=True)

        st.markdown("<hr style='margin:4px 0;'>", unsafe_allow_html=True)
