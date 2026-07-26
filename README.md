# EcoLoop Building Agents

Closed-loop AI control of a live EnergyPlus simulation: an open-source LLM
reads real-time zone/energy data and injects new HVAC setpoints back into
the running simulation, compared against an unmodified baseline run.

## 1. Prerequisites

- **EnergyPlus** (v9.5+, tested against v24.1) installed locally.
  Download: https://energyplus.net/downloads
- **Ollama** installed locally: https://ollama.com/download
- Python 3.9+

## 2. Setup

```bash
# 1. Install Python deps
pip install -r requirements.txt

# 2. Pull the LLM
ollama pull qwen2.5:7b-instruct

# 3. Set your EnergyPlus install path (Windows example)
# Edit backend/config.py -> EPLUS_INSTALL_PATH
# or set an env var:
setx EPLUS_INSTALL_PATH "C:\EnergyPlusV24-1-0"

# 4. Copy the example building + weather files into building/
#    (both ship inside your EnergyPlus install)
copy "C:\EnergyPlusV24-1-0\ExampleFiles\5ZoneAirCooled.idf" building\
copy "C:\EnergyPlusV24-1-0\WeatherData\USA_CO_Golden-NREL.724666_TMY3.epw" building\weather.epw

# 5. Convert the thermostat schedules so they're live-actuatable
cd building
python prepare_idf.py
cd ..
```

## 3. Run the closed loop

```bash
# Start Ollama in the background if not already running
ollama serve

# Run baseline + AI-controlled simulations back to back
cd backend
python orchestrator.py
```

This produces `logs/baseline_log.csv` and `logs/ai_log.csv`, and prints a
percentage energy savings summary to the console.

## 4. View the dashboard

```bash
cd dashboard
streamlit run dashboard.py
```

## 5. Project structure

```
EcoLoop/
├── backend/
│   ├── config.py               # paths, control targets, model choice
│   ├── energyplus_controller.py # EnergyPlus API wrapper + callback loop
│   ├── llm_agent.py            # Ollama tool-calling agent
│   └── orchestrator.py         # runs baseline + AI sims, prints savings
├── building/
│   ├── prepare_idf.py          # converts schedules to actuatable form
│   ├── 5ZoneAirCooled.idf      # (you provide — from your EP install)
│   └── weather.epw             # (you provide)
├── dashboard/
│   └── dashboard.py            # Streamlit savings/comfort dashboard
├── logs/                       # generated CSV logs (gitignored contents)
├── ARCHITECTURE.md             # system architecture writeup (deliverable #4)
└── requirements.txt
```

## 6. Known constraints / what to say in the demo

- LLM is consulted every `LLM_CALL_EVERY_N_STEPS` timesteps (default: every
  4th zone timestep), not every single timestep — this bounds latency and
  Ollama call volume across a full annual/design-day run. State this
  explicitly in the demo; it's a deliberate latency-management decision,
  not a limitation you missed.
- If the LLM call fails or returns unparseable output, the controller falls
  back to holding the previous setpoint rather than crashing the sim — this
  is what "System Integration (30%)" is graded on, so don't cut it even
  under time pressure.
- Comfort bounds are hard-clamped in code (`_clamp_heating`/`_clamp_cooling`
  in `energyplus_controller.py`), not just requested via prompt — the LLM
  can't override them even if it hallucinates a bad value.
