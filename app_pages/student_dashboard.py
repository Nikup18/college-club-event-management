import streamlit as st
import plotly.express as px
import pandas as pd
import database as db


def render():
    user = st.session_state.user
    st.markdown(f"## 👋 Welcome back, {user['name'].split(' ')[0]}!")
    st.caption("Here's what's happening in your college clubs and events.")

    clubs = db.get_clubs()
    events = db.get_events(upcoming_only=True)
    memberships = db.get_user_memberships(user["id"])
    registrations = db.get_user_registrations(user["id"])

    joined_clubs = [m for m in memberships if m["status"] == "Approved"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏛️ Available Clubs", len(clubs))
    col2.metric("✅ Clubs Joined", len(joined_clubs))
    col3.metric("📅 Upcoming Events", len(events))
    col4.metric("🎟️ Events Registered", len(registrations))

    st.markdown("---")

    left, right = st.columns([1.3, 1])

    with left:
        st.markdown("### 📅 Upcoming Events")
        if events:
            for e in events[:5]:
                seats_left = e["capacity"] - db.get_event_registration_count(e["id"])
                st.markdown(f"""
                <div class="cc-card">
                    <h3>{e['title']}</h3>
                    <div class="cc-meta">🏛️ {e['club_name']} &nbsp;|&nbsp; 📅 {e['date']} &nbsp;|&nbsp; 🕐 {e.get('time') or 'TBA'}</div>
                    <div class="cc-meta">📍 {e.get('venue') or 'TBA'} &nbsp;|&nbsp; 🪑 {seats_left} seats left</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No upcoming events at the moment. Check back soon!")

    with right:
        st.markdown("### 📢 Recent Announcements")
        announcements = db.get_announcements()
        if announcements:
            for a in announcements[:3]:
                st.markdown(f"""
                <div class="cc-card">
                    <h3 style="font-size:1.05rem;">{a['title']}</h3>
                    <div class="cc-meta">{a['content'][:120]}{'...' if len(a['content']) > 120 else ''}</div>
                    <div class="cc-meta" style="margin-top:6px;">🗓️ {a['created_at'][:10]}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No announcements yet.")

    st.markdown("---")
    st.markdown("### 📊 Club Activity Overview")

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        all_events = db.get_events()
        if all_events:
            ev_df = pd.DataFrame(all_events)
            counts = ev_df.groupby("club_name").size().reset_index(name="Events")
            fig = px.bar(counts, x="club_name", y="Events", title="Events by Club",
                         color="Events", color_continuous_scale="Purples")
            fig.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)",
                               paper_bgcolor="rgba(0,0,0,0)", xaxis_title="", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No event data yet.")

    with chart_col2:
        if clubs:
            member_counts = [{"Club": c["name"], "Members": db.get_club_member_count(c["id"])} for c in clubs]
            mdf = pd.DataFrame(member_counts)
            fig2 = px.pie(mdf, names="Club", values="Members", title="Club Membership Share", hole=0.45)
            fig2.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No club data yet.")
