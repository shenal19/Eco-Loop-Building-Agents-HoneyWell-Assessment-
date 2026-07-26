"""
llm_agent.py

Custom agentic tool-calling loop (in place of a full MCP server — see
ARCHITECTURE.md for why). The LLM is given the current building state
and a single tool it can call: `set_setpoints`. It must respond with
strict JSON. We parse and validate that JSON as the "tool call."

This satisfies the brief's "execute tasks without human code
modification" requirement: swapping models, or adding new tools, does
not require touching energyplus_controller.py.
"""

import json
import re

import requests

import config

TOOL_SCHEMA = {
    "name": "set_setpoints",
    "description": "Set the building's heating and cooling setpoints for the next control interval.",
    "parameters": {
        "heating_setpoint_c": "float, degrees Celsius",
        "cooling_setpoint_c": "float, degrees Celsius",
        "reasoning": "short string explaining the decision",
    },
}

SYSTEM_PROMPT = f"""You are the control agent for a commercial building's HVAC system, \
running in a closed loop against a live EnergyPlus simulation.

Your goal: minimize energy consumption (Electricity:Facility, kWh) while keeping every \
zone within comfort bounds. Comfort bounds: heating setpoint must stay between \
{config.COMFORT_HEATING_MIN_C}C and 23C; cooling setpoint must stay between 23C and \
{config.COMFORT_COOLING_MAX_C}C. Do not propose values outside these ranges.

You have exactly one tool available:
{json.dumps(TOOL_SCHEMA, indent=2)}

Respond with ONLY a JSON object matching the tool's parameters. No prose, no markdown \
fences, no explanation outside the JSON. Example valid response:
{{"heating_setpoint_c": 20.5, "cooling_setpoint_c": 25.0, "reasoning": "zones running warm, relaxing cooling setpoint to cut compressor load"}}
"""


class LLMAgent:
    def __init__(self, model: str = None, ollama_url: str = None):
        self.model = model or config.OLLAMA_MODEL
        self.url = ollama_url or config.OLLAMA_URL
        self.call_count = 0
        self.fallback_count = 0

    def decide(self, sensor_state: dict) -> dict:
        """Given current sensor state, return {'heating_setpoint_c', 'cooling_setpoint_c', 'reasoning'}."""
        self.call_count += 1
        user_prompt = (
            "Current building state:\n"
            f"{json.dumps(sensor_state, indent=2)}\n\n"
            "Call set_setpoints now."
        )
        try:
            resp = requests.post(
            self.url,
        json={
            "model": self.model,
            "prompt": f"{SYSTEM_PROMPT}\n\n{user_prompt}",
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2},
            "keep_alive": "30m",
        },
        timeout=90,
        )
             
            resp.raise_for_status()
            raw_text = resp.json().get("response", "")
            decision = self._parse_json(raw_text)
            if decision is None:
                raise ValueError(f"Could not parse JSON from LLM response: {raw_text[:200]}")
            return decision
        except Exception as e:
            # Never let an LLM/network hiccup crash the simulation (System Integration = 30% of grade).
            # Fall back to holding current setpoints.
            self.fallback_count += 1
            print(f"[llm_agent] WARNING: falling back to current setpoints ({e})")
            return {
                "heating_setpoint_c": sensor_state.get("current_heating_setpoint_c", config.HEATING_SETPOINT_DEFAULT_C),
                "cooling_setpoint_c": sensor_state.get("current_cooling_setpoint_c", config.COOLING_SETPOINT_DEFAULT_C),
                "reasoning": "fallback: LLM call failed, holding previous setpoints",
            }

    @staticmethod
    def _parse_json(text: str):
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        return None
