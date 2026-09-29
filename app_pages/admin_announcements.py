import streamlit as st
import database as db


def render():
    st.markdown("## 📢 Manage Announcements")

    with st.form("create_announcement_form", clear_on_submit=True):
        title = st.text_input("Title *")
        content = st.text_area("Content *")
        submitted = st.form_submit_button("Post Announcement")
        if submitted:
            if not title.strip() or not content.strip():
                st.error("Both title and content are required.")
            else:
                db.create_announcement(title.strip(), content.strip())
                st.success("Announcement posted!")
                st.rerun()

    st.markdown("---")
    st.markdown("### 📋 All Announcements")

    announcements = db.get_announcements()
    if not announcements:
        st.info("No announcements yet.")
        return

    for a in announcements:
        col1, col2 = st.columns([5, 1])
        with col1:
            st.markdown(f"""
            <div class="cc-card">
                <h3 style="font-size:1.05rem;">{a['title']}</h3>
                <div class="cc-meta" style="margin-bottom:6px;">🗓️ {a['created_at'][:10]}</div>
                <p style="color:#EAEAF5;">{a['content']}</p>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            if st.button("🗑️ Delete", key=f"del_ann_{a['id']}"):
                db.delete_announcement(a["id"])
                st.success("Announcement deleted.")
                st.rerun()
