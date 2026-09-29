import streamlit as st
import database as db


def render():
    st.markdown("## 📢 Announcements")
    st.caption("Stay up to date with the latest college news.")

    announcements = db.get_announcements()
    if not announcements:
        st.info("No announcements have been posted yet.")
        return

    for a in announcements:
        st.markdown(f"""
        <div class="cc-card">
            <h3>{a['title']}</h3>
            <div class="cc-meta" style="margin-bottom:8px;">🗓️ {a['created_at'][:10]}</div>
            <p style="color:#EAEAF5;">{a['content']}</p>
        </div>
        """, unsafe_allow_html=True)
