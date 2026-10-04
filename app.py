import streamlit as st
import requests

from ui.sidebar import render_sidebar
from ui.day_card import render_day_card
from ui.budget_section import render_budget_section

st.set_page_config(
    page_title="VoyageAI — AI Travel Planner",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

BACKEND_URL = "http://localhost:8080"

# Render CSS
def load_css():
    try:
        with open("ui/style.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

load_css()

st.markdown(
    """
    <div class="hero-banner">
        <h1>✈️ VoyageAI 2.0 (Agentic Planner)</h1>
        <p>Your AI-powered travel planner — verified day-by-day agentic planning.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Render Modular Sidebar
sidebar_data = render_sidebar()

if sidebar_data["generate_btn"]:
    errors = []
    if not sidebar_data["source_city"].strip():
        errors.append("Source city is required.")
    if not sidebar_data["destination"].strip():
        errors.append("Destination is required.")
    if sidebar_data["end_date"] < sidebar_data["start_date"]:
        errors.append("End date must be on or after start date.")

    if errors:
        for e in errors:
            st.error(e)
        st.stop()

    payload = {
        "source_city": sidebar_data["source_city"].strip(),
        "destination": sidebar_data["destination"].strip(),
        "start_date": sidebar_data["start_date"].strftime("%Y-%m-%d"),
        "end_date": sidebar_data["end_date"].strftime("%Y-%m-%d"),
        "budget": sidebar_data["budget"].strip() or "0 INR",
        "transport_mode": sidebar_data["transport_mode"],
        "train_class": sidebar_data["train_class"],
        "rail_distance_km": sidebar_data["rail_distance_km"],
        "hotel_type": sidebar_data["hotel_type"],
        "interests": sidebar_data["interests"],
        "passengers": sidebar_data["passengers"],
        "random_seed": sidebar_data["random_seed"],
    }

    with st.spinner("🧠 VoyageAI Agent is iteratively crafting your day-by-day trip…"):
        try:
            response = requests.post(f"{BACKEND_URL}/api/plan", json=payload, timeout=(10, 1800))
        except requests.exceptions.ConnectionError:
            st.error("⚠️ **Backend server is not running.**")
            st.stop()
        except Exception as exc:
            st.error(f"🔌 **Network error:** {exc}")
            st.stop()

    if response.status_code != 200:
        st.error(f"❌ **Backend returned HTTP {response.status_code}.**")
        st.stop()

    data = response.json().get("data", {})
    planning_status = data.get("metadata", {}).get("planning_status", "PARTIAL")
    if planning_status == "FAILED":
        st.error("No itinerary was generated. Check the model/API warnings below before trying again.")
    elif planning_status == "PARTIAL":
        st.warning("Your itinerary is incomplete. Some information or day schedules are unavailable.")
    else:
        st.success("Your travel plan is ready.")
    known_prices = any(entry.get("amount") is not None for entry in data.get("budget", {}).get("entries", []))

    # Top-Level Trip Info
    days_count = data.get("metadata", {}).get("total_days", 1)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏙️ From", sidebar_data["source_city"])
    col2.metric("📍 To", sidebar_data["destination"])
    col3.metric("📅 Duration", f"{days_count} day(s)")
    col4.metric("💰 Known subtotal", f"₹{data.get('budget', {}).get('known_subtotal', 0):,}" if known_prices else "Unavailable")
    
    st.markdown("---")

    st.subheader("Transport legs and accommodation periods")
    for leg in data.get("transport", []):
        st.write(f"{leg['mode']}: {leg['origin']} → {leg['destination']} ({leg['departure_date']})")
        result = leg.get("result", {})
        if result.get("fares"):
            st.caption(f"Reported rail distance: {result['distance_km']} km. Configured estimates per traveler; not live ticket fares.")
            st.dataframe(result["fares"], use_container_width=True)
            distance = result.get("distance", {})
            st.write("Distance source:", distance.get("source", "Unavailable"))
        elif result.get("success"):
            st.write(result.get("airline", "Carrier unavailable"), result.get("price", "Price unavailable"), result.get("currency", ""))
        else:
            st.info(result.get("reason", "Transport was not searched; information unavailable."))
    with st.expander("Accommodation periods and provider details"):
        st.json(data.get("accommodation", []))

    # Day by day rendering
    daily_plans = data.get("days", [])
    if not daily_plans:
        st.info("No detailed daily plan was generated.")
    else:
        for plan in daily_plans:
            render_day_card(plan)

    # Budget Breakdown & Agent Activity
    budget_breakdown = data.get("budget", {})
    warnings = data.get("warnings", [])
    agent_activity = data.get("tool_trace", [])
    
    if budget_breakdown:
        render_budget_section(budget_breakdown, warnings, agent_activity)

else:
    st.markdown(
        """
        <div style="text-align:center;padding:3rem 1rem;color:#6b7a99;">
            <div style="font-size:4rem;margin-bottom:1rem;">🌍</div>
            <h3 style="color:#3a4a6b;">Ready to explore with Agents?</h3>
            <p>Fill in your preferences in the sidebar and the Agent will build a day-by-day itinerary.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )