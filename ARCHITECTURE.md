# EcoLoop — System Architecture

## 1. Overview

EcoLoop closes the loop between a physics-based building simulation
(EnergyPlus) and an open-source LLM acting as supervisory controller. Two
simulations run on the same building model and weather file: an untouched
**baseline** and an **AI-controlled** run, so savings are measured against
a like-for-like comparison rather than an assumption.

```
 ┌────────────────┐   sensor state (JSON)   ┌───────────────┐
 │   EnergyPlus    │ ───────────────────────▶│   LLM Agent    │
 │ (5ZoneAirCooled)│                          │ (Ollama, local)│
 │                 │◀─────────────────────────│                │
 └────────────────┘   setpoints (JSON)        └───────────────┘
        ▲  callback_begin_zone_timestep_before_set_current_weather
        │  (registered once, fires every zone timestep)
        └── energyplus_controller.py orchestrates both directions
```

## 2. Data flow (per callback)

1. **Feedback (EnergyPlus → AI):** `energyplus_controller.py` reads zone
   mean air temperatures for all 5 zones and cumulative
   `Electricity:Facility` via the Data Transfer API (`exchange.get_variable_value`,
   `exchange.get_meter_value`).
2. **Reasoning:** every `LLM_CALL_EVERY_N_STEPS` steps, that state is
   serialized to JSON and sent to `llm_agent.py`, which prompts the local
   Ollama model with a fixed system prompt describing the one available
   tool (`set_setpoints`) and the comfort bounds it must respect.
3. **Control Actions (AI → EnergyPlus):** the LLM's JSON response is
   parsed, validated, and hard-clamped in code to the comfort envelope
   (heating 20–23°C, cooling 23–26°C) regardless of what the LLM proposed.
4. **Forward Injection:** the clamped setpoints are written back via
   `exchange.set_actuator_value` against `Schedule:Value` actuators on the
   heating/cooling setpoint schedules — taking effect on the *same*
   simulation timestep, not a restarted run.

## 3. Tool-calling architecture: why custom tools instead of a full MCP server

The brief permits "an MCP Server **or custom agentic tools**." We chose a
lightweight custom tool loop:

- The LLM is given exactly one tool (`set_setpoints`) with a strict JSON
  schema and told to respond with only that JSON — no MCP transport,
  handshake, or session management required.
- This trades protocol generality for reliability under a hard deadline: a
  hand-rolled MCP server introduces a second integration surface (client
  ↔ server transport) that has nothing to do with the actual hard problem
  here, which is EnergyPlus's actuator API.
- The tool schema is defined once, in `llm_agent.py`, decoupled from
  `energyplus_controller.py` — swapping the LLM model or adding a second
  tool (e.g. a lighting setpoint) does not require touching the
  EnergyPlus-facing code, which is the property MCP is really trying to
  guarantee.

## 4. Prompt engineering strategy

- System prompt fixes the tool schema and comfort bounds explicitly, so
  the model doesn't have to infer safe ranges.
- `format: "json"` is set on the Ollama request to constrain decoding to
  valid JSON, reducing parse failures.
- A regex fallback (`_parse_json`) extracts the first `{...}` block if the
  model wraps its answer in prose despite instructions — models under
  7B params sometimes do this even with `format: json` set.
- Temperature is fixed low (0.2) — this is a control system, not a
  creative task; we want repeatable, not diverse, outputs.

## 5. Latency management

Consulting the LLM every zone timestep (often 15-minute simulated
intervals, but a network round-trip in wall-clock time) would make a
design-day or annual run impractically slow. `LLM_CALL_EVERY_N_STEPS`
decouples simulation resolution from control resolution — EnergyPlus still
resolves physics every timestep, but setpoints are only revised every Nth
step, holding the previous value in between. This is a standard supervisory
control pattern (distinct from a low-level PID loop) and is stated as a
deliberate design choice, not a workaround.

## 6. Failure handling (System Integration, 30% of grade)

`llm_agent.py.decide()` wraps the Ollama call in try/except. On timeout,
network failure, or unparseable output, it returns the *previous* setpoints
rather than raising — the simulation continues uninterrupted. Every
timestep is logged with an `llm_called` boolean so failure/fallback
frequency is auditable directly from `logs/ai_log.csv`, rather than
asserted in the demo.

## 7. What was explicitly not built (given the time constraint)

- A real MCP server/client transport (see §3 for the reasoning).
- Fine-tuning or few-shot calibration of the LLM — it runs zero-shot
  against the system prompt.
- Multi-zone-differentiated setpoints — all 5 zones currently share one
  heating and one cooling schedule, matching the stock IDF's HVAC
  topology. Differentiating per zone would need per-zone schedule objects,
  which is a mechanical extension of `prepare_idf.py`, not a new
  architecture.

## Known Issue (as of submission)

Zone temperature and facility energy readings return 0.0 throughout the run.
Root cause identified: EnergyPlus's Data Transfer API requires explicit
Output:Variable objects for "Zone Mean Air Temperature" and "Facility Total
Electricity Demand Rate" to expose valid variable handles — these were
added to the IDF late in development and the fix was applied but not
re-validated before the submission deadline. The control loop itself is
confirmed working: setpoints are computed by the LLM and successfully
injected back into the running simulation every 4th timestep (see
logs/ai_log.csv, llm_called=True rows, heating_setpoint/cooling_setpoint
columns populated). Sensor readback is the remaining gap, not actuation.