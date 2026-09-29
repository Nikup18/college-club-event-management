import streamlit as st
import pandas as pd
import plotly.express as px
import database as db


def render():
    st.markdown("## 🛠️ Admin Dashboard")
    st.caption("Overview of college club & event activity.")

    stats = db.get_stats()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👨‍🎓 Total Students", stats["total_students"])
    col2.metric("🏛️ Total Clubs", stats["total_clubs"])
    col3.metric("📅 Total Events", stats["total_events"])
    col4.metric("🎟️ Total Registrations", stats["total_registrations"])

    st.markdown("---")

    events = db.get_events(upcoming_only=True)
    clubs = db.get_clubs()

    left, right = st.columns([1.2, 1])
    with left:
        st.markdown("### 📅 Upcoming Events")
        if events:
            for e in events[:5]:
                reg_count = db.get_event_registration_count(e["id"])
                st.markdown(f"""
                <div class="cc-card">
                    <h3 style="font-size:1.05rem;">{e['title']}</h3>
                    <div class="cc-meta">🏛️ {e['club_name']} &nbsp;|&nbsp; 📅 {e['date']} &nbsp;|&nbsp; 🪑 {reg_count}/{e['capacity']} registered</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No upcoming events.")

    with right:
        st.markdown("### 🏆 Most Popular Clubs")
        if clubs:
            pop = sorted(
                [{"Club": c["name"], "Members": db.get_club_member_count(c["id"])} for c in clubs],
                key=lambda x: x["Members"], reverse=True
            )
            for p in pop[:5]:
                st.markdown(f"- **{p['Club']}** — {p['Members']} members")
        else:
            st.info("No clubs yet.")

    st.markdown("---")
    st.markdown("### 📊 Statistics")

    c1, c2 = st.columns(2)
    with c1:
        regs = db.get_all_registrations()
        if regs:
            df = pd.DataFrame(regs)
            counts = df.groupby("event_title").size().reset_index(name="Registrations")
            fig = px.bar(counts, x="event_title", y="Registrations", title="Event Registration Statistics",
                         color="Registrations", color_continuous_scale="Teal")
            fig.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                               xaxis_title="", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No registrations yet.")

    with c2:
        mems = db.get_all_memberships()
        if mems:
            mdf = pd.DataFrame(mems)
            mcounts = mdf[mdf["status"] == "Approved"].groupby("club_name").size().reset_index(name="Members")
            if not mcounts.empty:
                fig2 = px.pie(mcounts, names="club_name", values="Members", title="Club Membership Statistics", hole=0.45)
                fig2.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No approved memberships yet.")
        else:
            st.info("No membership data yet.")
