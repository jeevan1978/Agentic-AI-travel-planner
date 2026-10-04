import streamlit as st
from datetime import date, timedelta

def render_sidebar():
    with st.sidebar:
        st.markdown("## 🗺️ Plan Your Trip")

        source_city = st.text_input("🏠 From (Source City)", placeholder="e.g. Mumbai")
        destination = st.text_input("📍 To (Destination)", placeholder="e.g. Goa")

        col_s, col_e = st.columns(2)
        with col_s:
            start_date = st.date_input("📅 Start Date", value=date.today() + timedelta(days=7))
        with col_e:
            end_date = st.date_input("📅 End Date", value=date.today() + timedelta(days=12))

        passengers = st.number_input("Travelers", min_value=1, max_value=100, value=1)
        random_seed = st.number_input("Selection seed", value=0, step=1)
        budget = st.text_input("💰 Budget (e.g. 30000 INR)", placeholder="30000 INR")

        transport_mode = st.selectbox(
            "🚗 Transport Mode",
            ["Flight", "Train"],
        )

        train_class = "3A"
        rail_distance_km = None
        if transport_mode == "Train":
            st.info("Enter the one-way railway distance from source to destination. This distance is used for each outbound and return leg. Fares are configured estimates, not live ticket quotes.")
            train_class = st.selectbox("Train class for budget", ["SL", "3A", "2A", "1A"], index=1)
            supplied = st.number_input("Source to destination railway distance (km)", min_value=0.0, value=None, step=1.0, placeholder="Enter one-way distance in km")
            rail_distance_km = supplied or None

        hotel_type = st.selectbox(
            "🏨 Hotel Type",
            ["Budget", "3-star", "4-star", "5-star"],
            index=1,
        )

        interest_options = [
            "History & Culture", "Nature & Adventure", "Food & Cuisine",
            "Beaches", "Shopping", "Nightlife", "Art & Museums", "Spirituality",
        ]
        interests = st.multiselect(
            "🎯 Interests",
            interest_options,
            default=["History & Culture", "Food & Cuisine"],
        )

        st.markdown("---")
        missing_distance = transport_mode == "Train" and rail_distance_km is None
        if missing_distance:
            st.warning("Enter a railway distance greater than zero to generate your train plan.")
        generate_btn = st.button("🚀 Generate Plan", use_container_width=True, type="primary", disabled=missing_distance)
        
        return {
            "source_city": source_city,
            "destination": destination,
            "start_date": start_date,
            "end_date": end_date,
            "budget": budget,
            "passengers": passengers,
            "random_seed": random_seed,
            "transport_mode": transport_mode,
            "train_class": train_class,
            "rail_distance_km": rail_distance_km,
            "hotel_type": hotel_type,
            "interests": interests,
            "generate_btn": generate_btn
        }
