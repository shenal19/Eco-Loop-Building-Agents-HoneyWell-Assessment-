"""
dashboard.py — Quantitative Savings Dashboard

Run with: streamlit run dashboard.py
(from inside the dashboard/ folder, after orchestrator.py has produced logs)
"""

import os

import pandas as pd
import streamlit as st

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
BASELINE_LOG = os.path.join(LOG_DIR, "baseline_log.csv")
AI_LOG = os.path.join(LOG_DIR, "ai_log.csv")

st.set_page_config(page_title="EcoLoop Savings Dashboard", layout="wide")
st.title("EcoLoop Building Agents — Savings Dashboard")

if not (os.path.exists(BASELINE_LOG) and os.path.exists(AI_LOG)):
    st.error("Run `python backend/orchestrator.py` first to generate logs.")
    st.stop()

baseline = pd.read_csv(BASELINE_LOG)
ai = pd.read_csv(AI_LOG)

baseline_final = baseline["facility_kwh"].iloc[-1]
ai_final = ai["facility_kwh"].iloc[-1]
savings_pct = (1 - ai_final / baseline_final) * 100 if baseline_final else 0

col1, col2, col3 = st.columns(3)
col1.metric("Baseline energy (kWh)", f"{baseline_final:,.1f}")
col2.metric("AI-controlled energy (kWh)", f"{ai_final:,.1f}", delta=f"{-savings_pct:.1f}%")
col3.metric("Net reduction", f"{savings_pct:.2f}%")

st.subheader("Cumulative Facility Energy Use")
compare_df = pd.DataFrame({
    "timestep": baseline["timestep"],
    "Baseline (kWh)": baseline["facility_kwh"],
    "AI-controlled (kWh)": ai["facility_kwh"].reindex(range(len(baseline))).values,
})
st.line_chart(compare_df.set_index("timestep"))

st.subheader("Zone Temperatures — AI-controlled run")
zone_cols = [c for c in ai.columns if c.startswith("temp_")]
st.line_chart(ai.set_index("timestep")[zone_cols])

st.subheader("Setpoints over time — AI-controlled run")
st.line_chart(ai.set_index("timestep")[["heating_setpoint", "cooling_setpoint"]])

st.subheader("Comfort check")
min_htg = ai["heating_setpoint"].min()
max_clg = ai["cooling_setpoint"].max()
st.write(f"Min heating setpoint requested: **{min_htg:.2f}C**")
st.write(f"Max cooling setpoint requested: **{max_clg:.2f}C**")
st.write(f"LLM calls: **{int(ai['llm_called'].sum())}** out of {len(ai)} timesteps")

with st.expander("Raw AI-run log"):
    st.dataframe(ai)
