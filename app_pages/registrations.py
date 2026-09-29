import streamlit as st
import pandas as pd
import database as db


def render():
    st.markdown("## 🎟️ Event Registrations")

    registrations = db.get_all_registrations()
    if not registrations:
        st.info("No event registrations yet.")
        return

    df = pd.DataFrame(registrations)

    col1, col2, col3 = st.columns(3)
    with col1:
        event_options = ["All"] + sorted(df["event_title"].unique().tolist())
        selected_event = st.selectbox("Filter by Event", event_options)
    with col2:
        club_options = ["All"] + sorted(df["club_name"].unique().tolist())
        selected_club = st.selectbox("Filter by Club", club_options)
    with col3:
        date_options = ["All"] + sorted(df["event_date"].unique().tolist())
        selected_date = st.selectbox("Filter by Date", date_options)

    filtered = df.copy()
    if selected_event != "All":
        filtered = filtered[filtered["event_title"] == selected_event]
    if selected_club != "All":
        filtered = filtered[filtered["club_name"] == selected_club]
    if selected_date != "All":
        filtered = filtered[filtered["event_date"] == selected_date]

    st.caption(f"Showing {len(filtered)} of {len(df)} registrations")

    display_df = filtered[["student_name", "email", "event_title", "club_name", "event_date", "registered_at"]].rename(
        columns={
            "student_name": "Student",
            "email": "Email",
            "event_title": "Event",
            "club_name": "Club",
            "event_date": "Event Date",
            "registered_at": "Registered On",
        }
    )
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    csv = display_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download CSV",
        data=csv,
        file_name="event_registrations.csv",
        mime="text/csv",
    )
