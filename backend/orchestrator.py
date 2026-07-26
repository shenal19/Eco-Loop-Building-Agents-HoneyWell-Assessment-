"""
orchestrator.py

Entry point. Runs two EnergyPlus simulations back to back on the same
IDF/EPW:
  1. baseline  — untouched, fixed schedules (ai_enabled=False)
  2. ai        — LLM-controlled closed loop (ai_enabled=True)

Then prints a savings summary. The dashboard (dashboard/dashboard.py)
visualizes both logs.

Usage: python orchestrator.py
"""

import csv
import os

import config
from energyplus_controller import EcoLoopController
from llm_agent import LLMAgent


def summarize(log_path: str) -> float:
    """Return final cumulative facility kWh from a run's log."""
    last_kwh = 0.0
    with open(log_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            last_kwh = float(row["facility_kwh"])
    return last_kwh


def main():
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("STEP 1/2: Baseline run (no AI control)")
    print("=" * 60)
    baseline = EcoLoopController(run_label="baseline", ai_enabled=False)
    baseline.run()

    print("=" * 60)
    print("STEP 2/2: AI-controlled run (EcoLoop closed loop)")
    print("=" * 60)
    agent = LLMAgent()
    ai_run = EcoLoopController(run_label="ai", ai_enabled=True, agent=agent)
    ai_run.run()

    baseline_kwh = summarize(baseline.log_path)
    ai_kwh = summarize(ai_run.log_path)
    savings_pct = (1 - ai_kwh / baseline_kwh) * 100 if baseline_kwh else 0.0

    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Baseline facility energy: {baseline_kwh:.2f} kWh")
    print(f"AI-controlled energy:     {ai_kwh:.2f} kWh")
    print(f"Net change:               {savings_pct:+.2f}%")
    print(f"LLM calls made:           {agent.call_count} (fallbacks: {agent.fallback_count})")
    print(f"\nLogs: {baseline.log_path}\n      {ai_run.log_path}")
    print("Run `streamlit run ../dashboard/dashboard.py` to view the comparison.")


if __name__ == "__main__":
    main()
