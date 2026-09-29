import streamlit as st
import pandas as pd
import database as db


def render():
    st.markdown("## 👨‍🎓 Registered Users")

    search = st.text_input("🔍 Search by name or email")
    users = db.get_all_users(search=search if search else None)

    if not users:
        st.info("No users found.")
        return

    df = pd.DataFrame(users)
    display_df = df[["name", "email", "course", "year", "role", "created_at"]].rename(columns={
        "name": "Name",
        "email": "Email",
        "course": "Course",
        "year": "Year",
        "role": "Role",
        "created_at": "Created On",
    })
    st.caption(f"{len(display_df)} user(s) found")
    st.dataframe(display_df, use_container_width=True, hide_index=True)
