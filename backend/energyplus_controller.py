"""
energyplus_controller.py

Runs an EnergyPlus simulation with a live callback that:
  1. Reads current sensor state (zone temps, facility energy) via the
     Data Transfer API ("exchange").
  2. Every N steps, hands that state to the LLM agent and gets back
     new heating/cooling setpoints.
  3. Writes those setpoints back into the running simulation via
     set_actuator_value ("Forward Injection").

This is the closed loop: EnergyPlus -> AI -> EnergyPlus, live, mid-run.
"""

import csv
import os
import sys
import time

import config

sys.path.append(config.EPLUS_INSTALL_PATH)
from pyenergyplus.api import EnergyPlusAPI  # noqa: E402


class EcoLoopController:
    def __init__(self, run_label: str, ai_enabled: bool, agent=None):
        """
        run_label: 'baseline' or 'ai' — used for log filenames.
        ai_enabled: if False, runs EnergyPlus untouched (for comparison).
        agent: an LLMAgent instance (required if ai_enabled=True).
        """
        self.api = EnergyPlusAPI()
        self.run_label = run_label
        self.ai_enabled = ai_enabled
        self.agent = agent

        self.step_count = 0
        self.htg_handle = None
        self.clg_handle = None
        self.zone_temp_handles = {}
        self.energy_handle = None

        self.log_path = os.path.join(config.OUTPUT_DIR, f"{run_label}_log.csv")
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        self._log_file = open(self.log_path, "w", newline="")
        self._csv = csv.writer(self._log_file)
        self._csv.writerow(
            ["timestep", "sim_time", *[f"temp_{z}" for z in config.ZONE_NAMES],
             "facility_kwh", "heating_setpoint", "cooling_setpoint", "llm_called"]
        )

    def _get_handles(self, state):
        exchange = self.api.exchange
        if self.htg_handle is None:
            self.htg_handle = exchange.get_actuator_handle(
                state, "Schedule:Value", "Schedule Value", config.HEATING_SCHEDULE_NAME
            )
            self.clg_handle = exchange.get_actuator_handle(
                state, "Schedule:Value", "Schedule Value", config.COOLING_SCHEDULE_NAME
            )
            for zone in config.ZONE_NAMES:
                self.zone_temp_handles[zone] = exchange.get_variable_handle(
                    state, "Zone Mean Air Temperature", zone
                )
            self.energy_handle = exchange.get_meter_handle(state, "Electricity:Facility")

    def _callback(self, state):
        exchange = self.api.exchange
        if not exchange.api_data_fully_ready(state):
            return

        self._get_handles(state)
        self.step_count += 1

        zone_temps = {
            z: exchange.get_variable_value(state, h)
            for z, h in self.zone_temp_handles.items()
        }
        facility_j = exchange.get_meter_value(state, self.energy_handle)
        facility_kwh = facility_j / 3_600_000.0

        current_htg = exchange.get_actuator_value(state, self.htg_handle) if self.htg_handle else config.HEATING_SETPOINT_DEFAULT_C
        current_clg = exchange.get_actuator_value(state, self.clg_handle) if self.clg_handle else config.COOLING_SETPOINT_DEFAULT_C

        llm_called = False
        new_htg, new_clg = current_htg, current_clg

        if self.ai_enabled and self.step_count % config.LLM_CALL_EVERY_N_STEPS == 0:
            llm_called = True
            sensor_state = {
                "zone_temps_c": zone_temps,
                "facility_kwh_cumulative": round(facility_kwh, 3),
                "current_heating_setpoint_c": current_htg,
                "current_cooling_setpoint_c": current_clg,
            }
            decision = self.agent.decide(sensor_state)
            new_htg = self._clamp_heating(decision.get("heating_setpoint_c", current_htg))
            new_clg = self._clamp_cooling(decision.get("cooling_setpoint_c", current_clg))

            exchange.set_actuator_value(state, self.htg_handle, new_htg)
            exchange.set_actuator_value(state, self.clg_handle, new_clg)

        sim_time = f"{exchange.hour(state):02d}:{exchange.minutes(state):02d}"
        self._csv.writerow(
            [self.step_count, sim_time, *[zone_temps[z] for z in config.ZONE_NAMES],
             round(facility_kwh, 4), new_htg, new_clg, llm_called]
        )
        self._log_file.flush()

    @staticmethod
    def _clamp_heating(val):
        try:
            val = float(val)
        except (TypeError, ValueError):
            val = config.HEATING_SETPOINT_DEFAULT_C
        return max(config.COMFORT_HEATING_MIN_C, min(val, 23.0))

    @staticmethod
    def _clamp_cooling(val):
        try:
            val = float(val)
        except (TypeError, ValueError):
            val = config.COOLING_SETPOINT_DEFAULT_C
        return min(config.COMFORT_COOLING_MAX_C, max(val, 23.0))

    def run(self):
        state = self.api.state_manager.new_state()
        self.api.runtime.callback_begin_zone_timestep_before_set_current_weather(state, self._callback)

        args = [
            "-w", config.EPW_PATH,
            "-d", os.path.join(config.OUTPUT_DIR, self.run_label),
            "-r",
            config.IDF_PATH,
        ]
        print(f"[{self.run_label}] Starting EnergyPlus run (ai_enabled={self.ai_enabled})...")
        t0 = time.time()
        self.api.runtime.run_energyplus(state, args)
        print(f"[{self.run_label}] Finished in {time.time() - t0:.1f}s. Log: {self.log_path}")
        self._log_file.close()
        self.api.state_manager.delete_state(state)
