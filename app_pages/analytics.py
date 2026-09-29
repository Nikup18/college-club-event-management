import streamlit as st
import pandas as pd
import plotly.express as px
import database as db


def render():
    st.markdown("## 📊 Analytics")
    st.caption("Deeper insights into club and event activity.")

    clubs = db.get_clubs()
    events = db.get_events()
    memberships = db.get_all_memberships()
    registrations = db.get_all_registrations()

    if not clubs:
        st.info("No data available yet. Create some clubs and events first.")
        return

    # 1. Number of students per club
    st.markdown("### 👥 Students per Club")
    member_counts = [{"Club": c["name"], "Students": db.get_club_member_count(c["id"])} for c in clubs]
    mdf = pd.DataFrame(member_counts)
    fig1 = px.bar(mdf, x="Club", y="Students", color="Students", color_continuous_scale="Purples",
                  title="Approved Members per Club")
    fig1.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
    st.plotly_chart(fig1, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🎟️ Event Registrations by Event")
        if registrations:
            rdf = pd.DataFrame(registrations)
            counts = rdf.groupby("event_title").size().reset_index(name="Registrations")
            fig2 = px.bar(counts, x="event_title", y="Registrations", title="Registrations per Event",
                          color="Registrations", color_continuous_scale="Teal")
            fig2.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                xaxis_title="", showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No registrations yet.")

    with col2:
        st.markdown("### 📅 Events by Club")
        if events:
            edf = pd.DataFrame(events)
            ecounts = edf.groupby("club_name").size().reset_index(name="Events")
            fig3 = px.pie(ecounts, names="club_name", values="Events", title="Event Distribution by Club", hole=0.4)
            fig3.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("No events yet.")

    col3, col4 = st.columns(2)

    with col3:
        st.markdown("### 📈 Monthly Registrations")
        if registrations:
            rdf = pd.DataFrame(registrations)
            rdf["month"] = pd.to_datetime(rdf["registered_at"]).dt.strftime("%Y-%m")
            monthly = rdf.groupby("month").size().reset_index(name="Registrations").sort_values("month")
            fig4 = px.line(monthly, x="month", y="Registrations", markers=True, title="Registrations Over Time")
            fig4.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                xaxis_title="Month")
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("No registration data yet.")

    with col4:
        st.markdown("### 🏆 Club Popularity")
        if memberships:
            memdf = pd.DataFrame(memberships)
            approved = memdf[memdf["status"] == "Approved"]
            if not approved.empty:
                pop = approved.groupby("club_name").size().reset_index(name="Members").sort_values("Members", ascending=True)
                fig5 = px.bar(pop, x="Members", y="club_name", orientation="h", title="Club Popularity Ranking",
                              color="Members", color_continuous_scale="Purples")
                fig5.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                    yaxis_title="", showlegend=False)
                st.plotly_chart(fig5, use_container_width=True)
            else:
                st.info("No approved memberships yet.")
        else:
            st.info("No membership data yet.")
