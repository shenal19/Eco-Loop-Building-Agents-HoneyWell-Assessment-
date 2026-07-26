"""
EcoLoop configuration.
Adjust EPLUS_INSTALL_PATH to match your local EnergyPlus install.
"""

import os

# --- EnergyPlus ---
# Windows default install path pattern. Change version folder if different.

EPLUS_INSTALL_PATH = os.environ.get(
    "EPLUS_INSTALL_PATH", r"C:\EnergyPlusV26-1-0"
)
IDF_PATH = os.environ.get(
    "ECOLOOP_IDF", os.path.join(os.path.dirname(__file__), "..", "building", "5ZoneAirCooled_modified.idf")
)
EPW_PATH = os.environ.get(
    "ECOLOOP_EPW", os.path.join(os.path.dirname(__file__), "..", "building", "weather.epw")
)
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")

# --- LLM (Ollama) ---
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct")

# --- Control loop ---
# How often (in simulation zone timesteps) the LLM is consulted.
# Every timestep = maximum responsiveness but higher LLM call volume.
# Set to e.g. 4 to consult once per hour if timestep=15min (4 steps/hr).
LLM_CALL_EVERY_N_STEPS = 12

# --- Comfort & efficiency targets given to the LLM ---
COMFORT_HEATING_MIN_C = 20.0   # never let heating setpoint request go below this
COMFORT_COOLING_MAX_C = 26.0   # never let cooling setpoint request go above this
HEATING_SETPOINT_DEFAULT_C = 21.0
COOLING_SETPOINT_DEFAULT_C = 24.0

# Zones present in 5ZoneAirCooled.idf
ZONE_NAMES = [
    "SPACE1-1", "SPACE2-1", "SPACE3-1", "SPACE4-1", "SPACE5-1",
]

# Schedule names that will be converted to Schedule:Constant and actuated
HEATING_SCHEDULE_NAME = "Htg-SetP-Sch"
COOLING_SCHEDULE_NAME = "Clg-SetP-Sch"
