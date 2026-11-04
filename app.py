"""
TerraVision — Website
Run:  streamlit run app.py
"""

import altair as alt
import pandas as pd
import requests
import streamlit as st

from terravision_core import (MONTHS, PERFORMANCE_RATIO, get_sunlight,
                              get_elevations, calc_slope, sunlight_score,
                              land_score, verdict, get_land_use, classify_land,
                              RADIUS_M)

# ---- 1. Page setup ----
st.set_page_config(page_title="TerraVision", page_icon="🛰️")
st.title("🛰️ TerraVision")
st.subheader("Solar site assessment from satellite data")
st.write("Enter any location and get a solar suitability score in seconds, "
         "using NASA sunlight and elevation data.")

# ---- 2. Input boxes ----
site_name = st.text_input("Site name", "Pavagada")
col1, col2 = st.columns(2)
lat = col1.number_input("Latitude", value=14.10, min_value=-60.0,
                        max_value=60.0, format="%.4f")
lon = col2.number_input("Longitude", value=77.28, min_value=-180.0,
                        max_value=180.0, format="%.4f")


# ---- 3. Fetch data (remembered, so the same place isn't fetched twice) ----
@st.cache_data
def fetch_data(lat, lon):
    elev = get_elevations(lat, lon)
    sun, temp = get_sunlight(lat, lon)
    land_use = get_land_use(lat, lon)
    return elev, sun, temp, land_use


# ---- 4. When the button is clicked, build the report ----
if st.button("Analyse site", type="primary"):
    try:
        with st.spinner("Fetching satellite data..."):
            elev, sun, temp, land_use = fetch_data(lat, lon)
    except requests.RequestException:
        st.error("Couldn't reach the data service. Wait a few seconds and try again.")
        st.stop()

    if None in elev.values():
        st.error("No elevation data for this spot (it may be sea). Try another location.")
        st.stop()

    # --- calculations (same as step 3) ---
    annual_sun = sun["ANN"]
    yield_per_kwp = annual_sun * 365 * PERFORMANCE_RATIO
    slope, aspect, facing = calc_slope(elev)
    sun_pts = sunlight_score(annual_sun)
    land_pts = land_score(slope, facing)
    land_type, use_pts, buildable = classify_land(land_use)
    overall = 0.5 * sun_pts + 0.3 * land_pts + 0.2 * use_pts
    if not buildable:
        overall = min(overall, 30)     # can't build a solar farm on a city

    # --- map ---
    st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}), zoom=11)

    # --- scores ---
    st.header(f"Report: {site_name}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Overall score", f"{overall:.0f} / 100")
    c2.metric("Sunlight", f"{sun_pts:.0f}")
    c3.metric("Slope", f"{land_pts:.0f}")
    c4.metric("Land use", f"{use_pts:.0f}")

    message = f"**Verdict: {verdict(overall)}**"
    if not buildable:
        st.error(f"**Verdict: NOT SUITABLE - {land_type.lower()}, "
                 "a solar farm can't be built here**")
    elif overall >= 65:
        st.success(message)
    elif overall >= 50:
        st.warning(message)
    else:
        st.error(message)

    # --- sunlight section ---
    st.subheader("☀️ Sunlight")
    chart_data = pd.DataFrame({
        "Month": MONTHS,
        "Sunlight (kWh/m²/day)": [sun[m] for m in MONTHS],
    })
    chart = alt.Chart(chart_data).mark_bar(color="#f5a623").encode(
        x=alt.X("Month", sort=MONTHS),
        y="Sunlight (kWh/m²/day)",
    )
    st.altair_chart(chart, width="stretch")

    best = max(MONTHS, key=lambda m: sun[m])
    worst = min(MONTHS, key=lambda m: sun[m])
    s1, s2, s3 = st.columns(3)
    s1.metric("Sunlight (kWh/m²/day)", f"{annual_sun:.2f}")
    s2.metric("Yield (kWh/kWp/year)", f"{yield_per_kwp:,.0f}")
    s3.metric("Avg temperature", f"{temp['ANN']:.1f} °C")
    st.write(f"Best month: **{best}** · Worst month: **{worst}**")

    # --- land section ---
    st.subheader("⛰️ Land")
    l1, l2, l3 = st.columns(3)
    l1.metric("Ground height", f"{elev['centre']:.0f} m")
    l2.metric("Slope", f"{slope:.1f}°")
    l3.metric("Faces", facing)

    st.subheader("🏘️ Land use")
    st.write(f"**{land_type}** (within {RADIUS_M} m)")
    u1, u2, u3, u4 = st.columns(4)
    u1.metric("Buildings", land_use["buildings"])
    u2.metric("Water", land_use["water"])
    u3.metric("Forest", land_use["forest"])
    u4.metric("Farmland", land_use["farmland"])

    st.caption("Data: NASA POWER (sunlight), NASA SRTM 30 m via OpenTopoData (elevation), "
               "© OpenStreetMap contributors (land use). "
               "Estimates only — confirm with an on-site survey before investing.")